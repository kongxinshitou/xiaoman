import os
import tempfile
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from typing import List, Optional
import uuid
from datetime import datetime, timezone

from app.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.session import ChatSession, ChatMessage
from app.schemas.chat import SessionCreate, SessionUpdate, SessionRead, MessageRead, ChatRequest
from app.services.chat_service import process_message

router = APIRouter()

CHAT_UPLOAD_ALLOWED = {".txt", ".md", ".pdf", ".docx", ".pptx", ".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".gif", ".webp"}
CHAT_MAX_CONTEXT_CHARS = 8000


@router.post("/parse-file")
async def parse_file_for_chat(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Parse an uploaded file and return its extracted text for use as chat context."""
    from app.services.document_parser import parse_document, IMAGE_EXTENSIONS
    from app.services.ocr_service import ocr_image
    from app.services import llm_service
    from app.models.llm_provider import LLMProvider

    file_ext = os.path.splitext(file.filename or "")[1].lower()
    if file_ext not in CHAT_UPLOAD_ALLOWED:
        raise HTTPException(status_code=400, detail=f"不支持的文件格式: {file_ext}")

    content = await file.read()
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="文件超过 20MB 限制")

    # Write to temp file for parsing
    with tempfile.NamedTemporaryFile(suffix=file_ext, delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        if file_ext in IMAGE_EXTENSIONS:
            from app.models.ocr_provider import OCRProvider
            # Use default OCR provider, fallback to default LLM
            ocr_result = await db.execute(
                select(OCRProvider).where(
                    OCRProvider.is_default == True,
                    OCRProvider.is_active == True,
                ).limit(1)
            )
            ocr_provider = ocr_result.scalar_one_or_none()
            if ocr_provider is None:
                any_ocr = await db.execute(
                    select(OCRProvider).where(OCRProvider.is_active == True).limit(1)
                )
                ocr_provider = any_ocr.scalar_one_or_none()
            if ocr_provider is None:
                ocr_provider = await llm_service.get_default_provider(db)
            chunks = await ocr_image(tmp_path, ocr_provider)
        else:
            chunks = parse_document(tmp_path)
    finally:
        os.unlink(tmp_path)

    full_text = "\n".join(chunks)
    truncated = len(full_text) > CHAT_MAX_CONTEXT_CHARS
    if truncated:
        full_text = full_text[:CHAT_MAX_CONTEXT_CHARS]

    return {
        "text": full_text,
        "filename": file.filename,
        "truncated": truncated,
    }


@router.post("/sessions", response_model=SessionRead)
async def create_session(
    payload: SessionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session = ChatSession(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        title=payload.title,
        active_provider_id=payload.active_provider_id,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


@router.get("/sessions", response_model=List[SessionRead])
async def list_sessions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.user_id == current_user.id)
        .order_by(ChatSession.updated_at.desc())
    )
    return result.scalars().all()


@router.get("/sessions/{session_id}", response_model=SessionRead)
async def get_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == current_user.id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    return session


@router.patch("/sessions/{session_id}", response_model=SessionRead)
async def update_session(
    session_id: str,
    payload: SessionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == current_user.id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    if payload.title is not None:
        session.title = payload.title
    if payload.active_provider_id is not None:
        session.active_provider_id = payload.active_provider_id
    session.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(session)
    return session


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == current_user.id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    await db.execute(delete(ChatMessage).where(ChatMessage.session_id == session_id))
    await db.delete(session)
    await db.commit()
    return {"message": "会话已删除"}


@router.get("/sessions/{session_id}/messages", response_model=List[MessageRead])
async def get_messages(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == current_user.id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="会话不存在")
    msgs_result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at)
    )
    msgs = list(msgs_result.scalars().all())

    # ── Rehydrate inline images for assistant messages ──
    # chat_service persists a lightweight {id, description} list in meta.images
    # for each message that yielded image events. On load we need to:
    #   1. Collect every cited id across the session (from meta.images and
    #      from any [IMG_xxx] markers in content as a fallback).
    #   2. Resolve them to DocumentImage rows via exact + prefix match —
    #      legacy data may have long ids that the LLM cites in short form.
    #   3. Read base64 from each row's local_path and attach to the message.
    import json as _json
    import base64 as _b64
    import re as _re
    from app.services.image_lookup import resolve_image_ids

    per_msg_ids: dict = {}  # message_id -> ordered list of cited ids
    all_cited: set = set()

    for m in msgs:
        if m.role != "assistant":
            continue
        ids_for_msg: list = []
        try:
            meta_obj = _json.loads(m.meta or "{}")
        except Exception:
            meta_obj = {}
        for ref in meta_obj.get("images", []) or []:
            iid = ref.get("id") if isinstance(ref, dict) else None
            if iid and iid not in ids_for_msg:
                ids_for_msg.append(iid)
        # Fallback: catch markers in content even when meta.images is missing
        # (handles messages written before meta.images was introduced).
        for marker in _re.findall(r"\[IMG_[^\]]+\]", m.content or ""):
            iid = marker.strip("[]")
            if iid and iid not in ids_for_msg:
                ids_for_msg.append(iid)
        if ids_for_msg:
            per_msg_ids[m.id] = ids_for_msg
            all_cited.update(ids_for_msg)

    cited_to_row = await resolve_image_ids(list(all_cited), db) if all_cited else {}

    # Build response, attaching images per message
    response: List[MessageRead] = []
    for m in msgs:
        record = MessageRead.model_validate(m)
        ids = per_msg_ids.get(m.id) or []
        if ids:
            inflated = []
            seen: set = set()
            for cited_id in ids:
                if cited_id in seen:
                    continue
                seen.add(cited_id)
                row = cited_to_row.get(cited_id)
                if row is None:
                    continue
                b64 = None
                if row.local_path and os.path.exists(row.local_path):
                    try:
                        with open(row.local_path, "rb") as _f:
                            b64 = _b64.b64encode(_f.read()).decode()
                    except Exception:
                        pass
                # Return the CITED id — that's the key the frontend will
                # match against the [IMG_xxx] marker in the message content.
                inflated.append({
                    "id": cited_id,
                    "description": row.description or "",
                    "base64": b64,
                })
            if inflated:
                record.images = inflated  # type: ignore[assignment]
        response.append(record)
    return response


@router.post("/stream")
async def stream_chat(
    payload: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Verify session belongs to user
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == payload.session_id,
            ChatSession.user_id == current_user.id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="会话不存在")

    async def event_generator():
        try:
            async for event in process_message(
                session_id=payload.session_id,
                user_message=payload.message,
                user_id=current_user.id,
                provider_id=payload.provider_id,
                kb_ids=payload.kb_ids,
                web_search=payload.web_search,
                image_data_url=payload.image_data_url,
                db=db,
            ):
                yield event
        except (GeneratorExit, KeyboardInterrupt, SystemExit):
            raise
        except BaseException as e:
            import json as _json
            yield f"event: error\ndata: {_json.dumps({'message': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


CHAT_IMAGE_ALLOWED = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}


@router.post("/upload-image")
async def upload_image_for_chat(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload an image to be used as vision input in the next chat message.

    Returns a base64-encoded data URL that the frontend embeds in the message
    sent to the LLM as an image_url content block.
    """
    import base64

    file_ext = os.path.splitext(file.filename or "")[1].lower()
    if file_ext not in CHAT_IMAGE_ALLOWED:
        raise HTTPException(status_code=400, detail=f"不支持的图片格式: {file_ext}")

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="图片超过 10MB 限制")

    mime_map = {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".png": "image/png", ".webp": "image/webp",
        ".gif": "image/gif", ".bmp": "image/bmp",
    }
    mime = mime_map.get(file_ext, "image/png")
    b64 = base64.b64encode(content).decode()
    data_url = f"data:{mime};base64,{b64}"

    return {
        "filename": file.filename,
        "data_url": data_url,
        "mime_type": mime,
    }


@router.post("/transcribe")
async def transcribe_audio(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Transcribe an uploaded audio file using DashScope paraformer (Tongyi Qianwen).

    Reuses the API key from the configured Qwen LLM provider — no extra credential
    needed.  Falls back to the DASHSCOPE_API_KEY environment variable if no Qwen
    provider is configured.

    The frontend uploads a WebM / OGG / WAV blob recorded via MediaRecorder.
    Returns {"text": "..."}.
    """
    import tempfile

    content = await file.read()
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="音频超过 20MB 限制")

    file_ext = os.path.splitext(file.filename or "audio.webm")[1].lower() or ".webm"

    with tempfile.NamedTemporaryFile(suffix=file_ext, delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        text = await _dashscope_asr(tmp_path, file_ext, db)
    finally:
        os.unlink(tmp_path)

    return {"text": text, "filename": file.filename}


async def _dashscope_asr(audio_path: str, file_ext: str, db: AsyncSession) -> str:
    """Call DashScope paraformer via the OpenAI-compatible transcription endpoint.

    Priority for API key:
      1. Configured Qwen LLM provider (provider_type == 'qwen', is_active)
      2. DASHSCOPE_API_KEY environment variable

    Uses the openai SDK pointed at DashScope's compatible-mode base URL.
    Model: paraformer-realtime-v2 (supports synchronous file upload transcription).
    """
    import os as _os
    from app.models.llm_provider import LLMProvider
    from app.services.encryption import decrypt

    # ── 1. Resolve API key ────────────────────────────────────────────────────
    api_key = ""

    # Prefer the active Qwen provider already configured in the system
    result = await db.execute(
        select(LLMProvider).where(
            LLMProvider.provider_type == "qwen",
            LLMProvider.is_active == True,
        ).limit(1)
    )
    qwen_provider = result.scalar_one_or_none()
    if qwen_provider and qwen_provider.encrypted_api_key:
        try:
            api_key = decrypt(qwen_provider.encrypted_api_key)
        except Exception:
            pass

    # Fallback to env var
    if not api_key:
        api_key = _os.environ.get("DASHSCOPE_API_KEY", "")

    if not api_key:
        return (
            "[未找到 DashScope API Key。"
            "请在「模型配置」中添加一个通义千问提供商并启用，"
            "或在环境变量中设置 DASHSCOPE_API_KEY]"
        )

    # ── 2. Call DashScope via OpenAI-compatible SDK ───────────────────────────
    # Use openai SDK with DashScope base URL — it handles multipart formatting correctly.
    # paraformer-realtime-v2 supports synchronous file-based transcription.
    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(
            api_key=api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )

        with open(audio_path, "rb") as audio_file:
            audio_filename = f"audio{file_ext}"
            response = await client.audio.transcriptions.create(
                model="paraformer-realtime-v2",
                file=(audio_filename, audio_file),
            )
        return response.text or ""

    except Exception as e:
        err_str = str(e)
        raise HTTPException(
            status_code=500,
            detail=f"DashScope ASR 识别失败: {err_str[:300]}",
        )
