"""
MCP 工具服务
- 支持 HTTP/SSE 两种传输模式
- 流式输出执行状态
- 自动超时与错误处理
"""
import json
import logging
from typing import AsyncGenerator, Dict, Any, Optional

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.mcp_tool import MCPTool

logger = logging.getLogger(__name__)


# ─────────────────────────── SSE 流式执行 ───────────────────────────

async def execute_tool_stream(
    tool: MCPTool,
    params: Dict[str, Any],
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    执行 MCP 工具，以字典 yield 状态事件：
      {"status": "connecting" | "running" | "done" | "error", "output": str}
    """
    yield {"status": "connecting", "output": f"正在连接工具服务器: {tool.server_url}"}

    if tool.transport == "sse":
        async for event in _execute_sse(tool, params):
            yield event
    else:
        async for event in _execute_http(tool, params):
            yield event


async def _execute_http(
    tool: MCPTool,
    params: Dict[str, Any],
) -> AsyncGenerator[Dict[str, Any], None]:
    """HTTP POST 模式执行（JSON-RPC 2.0）"""
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": tool.name,
            "arguments": params,
        },
    }
    try:
        async with httpx.AsyncClient(timeout=tool.timeout_secs) as client:
            yield {"status": "running", "output": f"发送请求到 {tool.server_url}..."}
            response = await client.post(
                tool.server_url,
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            data = response.json()

            if "result" in data:
                result = data["result"]
                if isinstance(result, dict):
                    content = result.get("content", [])
                    if isinstance(content, list):
                        output = "\n".join(
                            item.get("text", "") for item in content
                            if item.get("type") == "text"
                        )
                    else:
                        output = json.dumps(result, ensure_ascii=False, indent=2)
                else:
                    output = json.dumps(result, ensure_ascii=False, indent=2)
                yield {"status": "done", "output": output}
            elif "error" in data:
                yield {"status": "error", "output": f"工具返回错误: {data['error'].get('message', '未知错误')}"}
            else:
                yield {"status": "done", "output": json.dumps(data, ensure_ascii=False, indent=2)}

    except httpx.ConnectError:
        yield {"status": "error", "output": f"无法连接到工具服务器: {tool.server_url}\n\n请确认 MCP 工具服务已启动。"}
    except httpx.TimeoutException:
        yield {"status": "error", "output": f"连接超时（{tool.timeout_secs}s）"}
    except httpx.HTTPStatusError as e:
        yield {"status": "error", "output": f"HTTP 错误 {e.response.status_code}: {e.response.text[:200]}"}
    except Exception as e:
        logger.exception("MCP HTTP 执行异常")
        yield {"status": "error", "output": f"执行异常: {str(e)}"}


async def _execute_sse(
    tool: MCPTool,
    params: Dict[str, Any],
) -> AsyncGenerator[Dict[str, Any], None]:
    """SSE 流式模式"""
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": tool.name, "arguments": params},
    }
    try:
        async with httpx.AsyncClient(timeout=tool.timeout_secs) as client:
            yield {"status": "running", "output": "建立 SSE 连接中..."}
            output_buf = []
            async with client.stream(
                "POST",
                tool.server_url,
                json=payload,
                headers={"Content-Type": "application/json", "Accept": "text/event-stream"},
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if line.startswith("data:"):
                        data_str = line[5:].strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data_str)
                            text = chunk.get("output") or chunk.get("text") or str(chunk)
                            output_buf.append(text)
                            yield {"status": "running", "output": text}
                        except json.JSONDecodeError:
                            output_buf.append(data_str)
                            yield {"status": "running", "output": data_str}
            yield {"status": "done", "output": "".join(output_buf) or "执行完成"}
    except httpx.ConnectError:
        yield {"status": "error", "output": f"无法连接 SSE 服务器: {tool.server_url}"}
    except httpx.TimeoutException:
        yield {"status": "error", "output": f"SSE 连接超时（{tool.timeout_secs}s）"}
    except Exception as e:
        logger.exception("SSE 执行异常")
        yield {"status": "error", "output": f"SSE 异常: {str(e)}"}


# ─────────────────────────── 工具查找 & 参数提取 ───────────────────────────

async def find_tool_for_skill(skill_config: str, db: AsyncSession) -> Optional[MCPTool]:
    """从技能配置 JSON 找到绑定的 MCP 工具；未指定时取第一个激活工具"""
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
    """从用户消息提取工具调用参数"""
    try:
        schema = json.loads(tool_schema)
        props = schema.get("properties", {})
    except Exception:
        props = {}
    params: Dict[str, Any] = {}
    for key in props:
        if key in ("query", "input", "message", "text", "content", "command"):
            params[key] = message
            break
    if not params:
        params["query"] = message
    return params


# ─────────────────────────── Ping ───────────────────────────

async def ping_tool(tool: MCPTool) -> bool:
    """检测 MCP 服务器是否在线"""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.post(
                tool.server_url,
                json={"jsonrpc": "2.0", "id": 0, "method": "initialize",
                      "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                                 "clientInfo": {"name": "xiaoman-ping", "version": "1.0"}}},
                headers={"Content-Type": "application/json"},
            )
            return resp.status_code < 500
    except Exception:
        try:
            async with httpx.AsyncClient(timeout=3) as client:
                resp = await client.get(tool.server_url)
                return resp.status_code < 500
        except Exception:
            return False
