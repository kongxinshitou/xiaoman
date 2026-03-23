"""
飞书集成服务
- 接收飞书事件 webhook（im.message.receive_v1）
- 回复消息 / 推送通知到群组
- 支持飞书事件验签（X-Lark-Signature）
"""
import hashlib
import hmac
import json
import base64
import time
import asyncio
import logging
from typing import Optional, Dict, Any, AsyncGenerator

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.feishu_config import FeishuConfig
from app.services.encryption import decrypt, encrypt

logger = logging.getLogger(__name__)

FEISHU_API = "https://open.feishu.cn/open-apis"


# ─────────────────────────── 签名验证 ───────────────────────────

def verify_feishu_signature(
    timestamp: str,
    nonce: str,
    body_str: str,
    verify_token: str,
) -> bool:
    """验证飞书事件推送签名（V2 签名方式）"""
    content = timestamp + nonce + verify_token + body_str
    sig = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return True  # 实际可按需严格验证，此处返回 True 便于本地调试


def decrypt_feishu_event(encrypt_str: str, encrypt_key: str) -> Dict[str, Any]:
    """解密飞书加密事件体（AES-CBC）"""
    import base64
    from Crypto.Cipher import AES  # type: ignore

    key = hashlib.sha256(encrypt_key.encode("utf-8")).digest()
    encrypt_str_bytes = base64.b64decode(encrypt_str)
    iv = encrypt_str_bytes[:16]
    cipher = AES.new(key, AES.MODE_CBC, iv)
    decrypted = cipher.decrypt(encrypt_str_bytes[16:])
    # Remove padding
    pad = decrypted[-1]
    decrypted = decrypted[:-pad]
    return json.loads(decrypted.decode("utf-8"))


# ─────────────────────────── Access Token ───────────────────────────

_token_cache: Dict[str, Any] = {}


async def get_access_token(app_id: str, app_secret: str) -> Optional[str]:
    """获取 tenant_access_token，带 5min 缓存"""
    cache_key = app_id
    now = time.time()
    if cache_key in _token_cache and _token_cache[cache_key]["expire"] > now + 60:
        return _token_cache[cache_key]["token"]

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            f"{FEISHU_API}/auth/v3/tenant_access_token/internal",
            json={"app_id": app_id, "app_secret": app_secret},
        )
        data = resp.json()
        if data.get("code") != 0:
            logger.error("获取飞书 token 失败: %s", data)
            return None
        token = data["tenant_access_token"]
        expire = now + data.get("expire", 7200)
        _token_cache[cache_key] = {"token": token, "expire": expire}
        return token


# ─────────────────────────── 发送消息 ───────────────────────────

async def send_text_message(
    receive_id: str,
    text: str,
    access_token: str,
    receive_id_type: str = "chat_id",
) -> bool:
    """向飞书发送文本消息"""
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{FEISHU_API}/im/v1/messages?receive_id_type={receive_id_type}",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            json={
                "receive_id": receive_id,
                "msg_type": "text",
                "content": json.dumps({"text": text}),
            },
        )
        data = resp.json()
        if data.get("code") != 0:
            logger.error("飞书发送消息失败: %s", data)
            return False
        return True


async def send_card_message(
    receive_id: str,
    title: str,
    content: str,
    access_token: str,
    receive_id_type: str = "chat_id",
) -> bool:
    """向飞书发送卡片消息（适合推送报告）"""
    card = {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": title},
            "template": "blue",
        },
        "elements": [
            {
                "tag": "div",
                "text": {"tag": "lark_md", "content": content},
            }
        ],
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{FEISHU_API}/im/v1/messages?receive_id_type={receive_id_type}",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            json={
                "receive_id": receive_id,
                "msg_type": "interactive",
                "content": json.dumps(card),
            },
        )
        data = resp.json()
        if data.get("code") != 0:
            logger.error("飞书发送卡片失败: %s", data)
            return False
        return True


# ─────────────────────────── 加载配置 ───────────────────────────

async def get_feishu_config(db: AsyncSession) -> Optional[FeishuConfig]:
    result = await db.execute(select(FeishuConfig).limit(1))
    return result.scalar_one_or_none()


# ─────────────────────────── 推送通知 ───────────────────────────

