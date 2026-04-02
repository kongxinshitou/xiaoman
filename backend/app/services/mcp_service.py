"""
MCP 工具服务 — 基于官方 MCP Python SDK
使用与 Cline 相同的 mcp.client.sse.sse_client + mcp.ClientSession
"""
import json
import logging
from typing import AsyncGenerator, Dict, Any, Optional, List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.mcp_tool import MCPTool

logger = logging.getLogger(__name__)


def _schema_to_dict(schema) -> dict:
    """将 MCP SDK 返回的 schema 对象转为普通 dict。"""
    if schema is None:
        return {}
    if isinstance(schema, dict):
        return schema
    # Pydantic model or similar
    try:
        return schema.model_dump()
    except AttributeError:
        pass
    try:
        return dict(schema)
    except Exception:
        return {}


# ─────────────────── 工具发现 ───────────────────

async def discover_tools(
    server_url: str,
    transport: str = "sse",
    timeout: int = 30,
) -> List[Dict[str, Any]]:
    """连接 MCP 服务器，调用 tools/list，返回完整工具列表（含 inputSchema）。"""
    if transport == "sse":
        return await _discover_sse(server_url, timeout)
    else:
        return await _discover_http(server_url, timeout)


async def _discover_sse(server_url: str, timeout: int) -> List[Dict[str, Any]]:
    from mcp import ClientSession
    from mcp.client.sse import sse_client

    async with sse_client(server_url, timeout=10, sse_read_timeout=float(timeout)) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.list_tools()
            tools = []
            for t in result.tools:
                tools.append({
                    "name": t.name,
                    "description": t.description or "",
                    "inputSchema": _schema_to_dict(t.inputSchema),
                })
            logger.info("MCP 发现 %d 个工具 from %s", len(tools), server_url)
            return tools


async def _discover_http(server_url: str, timeout: int) -> List[Dict[str, Any]]:
    import httpx
    async with httpx.AsyncClient(timeout=float(timeout)) as client:
        await client.post(server_url, json={
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                       "clientInfo": {"name": "xiaoman", "version": "1.0"}},
        })
        resp = await client.post(server_url, json={
            "jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {},
        })
        resp.raise_for_status()
        raw = resp.json().get("result", {}).get("tools", [])
        return [
            {
                "name": t.get("name", ""),
                "description": t.get("description", ""),
                "inputSchema": t.get("inputSchema") or {},
            }
            for t in raw
        ]


# ─────────────────── 工具执行 ───────────────────

async def execute_tool_stream(
    tool: MCPTool,
    params: Dict[str, Any],
) -> AsyncGenerator[Dict[str, Any], None]:
    yield {"status": "connecting", "output": f"正在连接: {tool.server_url}"}
    if tool.transport == "sse":
        async for event in _execute_sse(tool, params):
            yield event
    else:
        async for event in _execute_http(tool, params):
            yield event


async def _execute_sse(
    tool: MCPTool,
    params: Dict[str, Any],
) -> AsyncGenerator[Dict[str, Any], None]:
    from mcp import ClientSession
    from mcp.client.sse import sse_client
    from mcp.types import TextContent

    try:
        yield {"status": "running", "output": "建立 MCP SSE 连接..."}
        async with sse_client(tool.server_url, timeout=10, sse_read_timeout=float(tool.timeout_secs)) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                yield {"status": "running", "output": f"调用工具 {tool.name}..."}
                result = await session.call_tool(tool.name, params)
                texts = [
                    c.text for c in result.content
                    if isinstance(c, TextContent)
                ]
                output = "\n".join(texts) if texts else json.dumps(
                    [c.model_dump() if hasattr(c, "model_dump") else str(c) for c in result.content],
                    ensure_ascii=False
                )
                is_error = getattr(result, "isError", False)
                yield {"status": "error" if is_error else "done", "output": output}
    except Exception as e:
        logger.exception("SSE 执行异常 tool=%s", tool.name)
        yield {"status": "error", "output": f"执行异常: {e}"}


async def _execute_http(
    tool: MCPTool,
    params: Dict[str, Any],
) -> AsyncGenerator[Dict[str, Any], None]:
    import httpx

    try:
        async with httpx.AsyncClient(timeout=float(tool.timeout_secs)) as client:
            yield {"status": "running", "output": f"发送请求到 {tool.server_url}..."}
            resp = await client.post(tool.server_url, json={
                "jsonrpc": "2.0", "id": 1, "method": "tools/call",
                "params": {"name": tool.name, "arguments": params},
            }, headers={"Content-Type": "application/json"})
            resp.raise_for_status()
            data = resp.json()
            if "result" in data:
                result = data["result"]
                content = result.get("content", [])
                if isinstance(content, list):
                    texts = [item.get("text", "") for item in content
                             if isinstance(item, dict) and item.get("type") == "text"]
                    output = "\n".join(texts) if texts else json.dumps(result, ensure_ascii=False)
                else:
                    output = json.dumps(result, ensure_ascii=False)
            elif "error" in data:
                err = data["error"]
                output = f"工具错误: {err.get('message', str(err)) if isinstance(err, dict) else str(err)}"
                yield {"status": "error", "output": output}
                return
            else:
                output = json.dumps(data, ensure_ascii=False)
            yield {"status": "done", "output": output}
    except httpx.ConnectError:
        yield {"status": "error", "output": f"无法连接: {tool.server_url}"}
    except httpx.TimeoutException:
        yield {"status": "error", "output": f"超时 ({tool.timeout_secs}s)"}
    except Exception as e:
        logger.exception("HTTP 执行异常 tool=%s", tool.name)
        yield {"status": "error", "output": f"异常: {e}"}


# ─────────────────── Ping ───────────────────

async def ping_tool(tool: MCPTool) -> bool:
    try:
        if tool.transport == "sse":
            from mcp import ClientSession
            from mcp.client.sse import sse_client
            async with sse_client(tool.server_url, timeout=5) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    return True
        else:
            import httpx
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(tool.server_url, json={
                    "jsonrpc": "2.0", "id": 1, "method": "initialize",
                    "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                               "clientInfo": {"name": "xiaoman-ping", "version": "1.0"}},
                })
                return resp.status_code < 500
    except Exception:
        return False


# ─────────────────── 工具查找 & 参数提取 ───────────────────

async def find_tool_for_skill(skill_config: str, db: AsyncSession) -> Optional[MCPTool]:
    try:
        config = json.loads(skill_config)
        tool_name = config.get("tool_name")
        if tool_name:
            result = await db.execute(
                select(MCPTool).where(MCPTool.name == tool_name, MCPTool.is_active == True)
            )
            return result.scalar_one_or_none()
    except Exception:
        pass
    result = await db.execute(select(MCPTool).where(MCPTool.is_active == True).limit(1))
    return result.scalar_one_or_none()


async def extract_params_from_message(message: str, tool_schema: str) -> Dict[str, Any]:
    try:
        schema = json.loads(tool_schema)
        props = schema.get("properties", {})
    except Exception:
        props = {}
    for key in props:
        if key in ("query", "input", "message", "text", "content", "command"):
            return {key: message}
    return {"query": message}
