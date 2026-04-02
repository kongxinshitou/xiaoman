import asyncio
import json
import logging
from typing import List, Dict, Any, Optional, TYPE_CHECKING

import chromadb
from langchain_community.vectorstores import Chroma
from langchain_core.embeddings import Embeddings

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.models.knowledge import DocumentChunk, Document
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

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        import litellm
        kwargs: Dict[str, Any] = {
            "model": self.model,
            "input": texts,
            "api_key": self.api_key,
        }
        if self.api_base:
            kwargs["api_base"] = self.api_base
        resp = litellm.embedding(**kwargs)
        return [item["embedding"] for item in resp.data]

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
) -> int:
    """Index document chunks into ChromaDB and SQLite."""
    col_name = _collection_name(kb_id)

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

    # Add to Chroma
    ids = [f"{doc_id}_{i}" for i in range(len(chunks))]
    metadatas = [{"doc_id": doc_id, "kb_id": kb_id, "chunk_idx": i} for i in range(len(chunks))]

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

    # Update SQLite DocumentChunk (without embedding column)
    await db.execute(delete(DocumentChunk).where(DocumentChunk.doc_id == doc_id))
    for idx, chunk_text in enumerate(chunks):
        chunk = DocumentChunk(
            doc_id=doc_id,
            kb_id=kb_id,
            chunk_text=chunk_text,
            chunk_idx=idx,
            embedding=None,
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
