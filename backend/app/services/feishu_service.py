"""
飞书（Lark）集成服务

Provides:
- Tenant access token management (cached)
- Event signature verification
- Encrypted event decryption (AES-256-CBC)
- Feishu API helpers: send message, create group, add members
- Internal user/session mapping for Feishu identities
- Background task for async message processing
- Built-in tool executor (feishu_create_group)
"""

import asyncio
import hashlib
import hmac
import json
import time
import uuid
import base64
import logging
from typing import Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.feishu_config import FeishuConfig, FeishuUserMapping, FeishuChatMapping
from app.models.user import User
from app.models.session import ChatSession
from app.services import encryption
from app.services.auth_service import hash_password

logger = logging.getLogger(__name__)

FEISHU_API_BASE = "https://open.feishu.cn/open-apis"

# ── Token Cache ──────────────────────────────────────────────────────────────

_token_cache: dict = {"token": None, "expires_at": 0.0}


async def get_tenant_access_token(app_id: str, app_secret: str) -> str:
    """Return a cached tenant access token, refreshing if within 5 min of expiry."""
    if _token_cache["token"] and time.time() < _token_cache["expires_at"]:
        return _token_cache["token"]

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            f"{FEISHU_API_BASE}/auth/v3/tenant_access_token/internal",
            json={"app_id": app_id, "app_secret": app_secret},
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(f"飞书 token 获取失败: {data.get('msg')}")
        token = data["tenant_access_token"]
        expire_in = data.get("expire", 7200)
        _token_cache["token"] = token
        _token_cache["expires_at"] = time.time() + expire_in - 300  # refresh 5 min early
        return token


# ── Security ─────────────────────────────────────────────────────────────────

def verify_signature(verify_token: str, timestamp: str, nonce: str, body: bytes, signature: str) -> bool:
    """Verify Feishu v2 event signature: SHA256(timestamp + nonce + token + body)."""
    content = (timestamp + nonce + verify_token).encode() + body
    expected = hashlib.sha256(content).hexdigest()
    return hmac.compare_digest(expected, signature)


def decrypt_event(encrypt_key: str, encrypted: str) -> dict:
    """Decrypt a Feishu AES-256-CBC encrypted event payload."""
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.backends import default_backend

    key = hashlib.sha256(encrypt_key.encode()).digest()
    buf = base64.b64decode(encrypted)
    iv = buf[:16]
    ciphertext = buf[16:]
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    decryptor = cipher.decryptor()
    plaintext_bytes = decryptor.update(ciphertext) + decryptor.finalize()
    # Strip PKCS7 padding
    pad_len = plaintext_bytes[-1]
    plaintext_bytes = plaintext_bytes[:-pad_len]
    return json.loads(plaintext_bytes.decode())


# ── Event Deduplication ───────────────────────────────────────────────────────

_processed_events: dict[str, float] = {}


def is_duplicate_event(event_id: str) -> bool:
    """Return True if we've already processed this event (within last 5 min)."""
    now = time.time()
    expired = [k for k, v in _processed_events.items() if now - v > 300]
    for k in expired:
        del _processed_events[k]
    if event_id in _processed_events:
        return True
    _processed_events[event_id] = now
    return False


# ── Feishu API Wrappers ───────────────────────────────────────────────────────

async def send_text_message(token: str, receive_id: str, receive_id_type: str, text: str) -> dict:
    """Send a plain text message via Feishu IM API. Returns full response (contains message_id)."""
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{FEISHU_API_BASE}/im/v1/messages",
            params={"receive_id_type": receive_id_type},
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={
                "receive_id": receive_id,
                "msg_type": "text",
                "content": json.dumps({"text": text}),
            },
        )
        resp.raise_for_status()
        return resp.json()


