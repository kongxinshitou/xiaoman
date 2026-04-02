from pydantic import BaseModel, model_validator
from typing import Optional, List, Any
from datetime import datetime


class KnowledgeBaseCreate(BaseModel):
    name: str
    description: Optional[str] = None
    embed_model: str = "text-embedding-3-small"
    embed_api_key: Optional[str] = None
    embed_base_url: Optional[str] = None
    embed_provider_id: Optional[str] = None
    ocr_provider_id: Optional[str] = None
    chunk_size: int = 500
    chunk_overlap: int = 50
    top_k: int = 5


class KnowledgeBaseUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    embed_model: Optional[str] = None
    embed_api_key: Optional[str] = None
    embed_base_url: Optional[str] = None
    embed_provider_id: Optional[str] = None
    ocr_provider_id: Optional[str] = None
    chunk_size: Optional[int] = None
    chunk_overlap: Optional[int] = None
    top_k: Optional[int] = None


class KnowledgeBaseRead(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    owner_id: str
    embed_model: str
    embed_base_url: Optional[str] = None
    has_embed_key: bool = False
    embed_provider_id: Optional[str] = None
    ocr_provider_id: Optional[str] = None
    milvus_collection: Optional[str] = None
    chunk_size: int = 500
    chunk_overlap: int = 50
    top_k: int = 5
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @model_validator(mode="before")
    @classmethod
    def compute_has_embed_key(cls, data: Any) -> Any:
        if hasattr(data, "__dict__"):
            # SQLAlchemy model
            val = getattr(data, "embed_api_key_encrypted", None)
            embed_provider = getattr(data, "embed_provider_id", None)
            data.__dict__["has_embed_key"] = bool(val) or bool(embed_provider)
        elif isinstance(data, dict):
            data["has_embed_key"] = bool(data.get("embed_api_key_encrypted")) or bool(data.get("embed_provider_id"))
        return data


class SearchResult(BaseModel):
    chunk_text: str
    score: float
    doc_id: str
    chunk_idx: int
    document_name: Optional[str] = None


class DocumentRead(BaseModel):
    id: str
    kb_id: str
    filename: str
    file_type: str
    file_size: int
    status: str
    chunk_count: int
    error_msg: Optional[str] = None
    uploaded_by: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
