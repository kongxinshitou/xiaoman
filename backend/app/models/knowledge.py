import uuid
from typing import Optional
from sqlalchemy import String, Text, Integer, BigInteger, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime, timezone
from app.database import Base



class KnowledgeBase(Base):
    __tablename__ = "knowledge_bases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    milvus_collection: Mapped[str] = mapped_column(String(255), nullable=True)
    embed_model: Mapped[str] = mapped_column(String(100), default="text2vec-base-chinese")
    embed_api_key_encrypted: Mapped[str] = mapped_column(Text, nullable=True)
    embed_base_url: Mapped[str] = mapped_column(String(500), nullable=True)
    embed_provider_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("embed_providers.id"), nullable=True)
    ocr_provider_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("ocr_providers.id"), nullable=True)
    chunk_size: Mapped[int] = mapped_column(Integer, default=500)
    chunk_overlap: Mapped[int] = mapped_column(Integer, default=50)
    top_k: Mapped[int] = mapped_column(Integer, default=5)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    kb_id: Mapped[str] = mapped_column(String(36), ForeignKey("knowledge_bases.id"), nullable=False)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    file_type: Mapped[str] = mapped_column(String(20), default="txt")
    file_size: Mapped[int] = mapped_column(BigInteger, default=0)
    file_path: Mapped[str] = mapped_column(String(1000), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    error_msg: Mapped[str] = mapped_column(Text, nullable=True)
    uploaded_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    doc_id: Mapped[str] = mapped_column(String(36), ForeignKey("documents.id"), nullable=False)
    kb_id: Mapped[str] = mapped_column(String(36), nullable=False)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_idx: Mapped[int] = mapped_column(Integer, default=0)
    embedding: Mapped[str] = mapped_column(Text, nullable=True)  # JSON float list
    image_ids: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON list of associated image IDs


class DocumentImage(Base):
    """Stores metadata for images extracted from documents."""
    __tablename__ = "document_images"

    id: Mapped[str] = mapped_column(String(150), primary_key=True)  # e.g. IMG_report_001_销售趋势图
    doc_id: Mapped[str] = mapped_column(String(36), ForeignKey("documents.id"), nullable=False)
    kb_id: Mapped[str] = mapped_column(String(36), nullable=False)
    seq_num: Mapped[int] = mapped_column(Integer, default=0)
    page_num: Mapped[int] = mapped_column(Integer, default=0)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    local_path: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    source_doc: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