async def update_text_message(token: str, message_id: str, text: str) -> dict:
    """Update (edit) a previously sent Feishu message by message_id."""
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.patch(
            f"{FEISHU_API_BASE}/im/v1/messages/{message_id}",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={
                "msg_type": "text",
                "content": json.dumps({"text": text}),
            },
        )
        resp.raise_for_status()
        return resp.json()


async def create_group_chat(token: str, name: str, user_open_ids: list[str], description: str = "") -> dict:
    """Create a Feishu group chat and return its info."""
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{FEISHU_API_BASE}/im/v1/chats",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={
                "name": name,
                "description": description,
                "user_id_list": user_open_ids,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(f"创建群聊失败: {data.get('msg')}")
        return data.get("data", {})


async def add_members_to_chat(token: str, chat_id: str, user_open_ids: list[str]) -> dict:
    """Add members to an existing Feishu group chat."""
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{FEISHU_API_BASE}/im/v1/chats/{chat_id}/members",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"member_id_type": "open_id", "id_list": user_open_ids},
        )
        resp.raise_for_status()
        return resp.json()


# ── DB Helpers ────────────────────────────────────────────────────────────────

async def get_feishu_config(db: AsyncSession) -> Optional[FeishuConfig]:
    result = await db.execute(select(FeishuConfig).where(FeishuConfig.singleton_id == "default"))
    return result.scalar_one_or_none()


async def get_feishu_config_if_enabled(db: AsyncSession) -> Optional[FeishuConfig]:
    cfg = await get_feishu_config(db)
    if cfg and cfg.enabled and cfg.app_id and cfg.encrypted_app_secret:
        return cfg
    return None


async def get_or_create_internal_user(db: AsyncSession, open_id: str) -> User:
    """Return (or auto-create) the internal User mapped to a Feishu open_id."""
    mapping_result = await db.execute(
        select(FeishuUserMapping).where(FeishuUserMapping.open_id == open_id)
    )
    mapping = mapping_result.scalar_one_or_none()

    if mapping:
        user_result = await db.execute(select(User).where(User.id == mapping.internal_user_id))
        user = user_result.scalar_one_or_none()
        if user:
            return user

    # Create a virtual user that cannot log in to the web UI
    random_pw = hash_password(str(uuid.uuid4()))
    user = User(
        id=str(uuid.uuid4()),
        username=f"feishu_{open_id[:20]}",
        email=None,
        hashed_password=random_pw,
        role="member",
        is_active=True,
    )
    db.add(user)
    await db.flush()

    new_mapping = FeishuUserMapping(open_id=open_id, internal_user_id=user.id)
    db.add(new_mapping)
    await db.commit()
    return user


async def get_or_create_session(db: AsyncSession, feishu_chat_id: str, user_id: str) -> ChatSession:
    """Return (or create) a ChatSession mapped to a Feishu chat_id."""
    mapping_result = await db.execute(
        select(FeishuChatMapping).where(FeishuChatMapping.feishu_chat_id == feishu_chat_id)
    )
    mapping = mapping_result.scalar_one_or_none()

    if mapping:
        session_result = await db.execute(
            select(ChatSession).where(ChatSession.id == mapping.session_id)
        )
        session = session_result.scalar_one_or_none()
        if session:
            return session

    # Create a new chat session
    session = ChatSession(
        id=str(uuid.uuid4()),
        user_id=user_id,
        title=f"飞书-{feishu_chat_id[:16]}",
    )
    db.add(session)
    await db.flush()

    if mapping:
        mapping.session_id = session.id
    else:
        db.add(FeishuChatMapping(feishu_chat_id=feishu_chat_id, session_id=session.id))
    await db.commit()
    return session


# ── Background Message Processing ─────────────────────────────────────────────

