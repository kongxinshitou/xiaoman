from typing import List
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.embed_provider import EmbedProvider
from app.schemas.embed_provider import (
    EmbedProviderCreate, EmbedProviderUpdate, EmbedProviderRead,
    FetchEmbedModelsRequest, FetchEmbedModelsResponse,
)
from app.services.encryption import encrypt
from app.services.embed_service import test_embed_provider, EMBED_PROVIDER_CONFIG, EMBED_PROVIDER_FALLBACK_MODELS

router = APIRouter()


@router.post("/fetch-models", response_model=FetchEmbedModelsResponse)
async def fetch_embed_models(
    payload: FetchEmbedModelsRequest,
    current_user: User = Depends(get_current_user),
):
    """Fetch available embedding models from a provider using the given API key."""
    provider_cfg = EMBED_PROVIDER_CONFIG.get(payload.provider_type, {"api_base": None})
    base_url = payload.base_url or provider_cfg.get("api_base")
    fallback = EMBED_PROVIDER_FALLBACK_MODELS.get(payload.provider_type, [])

    models: List[str] = []
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            if base_url:
                url = base_url.rstrip("/") + "/models"
                resp = await client.get(
                    url,
                    headers={"Authorization": f"Bearer {payload.api_key}"},
                )
                resp.raise_for_status()
                data = resp.json()
                # Filter to embedding models only (heuristic: model id contains "embed")
                all_models = [m["id"] for m in data.get("data", [])]
                models = [m for m in all_models if "embed" in m.lower()] or all_models
            else:
                models = fallback
    except Exception:
        models = fallback

    # Merge with fallback
    if models and fallback:
        seen = set(models)
        for m in fallback:
            if m not in seen:
                models.append(m)
    elif not models:
        models = fallback

    return {"models": models}


@router.post("", response_model=EmbedProviderRead)
async def create_embed_provider(
    payload: EmbedProviderCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")

    if payload.is_default:
        result = await db.execute(select(EmbedProvider).where(EmbedProvider.is_default == True))
        for p in result.scalars().all():
            p.is_default = False

    provider = EmbedProvider(
        name=payload.name,
        provider_type=payload.provider_type,
        base_url=payload.base_url,
        encrypted_api_key=encrypt(payload.api_key),
        model_name=payload.model_name,
        is_active=payload.is_active,
        is_default=payload.is_default,
        created_by=current_user.id,
    )
    db.add(provider)
    await db.commit()
    await db.refresh(provider)
    return provider


@router.get("", response_model=List[EmbedProviderRead])
async def list_embed_providers(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(EmbedProvider).order_by(EmbedProvider.created_at.desc()))
    return result.scalars().all()


@router.get("/{provider_id}", response_model=EmbedProviderRead)
async def get_embed_provider(
    provider_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(EmbedProvider).where(EmbedProvider.id == provider_id))
    provider = result.scalar_one_or_none()
    if not provider:
        raise HTTPException(status_code=404, detail="Embed 提供商不存在")
    return provider


@router.patch("/{provider_id}", response_model=EmbedProviderRead)
async def update_embed_provider(
    provider_id: str,
    payload: EmbedProviderUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    result = await db.execute(select(EmbedProvider).where(EmbedProvider.id == provider_id))
    provider = result.scalar_one_or_none()
    if not provider:
        raise HTTPException(status_code=404, detail="Embed 提供商不存在")

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
            existing = await db.execute(select(EmbedProvider).where(EmbedProvider.is_default == True))
            for p in existing.scalars().all():
                if p.id != provider_id:
                    p.is_default = False
        provider.is_default = payload.is_default
    provider.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(provider)
    return provider


@router.delete("/{provider_id}")
async def delete_embed_provider(
    provider_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    result = await db.execute(select(EmbedProvider).where(EmbedProvider.id == provider_id))
    provider = result.scalar_one_or_none()
    if not provider:
        raise HTTPException(status_code=404, detail="Embed 提供商不存在")
    await db.delete(provider)
    await db.commit()
    return {"message": "Embed 提供商已删除"}


@router.post("/{provider_id}/test")
async def test_embed_provider_connection(
    provider_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(EmbedProvider).where(EmbedProvider.id == provider_id))
    provider = result.scalar_one_or_none()
    if not provider:
        raise HTTPException(status_code=404, detail="Embed 提供商不存在")

    success = await test_embed_provider(provider)
    provider.last_test_status = "ok" if success else "failed"
    provider.last_tested_at = datetime.now(timezone.utc)
    await db.commit()

    return {"status": "ok" if success else "failed", "message": "连接成功" if success else "连接失败"}
