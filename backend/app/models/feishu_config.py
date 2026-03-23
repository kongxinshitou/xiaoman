import uuid
from sqlalchemy import String, Boolean, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime, timezone
from app.database import Base


class FeishuConfig(Base):
    __tablename__ = "feishu_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    app_id: Mapped[str] = mapped_column(String(100), default="")
    encrypted_app_secret: Mapped[str] = mapped_column(Text, default="")
    verify_token: Mapped[str] = mapped_column(String(200), default="")
    encrypt_key: Mapped[str] = mapped_column(String(200), default="")
    # Push targets: comma-separated chat_ids or open_ids
    default_push_chat_id: Mapped[str] = mapped_column(String(500), default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
