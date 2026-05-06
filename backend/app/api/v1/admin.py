"""Admin API: department management, resource policy CRUD, change history.

All routes are guarded by ``require_admin``. Mutations require a non-empty
``reason`` field — missing ``reason`` returns 400 (per task requirement).
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import require_admin
from app.core.permissions import policy as policy_svc
from app.database import get_db
from app.models.user import User

router = APIRouter()


# ── Schemas ─────────────────────────────────────────────────────────────────

class DepartmentIn(BaseModel):
    code: str
    name: str


class DepartmentPatch(BaseModel):
    name: Optional[str] = None
    enabled: Optional[bool] = None


class PolicyIn(BaseModel):
    name: str
    display_name: str
    description: Optional[str] = None
    type: str = Field(..., description="tool|skill|knowledge_base")
    level: str = Field(..., description="public|internal|restricted")
    allow_dept: list[str] = Field(default_factory=list)
    allow_role: list[str] = Field(default_factory=list)
    write: bool = False
    require_confirm: bool = False
    enabled: bool = True
    reason: str


class PolicyPatch(BaseModel):
    display_name: Optional[str] = None
    description: Optional[str] = None
    type: Optional[str] = None
    level: Optional[str] = None
    allow_dept: Optional[list[str]] = None
    allow_role: Optional[list[str]] = None
    write: Optional[bool] = None
    require_confirm: Optional[bool] = None
    enabled: Optional[bool] = None
    reason: str


class TogglePayload(BaseModel):
    enabled: bool
    reason: str


class DeletePayload(BaseModel):
    reason: str


# ── Departments ─────────────────────────────────────────────────────────────

@router.get("/depts")
async def list_depts(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    return await policy_svc.list_departments(db)


@router.post("/depts", status_code=201)
async def create_dept(
    payload: DepartmentIn,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    try:
        return await policy_svc.create_department(db, payload.code, payload.name)
    except ValueError as e:
        raise HTTPException(400, {"error": "INVALID_INPUT", "message": str(e)})


@router.patch("/depts/{code}")
async def patch_dept(
    code: str,
    payload: DepartmentPatch,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    try:
        return await policy_svc.update_department(
            db, code, name=payload.name, enabled=payload.enabled
        )
    except LookupError:
        raise HTTPException(404, {"error": "NOT_FOUND", "message": "department not found"})


@router.delete("/depts/{code}")
async def delete_dept(
    code: str,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    ok = await policy_svc.delete_department(db, code)
    if not ok:
        raise HTTPException(404, {"error": "NOT_FOUND", "message": "department not found"})
    return {"deleted": True}


# ── Policies ────────────────────────────────────────────────────────────────

def _policy_dict(p: policy_svc.Policy) -> dict:
    return {
        "name": p.name,
        "display_name": p.display_name,
        "description": p.description,
        "type": p.type,
        "level": p.level,
        "allow_dept": p.allow_dept,
        "allow_role": p.allow_role,
        "write": p.write,
        "require_confirm": p.require_confirm,
        "enabled": p.enabled,
    }


@router.get("/policies")
async def list_policies(
    type: Optional[str] = Query(None),
    level: Optional[str] = Query(None),
    dept: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    rows = await policy_svc.list_policies(db, type_=type, level=level, dept=dept)
    return [_policy_dict(p) for p in rows]


@router.get("/policies/version")
async def get_version(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    return {"version": await policy_svc.get_current_version(db)}


@router.get("/policies/{name}")
async def get_policy(
    name: str,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    p = await policy_svc.get_policy(db, name)
    if p is None:
        raise HTTPException(404, {"error": "NOT_FOUND", "message": "policy not found"})
    return _policy_dict(p)


@router.post("/policies", status_code=201)
async def create_policy(
    payload: PolicyIn,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    if not payload.reason or not payload.reason.strip():
        raise HTTPException(400, {"error": "REASON_REQUIRED", "message": "reason is required"})
    data = payload.model_dump(exclude={"reason"})
    try:
        p = await policy_svc.create_policy(db, data, operator=admin.username, reason=payload.reason)
    except ValueError as e:
        raise HTTPException(400, {"error": "INVALID_INPUT", "message": str(e)})
    return _policy_dict(p)


@router.patch("/policies/{name}")
async def update_policy(
    name: str,
    payload: PolicyPatch,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    if not payload.reason or not payload.reason.strip():
        raise HTTPException(400, {"error": "REASON_REQUIRED", "message": "reason is required"})
    changes = payload.model_dump(exclude={"reason"}, exclude_none=True)
    try:
        p = await policy_svc.update_policy(db, name, changes, operator=admin.username, reason=payload.reason)
    except LookupError:
        raise HTTPException(404, {"error": "NOT_FOUND", "message": "policy not found"})
    except ValueError as e:
        raise HTTPException(400, {"error": "INVALID_INPUT", "message": str(e)})
    return _policy_dict(p)


@router.delete("/policies/{name}")
async def delete_policy(
    name: str,
    payload: DeletePayload = Body(...),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    if not payload.reason or not payload.reason.strip():
        raise HTTPException(400, {"error": "REASON_REQUIRED", "message": "reason is required"})
    ok = await policy_svc.delete_policy(db, name, operator=admin.username, reason=payload.reason)
    if not ok:
        raise HTTPException(404, {"error": "NOT_FOUND", "message": "policy not found"})
    return {"deleted": True}


@router.post("/policies/{name}/toggle")
async def toggle_policy(
    name: str,
    payload: TogglePayload,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    if not payload.reason or not payload.reason.strip():
        raise HTTPException(400, {"error": "REASON_REQUIRED", "message": "reason is required"})
    try:
        p = await policy_svc.toggle_policy(
            db, name, payload.enabled, operator=admin.username, reason=payload.reason
        )
    except LookupError:
        raise HTTPException(404, {"error": "NOT_FOUND", "message": "policy not found"})
    return _policy_dict(p)


@router.get("/policies/{name}/history")
async def policy_history(
    name: str,
    limit: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    return await policy_svc.get_change_history(db, name=name, limit=limit)


# ── Audit / global change history ───────────────────────────────────────────

@router.get("/audit/changes")
async def all_changes(
    limit: int = Query(50, ge=1, le=500),
    from_: Optional[str] = Query(None, alias="from"),
    to: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    since = datetime.fromisoformat(from_) if from_ else None
    until = datetime.fromisoformat(to) if to else None
    return await policy_svc.get_change_history(db, name=None, limit=limit, since=since, until=until)
