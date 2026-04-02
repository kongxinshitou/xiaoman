from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Dict, Optional
from pydantic import BaseModel

from app.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.knowledge import KnowledgeBase, Document
from app.models.llm_provider import LLMProvider
from app.models.session import ChatSession, ChatMessage
from app.models.mcp_tool import MCPTool
from app.models.system_setting import SystemSetting

router = APIRouter()


class SystemConfigUpdate(BaseModel):
    search_provider: Optional[str] = None  # "duckduckgo" | "tavily"
    search_api_key: Optional[str] = None


@router.get("/config")
async def get_system_config(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return current system config (non-sensitive fields only)."""
    result = await db.execute(select(SystemSetting))
    settings = {s.key: s.value for s in result.scalars().all()}
    return {
        "search_provider": settings.get("search_provider", "duckduckgo"),
        "has_search_api_key": bool(settings.get("search_api_key", "")),
    }


@router.put("/config")
async def update_system_config(
    payload: SystemConfigUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")

    updates: Dict[str, str] = {}
    if payload.search_provider is not None:
        updates["search_provider"] = payload.search_provider
    if payload.search_api_key is not None:
        updates["search_api_key"] = payload.search_api_key

    for key, value in updates.items():
        result = await db.execute(select(SystemSetting).where(SystemSetting.key == key))
        setting = result.scalar_one_or_none()
        if setting:
            setting.value = value
        else:
            db.add(SystemSetting(key=key, value=value))
    await db.commit()
    return {"message": "配置已保存"}


@router.get("/health")
async def health_check():
    return {"status": "ok", "service": "晓曼 Xiaoman API"}


@router.get("/stats")
async def get_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    kb_count = (await db.execute(select(func.count()).select_from(KnowledgeBase))).scalar()
    doc_count = (await db.execute(select(func.count()).select_from(Document))).scalar()
    provider_count = (await db.execute(select(func.count()).select_from(LLMProvider))).scalar()
    session_count = (await db.execute(select(func.count()).select_from(ChatSession))).scalar()
    message_count = (await db.execute(select(func.count()).select_from(ChatMessage))).scalar()
    tool_count = (await db.execute(select(func.count()).select_from(MCPTool))).scalar()

    return {
        "knowledge_bases": kb_count,
        "documents": doc_count,
        "llm_providers": provider_count,
        "chat_sessions": session_count,
        "chat_messages": message_count,
        "mcp_tools": tool_count,
    }
