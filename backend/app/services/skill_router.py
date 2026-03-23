from typing import List, Dict, Any

RAG_KEYWORDS = [
    "怎么", "如何", "什么是", "查询", "查找", "知识", "文档",
    "how", "what", "why", "查一下", "介绍", "说明", "解释",
]

MCP_KEYWORDS = [
    "执行", "运行", "启动", "run", "execute", "runbook",
    "日志分析", "analyze", "脚本", "script", "部署", "重启",
]


def route(message: str, active_skills: List[Any]) -> Dict[str, str]:
    msg_lower = message.lower()

    has_rag = any(kw in msg_lower for kw in RAG_KEYWORDS)
    has_mcp = any(kw in msg_lower for kw in MCP_KEYWORDS)

    # MCP takes priority if both match
    if has_mcp:
        mcp_skill = next(
            (s for s in active_skills if getattr(s, "skill_type", "") == "mcp" and s.is_active),
            None,
        )
        if mcp_skill:
            return {"type": "mcp", "skill_name": mcp_skill.name}

    if has_rag:
        rag_skill = next(
            (s for s in active_skills if getattr(s, "skill_type", "") == "rag" and s.is_active),
            None,
        )
        if rag_skill:
            return {"type": "rag", "skill_name": rag_skill.name}

    return {"type": "chat", "skill_name": "direct_chat"}
