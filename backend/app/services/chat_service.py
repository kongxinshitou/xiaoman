import json
import uuid
from typing import AsyncGenerator, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone

from app.models.session import ChatSession, ChatMessage
from app.models.skill import Skill
from app.models.knowledge import KnowledgeBase
from app.services import llm_service, skill_router, rag_service, mcp_service


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

    # Update session title
    result = await db.execute(select(ChatSession).where(ChatSession.id == session_id))
    session = result.scalar_one_or_none()
    if session:
        session.updated_at = datetime.now(timezone.utc)
        if session.title == "新对话" and user_message:
            session.title = user_message[:30] + ("..." if len(user_message) > 30 else "")
        await db.commit()

    # Load active skills and route
    skills_result = await db.execute(select(Skill).where(Skill.is_active == True))
    active_skills = skills_result.scalars().all()
    route = skill_router.route(user_message, active_skills)
    route_type = route["type"]
    routed_skill = route.get("skill")

    # Get LLM provider
    provider = await llm_service.get_default_provider(
        db, provider_id or (session.active_provider_id if session else None)
    )

    # Build message history
    history_result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at)
    )
    messages = [
        {"role": m.role, "content": m.content}
        for m in history_result.scalars().all()
        if m.role in ("user", "assistant")
    ]

    assistant_content = ""
    assistant_msg_id = str(uuid.uuid4())
    meta = {"route": {"type": route_type, "skill_name": route.get("skill_name")}}

    # ── MCP Tool Execution ──
    if route_type == "mcp":
        skill_config = getattr(routed_skill, "config", "{}") if routed_skill else "{}"
        tool = await mcp_service.find_tool_for_skill(skill_config, db)
        tool_name = (tool.display_name or tool.name) if tool else "MCP工具"

        yield f"event: tool_call\ndata: {json.dumps({'tool': tool_name, 'status': 'running', 'message': '正在调用工具...'}, ensure_ascii=False)}\n\n"

        tool_output = ""
        if tool:
            params = await mcp_service.extract_params_from_message(user_message, tool.tool_schema)
            async for event in mcp_service.execute_tool_stream(tool, params):
                status = event["status"]
                output = event["output"]
                tool_output += output + "\n"
                sse_status = "done" if status == "done" else ("error" if status == "error" else "running")
                yield f"event: tool_call\ndata: {json.dumps({'tool': tool_name, 'status': sse_status, 'message': output}, ensure_ascii=False)}\n\n"
        else:
            no_tool = "未找到可用的 MCP 工具。请在「设置 → MCP 工具」中添加并启用工具。"
            yield f"event: tool_call\ndata: {json.dumps({'tool': tool_name, 'status': 'error', 'message': no_tool}, ensure_ascii=False)}\n\n"
            tool_output = no_tool

        if tool_output.strip():
            messages.append({
                "role": "system",
                "content": f"以下是工具「{tool_name}」的执行结果，请基于此内容给出简明的运维诊断和建议：\n\n```\n{tool_output[:3000]}\n```",
            })
        meta["tool_name"] = tool_name

    # ── RAG Knowledge Search ──
    elif route_type == "rag":
        skill_config_json = getattr(routed_skill, "config", "{}") if routed_skill else "{}"
        try:
            configured_kb_ids = json.loads(skill_config_json).get("kb_ids", [])
        except Exception:
            configured_kb_ids = []

        search_kb_ids = configured_kb_ids or kb_ids
        if not search_kb_ids:
            kb_result = await db.execute(select(KnowledgeBase))
            search_kb_ids = [kb.id for kb in kb_result.scalars().all()]

        citations = []
        context_texts = []
        for kid in search_kb_ids:
            results = await rag_service.search(user_message, kid, db, top_k=3)
            for r in results:
                context_texts.append(r["text"])
                citations.append({"doc_id": r["doc_id"], "text": r["text"][:120], "score": round(r["score"], 3)})

        if context_texts:
            context = "\n\n---\n\n".join(context_texts[:5])
            messages.insert(0, {
                "role": "system",
                "content": f"你是晓曼，专业的AI运维助手。请根据以下知识库内容回答：\n\n{context}",
            })
            for cit in citations[:3]:
                yield f"event: citation\ndata: {json.dumps(cit, ensure_ascii=False)}\n\n"
        else:
            messages.insert(0, {"role": "system", "content": "你是晓曼，专业的AI运维助手。知识库暂无相关内容，请基于自身知识回答。"})

    # ── Direct Chat ──
    else:
        if not any(m["role"] == "system" for m in messages):
            messages.insert(0, {"role": "system", "content": "你是晓曼，专业的AI运维助手，擅长 DevOps、SRE、云原生问题。请用中文回答。"})

    # ── Stream LLM Response ──
    try:
        async for delta in llm_service.stream_chat(messages, provider, db):
            assistant_content += delta
            yield f"event: token\ndata: {json.dumps({'delta': delta}, ensure_ascii=False)}\n\n"
    except Exception as e:
        yield f"event: error\ndata: {json.dumps({'message': str(e)}, ensure_ascii=False)}\n\n"
        assistant_content = f"[错误] {str(e)}"

    # ── Save Assistant Message ──
    db.add(ChatMessage(
        id=assistant_msg_id,
        session_id=session_id,
        role="assistant",
        content=assistant_content,
        meta=json.dumps(meta),
    ))
    await db.commit()

    yield f"event: done\ndata: {json.dumps({'message_id': assistant_msg_id, 'session_id': session_id}, ensure_ascii=False)}\n\n"
