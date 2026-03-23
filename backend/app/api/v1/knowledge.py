import os
import uuid
from typing import List
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
import aiofiles

from app.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.knowledge import KnowledgeBase, Document, DocumentChunk
from app.schemas.knowledge import KnowledgeBaseCreate, KnowledgeBaseUpdate, KnowledgeBaseRead, DocumentRead
from app.services.document_parser import parse_document
from app.services.rag_service import index_document, delete_document_chunks
from app.config import settings

router = APIRouter()


@router.post("", response_model=KnowledgeBaseRead)
async def create_kb(
    payload: KnowledgeBaseCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    kb = KnowledgeBase(
        name=payload.name,
        description=payload.description,
        owner_id=current_user.id,
        embed_model=payload.embed_model,
    )
    db.add(kb)
    await db.commit()
    await db.refresh(kb)
    return kb


@router.get("", response_model=List[KnowledgeBaseRead])
async def list_kbs(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(KnowledgeBase).order_by(KnowledgeBase.created_at.desc())
    )
    return result.scalars().all()


@router.get("/{kb_id}", response_model=KnowledgeBaseRead)
async def get_kb(
    kb_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(KnowledgeBase).where(KnowledgeBase.id == kb_id))
    kb = result.scalar_one_or_none()
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")
    return kb


@router.patch("/{kb_id}", response_model=KnowledgeBaseRead)
async def update_kb(
    kb_id: str,
    payload: KnowledgeBaseUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(KnowledgeBase).where(KnowledgeBase.id == kb_id))
    kb = result.scalar_one_or_none()
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")
    if payload.name is not None:
        kb.name = payload.name
    if payload.description is not None:
        kb.description = payload.description
    if payload.embed_model is not None:
        kb.embed_model = payload.embed_model
    kb.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(kb)
    return kb


@router.delete("/{kb_id}")
async def delete_kb(
    kb_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(KnowledgeBase).where(KnowledgeBase.id == kb_id))
    kb = result.scalar_one_or_none()
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")
    # Delete chunks
    await db.execute(delete(DocumentChunk).where(DocumentChunk.kb_id == kb_id))
    # Delete documents
    docs_result = await db.execute(select(Document).where(Document.kb_id == kb_id))
    for doc in docs_result.scalars().all():
        if doc.file_path and os.path.exists(doc.file_path):
            os.remove(doc.file_path)
    await db.execute(delete(Document).where(Document.kb_id == kb_id))
    await db.delete(kb)
    await db.commit()
    return {"message": "知识库已删除"}


@router.get("/{kb_id}/documents", response_model=List[DocumentRead])
async def list_documents(
    kb_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Document).where(Document.kb_id == kb_id).order_by(Document.created_at.desc())
    )
    return result.scalars().all()


@router.post("/{kb_id}/documents", response_model=DocumentRead)
async def upload_document(
    kb_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Verify KB exists
    result = await db.execute(select(KnowledgeBase).where(KnowledgeBase.id == kb_id))
    kb = result.scalar_one_or_none()
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")

    # Check file size
    content = await file.read()
    file_size = len(content)
    max_size = settings.max_file_size_mb * 1024 * 1024
    if file_size > max_size:
        raise HTTPException(status_code=400, detail=f"文件超过最大限制 {settings.max_file_size_mb}MB")

    # Save file
    kb_upload_dir = os.path.join(settings.upload_dir, kb_id)
    os.makedirs(kb_upload_dir, exist_ok=True)
    file_ext = os.path.splitext(file.filename)[1].lower()
    saved_filename = f"{uuid.uuid4()}{file_ext}"
    file_path = os.path.join(kb_upload_dir, saved_filename)

    async with aiofiles.open(file_path, "wb") as f:
        await f.write(content)

    # Create document record
    doc = Document(
        kb_id=kb_id,
        filename=file.filename,
        file_type=file_ext.lstrip(".") or "txt",
        file_size=file_size,
        file_path=file_path,
        status="processing",
        uploaded_by=current_user.id,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    # Parse and index
    try:
        chunks = parse_document(file_path)
        chunk_count = await index_document(doc.id, kb_id, chunks, db)
        doc.status = "ready"
        doc.chunk_count = chunk_count
        doc.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(doc)
    except Exception as e:
        doc.status = "error"
        doc.error_msg = str(e)
        await db.commit()
        await db.refresh(doc)

    return doc


@router.delete("/{kb_id}/documents/{doc_id}")
async def delete_document(
    kb_id: str,
    doc_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Document).where(Document.id == doc_id, Document.kb_id == kb_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    await delete_document_chunks(doc_id, db)
    if doc.file_path and os.path.exists(doc.file_path):
        os.remove(doc.file_path)
    await db.delete(doc)
    await db.commit()
    return {"message": "文档已删除"}
