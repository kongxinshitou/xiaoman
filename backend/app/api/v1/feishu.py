"""
飞书集成 API（WebSocket 长连接模式）

Admin endpoints:
  GET  /config    — read current Feishu configuration
  PATCH /config   — update Feishu configuration
  POST /test      — test connection (sends a test message)
  POST /push      — push a message to a Feishu chat
  POST /create-group — create a Feishu group chat directly
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone

from app.database import get_db
from app.core.dependencies import get_current_user, require_admin
from app.models.user import User
from app.models.feishu_config import FeishuConfig
from app.schemas.feishu import FeishuConfigUpdate, FeishuConfigRead, FeishuPushRequest, FeishuCreateGroupRequest
from app.services import feishu_service, encryption

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Config (admin) ────────────────────────────────────────────────────────────

@router.get("/config", response_model=FeishuConfigRead)
async def get_config(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cfg = await feishu_service.get_feishu_config(db)
    if not cfg:
        return FeishuConfigRead()
    return FeishuConfigRead(
        app_id=cfg.app_id,
        has_app_secret=bool(cfg.encrypted_app_secret),
        bot_open_id=cfg.bot_open_id,
        default_push_chat_id=cfg.default_push_chat_id,
        ws_connected=feishu_service.ws_client_running(),
        enabled=cfg.enabled,
    )


@router.patch("/config")
async def update_config(
    payload: FeishuConfigUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    result = await db.execute(select(FeishuConfig).where(FeishuConfig.singleton_id == "default"))
    cfg = result.scalar_one_or_none()

    if not cfg:
        cfg = FeishuConfig(singleton_id="default")
        db.add(cfg)

    if payload.app_id is not None:
        cfg.app_id = payload.app_id
    if payload.app_secret is not None:
        cfg.encrypted_app_secret = encryption.encrypt(payload.app_secret)
    if payload.bot_open_id is not None:
        cfg.bot_open_id = payload.bot_open_id
    if payload.default_push_chat_id is not None:
        cfg.default_push_chat_id = payload.default_push_chat_id
    if payload.enabled is not None:
        cfg.enabled = payload.enabled
    cfg.updated_at = datetime.now(timezone.utc)

    # Invalidate token cache when credentials change
    if payload.app_id or payload.app_secret:
        feishu_service._token_cache["token"] = None

    await db.commit()

    # Restart WS client if credentials or enabled state changed
    ws_relevant = any(x is not None for x in [
        payload.app_id, payload.app_secret,
        payload.enabled, payload.bot_open_id,
    ])
    if ws_relevant:
        await feishu_service.maybe_start_ws_from_config(cfg)

    return {"message": "飞书配置已更新"}


# ── Test Connection ───────────────────────────────────────────────────────────

@router.post("/test")
async def test_connection(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    cfg = await feishu_service.get_feishu_config(db)
    if not cfg or not cfg.app_id or not cfg.encrypted_app_secret:
        raise HTTPException(status_code=400, detail="飞书未配置 App ID / App Secret")

    try:
        app_secret = encryption.decrypt(cfg.encrypted_app_secret)
        token = await feishu_service.get_tenant_access_token(cfg.app_id, app_secret)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"获取 access token 失败: {e}")

    if cfg.default_push_chat_id:
        try:
            await feishu_service.send_text_message(
                token, cfg.default_push_chat_id, "chat_id", "晓曼机器人测试消息 - 连接正常"
            )
            return {"message": "连接成功，测试消息已发送"}
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"发送测试消息失败: {e}")

    return {"message": "连接成功，Token 获取正常（未配置默认推送群，跳过发送测试消息）"}


# ── Push Message ──────────────────────────────────────────────────────────────

@router.post("/push")
async def push_message(
    payload: FeishuPushRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    cfg = await feishu_service.get_feishu_config(db)
    if not cfg or not cfg.app_id or not cfg.encrypted_app_secret:
        raise HTTPException(status_code=400, detail="飞书未配置")

    try:
        app_secret = encryption.decrypt(cfg.encrypted_app_secret)
        token = await feishu_service.get_tenant_access_token(cfg.app_id, app_secret)
        await feishu_service.send_text_message(
            token, payload.chat_id, payload.receive_id_type, payload.message
        )
        return {"message": "消息已发送"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"发送失败: {e}")


# ── Create Group ──────────────────────────────────────────────────────────────

@router.post("/create-group")
async def create_group(
    payload: FeishuCreateGroupRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    cfg = await feishu_service.get_feishu_config(db)
    if not cfg or not cfg.app_id or not cfg.encrypted_app_secret:
        raise HTTPException(status_code=400, detail="飞书未配置")

    try:
        app_secret = encryption.decrypt(cfg.encrypted_app_secret)
        token = await feishu_service.get_tenant_access_token(cfg.app_id, app_secret)
        result = await feishu_service.create_group_chat(
            token, payload.name, payload.user_open_ids, payload.description
        )
        return {"message": f"群聊「{payload.name}」创建成功", "chat_id": result.get("chat_id"), "name": payload.name}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"创建群聊失败: {e}")
