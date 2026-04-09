import json
import uuid
from typing import AsyncGenerator, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone, timedelta

_TZ_BEIJING = timezone(timedelta(hours=8))

def _beijing_now() -> str:
    return datetime.now(_TZ_BEIJING).strftime("%Y-%m-%d %H:%M:%S %Z")

from app.models.session import ChatSession, ChatMessage
from app.models.knowledge import KnowledgeBase
from app.models.mcp_tool import MCPTool
from app.services import llm_service, rag_service, mcp_service, ocr_service
from app.services.web_search_service import search_web


async def process_message(
    session_id: str,
    user_message: str,
    user_id: str,
    provider_id: Optional[str],
    kb_ids: Optional[List[str]],
    db: AsyncSession,
    web_search: bool = False,
    image_data_url: Optional[str] = None,
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
    history_msgs = list(history_result.scalars().all())
    messages = []
    for m in history_msgs:
        if m.role not in ("user", "assistant"):
            continue
        messages.append({"role": m.role, "content": m.content})

    # If current user message has an attached image, ask the OCR/vision provider
    # to describe it first, then inject the description as plain text. This way
    # the main LLM never receives image_url blocks (which non-vision providers
    # like DashScope text models reject as "unknown variant").
    if image_data_url and messages and messages[-1]["role"] == "user":
        text_part = (messages[-1]["content"] or "").replace("[图片]\n", "").strip()
        ocr_provider = await ocr_service.get_default_ocr_provider(db)
        try:
            image_description = await ocr_service.describe_image_data_url(
                image_data_url, ocr_provider
            )
            messages[-1]["content"] = (
                f"用户上传了一张图片，以下是图片的视觉解析内容：\n"
                f"---\n{image_description}\n---\n\n"
                f"用户提问：{text_part or '请基于上述图片内容回答或分析。'}"
            )
            yield (
                "event: image_understanding\n"
                "data: " + json.dumps(
                    {"description": image_description}, ensure_ascii=False
                ) + "\n\n"
            )
        except Exception as e:
            err_msg = f"图片解析失败：{str(e)[:200]}。请在「设置 → OCR 视觉模型」中配置可用的视觉模型。"
            yield "event: error\ndata: " + json.dumps({"message": err_msg}, ensure_ascii=False) + "\n\n"
            messages[-1]["content"] = text_part or "（图片解析失败，无法分析）"

    assistant_content = ""
    assistant_msg_id = str(uuid.uuid4())
    meta = {}

    # ── RAG Knowledge Search (when kb_ids are selected) ──
    if kb_ids:
        citations = []
        context_texts = []
        all_doc_ids = []
        referenced_ids: set = set()
        for kid in kb_ids:
            kb_result = await db.execute(select(KnowledgeBase).where(KnowledgeBase.id == kid))
            kb = kb_result.scalar_one_or_none()
            if not kb:
                continue

            # Resolve embed provider
            embed_provider = None
            if kb.embed_provider_id:
                from app.models.embed_provider import EmbedProvider
                ep_result = await db.execute(select(EmbedProvider).where(EmbedProvider.id == kb.embed_provider_id))
                embed_provider = ep_result.scalar_one_or_none()

            results = await rag_service.search(user_message, kid, db, top_k=kb.top_k, kb=kb, embed_provider=embed_provider)
            for r in results:
                context_texts.append(r["text"])
                all_doc_ids.append(r["doc_id"])
                # Merge image IDs the retriever attached to this chunk's metadata
                for iid in r.get("image_ids", []) or []:
                    referenced_ids.add(iid)
                citations.append({"doc_id": r["doc_id"], "text": r["text"][:120], "score": round(r["score"], 3)})

        if context_texts:
            context = "\n\n---\n\n".join(context_texts[:10])

            # Fetch image metadata associated with retrieved docs
            image_map = await rag_service.get_document_images(list(set(all_doc_ids)), db)

            # Also pick up any inline [IMG_xxx] markers that survived chunking
            import re as _re
            for marker in _re.findall(r"\[IMG_[^\]]+\]", context):
                referenced_ids.add(marker.strip("[]"))

            available_images = {
                iid: image_map[iid] for iid in referenced_ids if iid in image_map
            }

            image_section = ""
            if available_images:
                image_section = "\n\n可用图片（仅引用与回答相关的，不要引用不相关的）：\n" + "\n".join(
                    f"[{img_id}] - {info['description']}"
                    for img_id, info in available_images.items()
                )

            system_content = (
                f"你是晓曼，专业的AI运维助手。当前北京时间：{_beijing_now()}。"
                f"请根据以下知识库内容回答用户的问题。"
                f"如回答涉及到上文检索到的图片内容，请在对应位置以方括号形式插入图片ID标记，"
                f"形如 [IMG_xxx]，不要捏造不存在的图片ID。\n\n"
                f"文档内容：\n{context}"
                f"{image_section}"
                f"\n\n当你调用工具后，请务必根据工具返回的结果，用中文给出完整、清晰的文字回答和总结。"
            )
            messages.insert(0, {"role": "system", "content": system_content})
            for cit in citations[:5]:
                yield f"event: citation\ndata: {json.dumps(cit, ensure_ascii=False)}\n\n"
        else:
            messages.insert(0, {"role": "system", "content": f"你是晓曼，专业的AI运维助手。当前北京时间：{_beijing_now()}。知识库暂无相关内容，请基于自身知识回答。当你调用工具后，请务必根据工具返回的结果，用中文给出完整、清晰的文字回答和总结。"})
        meta["rag"] = True
    else:
        if not any(m["role"] == "system" for m in messages):
            messages.insert(0, {"role": "system", "content": f"你是晓曼，专业的AI运维助手，擅长 DevOps、SRE、云原生问题。当前北京时间：{_beijing_now()}。请用中文回答。当你调用工具后，请务必根据工具返回的结果，用中文给出完整、清晰的文字回答和总结。"})

    # ── Web Search ──
    if web_search:
        yield f"event: web_search_start\ndata: {json.dumps({'message': '正在联网搜索...'}, ensure_ascii=False)}\n\n"
        web_results = await search_web(user_message, max_results=5)
        if web_results:
            for wr in web_results:
                yield f"event: web_result\ndata: {json.dumps(wr, ensure_ascii=False)}\n\n"
            search_context = "\n\n".join(
                f"[{i+1}] {r['title']}\n来源: {r['url']}\n摘要: {r['snippet']}"
                for i, r in enumerate(web_results)
            )
            web_system = f"以下是联网搜索到的最新信息，请结合这些信息回答用户问题，并在适当位置注明来源链接：\n\n{search_context}"
            if messages and messages[0]["role"] == "system":
                messages[0]["content"] = web_system + "\n\n" + messages[0]["content"]
            else:
                messages.insert(0, {"role": "system", "content": web_system})
            meta["web_search"] = True
            meta["web_result_count"] = len(web_results)
        else:
            yield f"event: web_result\ndata: {json.dumps({'title': '', 'url': '', 'snippet': '未找到相关搜索结果'}, ensure_ascii=False)}\n\n"

    # ── Gather active MCP tools for LLM function calling ──
    tools_result = await db.execute(select(MCPTool).where(MCPTool.is_active == True))
    active_tools = tools_result.scalars().all()

    llm_tools = None
    tool_map = {}
    if active_tools:
        llm_tools = []
        for t in active_tools:
            try:
                schema = json.loads(t.tool_schema) if t.tool_schema else {}
            except Exception:
                schema = {}
            llm_tools.append({
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description or t.display_name or t.name,
                    "parameters": schema if schema else {"type": "object", "properties": {}},
                }
            })
            tool_map[t.name] = t

    # ── Inject built-in Feishu tools (if enabled) ──
    from app.services import feishu_service as _feishu_svc
    builtin_tool_names: set = set()
    feishu_cfg = await _feishu_svc.get_feishu_config_if_enabled(db)
    if feishu_cfg:
        feishu_builtin = {
            "type": "function",
            "function": {
                "name": "feishu_create_group",
                "description": "在飞书中创建群聊，并拉入指定成员。适用于需要建立沟通群的场景。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "群聊名称"},
                        "user_open_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "要拉入群聊的成员飞书 open_id 列表",
                        },
                        "description": {"type": "string", "description": "群聊描述（可选）"},
                    },
                    "required": ["name", "user_open_ids"],
                },
            },
        }
        builtin_tool_names.add("feishu_create_group")
        if llm_tools is None:
            llm_tools = []
        llm_tools.append(feishu_builtin)

    # ── Stream LLM Response (Agentic Loop) ──
    try:
        MAX_TOOL_ITERATIONS = 20
        iteration = 0

        while iteration < MAX_TOOL_ITERATIONS:
            iteration += 1
            tool_calls_this_round = []
            text_this_round = ""

            async for delta in llm_service.stream_chat(messages, provider, db, tools=llm_tools):
                if isinstance(delta, dict) and delta.get("type") == "tool_call":
                    tool_calls_this_round.append(delta)
                elif isinstance(delta, dict) and delta.get("type") == "thinking":
                    yield f"event: thinking\ndata: {json.dumps({'delta': delta['delta']}, ensure_ascii=False)}\n\n"
                else:
                    text_this_round += delta
                    assistant_content += delta
                    yield f"event: token\ndata: {json.dumps({'delta': delta}, ensure_ascii=False)}\n\n"

            if not tool_calls_this_round:
                # LLM returned pure text — done
                break

            # Append assistant message with all tool calls from this round
            messages.append({
                "role": "assistant",
                "content": text_this_round or None,
                "tool_calls": [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {"name": tc["name"], "arguments": json.dumps(tc["arguments"])},
                    }
                    for tc in tool_calls_this_round
                ],
            })

            # Execute each tool call and append results
            for tc in tool_calls_this_round:
                tool_name = tc["name"]
                tool_args = tc.get("arguments", {})
                tool_call_id = tc.get("id", str(uuid.uuid4()))
                tool = tool_map.get(tool_name)

                if tool_name in builtin_tool_names:
                    # Execute built-in Feishu tool natively (no external MCP server)
                    yield f"event: tool_call\ndata: {json.dumps({'tool': tool_name, 'status': 'running', 'message': '正在调用内置工具...'}, ensure_ascii=False)}\n\n"
                    tool_output = await _feishu_svc.execute_builtin_tool(tool_name, tool_args, db)
                    yield f"event: tool_call\ndata: {json.dumps({'tool': tool_name, 'status': 'done', 'message': tool_output}, ensure_ascii=False)}\n\n"
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "content": tool_output,
                    })
                    meta["tool_name"] = tool_name
                elif tool:
                    display_name = tool.display_name or tool.name
                    yield f"event: tool_call\ndata: {json.dumps({'tool': display_name, 'status': 'running', 'message': '正在调用工具...'}, ensure_ascii=False)}\n\n"

                    tool_output = ""
                    async for event in mcp_service.execute_tool_stream(tool, tool_args):
                        status = event["status"]
                        output = event["output"]
                        tool_output += output + "\n"
                        sse_status = "done" if status == "done" else ("error" if status == "error" else "running")
                        yield f"event: tool_call\ndata: {json.dumps({'tool': display_name, 'status': sse_status, 'message': output}, ensure_ascii=False)}\n\n"

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "content": tool_output[:20000],
                    })
                    meta["tool_name"] = display_name
                else:
                    yield f"event: tool_call\ndata: {json.dumps({'tool': tool_name, 'status': 'error', 'message': f'未找到工具: {tool_name}'}, ensure_ascii=False)}\n\n"
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "content": f"Error: tool '{tool_name}' not found",
                    })
            # Loop continues: LLM sees all tool results and decides next step

    except BaseException as e:
        if isinstance(e, (GeneratorExit, KeyboardInterrupt, SystemExit)):
            raise
        err_str = str(e)
        yield f"event: error\ndata: {json.dumps({'message': err_str}, ensure_ascii=False)}\n\n"
        assistant_content = f"[错误] {err_str}"

    # ── Fallback: force summary if tools were called but no text was generated ──
    if not assistant_content.strip() and meta.get("tool_name"):
        try:
            messages.append({
                "role": "user",
                "content": "请根据以上工具调用的结果，总结并回答用户的问题。",
            })
            async for delta in llm_service.stream_chat(messages, provider, db):
                if isinstance(delta, dict):
                    continue
                assistant_content += delta
                yield f"event: token\ndata: {json.dumps({'delta': delta}, ensure_ascii=False)}\n\n"
        except BaseException:
            pass

    # ── Extract image references from LLM answer and emit image events ──
    # Strategy: scan the assistant content for ALL [IMG_xxx] markers and look
    # them up in the DocumentImage table. Uses exact match first, then falls
    # back to a prefix-with-underscore match so that short marker IDs cited
    # by the LLM (e.g. "IMG_xxx_018") still resolve to legacy long IDs
    # (e.g. "IMG_xxx_018_图片为一台智能…") stored by the old indexer.
    persisted_image_refs: list = []  # what we'll save back into ChatMessage.meta
    if assistant_content:
        import re as _re2
        import base64 as _b64
        from app.models.knowledge import DocumentImage as _DocImg
        from app.services.image_lookup import resolve_image_ids

        found_markers = _re2.findall(r'\[IMG_[^\]]+\]', assistant_content)
        wanted_ids: list = []
        seen_marker: set = set()
        # Preserve the exact marker text as cited — this is the key the
        # frontend uses (it splits content by the literal marker).
        for marker in found_markers:
            iid = marker.strip("[]")
            if iid and iid not in seen_marker:
                seen_marker.add(iid)
                wanted_ids.append(iid)

        # Resolve cited marker IDs → DocumentImage rows (exact + prefix fallback)
        cited_to_row = await resolve_image_ids(wanted_ids, db)

        for cited_id in wanted_ids:
            row = cited_to_row.get(cited_id)
            if row is None:
                continue
            img_b64 = None
            if row.local_path and __import__("os").path.exists(row.local_path):
                try:
                    with open(row.local_path, "rb") as _f:
                        img_b64 = _b64.b64encode(_f.read()).decode()
                except Exception:
                    pass
            # Emit under the CITED id (what the frontend will match against),
            # not the stored id — that way the marker the LLM wrote and the
            # key in message.images agree.
            yield (
                "event: image\ndata: "
                + json.dumps(
                    {
                        "id": cited_id,
                        "description": row.description or "",
                        "base64": img_b64,
                    },
                    ensure_ascii=False,
                )
                + "\n\n"
            )
            # Persist a lightweight reference (no base64). We store BOTH the
            # cited id (so history reload can match the marker in content)
            # and the resolved stored id (so we can re-fetch the row later).
            persisted_image_refs.append(
                {
                    "id": cited_id,
                    "stored_id": row.id,
                    "description": row.description or "",
                }
            )

    # Stash the references inside meta so the GET messages endpoint can
    # rehydrate base64 from local_path on demand.
    if persisted_image_refs:
        meta["images"] = persisted_image_refs

    # ── Save Assistant Message ──
    try:
        db.add(ChatMessage(
            id=assistant_msg_id,
            session_id=session_id,
            role="assistant",
            content=assistant_content,
            meta=json.dumps(meta, ensure_ascii=False),
        ))
        await db.commit()
    except Exception:
        pass

    yield f"event: done\ndata: {json.dumps({'message_id': assistant_msg_id, 'session_id': session_id}, ensure_ascii=False)}\n\n"
