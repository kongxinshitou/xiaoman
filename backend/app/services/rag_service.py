from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from app.models.knowledge import DocumentChunk, Document


async def index_document(
    doc_id: str,
    kb_id: str,
    chunks: List[str],
    db: AsyncSession,
) -> int:
    # Remove existing chunks for this document
    await db.execute(delete(DocumentChunk).where(DocumentChunk.doc_id == doc_id))

    # Insert new chunks
    for idx, chunk_text in enumerate(chunks):
        chunk = DocumentChunk(
            doc_id=doc_id,
            kb_id=kb_id,
            chunk_text=chunk_text,
            chunk_idx=idx,
        )
        db.add(chunk)

    await db.commit()
    return len(chunks)


async def search(
    query: str,
    kb_id: str,
    db: AsyncSession,
    top_k: int = 5,
) -> List[Dict[str, Any]]:
    # Simple keyword search in document_chunks
    result = await db.execute(
        select(DocumentChunk).where(DocumentChunk.kb_id == kb_id)
    )
    all_chunks = result.scalars().all()

    # Score chunks by keyword overlap
    query_words = set(query.lower().split())
    scored = []
    for chunk in all_chunks:
        chunk_words = set(chunk.chunk_text.lower().split())
        overlap = len(query_words & chunk_words)
        if overlap > 0:
            scored.append({
                "text": chunk.chunk_text,
                "doc_id": chunk.doc_id,
                "chunk_idx": chunk.chunk_idx,
                "score": overlap / max(len(query_words), 1),
            })

    # Sort by score descending
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]


async def delete_document_chunks(doc_id: str, db: AsyncSession) -> None:
    await db.execute(delete(DocumentChunk).where(DocumentChunk.doc_id == doc_id))
    await db.commit()
