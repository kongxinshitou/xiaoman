from typing import List
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.mcp_tool import MCPTool
from app.schemas.mcp_tool import MCPToolCreate, MCPToolUpdate, MCPToolRead
from app.services.mcp_service import ping_tool

router = APIRouter()


@router.post("", response_model=MCPToolRead)
async def create_tool(
    payload: MCPToolCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    existing = await db.execute(select(MCPTool).where(MCPTool.name == payload.name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="工具名称已存在")
    tool = MCPTool(**payload.model_dump())
    db.add(tool)
    await db.commit()
    await db.refresh(tool)
    return tool


@router.get("", response_model=List[MCPToolRead])
async def list_tools(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(MCPTool).order_by(MCPTool.created_at.desc()))
    return result.scalars().all()


@router.get("/{tool_id}", response_model=MCPToolRead)
async def get_tool(
    tool_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(MCPTool).where(MCPTool.id == tool_id))
    tool = result.scalar_one_or_none()
    if not tool:
        raise HTTPException(status_code=404, detail="工具不存在")
    return tool


@router.patch("/{tool_id}", response_model=MCPToolRead)
async def update_tool(
    tool_id: str,
    payload: MCPToolUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    result = await db.execute(select(MCPTool).where(MCPTool.id == tool_id))
    tool = result.scalar_one_or_none()
    if not tool:
        raise HTTPException(status_code=404, detail="工具不存在")
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(tool, field, value)
    tool.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(tool)
    return tool


@router.delete("/{tool_id}")
async def delete_tool(
    tool_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    result = await db.execute(select(MCPTool).where(MCPTool.id == tool_id))
    tool = result.scalar_one_or_none()
    if not tool:
        raise HTTPException(status_code=404, detail="工具不存在")
    await db.delete(tool)
    await db.commit()
    return {"message": "工具已删除"}


@router.post("/{tool_id}/ping")
async def ping_mcp_tool(
    tool_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(MCPTool).where(MCPTool.id == tool_id))
    tool = result.scalar_one_or_none()
    if not tool:
        raise HTTPException(status_code=404, detail="工具不存在")
    alive = await ping_tool(tool)
    return {"status": "online" if alive else "offline"}
