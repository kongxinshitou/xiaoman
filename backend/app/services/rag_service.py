import asyncio
import json
import logging
from typing import List, Dict, Any, Optional, TYPE_CHECKING

import chromadb
from langchain_community.vectorstores import Chroma
from langchain_core.embeddings import Embeddings

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.models.knowledge import DocumentChunk, Document, DocumentImage
from app.config import settings

if TYPE_CHECKING:
    from app.models.knowledge import KnowledgeBase
    from app.models.embed_provider import EmbedProvider

logger = logging.getLogger(__name__)

_chroma_client: Optional[chromadb.PersistentClient] = None


def get_chroma_client() -> chromadb.PersistentClient:
    global _chroma_client
    if _chroma_client is None:
        import os
        os.makedirs(settings.chroma_persist_dir, exist_ok=True)
        _chroma_client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
    return _chroma_client


def _collection_name(kb_id: str) -> str:
    """Build a valid Chroma collection name from kb_id."""
    name = f"kb_{kb_id.replace('-', '_')}"
    # Chroma requires 3-63 chars
    if len(name) > 63:
        name = name[:63]
    return name


class LiteLLMEmbeddings(Embeddings):
    """Wraps litellm embedding calls for LangChain compatibility."""

    def __init__(self, model: str, api_key: str, api_base: Optional[str] = None):
        self.model = model
        self.api_key = api_key
        self.api_base = api_base

    def embed_documents(self, texts: List[str], batch_size: int = 5) -> List[List[float]]:
        import litellm
        results: List[List[float]] = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i: i + batch_size]
            kwargs: Dict[str, Any] = {
                "model": self.model,
                "input": batch,
                "api_key": self.api_key,
            }
            if self.api_base:
                kwargs["api_base"] = self.api_base
            resp = litellm.embedding(**kwargs)
            results.extend(item["embedding"] for item in resp.data)
        return results

    def embed_query(self, text: str) -> List[float]:
        return self.embed_documents([text])[0]


def _build_embeddings_from_provider(provider: "EmbedProvider") -> Optional[LiteLLMEmbeddings]:
    """Build LiteLLMEmbeddings from an EmbedProvider."""
    try:
        from app.services.encryption import decrypt
        from app.services.embed_service import EMBED_PROVIDER_CONFIG

        api_key = decrypt(provider.encrypted_api_key)
        provider_cfg = EMBED_PROVIDER_CONFIG.get(provider.provider_type, {"api_base": None})
        base_url = provider.base_url or provider_cfg.get("api_base")

        model = provider.model_name
        if provider.provider_type not in ("openai",):
            model = f"openai/{provider.model_name}"

        return LiteLLMEmbeddings(model=model, api_key=api_key, api_base=base_url)
    except Exception:
        return None


def _build_embeddings_from_kb(kb: "KnowledgeBase") -> Optional[LiteLLMEmbeddings]:
    """Build LiteLLMEmbeddings from legacy KB embed config."""
    try:
        from app.services.encryption import decrypt
        if not kb.embed_api_key_encrypted:
            return None
        api_key = decrypt(kb.embed_api_key_encrypted)
        return LiteLLMEmbeddings(
            model=kb.embed_model,
            api_key=api_key,
            api_base=kb.embed_base_url,
        )
    except Exception:
        return None


def _build_embeddings(
    kb: Optional["KnowledgeBase"] = None,
    embed_provider: Optional["EmbedProvider"] = None,
) -> Optional[LiteLLMEmbeddings]:
    """Build embeddings, preferring embed_provider over legacy KB config."""
    if embed_provider is not None:
        emb = _build_embeddings_from_provider(embed_provider)
        if emb:
            return emb
    if kb is not None:
        return _build_embeddings_from_kb(kb)
    return None


