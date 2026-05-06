"""Seed the database with demo departments, sample policies, and demo users.

Run from the backend directory:

    python -m scripts.seed_demo

Idempotent: re-running upserts (does not duplicate rows).
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Allow `python -m scripts.seed_demo` from backend/
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import select  # noqa: E402

from app.database import AsyncSessionLocal, create_tables  # noqa: E402
from app.models.policy import Department, ResourcePolicy  # noqa: E402
from app.models.user import User  # noqa: E402
from app.core.permissions import policy as policy_svc  # noqa: E402
from app.services.auth_service import hash_password  # noqa: E402


DEPARTMENTS = [
    ("finance", "财务部"),
    ("sales", "销售部"),
    ("rd", "研发部"),
    ("hr", "人力资源部"),
]


# (name, display_name, type, level, allow_dept, allow_role, write, require_confirm)
POLICIES = [
    # public
    ("general_qa", "通用问答", "tool", "public", [], [], False, False),
    ("schedule_query", "日程查询", "tool", "public", [], [], False, False),
    # internal — by department
    ("crm_query", "CRM 客户查询", "tool", "internal", ["sales"], [], False, False),
    ("financial_report", "财务报表查看", "tool", "internal", ["finance"], [], False, False),
    ("rd_runbook", "研发运维知识库", "knowledge_base", "internal", ["rd"], [], False, False),
    # restricted — by department + role + write/confirm
    ("salary_query", "薪资查询", "tool", "restricted",
     ["hr", "finance"], ["manager", "admin"], False, False),
    ("delete_invoice", "删除发票", "tool", "restricted",
     ["finance"], ["manager", "admin"], True, True),
    # built-in tool defaults
    ("feishu_create_group", "飞书建群", "tool", "internal",
     ["finance", "sales", "rd", "hr"], [], False, False),
]


DEMO_USERS = [
    # username, password, role, dept
    ("alice_finance", "demo1234", "employee", "finance"),
    ("bob_sales", "demo1234", "employee", "sales"),
    ("carol_hr_mgr", "demo1234", "manager", "hr"),
    ("dave_rd", "demo1234", "employee", "rd"),
]


async def upsert_department(db, code: str, name: str) -> None:
    row = (
        await db.execute(select(Department).where(Department.code == code))
    ).scalar_one_or_none()
    if row is None:
        db.add(Department(code=code, name=name, enabled=True))
    else:
        row.name = name
        row.enabled = True


async def upsert_policy(db, *, name, display_name, type_, level, allow_dept, allow_role, write, require_confirm):
    existing = (
        await db.execute(select(ResourcePolicy).where(ResourcePolicy.name == name))
    ).scalar_one_or_none()
    data = {
        "name": name,
        "display_name": display_name,
        "type": type_,
        "level": level,
        "allow_dept": allow_dept,
        "allow_role": allow_role,
        "write": write,
        "require_confirm": require_confirm,
        "enabled": True,
    }
    if existing is None:
        await policy_svc.create_policy(db, data, operator="seed", reason="initial seed_demo")
    else:
        await policy_svc.update_policy(db, name, data, operator="seed", reason="re-seed (idempotent)")


async def upsert_user(db, *, username, password, role, dept) -> None:
    existing = (
        await db.execute(select(User).where(User.username == username))
    ).scalar_one_or_none()
    if existing is None:
        db.add(User(
            username=username,
            email=f"{username}@example.com",
            hashed_password=hash_password(password),
            role=role,
            dept=dept,
            is_active=True,
        ))
    else:
        existing.role = role
        existing.dept = dept


async def main() -> None:
    await create_tables()
    async with AsyncSessionLocal() as db:
        # Departments
        for code, name in DEPARTMENTS:
            await upsert_department(db, code, name)
        await db.commit()

        # Policies (each call commits internally and bumps the version)
        for tup in POLICIES:
            name, display, type_, level, allow_dept, allow_role, write, require_confirm = tup
            await upsert_policy(
                db,
                name=name, display_name=display, type_=type_, level=level,
                allow_dept=allow_dept, allow_role=allow_role,
                write=write, require_confirm=require_confirm,
            )

        # Users
        for username, password, role, dept in DEMO_USERS:
            await upsert_user(db, username=username, password=password, role=role, dept=dept)
        # Ensure admin gets a dept too (for filters that scope by dept)
        admin = (
            await db.execute(select(User).where(User.username == "admin"))
        ).scalar_one_or_none()
        if admin is not None and not admin.dept:
            admin.dept = "rd"
        await db.commit()

    print("[seed_demo] departments + policies + users inserted/updated.")
    print("Demo logins:")
    for u, p, r, d in DEMO_USERS:
        print(f"  {u}/{p}  role={r} dept={d}")


if __name__ == "__main__":
    asyncio.run(main())
