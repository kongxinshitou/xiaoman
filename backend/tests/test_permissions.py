"""Permission system tests — covers the 8 scenarios in the plan."""

from __future__ import annotations

import asyncio
import json
import os
import tempfile

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.api.v1 import admin as admin_api
from app.core.dependencies import get_current_user, require_admin
from app.core.permissions import audit
from app.core.permissions import policy as policy_svc
from app.core.permissions.gatekeeper import filter_capabilities
from app.core.permissions.kb_filter import filter_chunks
from app.core.permissions.policy import (
    Policy,
    UserCtx,
    can_access,
    create_policy,
    delete_policy,
    get_policy_index,
    requires_confirmation,
    update_policy,
)
from app.database import get_db
from app.models.user import User


# ── Helpers ─────────────────────────────────────────────────────────────────

async def make_user(db, *, role: str, dept: str | None = "rd") -> User:
    u = User(
        username=f"{role}_{dept or 'none'}_{os.urandom(3).hex()}",
        email=None,
        hashed_password="x",
        role=role,
        dept=dept,
        is_active=True,
    )
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


async def seed_policies(db) -> None:
    await create_policy(
        db,
        {
            "name": "general_qa",
            "display_name": "通用问答",
            "type": "tool",
            "level": "public",
            "allow_dept": [],
            "allow_role": [],
            "write": False,
        },
        operator="seed",
        reason="test seed",
    )
    await create_policy(
        db,
        {
            "name": "hr_kb_lookup",
            "display_name": "HR 知识库",
            "type": "knowledge_base",
            "level": "internal",
            "allow_dept": ["hr"],
        },
        operator="seed",
        reason="test seed",
    )
    await create_policy(
        db,
        {
            "name": "salary_query",
            "display_name": "薪资查询",
            "type": "tool",
            "level": "restricted",
            "allow_dept": ["hr", "finance"],
            "allow_role": ["manager", "admin"],
        },
        operator="seed",
        reason="test seed",
    )
    await create_policy(
        db,
        {
            "name": "delete_invoice",
            "display_name": "删除发票",
            "type": "tool",
            "level": "restricted",
            "allow_dept": ["finance"],
            "allow_role": ["manager", "admin"],
            "write": True,
            "require_confirm": True,
        },
        operator="seed",
        reason="test seed",
    )


# ── 1. Cross-dept denial ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_cross_dept_denial(db, tmp_path, monkeypatch):
    monkeypatch.setattr(audit, "_AUDIT_PATH", str(tmp_path / "audit.jsonl"))
    monkeypatch.setattr(audit, "_initialized", False)
    await seed_policies(db)
    finance_user = UserCtx("u1", "employee", "finance")
    assert await can_access(db, finance_user, "hr_kb_lookup") is False


# ── 2. Role insufficient + filter_capabilities hides tool ───────────────────

@pytest.mark.asyncio
async def test_role_insufficient_filter(db):
    await seed_policies(db)
    finance_emp = UserCtx("u2", "employee", "finance")
    assert await can_access(db, finance_emp, "salary_query") is False
    tools = [
        {"type": "function", "function": {"name": "general_qa"}},
        {"type": "function", "function": {"name": "salary_query"}},
    ]
    visible, _, _ = await filter_capabilities(db, finance_emp, tools)
    names = [t["function"]["name"] for t in visible]
    assert "general_qa" in names
    assert "salary_query" not in names


# ── 3. Write blocked / PermissionDenied via decorator ───────────────────────

@pytest.mark.asyncio
async def test_write_blocked_via_decorator(db):
    from app.core.permissions.gatekeeper import require_permission
    from app.core.permissions.policy import PermissionDenied
    await seed_policies(db)

    @require_permission("delete_invoice", action="write")
    async def do_delete(user, db, invoice_id):
        return f"deleted {invoice_id}"

    sales_emp = UserCtx("u3", "employee", "sales")
    with pytest.raises(PermissionDenied):
        await do_delete(sales_emp, db, "INV-001")


