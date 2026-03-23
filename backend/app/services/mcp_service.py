from typing import AsyncGenerator, Dict, Any
import httpx
import json
from app.models.mcp_tool import MCPTool


async def execute_tool(
    tool: MCPTool,
    params: Dict[str, Any],
) -> AsyncGenerator[str, None]:
    yield f"[MCP] 正在连接工具: {tool.display_name or tool.name}\n"
    yield f"[MCP] 服务器: {tool.server_url}\n"
    yield f"[MCP] 参数: {json.dumps(params, ensure_ascii=False)}\n"

    try:
        async with httpx.AsyncClient(timeout=tool.timeout_secs) as client:
            payload = {
                "tool": tool.name,
                "params": params,
            }
            response = await client.post(
                tool.server_url,
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            result = response.json()
            yield f"[MCP] 执行结果:\n{json.dumps(result, ensure_ascii=False, indent=2)}\n"
    except httpx.ConnectError:
        yield f"[MCP错误] 无法连接到工具服务器: {tool.server_url}\n"
    except httpx.TimeoutException:
        yield f"[MCP错误] 连接超时 ({tool.timeout_secs}s)\n"
    except Exception as e:
        yield f"[MCP错误] {str(e)}\n"


async def ping_tool(tool: MCPTool) -> bool:
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(tool.server_url)
            return response.status_code < 500
    except Exception:
        return False
