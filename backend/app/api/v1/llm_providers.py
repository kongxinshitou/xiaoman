from typing import List
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.llm_provider import LLMProvider
from app.schemas.llm_provider import (
    LLMProviderCreate, LLMProviderUpdate, LLMProviderRead,
    FetchModelsRequest, FetchModelsResponse,
)
from app.services.encryption import encrypt
from app.services.llm_service import test_provider, PROVIDER_CONFIG, PROVIDER_FALLBACK_MODELS

router = APIRouter()


@router.post("/fetch-models", response_model=FetchModelsResponse)
async def fetch_provider_models(
    payload: FetchModelsRequest,
    current_user: User = Depends(get_current_user),
):
    """Fetch available models from a provider using the given API key."""
    provider_cfg = PROVIDER_CONFIG.get(payload.provider_type, {"api_base": None})
    base_url = payload.base_url or provider_cfg.get("api_base")
    fallback = PROVIDER_FALLBACK_MODELS.get(payload.provider_type, [])

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            if payload.provider_type == "anthropic":
                resp = await client.get(
                    "https://api.anthropic.com/v1/models",
                    headers={
                        "x-api-key": payload.api_key,
                        "anthropic-version": "2023-06-01",
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                models = [m["id"] for m in data.get("data", [])]
            elif base_url:
                url = base_url.rstrip("/") + "/models"
                resp = await client.get(
                    url,
                    headers={"Authorization": f"Bearer {payload.api_key}"},
                )
                resp.raise_for_status()
                data = resp.json()
                models = [m["id"] for m in data.get("data", [])]
            else:
                models = fallback
    except Exception:
        models = fallback

    # If API returned models, merge with fallback (API result first, dedup)
    if models and fallback:
        seen = set(models)
        for m in fallback:
            if m not in seen:
                models.append(m)
    elif not models:
        models = fallback

    return {"models": models}


@router.post("", response_model=LLMProviderRead)
async def create_provider(
    payload: LLMProviderCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")

    if payload.is_default:
        # Unset existing defaults
        result = await db.execute(select(LLMProvider).where(LLMProvider.is_default == True))
        for p in result.scalars().all():
            p.is_default = False

    provider = LLMProvider(
        name=payload.name,
        provider_type=payload.provider_type,
        base_url=payload.base_url,
        encrypted_api_key=encrypt(payload.api_key),
        model_name=payload.model_name,
        is_active=payload.is_active,
        is_default=payload.is_default,
        supports_vision=payload.supports_vision,
        created_by=current_user.id,
    )
    db.add(provider)
    await db.commit()
    await db.refresh(provider)
    return provider


@router.get("", response_model=List[LLMProviderRead])
async def list_providers(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(LLMProvider).order_by(LLMProvider.created_at.desc()))
    return result.scalars().all()


@router.get("/{provider_id}", response_model=LLMProviderRead)
async def get_provider(
    provider_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(LLMProvider).where(LLMProvider.id == provider_id))
    provider = result.scalar_one_or_none()
    if not provider:
        raise HTTPException(status_code=404, detail="提供商不存在")
    return provider


@router.patch("/{provider_id}", response_model=LLMProviderRead)
async def update_provider(
    provider_id: str,
    payload: LLMProviderUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    result = await db.execute(select(LLMProvider).where(LLMProvider.id == provider_id))
    provider = result.scalar_one_or_none()
    if not provider:
        raise HTTPException(status_code=404, detail="提供商不存在")

    if payload.name is not None:
        provider.name = payload.name
    if payload.provider_type is not None:
        provider.provider_type = payload.provider_type
    if payload.base_url is not None:
        provider.base_url = payload.base_url
    if payload.api_key is not None:
        provider.encrypted_api_key = encrypt(payload.api_key)
    if payload.model_name is not None:
        provider.model_name = payload.model_name
    if payload.is_active is not None:
        provider.is_active = payload.is_active
    if payload.is_default is not None:
        if payload.is_default:
            existing = await db.execute(select(LLMProvider).where(LLMProvider.is_default == True))
            for p in existing.scalars().all():
                if p.id != provider_id:
                    p.is_default = False
        provider.is_default = payload.is_default
    if payload.supports_vision is not None:
        provider.supports_vision = payload.supports_vision
    provider.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(provider)
    return provider


@router.delete("/{provider_id}")
async def delete_provider(
    provider_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    result = await db.execute(select(LLMProvider).where(LLMProvider.id == provider_id))
    provider = result.scalar_one_or_none()
    if not provider:
        raise HTTPException(status_code=404, detail="提供商不存在")
    await db.delete(provider)
    await db.commit()
    return {"message": "提供商已删除"}


@router.post("/{provider_id}/test")
async def test_provider_connection(
    provider_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(LLMProvider).where(LLMProvider.id == provider_id))
    provider = result.scalar_one_or_none()
    if not provider:
        raise HTTPException(status_code=404, detail="提供商不存在")

    success = await test_provider(provider)
    provider.last_test_status = "ok" if success else "failed"
    provider.last_tested_at = datetime.now(timezone.utc)
    await db.commit()

    return {"status": "ok" if success else "failed", "message": "连接成功" if success else "连接失败"}
