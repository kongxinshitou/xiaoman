from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.knowledge import KnowledgeBase, Document
from app.models.llm_provider import LLMProvider
from app.models.session import ChatSession, ChatMessage
from app.models.skill import Skill
from app.models.mcp_tool import MCPTool

router = APIRouter()


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
    skill_count = (await db.execute(select(func.count()).select_from(Skill))).scalar()
    tool_count = (await db.execute(select(func.count()).select_from(MCPTool))).scalar()

    return {
        "knowledge_bases": kb_count,
        "documents": doc_count,
        "llm_providers": provider_count,
        "chat_sessions": session_count,
        "chat_messages": message_count,
        "skills": skill_count,
        "mcp_tools": tool_count,
    }