async def index_document(
    doc_id: str,
    kb_id: str,
    chunks: List[str],
    db: AsyncSession,
    kb: Optional["KnowledgeBase"] = None,
    embed_provider: Optional["EmbedProvider"] = None,
    chunk_image_ids: Optional[List[List[str]]] = None,
) -> int:
    """Index document chunks into ChromaDB and SQLite.

    ``chunk_image_ids`` (when provided) is a parallel list to ``chunks`` where
    each entry holds the image IDs referenced by that chunk.
    """
    col_name = _collection_name(kb_id)

    if chunk_image_ids is None:
        chunk_image_ids = [[] for _ in chunks]

    # Delete existing chunks for this doc from Chroma
    def _chroma_delete():
        client = get_chroma_client()
        collection = client.get_or_create_collection(col_name)
        try:
            existing = collection.get(where={"doc_id": doc_id})
            if existing["ids"]:
                collection.delete(ids=existing["ids"])
        except Exception:
            pass

    await asyncio.to_thread(_chroma_delete)

    # Build embeddings
    embeddings = _build_embeddings(kb, embed_provider)

    # Add to Chroma — chunk_image_ids stored as JSON string (Chroma metadata
    # only accepts scalar str/int/float/bool values, not lists).
    ids = [f"{doc_id}_{i}" for i in range(len(chunks))]
    metadatas = [
        {
            "doc_id": doc_id,
            "kb_id": kb_id,
            "chunk_idx": i,
            "image_ids": json.dumps(chunk_image_ids[i] if i < len(chunk_image_ids) else []),
        }
        for i in range(len(chunks))
    ]

    def _chroma_add():
        client = get_chroma_client()
        if embeddings:
            vectorstore = Chroma(
                collection_name=col_name,
                embedding_function=embeddings,
                client=client,
            )
            vectorstore.add_texts(texts=chunks, metadatas=metadatas, ids=ids)
        else:
            collection = client.get_or_create_collection(col_name)
            collection.add(documents=chunks, metadatas=metadatas, ids=ids)

    await asyncio.to_thread(_chroma_add)

    # Update SQLite DocumentChunk
    await db.execute(delete(DocumentChunk).where(DocumentChunk.doc_id == doc_id))
    for idx, chunk_text in enumerate(chunks):
        ids_for_chunk = chunk_image_ids[idx] if idx < len(chunk_image_ids) else []
        chunk = DocumentChunk(
            doc_id=doc_id,
            kb_id=kb_id,
            chunk_text=chunk_text,
            chunk_idx=idx,
            embedding=None,
            image_ids=json.dumps(ids_for_chunk) if ids_for_chunk else None,
        )
        db.add(chunk)
    await db.commit()
    return len(chunks)


async def search(
    query: str,
    kb_id: str,
    db: AsyncSession,
    top_k: int = 5,
    kb: Optional["KnowledgeBase"] = None,
    embed_provider: Optional["EmbedProvider"] = None,
) -> List[Dict[str, Any]]:
    """Search knowledge base using ChromaDB."""
    col_name = _collection_name(kb_id)
    embeddings = _build_embeddings(kb, embed_provider)

    def _chroma_search() -> List[Dict[str, Any]]:
        client = get_chroma_client()
        try:
            client.get_collection(col_name)
        except Exception:
            return []

        def _parse_ids(meta: Dict[str, Any]) -> List[str]:
            raw = meta.get("image_ids") if meta else None
            if not raw:
                return []
            try:
                val = json.loads(raw) if isinstance(raw, str) else raw
                return list(val) if isinstance(val, list) else []
            except Exception:
                return []

        if embeddings:
            vectorstore = Chroma(
                collection_name=col_name,
                embedding_function=embeddings,
                client=client,
            )
            results = vectorstore.similarity_search_with_score(query, k=top_k)
            return [
                {
                    "text": doc.page_content,
                    "doc_id": doc.metadata.get("doc_id", ""),
                    "chunk_idx": doc.metadata.get("chunk_idx", 0),
                    "score": round(float(1.0 / (1.0 + score)), 4),  # distance to similarity
                    "image_ids": _parse_ids(doc.metadata or {}),
                }
                for doc, score in results
            ]
        else:
            # Keyword-based search using Chroma's built-in query
            collection = client.get_collection(col_name)
            results = collection.query(query_texts=[query], n_results=top_k)
            items = []
            if results["documents"] and results["documents"][0]:
                for i, doc_text in enumerate(results["documents"][0]):
                    metadata = results["metadatas"][0][i] if results["metadatas"] else {}
                    distance = results["distances"][0][i] if results["distances"] else 1.0
                    items.append({
                        "text": doc_text,
                        "doc_id": metadata.get("doc_id", ""),
                        "chunk_idx": metadata.get("chunk_idx", 0),
                        "score": round(float(1.0 / (1.0 + distance)), 4),
                        "image_ids": _parse_ids(metadata),
                    })
            return items

    return await asyncio.to_thread(_chroma_search)