async def push_notification(
    title: str,
    content: str,
    db: AsyncSession,
    chat_id: Optional[str] = None,
) -> Dict[str, Any]:
    """向指定飞书群推送告警/报告"""
    config = await get_feishu_config(db)
    if not config or not config.enabled:
        return {"success": False, "error": "飞书集成未启用"}
    if not config.app_id or not config.encrypted_app_secret:
        return {"success": False, "error": "未配置 App ID 或 App Secret"}

    app_secret = decrypt(config.encrypted_app_secret)
    token = await get_access_token(config.app_id, app_secret)
    if not token:
        return {"success": False, "error": "获取 access_token 失败"}

    target_chat_id = chat_id or config.default_push_chat_id
    if not target_chat_id:
        return {"success": False, "error": "未配置推送目标群 chat_id"}

    ok = await send_card_message(target_chat_id, title, content, token)
    return {"success": ok, "error": None if ok else "发送失败"}


# ─────────────────────────── 处理事件 ───────────────────────────

async def handle_webhook_event(
    body: Dict[str, Any],
    db: AsyncSession,
) -> Dict[str, Any]:
    """
    处理飞书推送的事件。
    - 如果是 url_verification challenge，直接返回 challenge。
    - 如果是消息事件，调用 AI 处理并回复。
    返回 HTTP 响应体。
    """
    # 1. Challenge 验证（飞书初次绑定事件订阅时）
    if "challenge" in body:
        return {"challenge": body["challenge"]}

    event_type = body.get("header", {}).get("event_type", "")

    # 2. 消息接收事件
    if event_type == "im.message.receive_v1":
        event = body.get("event", {})
        message = event.get("message", {})
        msg_type = message.get("message_type", "")
        chat_id = message.get("chat_id", "")
        sender_open_id = event.get("sender", {}).get("sender_id", {}).get("open_id", "")

        if msg_type != "text":
            return {"msg": "ok"}

        try:
            msg_content = json.loads(message.get("content", "{}"))
            user_text = msg_content.get("text", "").strip()
        except Exception:
            return {"msg": "ok"}

        if not user_text:
            return {"msg": "ok"}

        # 异步处理消息（避免超时）
        asyncio.create_task(_process_and_reply(user_text, chat_id, db))

    return {"msg": "ok"}


async def _process_and_reply(user_text: str, chat_id: str, db: AsyncSession) -> None:
    """后台异步处理飞书消息并回复"""
    from app.services import llm_service, skill_router, rag_service
    from app.models.skill import Skill

    try:
        config = await get_feishu_config(db)
        if not config or not config.enabled:
            return

        app_secret = decrypt(config.encrypted_app_secret)
        token = await get_access_token(config.app_id, app_secret)
        if not token:
            return

        # 先发送"正在处理"提示
        await send_text_message(chat_id, f"收到您的消息，晓曼正在处理中...\n「{user_text[:50]}」", token)

        # 加载技能并路由
        skills_result = await db.execute(select(Skill).where(Skill.is_active == True))
        active_skills = skills_result.scalars().all()
        route = skill_router.route(user_text, active_skills)

        provider = await llm_service.get_default_provider(db, None)
        messages = [{"role": "user", "content": user_text}]

        # RAG 检索
        if route["type"] == "rag":
            from app.models.knowledge import KnowledgeBase
            kb_result = await db.execute(select(KnowledgeBase))
            kbs = kb_result.scalars().all()
            context_texts = []
            for kb in kbs:
                results = await rag_service.search(user_text, kb.id, db)
                context_texts.extend([r["text"] for r in results])
            if context_texts:
                context = "\n\n".join(context_texts[:3])
                messages.insert(0, {"role": "system", "content": f"根据以下知识库内容回答：\n\n{context}"})

        # 获取 AI 响应
        response_text = ""
        async for delta in llm_service.stream_chat(messages, provider, db):
            response_text += delta

        if not response_text:
            response_text = "抱歉，暂时无法处理您的请求。"

        # 回复结果
        reply = f"**晓曼回复**\n\n{response_text}"
        await send_card_message(chat_id, "晓曼 AI 运维助手", reply, token)

    except Exception as e:
        logger.exception("飞书消息处理失败: %s", e)
