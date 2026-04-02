from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class DCInspectionCreate(BaseModel):
    datacenter: str  # 机房名称
    cabinet: Optional[str] = None  # 机柜号
    u_position: Optional[str] = None  # U位置
    device_id: Optional[int] = None  # 关联设备ID
    inspector: str  # 巡检人
    severity: str  # 严重程度：严重/一般/轻微
    issue: str  # 问题描述
    status: str = "待处理"  # 状态
    remark: Optional[str] = None  # 备注
    found_at: Optional[datetime] = None  # 发现时间


class DCInspectionUpdate(BaseModel):
    cabinet: Optional[str] = None
    u_position: Optional[str] = None
    device_id: Optional[int] = None
    inspector: Optional[str] = None
    severity: Optional[str] = None
    issue: Optional[str] = None
    status: Optional[str] = None
    remark: Optional[str] = None


class DCInspectionRead(BaseModel):
    id: int
    datacenter: str
    cabinet: Optional[str] = None
    u_position: Optional[str] = None
    device_id: Optional[int] = None
    inspector: str
    severity: str
    issue: str
    status: str
    remark: Optional[str] = None
    found_at: datetime
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class IssueStatusStats(BaseModel):
    """问题状态统计"""
    total: int = 0
    pending: int = 0  # 待处理
    processing: int = 0  # 处理中
    resolved: int = 0  # 已解决


class SeverityStats(BaseModel):
    """严重程度统计"""
    severe: int = 0  # 严重
    normal: int = 0  # 一般
    minor: int = 0  # 轻微


class DatacenterStats(BaseModel):
    """各机房统计"""
    datacenter: str
    total: int = 0
    severe: int = 0
    normal: int = 0
    minor: int = 0


class IssueStatusResponse(BaseModel):
    """问题状态统计响应"""
    overall: IssueStatusStats
    by_datacenter: List[DatacenterStats]
    by_severity: SeverityStats
