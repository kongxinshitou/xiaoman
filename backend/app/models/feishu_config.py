import uuid
from sqlalchemy import String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime, timezone
from app.database import Base


class FeishuConfig(Base):
    __tablename__ = "feishu_config"

    singleton_id: Mapped[str] = mapped_column(String(20), primary_key=True, default="default")
    app_id: Mapped[str] = mapped_column(String(100), nullable=True)
    encrypted_app_secret: Mapped[str] = mapped_column(String(500), nullable=True)
    verify_token: Mapped[str] = mapped_column(String(200), nullable=True)
    encrypted_encrypt_key: Mapped[str] = mapped_column(String(500), nullable=True)
    bot_open_id: Mapped[str] = mapped_column(String(100), nullable=True)
    default_push_chat_id: Mapped[str] = mapped_column(String(100), nullable=True)
    connection_mode: Mapped[str] = mapped_column(String(20), default="webhook")  # webhook | websocket | both
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class FeishuUserMapping(Base):
    """Maps Feishu open_id to an internal User record."""
    __tablename__ = "feishu_user_mappings"

    open_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    internal_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class FeishuChatMapping(Base):
    """Maps Feishu chat_id to a ChatSession for conversation continuity."""
    __tablename__ = "feishu_chat_mappings"

    feishu_chat_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("chat_sessions.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