# ── 4. KB metadata filter ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_kb_filter_chunks(db):
    await seed_policies(db)
    finance_emp = UserCtx("u4", "employee", "finance")
    chunks = [
        {"text": "public stuff", "doc_id": "d1", "level": "public", "dept": None, "kb_id": "kbA"},
        {"text": "finance internal", "doc_id": "d2", "level": "internal", "dept": "finance", "kb_id": "kbA"},
        {"text": "hr internal", "doc_id": "d3", "level": "internal", "dept": "hr", "kb_id": "kbA"},
        {"text": "untagged", "doc_id": "d4", "level": None, "dept": None, "kb_id": "kbA"},
    ]
    idx = await get_policy_index(db)
    out = filter_chunks(finance_emp, chunks, idx)
    texts = [c["text"] for c in out]
    assert "public stuff" in texts
    assert "finance internal" in texts
    assert "hr internal" not in texts
    assert "untagged" not in texts  # default-deny for untagged content


# ── 5. Audit log records denials ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_audit_records_denial(db, tmp_path, monkeypatch):
    log_path = str(tmp_path / "audit.jsonl")
    monkeypatch.setattr(audit, "_AUDIT_PATH", log_path)
    monkeypatch.setattr(audit, "_initialized", False)
    audit._logger.handlers.clear()
    await seed_policies(db)

    finance_emp = UserCtx("u5", "employee", "finance")
    tools = [{"type": "function", "function": {"name": "salary_query"}}]
    await filter_capabilities(db, finance_emp, tools)
    # Flush handlers
    for h in audit._logger.handlers:
        h.flush()

    assert os.path.exists(log_path)
    lines = [json.loads(l) for l in open(log_path, encoding="utf-8") if l.strip()]
    denied = [r for r in lines if r["resource_name"] == "salary_query" and not r["allowed"]]
    assert denied, "expected at least one denial record for salary_query"
    assert denied[0]["reason_if_denied"] in ("dept_mismatch", "role_insufficient")


# ── 6. Cache invalidates on policy change ───────────────────────────────────

@pytest.mark.asyncio
async def test_cache_invalidates_on_update(db):
    await seed_policies(db)
    rd_emp = UserCtx("u6", "employee", "rd")
    # Initially rd has no access (allow_dept = [hr, finance])
    assert await can_access(db, rd_emp, "salary_query") is False
    # Admin updates allow_dept to include rd
    await update_policy(
        db,
        "salary_query",
        {"allow_dept": ["hr", "finance", "rd"], "allow_role": ["employee", "manager", "admin"]},
        operator="admin",
        reason="test cache invalidation",
    )
    # Cache should auto-reload via version mismatch
    assert await can_access(db, rd_emp, "salary_query") is True


# ── 7 & 8. Admin API auth (403) and missing reason (400) ────────────────────

def _build_test_app(db_session, current_user_factory):
    """Build a FastAPI app wired to use the supplied session + user override."""
    app = FastAPI()
    app.include_router(admin_api.router, prefix="/admin")

    async def _get_db_override():
        yield db_session

    async def _get_user_override():
        return current_user_factory()

    app.dependency_overrides[get_db] = _get_db_override
    app.dependency_overrides[get_current_user] = _get_user_override
    return app


@pytest.mark.asyncio
async def test_non_admin_returns_403(db):
    employee = await make_user(db, role="employee", dept="finance")
    app = _build_test_app(db, lambda: employee)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.get("/admin/policies")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_create_policy_without_reason_returns_400(db):
    admin = await make_user(db, role="admin", dept="rd")
    app = _build_test_app(db, lambda: admin)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.post(
            "/admin/policies",
            json={
                "name": "x_no_reason",
                "display_name": "x",
                "type": "tool",
                "level": "public",
                "reason": "",
            },
        )
    assert r.status_code == 400
    body = r.json()
    detail = body.get("detail")
    assert isinstance(detail, dict)
    assert detail.get("error") == "REASON_REQUIRED"
    # Confirm DB has no row for that name
    row = (
        await db.execute(
            select(policy_svc.ResourcePolicy).where(
                policy_svc.ResourcePolicy.name == "x_no_reason"
            )
        )
    ).scalar_one_or_none()
    assert row is None


# ── Bonus: admin role bypasses everything ──────────────────────────────────

@pytest.mark.asyncio
async def test_admin_bypass(db):
    await seed_policies(db)
    admin_ctx = UserCtx("a1", "admin", "rd")
    assert await can_access(db, admin_ctx, "salary_query") is True
    assert await can_access(db, admin_ctx, "totally_unregistered_tool") is True


# ── Bonus: requires_confirmation reflects policy ───────────────────────────

@pytest.mark.asyncio
async def test_requires_confirmation_flag(db):
    await seed_policies(db)
    assert await requires_confirmation(db, "delete_invoice") is True
    assert await requires_confirmation(db, "general_qa") is False
