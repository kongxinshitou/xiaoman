import json
from typing import List
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.mcp_tool import MCPTool
from app.schemas.mcp_tool import MCPToolCreate, MCPToolUpdate, MCPToolRead
from app.services.mcp_service import ping_tool, execute_tool_stream, discover_tools

router = APIRouter()


class ExecuteRequest(BaseModel):
    params: dict = {}
    query: str = ""


class DiscoverRequest(BaseModel):
    server_url: str
    transport: str = "sse"
    timeout_secs: int = 15


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


@router.post("/discover")
async def discover_mcp_tools(
    body: DiscoverRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """连接 MCP 服务器，自动发现工具并保存到数据库"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    try:
        tools = await discover_tools(body.server_url, body.transport, body.timeout_secs)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"无法连接 MCP 服务器: {str(e)}")

    saved = []
    for tool_def in tools:
        name = tool_def.get("name", "")
        if not name:
            continue
        # Skip if tool already exists with same name and server_url
        existing = await db.execute(
            select(MCPTool).where(MCPTool.name == name, MCPTool.server_url == body.server_url)
        )
        input_schema = tool_def.get("inputSchema") or {}
        description = tool_def.get("description") or ""
        if existing.scalar_one_or_none():
            # Update existing tool schema
            existing_tool = (await db.execute(
                select(MCPTool).where(MCPTool.name == name, MCPTool.server_url == body.server_url)
            )).scalar_one()
            existing_tool.description = description
            existing_tool.tool_schema = json.dumps(input_schema)
            existing_tool.updated_at = datetime.now(timezone.utc)
            saved.append(name)
            continue
        mcp_tool = MCPTool(
            name=name,
            display_name=name,  # tool name as display_name; description stored separately
            description=description,
            server_url=body.server_url,
            transport=body.transport,
            tool_schema=json.dumps(input_schema),
            timeout_secs=body.timeout_secs,
        )
        db.add(mcp_tool)
        saved.append(name)
    await db.commit()

    return {
        "discovered": len(tools),
        "saved": len(saved),
        "tools": [{"name": t.get("name"), "description": t.get("description", "")} for t in tools],
    }


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


@router.post("/{tool_id}/execute")
async def execute_mcp_tool(
    tool_id: str,
    body: ExecuteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """SSE 流式执行 MCP 工具，可在设置页面直接测试"""
    result = await db.execute(select(MCPTool).where(MCPTool.id == tool_id))
    tool = result.scalar_one_or_none()
    if not tool:
        raise HTTPException(status_code=404, detail="工具不存在")

    params = body.params
    if body.query and not params:
        params = {"query": body.query}

    async def event_generator():
        async for event in execute_tool_stream(tool, params):
            yield f"event: tool_status\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"
        yield "event: done\ndata: {}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
