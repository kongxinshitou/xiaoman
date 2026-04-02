from typing import List, Optional
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.dc_inspection import DCInspection
from app.schemas.dc_inspection import (
    DCInspectionCreate, DCInspectionUpdate, DCInspectionRead,
    IssueStatusResponse, IssueStatusStats, SeverityStats, DatacenterStats,
)

router = APIRouter()


@router.post("", response_model=DCInspectionRead)
async def create_inspection(
    payload: DCInspectionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建巡检记录"""
    found_at = payload.found_at if payload.found_at else datetime.now(timezone.utc)
    
    inspection = DCInspection(
        datacenter=payload.datacenter,
        cabinet=payload.cabinet,
        u_position=payload.u_position,
        device_id=payload.device_id,
        inspector=payload.inspector,
        severity=payload.severity,
        issue=payload.issue,
        status=payload.status,
        remark=payload.remark,
        found_at=found_at,
    )
    db.add(inspection)
    await db.commit()
    await db.refresh(inspection)
    return inspection


@router.post("/batch", response_model=List[DCInspectionRead])
async def create_inspections_batch(
    payloads: List[DCInspectionCreate],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """批量创建巡检记录"""
    inspections = []
    now = datetime.now(timezone.utc)
    
    for payload in payloads:
        found_at = payload.found_at if payload.found_at else now
        inspection = DCInspection(
            datacenter=payload.datacenter,
            cabinet=payload.cabinet,
            u_position=payload.u_position,
            device_id=payload.device_id,
            inspector=payload.inspector,
            severity=payload.severity,
            issue=payload.issue,
            status=payload.status,
            remark=payload.remark,
            found_at=found_at,
        )
        inspections.append(inspection)
    
    db.add_all(inspections)
    await db.commit()
    
    # Refresh all to get IDs
    for inspection in inspections:
        await db.refresh(inspection)
    
    return inspections


@router.get("", response_model=List[DCInspectionRead])
async def list_inspections(
    datacenter: Optional[str] = Query(None, description="机房名称"),
    cabinet: Optional[str] = Query(None, description="机柜号"),
    inspector: Optional[str] = Query(None, description="巡检人"),
    severity: Optional[str] = Query(None, description="问题等级"),
    status: Optional[str] = Query(None, description="状态"),
    start_time: Optional[str] = Query(None, description="开始时间 YYYY-MM-DD"),
    end_time: Optional[str] = Query(None, description="结束时间 YYYY-MM-DD"),
    keyword: Optional[str] = Query(None, description="关键字搜索"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """查询巡检记录"""
    query = select(DCInspection)
    
    # Filters
    if datacenter:
        query = query.where(DCInspection.datacenter == datacenter)
    if cabinet:
        query = query.where(DCInspection.cabinet == cabinet)
    if inspector:
        query = query.where(DCInspection.inspector == inspector)
    if severity:
        query = query.where(DCInspection.severity == severity)
    if status:
        query = query.where(DCInspection.status == status)
    if start_time:
        start_dt = datetime.strptime(start_time, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        query = query.where(DCInspection.found_at >= start_dt)
    if end_time:
        end_dt = datetime.strptime(end_time, "%Y-%m-%d").replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
        query = query.where(DCInspection.found_at <= end_dt)
    if keyword:
        query = query.where(DCInspection.issue.contains(keyword))
    
    # Pagination
    offset = (page - 1) * page_size
    query = query.order_by(DCInspection.found_at.desc()).offset(offset).limit(page_size)
    
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/stats", response_model=IssueStatusResponse)
async def get_issue_status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取问题状态统计"""
    # Get all inspections
    result = await db.execute(select(DCInspection))
    inspections = result.scalars().all()
    
    # Overall stats
    total = len(inspections)
    pending = sum(1 for i in inspections if i.status == "待处理")
    processing = sum(1 for i in inspections if i.status == "处理中")
    resolved = sum(1 for i in inspections if i.status == "已解决")
    
    overall = IssueStatusStats(
        total=total,
        pending=pending,
        processing=processing,
        resolved=resolved
    )
    
    # Severity stats
    severe = sum(1 for i in inspections if i.severity == "严重")
    normal = sum(1 for i in inspections if i.severity == "一般")
    minor = sum(1 for i in inspections if i.severity == "轻微")
    
    by_severity = SeverityStats(severe=severe, normal=normal, minor=minor)
    
    # By datacenter stats
    datacenter_stats = {}
    for inspection in inspections:
        dc = inspection.datacenter
        if dc not in datacenter_stats:
            datacenter_stats[dc] = {"total": 0, "severe": 0, "normal": 0, "minor": 0}
        datacenter_stats[dc]["total"] += 1
        if inspection.severity == "严重":
            datacenter_stats[dc]["severe"] += 1
        elif inspection.severity == "一般":
            datacenter_stats[dc]["normal"] += 1
        elif inspection.severity == "轻微":
            datacenter_stats[dc]["minor"] += 1
    
    by_datacenter = [
        DatacenterStats(
            datacenter=dc,
            total=stats["total"],
            severe=stats["severe"],
            normal=stats["normal"],
            minor=stats["minor"]
        )
        for dc, stats in sorted(datacenter_stats.items())
    ]
    
    return IssueStatusResponse(
        overall=overall,
        by_datacenter=by_datacenter,
        by_severity=by_severity
    )


@router.get("/{inspection_id}", response_model=DCInspectionRead)
async def get_inspection(
    inspection_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取单条巡检记录"""
    result = await db.execute(
        select(DCInspection).where(DCInspection.id == inspection_id)
    )
    inspection = result.scalar_one_or_none()
    if not inspection:
        raise HTTPException(status_code=404, detail="巡检记录不存在")
    return inspection


@router.patch("/{inspection_id}", response_model=DCInspectionRead)
async def update_inspection(
    inspection_id: int,
    payload: DCInspectionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新巡检记录"""
    result = await db.execute(
        select(DCInspection).where(DCInspection.id == inspection_id)
    )
    inspection = result.scalar_one_or_none()
    if not inspection:
        raise HTTPException(status_code=404, detail="巡检记录不存在")
    
    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(inspection, field, value)
    
    inspection.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(inspection)
    return inspection


@router.delete("/{inspection_id}")
async def delete_inspection(
    inspection_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除巡检记录"""
    result = await db.execute(
        select(DCInspection).where(DCInspection.id == inspection_id)
    )
    inspection = result.scalar_one_or_none()
    if not inspection:
        raise HTTPException(status_code=404, detail="巡检记录不存在")
    
    await db.delete(inspection)
    await db.commit()
    return {"message": "巡检记录已删除"}
