import os
import uuid
from typing import List, Optional
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
import aiofiles

from app.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.knowledge import KnowledgeBase, Document, DocumentChunk
from app.models.embed_provider import EmbedProvider
from app.models.llm_provider import LLMProvider
from app.models.ocr_provider import OCRProvider
from app.schemas.knowledge import (
    KnowledgeBaseCreate, KnowledgeBaseUpdate, KnowledgeBaseRead,
    DocumentRead, SearchResult,
)
from app.services.document_parser import parse_document, IMAGE_EXTENSIONS
from app.services.rag_service import index_document, delete_document_chunks, search as rag_search, delete_collection
from app.services.encryption import encrypt
from app.services.ocr_service import ocr_image
from app.services import llm_service
from app.config import settings

ALLOWED_EXTENSIONS = {
    ".txt", ".md", ".pdf", ".docx", ".pptx",
    ".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".gif", ".webp",
}

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
        embed_api_key_encrypted=encrypt(payload.embed_api_key) if payload.embed_api_key else None,
        embed_base_url=payload.embed_base_url,
        embed_provider_id=payload.embed_provider_id or None,
        ocr_provider_id=payload.ocr_provider_id or None,
        chunk_size=payload.chunk_size,
        chunk_overlap=payload.chunk_overlap,
        top_k=payload.top_k,
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
    if payload.embed_api_key is not None:
        kb.embed_api_key_encrypted = encrypt(payload.embed_api_key) if payload.embed_api_key else None
    if payload.embed_base_url is not None:
        kb.embed_base_url = payload.embed_base_url
    if payload.embed_provider_id is not None:
        kb.embed_provider_id = payload.embed_provider_id or None
    if payload.ocr_provider_id is not None:
        kb.ocr_provider_id = payload.ocr_provider_id or None
    if payload.chunk_size is not None:
        kb.chunk_size = payload.chunk_size
    if payload.chunk_overlap is not None:
        kb.chunk_overlap = payload.chunk_overlap
    if payload.top_k is not None:
        kb.top_k = payload.top_k
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
    # Delete chunks and Chroma collection
    await db.execute(delete(DocumentChunk).where(DocumentChunk.kb_id == kb_id))
    delete_collection(kb_id)
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

    # Validate file extension
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"不支持的文件格式: {file_ext}")

    # Save file
    kb_upload_dir = os.path.join(settings.upload_dir, kb_id)
    os.makedirs(kb_upload_dir, exist_ok=True)
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
        if file_ext in IMAGE_EXTENSIONS:
            # Resolve OCR provider: KB-specific OCRProvider > default OCRProvider > vision LLM fallback
            ocr_provider = None
            if kb.ocr_provider_id:
                ocr_result = await db.execute(
                    select(OCRProvider).where(OCRProvider.id == kb.ocr_provider_id)
                )
                ocr_provider = ocr_result.scalar_one_or_none()
            if ocr_provider is None:
                default_ocr = await db.execute(
                    select(OCRProvider).where(
                        OCRProvider.is_default == True,
                        OCRProvider.is_active == True,
                    ).limit(1)
                )
                ocr_provider = default_ocr.scalar_one_or_none()
            if ocr_provider is None:
                any_ocr = await db.execute(
                    select(OCRProvider).where(OCRProvider.is_active == True).limit(1)
                )
                ocr_provider = any_ocr.scalar_one_or_none()
            # Final fallback: use default LLM provider
            if ocr_provider is None:
                ocr_provider = await llm_service.get_default_provider(db)
            chunks = await ocr_image(file_path, ocr_provider)
        else:
            chunks = parse_document(file_path, chunk_size=kb.chunk_size, chunk_overlap=kb.chunk_overlap)

        # Resolve embed provider
        embed_provider = None
        if kb.embed_provider_id:
            ep_result = await db.execute(
                select(EmbedProvider).where(EmbedProvider.id == kb.embed_provider_id)
            )
            embed_provider = ep_result.scalar_one_or_none()

        chunk_count = await index_document(doc.id, kb_id, chunks, db, kb=kb, embed_provider=embed_provider)
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


@router.get("/{kb_id}/search", response_model=List[SearchResult])
async def search_kb(
    kb_id: str,
    q: str = Query(..., min_length=1, description="搜索关键词"),
    top_k: Optional[int] = Query(None, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(KnowledgeBase).where(KnowledgeBase.id == kb_id))
    kb = result.scalar_one_or_none()
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")

    # Resolve embed provider for search
    embed_provider = None
    if kb.embed_provider_id:
        ep_result = await db.execute(
            select(EmbedProvider).where(EmbedProvider.id == kb.embed_provider_id)
        )
        embed_provider = ep_result.scalar_one_or_none()

    raw_results = await rag_search(q, kb_id, db, top_k=top_k or kb.top_k, kb=kb, embed_provider=embed_provider)

    # Attach document filenames
    doc_ids = list({r["doc_id"] for r in raw_results})
    doc_map: dict = {}
    if doc_ids:
        docs_result = await db.execute(select(Document).where(Document.id.in_(doc_ids)))
        for doc in docs_result.scalars().all():
            doc_map[doc.id] = doc.filename

    return [
        SearchResult(
            chunk_text=r["text"],
            score=round(r["score"], 4),
            doc_id=r["doc_id"],
            chunk_idx=r["chunk_idx"],
            document_name=doc_map.get(r["doc_id"]),
        )
        for r in raw_results
    ]
