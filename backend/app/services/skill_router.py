"""
Skill 路由器 — 按 DB 中 trigger_keywords + 优先级进行意图分类
"""
import json
from typing import List, Dict, Any

_DEFAULT_RAG_KW = [
    "怎么", "如何", "什么是", "查询", "查找", "知识", "文档",
    "how", "what", "why", "查一下", "介绍", "说明", "解释", "告诉我",
]

_DEFAULT_MCP_KW = [
    "执行", "运行", "启动", "run", "execute", "runbook",
    "日志分析", "analyze", "脚本", "script", "部署", "重启",
    "检查", "扫描", "诊断", "repair", "fix", "kubectl", "helm",
]


def _load_keywords(kw_json: str) -> List[str]:
    try:
        kws = json.loads(kw_json)
        if isinstance(kws, list):
            return [str(k).lower() for k in kws if k]
    except Exception:
        pass
    return []


def route(message: str, active_skills: List[Any]) -> Dict[str, Any]:
    """
    路由结果: {"type": "mcp"|"rag"|"chat", "skill_name": str, "skill": obj|None}
    """
    msg_lower = message.lower()

    sorted_skills = sorted(
        [s for s in active_skills if s.is_active],
        key=lambda s: getattr(s, "priority", 100),
    )

    # MCP 优先检测
    for skill in sorted_skills:
        if getattr(skill, "skill_type", "") != "mcp":
            continue
        keywords = _load_keywords(getattr(skill, "trigger_keywords", "[]")) or _DEFAULT_MCP_KW
        if any(kw in msg_lower for kw in keywords):
            return {"type": "mcp", "skill_name": skill.name, "skill": skill}

    # RAG 检测
    for skill in sorted_skills:
        if getattr(skill, "skill_type", "") != "rag":
            continue
        keywords = _load_keywords(getattr(skill, "trigger_keywords", "[]")) or _DEFAULT_RAG_KW
        if any(kw in msg_lower for kw in keywords):
            return {"type": "rag", "skill_name": skill.name, "skill": skill}

    # 兜底关键词
    if any(kw in msg_lower for kw in _DEFAULT_MCP_KW):
        mcp_skill = next((s for s in sorted_skills if s.skill_type == "mcp"), None)
        if mcp_skill:
            return {"type": "mcp", "skill_name": mcp_skill.name, "skill": mcp_skill}

    if any(kw in msg_lower for kw in _DEFAULT_RAG_KW):
        rag_skill = next((s for s in sorted_skills if s.skill_type == "rag"), None)
        if rag_skill:
            return {"type": "rag", "skill_name": rag_skill.name, "skill": rag_skill}

    return {"type": "chat", "skill_name": "direct_chat", "skill": None}
