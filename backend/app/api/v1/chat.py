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
    return msgs_result.scalars().all()


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
