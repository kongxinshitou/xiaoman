"""End-to-end demo: build a UserCtx, run capability filtering, attempt tool calls.

This script does NOT call a real LLM — it simulates the chain so you can
inspect what the agent loop would see. Run after seed_demo.py:

    python -m scripts.example_agent --user alice_finance --query "查薪资"

Output shows: visible tools (post-filter), denial path, audit entries.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import select  # noqa: E402

from app.database import AsyncSessionLocal  # noqa: E402
from app.models.user import User  # noqa: E402
from app.core.permissions import audit, confirm  # noqa: E402
from app.core.permissions.gatekeeper import filter_capabilities  # noqa: E402
from app.core.permissions.policy import (  # noqa: E402
    UserCtx, can_access, deny_reason, requires_confirmation,
)


# Hardcoded "all" tools (mirrors what the LLM would otherwise see)
ALL_TOOLS = [
    {"type": "function", "function": {"name": "general_qa", "description": "通用问答"}},
    {"type": "function", "function": {"name": "schedule_query", "description": "日程查询"}},
    {"type": "function", "function": {"name": "crm_query", "description": "CRM 查询"}},
    {"type": "function", "function": {"name": "financial_report", "description": "财务报表"}},
    {"type": "function", "function": {"name": "salary_query", "description": "薪资查询"}},
    {"type": "function", "function": {"name": "delete_invoice", "description": "删除发票"}},
    {"type": "function", "function": {"name": "feishu_create_group", "description": "飞书建群"}},
]


def pick_tool_for_query(query: str) -> str:
    q = query.lower()
    if "薪资" in q or "salary" in q or "工资" in q:
        return "salary_query"
    if "删除" in q and ("发票" in q or "invoice" in q):
        return "delete_invoice"
    if "crm" in q or "客户" in q:
        return "crm_query"
    if "财务" in q or "报表" in q:
        return "financial_report"
    if "建群" in q or "群聊" in q:
        return "feishu_create_group"
    return "general_qa"


async def run(username: str, query: str) -> None:
    async with AsyncSessionLocal() as db:
        u = (
            await db.execute(select(User).where(User.username == username))
        ).scalar_one_or_none()
        if u is None:
            print(f"[error] user {username} not found. Run seed_demo first.")
            return
        ctx = UserCtx(user_id=u.id, role=u.role, dept=u.dept)
        print(f"[user] {u.username}  role={ctx.role}  dept={ctx.dept}\n")

        visible, _, _ = await filter_capabilities(db, ctx, ALL_TOOLS)
        names = [t["function"]["name"] for t in visible]
        print(f"[gatekeeper] visible tools ({len(names)}/{len(ALL_TOOLS)}): {names}\n")

        target = pick_tool_for_query(query)
        print(f"[router] query={query!r}  →  picked tool: {target}")

        if target not in names:
            reason = await deny_reason(db, ctx, target)
            audit.log(
                user_id=ctx.user_id, resource=target, action="write",
                params={"query": query}, result_summary="hidden",
                allowed=False, reason_if_denied=reason,
            )
            print(f"[deny] tool {target} not visible. reason={reason}")
            return

        if await requires_confirmation(db, target):
            tok = confirm.issue(ctx.user_id, target, {"__resource__": target, "query": query})
            print(f"[confirm_required] token={tok}  (caller would relay this to the user)")
            print(f"  ⤷ simulating user approval & retry…")
            consumed = confirm.consume(ctx.user_id, tok)
            if consumed is None:
                print("  ⤷ confirm consume failed (token expired / mismatch)")
                return

        if not await can_access(db, ctx, target):
            reason = await deny_reason(db, ctx, target)
            audit.log(
                user_id=ctx.user_id, resource=target, action="write",
                params={"query": query}, result_summary="blocked",
                allowed=False, reason_if_denied=reason,
            )
            print(f"[deny] can_access=False  reason={reason}")
            return

        # Pretend execution
        result_summary = f"executed {target}({query!r}) → ok"
        audit.log(
            user_id=ctx.user_id, resource=target, action="write",
            params={"query": query}, result_summary=result_summary,
            allowed=True,
        )
        print(f"[ok] {result_summary}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--user", required=True, help="seed username (e.g. alice_finance)")
    parser.add_argument("--query", required=True, help="natural-language user query")
    args = parser.parse_args()
    asyncio.run(run(args.user, args.query))


if __name__ == "__main__":
    main()
