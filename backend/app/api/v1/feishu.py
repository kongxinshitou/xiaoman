from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.feishu_config import FeishuConfig
from app.schemas.feishu import FeishuConfigUpdate, FeishuConfigRead, FeishuPushRequest
from app.services.feishu_service import (
    handle_webhook_event,
    push_notification,
    get_access_token,
    decrypt,
    encrypt,
)
from app.services.encryption import encrypt, decrypt

router = APIRouter()


# ─────────────────────────── 飞书 Webhook（无需登录） ───────────────────────────

@router.post("/webhook")
async def feishu_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """接收飞书事件推送"""
    body = await request.json()
    result = await handle_webhook_event(body, db)
    return result


# ─────────────────────────── 配置管理 ───────────────────────────

async def _get_or_create_config(db: AsyncSession) -> FeishuConfig:
    result = await db.execute(select(FeishuConfig).limit(1))
    config = result.scalar_one_or_none()
    if not config:
        config = FeishuConfig()
        db.add(config)
        await db.commit()
        await db.refresh(config)
    return config


@router.get("/config", response_model=FeishuConfigRead)
async def get_config(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    config = await _get_or_create_config(db)
    return FeishuConfigRead(
        id=config.id,
        app_id=config.app_id,
        verify_token=config.verify_token,
        encrypt_key=config.encrypt_key,
        default_push_chat_id=config.default_push_chat_id,
        enabled=config.enabled,
        has_app_secret=bool(config.encrypted_app_secret),
        updated_at=config.updated_at,
    )


@router.patch("/config", response_model=FeishuConfigRead)
async def update_config(
    payload: FeishuConfigUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")

    config = await _get_or_create_config(db)

    if payload.app_id is not None:
        config.app_id = payload.app_id
    if payload.app_secret is not None and payload.app_secret != "":
        config.encrypted_app_secret = encrypt(payload.app_secret)
    if payload.verify_token is not None:
        config.verify_token = payload.verify_token
    if payload.encrypt_key is not None:
        config.encrypt_key = payload.encrypt_key
    if payload.default_push_chat_id is not None:
        config.default_push_chat_id = payload.default_push_chat_id
    if payload.enabled is not None:
        config.enabled = payload.enabled

    config.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(config)

    return FeishuConfigRead(
        id=config.id,
        app_id=config.app_id,
        verify_token=config.verify_token,
        encrypt_key=config.encrypt_key,
        default_push_chat_id=config.default_push_chat_id,
        enabled=config.enabled,
        has_app_secret=bool(config.encrypted_app_secret),
        updated_at=config.updated_at,
    )


@router.post("/test")
async def test_connection(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """测试飞书 App ID + Secret 是否有效"""
    config = await _get_or_create_config(db)
    if not config.app_id or not config.encrypted_app_secret:
        raise HTTPException(status_code=400, detail="请先配置 App ID 和 App Secret")

    app_secret = decrypt(config.encrypted_app_secret)
    token = await get_access_token(config.app_id, app_secret)
    if token:
        return {"status": "ok", "message": "连接成功，已获取 access_token"}
    return {"status": "fail", "message": "获取 access_token 失败，请检查 App ID / Secret"}


@router.post("/push")
async def push_message(
    payload: FeishuPushRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """手动推送消息到飞书群"""
    result = await push_notification(
        title=payload.title,
        content=payload.content,
        db=db,
        chat_id=payload.chat_id,
    )
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result.get("error", "推送失败"))
    return {"message": "推送成功"}