async def delete_document_chunks(doc_id: str, db: AsyncSession) -> None:
    """Delete document chunks from both Chroma and SQLite."""
    # Find kb_id for this doc
    result = await db.execute(
        select(DocumentChunk.kb_id).where(DocumentChunk.doc_id == doc_id).limit(1)
    )
    kb_id = result.scalar_one_or_none()

    if kb_id:
        col_name = _collection_name(kb_id)

        def _chroma_delete():
            try:
                client = get_chroma_client()
                collection = client.get_collection(col_name)
                existing = collection.get(where={"doc_id": doc_id})
                if existing["ids"]:
                    collection.delete(ids=existing["ids"])
            except Exception:
                pass

        await asyncio.to_thread(_chroma_delete)

    await db.execute(delete(DocumentChunk).where(DocumentChunk.doc_id == doc_id))
    await db.commit()


def delete_collection(kb_id: str) -> None:
    """Delete the entire Chroma collection for a knowledge base."""
    try:
        client = get_chroma_client()
        client.delete_collection(_collection_name(kb_id))
    except Exception:
        pass


async def index_document_with_images(
    doc_id: str,
    kb_id: str,
    chunks: List[str],
    image_metas: List[Dict[str, Any]],
    db: AsyncSession,
    kb=None,
    embed_provider=None,
    chunk_image_ids: Optional[List[List[str]]] = None,
) -> int:
    """Index document chunks and persist image metadata."""
    # Store image metadata in SQLite — replace existing rows for this doc.
    await db.execute(delete(DocumentImage).where(DocumentImage.doc_id == doc_id))
    seen_ids: set = set()
    for meta in image_metas:
        img_id = meta["id"]
        if img_id in seen_ids:
            continue  # avoid PK collisions if a description hash repeats
        seen_ids.add(img_id)
        img = DocumentImage(
            id=img_id,
            doc_id=meta["doc_id"],
            kb_id=meta["kb_id"],
            seq_num=meta.get("seq_num", 0),
            page_num=meta.get("page_num", 0),
            description=meta.get("description", ""),
            local_path=meta.get("local_path"),
            source_doc=meta.get("source_doc", ""),
        )
        db.add(img)
    await db.commit()

    # Index chunks (with image_ids tracking)
    return await index_document(
        doc_id,
        kb_id,
        chunks,
        db,
        kb=kb,
        embed_provider=embed_provider,
        chunk_image_ids=chunk_image_ids,
    )


async def get_document_images(doc_ids: List[str], db: AsyncSession) -> Dict[str, Dict[str, Any]]:
    """Return a mapping of image_id → image metadata for a list of doc_ids."""
    if not doc_ids:
        return {}
    result = await db.execute(
        select(DocumentImage).where(DocumentImage.doc_id.in_(doc_ids))
    )
    images = result.scalars().all()
    return {
        img.id: {
            "id": img.id,
            "description": img.description,
            "local_path": img.local_path,
            "source_doc": img.source_doc,
            "page_num": img.page_num,
        }
        for img in images
    }


async def delete_document_images(doc_id: str, db: AsyncSession) -> None:
    """Delete document images from SQLite and from the local filesystem."""
    result = await db.execute(
        select(DocumentImage).where(DocumentImage.doc_id == doc_id)
    )
    for img in result.scalars().all():
        if img.local_path and __import__("os").path.exists(img.local_path):
            try:
                __import__("os").remove(img.local_path)
            except Exception:
                pass
    await db.execute(delete(DocumentImage).where(DocumentImage.doc_id == doc_id))
    await db.commit()