async def process_feishu_message_background(
    db_factory,
    config_snapshot: dict,
    open_id: str,
    chat_id: str,
    receive_id_type: str,
    user_message: str,
) -> None:
    """
    Background task: process a Feishu message through the agent and reply.

    Sends a "正在思考..." placeholder immediately, then updates it with the actual
    LLM response once ready.  Uses all active knowledge bases by default.
    """
    from app.services import chat_service
    from app.models.knowledge import KnowledgeBase
    from sqlalchemy import select as _select

    app_id = config_snapshot["app_id"]
    app_secret = encryption.decrypt(config_snapshot["encrypted_app_secret"])

    t0 = time.time()

    try:
        # ── 1. Obtain token and send placeholder ──────────────────────────────
        token = await get_tenant_access_token(app_id, app_secret)
        placeholder_resp = await send_text_message(token, chat_id, receive_id_type, "正在思考…")
        placeholder_msg_id = (
            placeholder_resp.get("data", {}).get("message_id")
            if isinstance(placeholder_resp, dict)
            else None
        )
        logger.info(
            "飞书占位消息已发送: chat_id=%s placeholder_msg_id=%s",
            chat_id, placeholder_msg_id,
        )

        # ── 2. Process message through LLM ────────────────────────────────────
        async with db_factory() as db:
            user = await get_or_create_internal_user(db, open_id)
            session = await get_or_create_session(db, chat_id, user.id)

            # Use all active knowledge bases for Feishu channel
            kb_result = await db.execute(
                _select(KnowledgeBase).order_by(KnowledgeBase.created_at)
            )
            all_kb_ids = [kb.id for kb in kb_result.scalars().all()]

            assistant_content = ""
            t_llm_start = time.time()
            async for chunk in chat_service.process_message(
                session_id=session.id,
                user_message=user_message,
                user_id=user.id,
                provider_id=None,
                kb_ids=all_kb_ids if all_kb_ids else None,
                db=db,
                web_search=False,
            ):
                if chunk.startswith("event: token\n"):
                    try:
                        data_line = chunk.split("\n")[1]
                        if data_line.startswith("data: "):
                            token_data = json.loads(data_line[6:])
                            assistant_content += token_data.get("delta", "")
                    except Exception:
                        pass

            logger.info(
                "飞书LLM处理完成: chat_id=%s 耗时=%.2fs total=%.2fs",
                chat_id, time.time() - t_llm_start, time.time() - t0,
            )

        if not assistant_content.strip():
            assistant_content = "（无法生成回复）"

        # ── 3. Update placeholder or send new message ─────────────────────────
        token = await get_tenant_access_token(app_id, app_secret)  # refresh if needed
        if placeholder_msg_id:
            try:
                await update_text_message(token, placeholder_msg_id, assistant_content)
                logger.info("飞书占位消息已更新: message_id=%s", placeholder_msg_id)
                return
            except Exception as e:
                logger.warning("更新占位消息失败，改为新发消息: %s", e)

        await send_text_message(token, chat_id, receive_id_type, assistant_content)

    except Exception:
        logger.exception("Feishu background processing failed for chat_id=%s", chat_id)


# ── Built-in Tool Executor ────────────────────────────────────────────────────

