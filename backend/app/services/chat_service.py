import json
import uuid
from typing import AsyncGenerator, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone

from app.models.session import ChatSession, ChatMessage
from app.models.skill import Skill
from app.models.llm_provider import LLMProvider
from app.models.knowledge import KnowledgeBase
from app.services import llm_service, skill_router, rag_service


async def process_message(
    session_id: str,
    user_message: str,
    user_id: str,
    provider_id: Optional[str],
    kb_ids: Optional[List[str]],
    db: AsyncSession,
) -> AsyncGenerator[str, None]:
    # Save user message
    user_msg = ChatMessage(
        id=str(uuid.uuid4()),
        session_id=session_id,
        role="user",
        content=user_message,
        meta="{}",
    )
    db.add(user_msg)
    await db.commit()

    # Update session timestamp
    result = await db.execute(select(ChatSession).where(ChatSession.id == session_id))
    session = result.scalar_one_or_none()
    if session:
        session.updated_at = datetime.now(timezone.utc)
        # Auto-set title from first message
        if session.title == "新对话" and len(user_message) > 0:
            session.title = user_message[:30] + ("..." if len(user_message) > 30 else "")
        await db.commit()

    # Load active skills
    skills_result = await db.execute(select(Skill).where(Skill.is_active == True))
    active_skills = skills_result.scalars().all()

    # Route the message
    route = skill_router.route(user_message, active_skills)
    route_type = route["type"]

    # Get provider
    provider = await llm_service.get_default_provider(db, provider_id or (session.active_provider_id if session else None))

    # Build message history
    history_result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at)
    )
    history = history_result.scalars().all()

    messages = []
    for msg in history:
        if msg.role in ("user", "assistant"):
            messages.append({"role": msg.role, "content": msg.content})

    # Accumulate assistant response
    assistant_content = ""
    assistant_msg_id = str(uuid.uuid4())

    # RAG: search knowledge base and prepend context
    if route_type == "rag" and kb_ids:
        citations = []
        context_texts = []
        for kb_id in kb_ids:
            results = await rag_service.search(user_message, kb_id, db)
            for r in results:
                context_texts.append(r["text"])
                citations.append({"doc_id": r["doc_id"], "text": r["text"][:100], "score": r["score"]})

        if context_texts:
            context = "\n\n".join(context_texts)
            # Prepend context to messages as system message
            rag_system = f"请根据以下知识库内容回答用户问题：\n\n{context}"
            messages.insert(0, {"role": "system", "content": rag_system})

            # Yield citations
            for cit in citations[:3]:
                event = f"event: citation\ndata: {json.dumps(cit, ensure_ascii=False)}\n\n"
                yield event

    # MCP: yield tool_call event
    if route_type == "mcp":
        tool_call_data = {
            "tool": route.get("skill_name", "unknown"),
            "status": "running",
            "message": "正在执行工具调用...",
        }
        yield f"event: tool_call\ndata: {json.dumps(tool_call_data, ensure_ascii=False)}\n\n"

    # Stream LLM response
    try:
        async for delta in llm_service.stream_chat(messages, provider, db):
            assistant_content += delta
            token_data = {"delta": delta}
            yield f"event: token\ndata: {json.dumps(token_data, ensure_ascii=False)}\n\n"
    except Exception as e:
        error_data = {"message": str(e)}
        yield f"event: error\ndata: {json.dumps(error_data, ensure_ascii=False)}\n\n"
        assistant_content = f"[错误] {str(e)}"

    # Save assistant message
    assistant_msg = ChatMessage(
        id=assistant_msg_id,
        session_id=session_id,
        role="assistant",
        content=assistant_content,
        meta=json.dumps({"route": route}),
    )
    db.add(assistant_msg)
    await db.commit()

    # Yield done event
    done_data = {"message_id": assistant_msg_id, "session_id": session_id}
    yield f"event: done\ndata: {json.dumps(done_data, ensure_ascii=False)}\n\n"
