from typing import List
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.ocr_provider import OCRProvider
from app.schemas.ocr_provider import (
    OCRProviderCreate, OCRProviderUpdate, OCRProviderRead,
    FetchOCRModelsRequest, FetchOCRModelsResponse,
)
from app.services.encryption import encrypt
from app.services.ocr_provider_service import test_ocr_provider, OCR_PROVIDER_CONFIG, OCR_PROVIDER_FALLBACK_MODELS

router = APIRouter()


@router.post("/fetch-models", response_model=FetchOCRModelsResponse)
async def fetch_ocr_models(
    payload: FetchOCRModelsRequest,
    current_user: User = Depends(get_current_user),
):
    """Fetch available vision/OCR models from a provider."""
    provider_cfg = OCR_PROVIDER_CONFIG.get(payload.provider_type, {"api_base": None})
    base_url = payload.base_url or provider_cfg.get("api_base")
    fallback = OCR_PROVIDER_FALLBACK_MODELS.get(payload.provider_type, [])

    models: List[str] = []
    try:
        if payload.provider_type == "anthropic":
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    "https://api.anthropic.com/v1/models",
                    headers={
                        "x-api-key": payload.api_key,
                        "anthropic-version": "2023-06-01",
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                all_models = [m["id"] for m in data.get("data", [])]
                models = [m for m in all_models if any(k in m.lower() for k in ("claude-3", "claude-opus", "claude-sonnet"))]
        elif base_url:
            async with httpx.AsyncClient(timeout=10) as client:
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

    # Merge with fallback
    if models and fallback:
        seen = set(models)
        for m in fallback:
            if m not in seen:
                models.append(m)
    elif not models:
        models = fallback

    return {"models": models}


@router.post("", response_model=OCRProviderRead)
async def create_ocr_provider(
    payload: OCRProviderCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")

    if payload.is_default:
        result = await db.execute(select(OCRProvider).where(OCRProvider.is_default == True))
        for p in result.scalars().all():
            p.is_default = False

    provider = OCRProvider(
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


@router.get("", response_model=List[OCRProviderRead])
async def list_ocr_providers(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(OCRProvider).order_by(OCRProvider.created_at.desc()))
    return result.scalars().all()


@router.get("/{provider_id}", response_model=OCRProviderRead)
async def get_ocr_provider(
    provider_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(OCRProvider).where(OCRProvider.id == provider_id))
    provider = result.scalar_one_or_none()
    if not provider:
        raise HTTPException(status_code=404, detail="OCR 提供商不存在")
    return provider


@router.patch("/{provider_id}", response_model=OCRProviderRead)
async def update_ocr_provider(
    provider_id: str,
    payload: OCRProviderUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    result = await db.execute(select(OCRProvider).where(OCRProvider.id == provider_id))
    provider = result.scalar_one_or_none()
    if not provider:
        raise HTTPException(status_code=404, detail="OCR 提供商不存在")

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
            existing = await db.execute(select(OCRProvider).where(OCRProvider.is_default == True))
            for p in existing.scalars().all():
                if p.id != provider_id:
                    p.is_default = False
        provider.is_default = payload.is_default
    provider.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(provider)
    return provider


@router.delete("/{provider_id}")
async def delete_ocr_provider(
    provider_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    result = await db.execute(select(OCRProvider).where(OCRProvider.id == provider_id))
    provider = result.scalar_one_or_none()
    if not provider:
        raise HTTPException(status_code=404, detail="OCR 提供商不存在")
    await db.delete(provider)
    await db.commit()
    return {"message": "OCR 提供商已删除"}


@router.post("/{provider_id}/test")
async def test_ocr_provider_connection(
    provider_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(OCRProvider).where(OCRProvider.id == provider_id))
    provider = result.scalar_one_or_none()
    if not provider:
        raise HTTPException(status_code=404, detail="OCR 提供商不存在")

    result = await test_ocr_provider(provider)
    success = result["success"]
    provider.last_test_status = "ok" if success else "failed"
    provider.last_tested_at = datetime.now(timezone.utc)
    await db.commit()

    if success:
        return {"status": "ok", "message": "连接成功"}
    else:
        return {"status": "failed", "message": f"连接失败: {result['error']}"}