async def execute_builtin_tool(tool_name: str, tool_args: dict, db: AsyncSession) -> str:
    """Execute a built-in Feishu tool called by the agent."""
    if tool_name == "feishu_create_group":
        cfg = await get_feishu_config_if_enabled(db)
        if not cfg:
            return json.dumps({"error": "飞书集成未启用或未配置"}, ensure_ascii=False)

        name = tool_args.get("name", "新群聊")
        user_open_ids = tool_args.get("user_open_ids", [])
        description = tool_args.get("description", "")

        try:
            app_secret = encryption.decrypt(cfg.encrypted_app_secret)
            token = await get_tenant_access_token(cfg.app_id, app_secret)
            result = await create_group_chat(token, name, user_open_ids, description)
            chat_id = result.get("chat_id", "")
            return json.dumps({
                "success": True,
                "chat_id": chat_id,
                "name": name,
                "message": f"群聊「{name}」创建成功，chat_id: {chat_id}",
            }, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": f"创建群聊失败: {str(e)}"}, ensure_ascii=False)

    return json.dumps({"error": f"未知内置工具: {tool_name}"}, ensure_ascii=False)


# ── WebSocket Long Connection Client ─────────────────────────────────────────

import threading
from typing import Optional as _Optional

_ws_thread: _Optional[threading.Thread] = None
_ws_client = None  # lark_oapi.ws.Client instance
_main_event_loop: _Optional[asyncio.AbstractEventLoop] = None


def _make_ws_message_handler(config_snapshot: dict, bot_open_id: str):
    """Return a sync event handler for lark_oapi WebSocket dispatcher."""

    def handle(data) -> None:
        try:
            event = data.event
            sender = event.sender
            msg = event.message

            open_id = (sender.sender_id.open_id or "") if sender and sender.sender_id else ""
            chat_id = msg.chat_id or "" if msg else ""
            chat_type = msg.chat_type or "p2p" if msg else "p2p"
            message_type = msg.message_type or "" if msg else ""
            event_id = (data.header.event_id or "") if data.header else ""

            logger.info(
                "WS收到消息: event_id=%s chat_type=%s message_type=%s open_id=%s chat_id=%s",
                event_id, chat_type, message_type, open_id, chat_id,
            )

            if not open_id or not chat_id or message_type != "text":
                logger.info("WS消息忽略: open_id=%r chat_id=%r message_type=%r", open_id, chat_id, message_type)
                return

            # Dedup (same store as webhook)
            if event_id and is_duplicate_event(event_id):
                logger.info("WS消息重复忽略: event_id=%s", event_id)
                return

            content_str = msg.content or "{}" if msg else "{}"
            try:
                content = json.loads(content_str)
            except Exception:
                return

            user_message = content.get("text", "").strip()
            logger.info("原始消息内容: %r", user_message[:100])

            # Group chat: only respond when @mentioned
            if chat_type == "group":
                mentions = msg.mentions or [] if msg else []
                logger.info(
                    "群聊@检查: bot_open_id=%r mentions_count=%d mentions=%r",
                    bot_open_id, len(mentions),
                    [
                        {
                            "open_id": getattr(getattr(m, "id", None), "open_id", None),
                            "name": getattr(m, "name", None),
                            "key": getattr(m, "key", None),
                        }
                        for m in mentions
                    ],
                )

                if bot_open_id:
                    # Check by open_id
                    bot_mentioned = any(
                        getattr(getattr(m, "id", None), "open_id", None) == bot_open_id
                        for m in mentions
                    )
                    # Fallback: check via "all" key (broadcast @all)
                    if not bot_mentioned:
                        bot_mentioned = any(
                            getattr(m, "key", None) in ("@_user_1", bot_open_id)
                            for m in mentions
                        )
                else:
                    # No bot_open_id configured: respond if any @mention present
                    bot_mentioned = len(mentions) > 0

                if not bot_mentioned:
                    logger.info("群聊消息未@机器人，忽略")
                    return

                # Strip all @mention text from user message
                for m in mentions:
                    name = getattr(m, "name", "") or ""
                    if name:
                        user_message = user_message.replace(f"@{name}", "").strip()
                # Also strip the literal @all or @bot patterns left from markdown
                user_message = user_message.strip("@").strip()

            if not user_message:
                logger.info("WS消息内容为空，忽略")
                return

            logger.info("处理飞书消息: chat_id=%s user_message=%r", chat_id, user_message[:50])
            receive_id_type = "chat_id"  # chat_id works for both P2P and group chats

            # Schedule async processing in the FastAPI event loop
            if _main_event_loop and not _main_event_loop.is_closed():
                from app.database import AsyncSessionLocal as _db_factory
                asyncio.run_coroutine_threadsafe(
                    process_feishu_message_background(
                        _db_factory,
                        config_snapshot,
                        open_id,
                        chat_id,
                        receive_id_type,
                        user_message,
                    ),
                    _main_event_loop,
                )
            else:
                logger.error("_main_event_loop 不可用: loop=%s", _main_event_loop)
        except Exception:
            logger.exception("WS event handler error")

    return handle


def start_ws_client(
    app_id: str,
    app_secret: str,
    encrypted_app_secret: str,
    bot_open_id: str,
    loop: asyncio.AbstractEventLoop,
) -> None:
    """Start Feishu WebSocket long-connection client in a daemon thread.

    All heavy work (importing lark_oapi, creating the WS client, connecting)
    happens inside the daemon thread so that app startup is never blocked.
    """
    global _ws_thread, _ws_client, _main_event_loop

    stop_ws_client()
    _main_event_loop = loop

    config_snapshot = {
        "app_id": app_id,
        "encrypted_app_secret": encrypted_app_secret,
    }

    def _run():
        # Create a fresh event loop for this daemon thread so that
        # lark_oapi's internal run_until_complete() doesn't conflict
        # with the main FastAPI event loop.
        thread_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(thread_loop)

        try:
            import lark_oapi as lark
            import lark_oapi.ws.client as _lark_ws_client
        except ImportError:
            logger.error("lark-oapi 未安装，无法启动 WebSocket 客户端。请执行: pip install lark-oapi")
            return

        # lark_oapi/ws/client.py 在模块顶层捕获了 event loop（模块级全局变量）。
        # 如果该模块是在主线程（uvicorn loop 已运行时）被首次导入的，
        # 它会存储主 loop，导致 start() 调用 loop.run_until_complete() 时
        # 抛出 "This event loop is already running"。
        # 替换该模块级变量，强制使用本线程自己的 loop。
        _lark_ws_client.loop = thread_loop

        global _ws_client
        handler = _make_ws_message_handler(config_snapshot, bot_open_id)

        dispatcher = (
            lark.EventDispatcherHandler.builder("", "")
            .register_p2_im_message_receive_v1(handler)
            .build()
        )

        ws_cli = lark.ws.Client(
            app_id=app_id,
            app_secret=app_secret,
            event_handler=dispatcher,
            log_level=lark.LogLevel.ERROR,
        )
        _ws_client = ws_cli

        logger.info("飞书 WebSocket 长连接已启动")
        try:
            ws_cli.start()
        except Exception:
            logger.exception("飞书 WebSocket 连接断开")
        finally:
            thread_loop.close()

    _ws_thread = threading.Thread(target=_run, daemon=True, name="feishu-ws")
    _ws_thread.start()
    logger.info("飞书 WebSocket 线程已启动 (app_id=%s)", app_id)


def stop_ws_client() -> None:
    """Stop the running WebSocket client (best-effort)."""
    global _ws_client, _ws_thread
    if _ws_client is not None:
        try:
            _ws_client.close()
        except Exception:
            pass
        _ws_client = None
        _ws_thread = None
        logger.info("飞书 WebSocket 客户端已停止")


def ws_client_running() -> bool:
    return _ws_thread is not None and _ws_thread.is_alive()


async def maybe_start_ws(db_factory) -> None:
    """Called at app startup: start WS client if config says so."""
    async with db_factory() as db:
        cfg = await get_feishu_config(db)
        await maybe_start_ws_from_config(cfg)


async def maybe_start_ws_from_config(cfg) -> None:
    """Start/restart/stop WS client based on a FeishuConfig object."""
    if (
        cfg
        and cfg.enabled
        and cfg.app_id
        and cfg.encrypted_app_secret
    ):
        app_secret = encryption.decrypt(cfg.encrypted_app_secret)
        loop = asyncio.get_event_loop()
        start_ws_client(
            cfg.app_id,
            app_secret,
            cfg.encrypted_app_secret,
            cfg.bot_open_id or "",
            loop,
        )
    else:
        # Disabled or mode is webhook-only — stop WS if running
        stop_ws_client()
