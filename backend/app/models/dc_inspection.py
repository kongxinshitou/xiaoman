from typing import Optional
from sqlalchemy import String, Text, DateTime, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime, timezone
from app.database import Base


class DCInspection(Base):
    __tablename__ = "dc_inspections"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    datacenter: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # 机房名称，如 IDC1-1
    cabinet: Mapped[str] = mapped_column(String(20), nullable=True, index=True)  # 机柜号，如 A-01
    u_position: Mapped[str] = mapped_column(String(20), nullable=True)  # U位置，如 01U, 03-10U
    device_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("dc_devices.id"), nullable=True)  # 关联设备ID
    inspector: Mapped[str] = mapped_column(String(100), nullable=False)  # 巡检人
    severity: Mapped[str] = mapped_column(String(20), nullable=False)  # 严重程度：严重/一般/轻微
    issue: Mapped[str] = mapped_column(Text, nullable=False)  # 问题描述
    status: Mapped[str] = mapped_column(String(20), default="待处理")  # 状态：待处理/处理中/已解决
    remark: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 备注
    found_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))  # 发现时间
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=True)
