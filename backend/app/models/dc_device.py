import uuid
from typing import Optional
from sqlalchemy import String, Text, DateTime, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime, timezone
from app.database import Base


class DCDevice(Base):
    __tablename__ = "dc_devices"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    datacenter: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # 机房名称，如 IDC1-1
    cabinet: Mapped[str] = mapped_column(String(20), nullable=False, index=True)  # 机柜号，如 A-01
    u_position: Mapped[str] = mapped_column(String(20), nullable=True)  # U位置，如 01U, 03-10U
    device_type: Mapped[str] = mapped_column(String(50), nullable=True)  # 设备类型
    brand: Mapped[str] = mapped_column(String(100), nullable=True)  # 品牌
    model: Mapped[str] = mapped_column(String(100), nullable=True)  # 型号
    serial_number: Mapped[str] = mapped_column(String(100), nullable=True)  # 序列号
    ip_address: Mapped[str] = mapped_column(String(50), nullable=True)  # IP地址
    mgmt_ip: Mapped[str] = mapped_column(String(50), nullable=True)  # 远程管理IP
    os: Mapped[str] = mapped_column(String(100), nullable=True)  # 操作系统
    status: Mapped[str] = mapped_column(String(20), default="Online")  # 状态
    purpose: Mapped[str] = mapped_column(String(255), nullable=True)  # 设备用途
    owner: Mapped[str] = mapped_column(String(100), nullable=True)  # 责任人
    source: Mapped[str] = mapped_column(String(100), nullable=True)  # 来源区域
    remark: Mapped[str] = mapped_column(Text, nullable=True)  # 备注
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=True)
