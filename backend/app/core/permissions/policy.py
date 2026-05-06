"""Policy engine: in-memory cache, version-based invalidation, CRUD, can_access.

The policy table is the single source of truth. A version row is bumped on every
write; readers compare their cached version with the DB version on each query and
reload the full table on mismatch (cheap — count is expected to be < 1000).

`admin` role bypasses all access checks (intentional: prevents lock-outs).
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, update, insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.policy import (
    Department,
    PolicyChange,
    PolicyVersion,
    ResourcePolicy,
)

logger = logging.getLogger(__name__)


# ── Public types ────────────────────────────────────────────────────────────

@dataclass
class UserCtx:
    """Lightweight user context, decoupled from ORM User."""

    user_id: str
    role: str                   # admin | manager | employee
    dept: Optional[str] = None


@dataclass
class Policy:
    name: str
    display_name: str
    type: str
    level: str                  # public | internal | restricted
    allow_dept: list[str] = field(default_factory=list)
    allow_role: list[str] = field(default_factory=list)
    write: bool = False
    require_confirm: bool = False
    enabled: bool = True
    description: Optional[str] = None


class PermissionDenied(Exception):
    """Raised when a user attempts a resource they do not have access to."""

    def __init__(self, user_id: str, resource: str, reason: str):
        super().__init__(f"user={user_id} denied access to {resource}: {reason}")
        self.user_id = user_id
        self.resource = resource
        self.reason = reason


# ── In-memory cache ─────────────────────────────────────────────────────────

_cache: dict[str, Policy] = {}
_cache_version: int = -1
_cache_lock = asyncio.Lock()


def _row_to_policy(row: ResourcePolicy) -> Policy:
    return Policy(
        name=row.name,
        display_name=row.display_name,
        type=row.type,
        level=row.level,
        allow_dept=json.loads(row.allow_dept) if row.allow_dept else [],
        allow_role=json.loads(row.allow_role) if row.allow_role else [],
        write=bool(row.write),
        require_confirm=bool(row.require_confirm),
        enabled=bool(row.enabled),
        description=row.description,
    )


async def _get_db_version(db: AsyncSession) -> int:
    result = await db.execute(select(PolicyVersion).where(PolicyVersion.id == 1))
    row = result.scalar_one_or_none()
    if row is None:
        # Initialize singleton row
        await db.execute(insert(PolicyVersion).values(id=1, version=0))
        await db.commit()
        return 0
    return int(row.version)


async def load_policies(db: AsyncSession) -> int:
    """Reload the cache from DB. Returns the new version number."""
    global _cache, _cache_version
    async with _cache_lock:
        result = await db.execute(select(ResourcePolicy))
        rows = result.scalars().all()
        new_cache: dict[str, Policy] = {}
        for r in rows:
            new_cache[r.name] = _row_to_policy(r)
        _cache = new_cache
        _cache_version = await _get_db_version(db)
        logger.info(
            "policy_cache_loaded count=%d version=%d", len(_cache), _cache_version
        )
        return _cache_version


async def _ensure_fresh(db: AsyncSession) -> None:
    """Ensure the in-memory cache is at the current DB version."""
    db_version = await _get_db_version(db)
    if db_version != _cache_version:
        await load_policies(db)


async def _bump_version(db: AsyncSession) -> int:
    db_version = await _get_db_version(db)
    new_version = db_version + 1
    await db.execute(
        update(PolicyVersion)
        .where(PolicyVersion.id == 1)
        .values(version=new_version, updated_at=datetime.now(timezone.utc))
    )
    return new_version


def _serialize_policy(p: ResourcePolicy) -> dict:
    return {
        "name": p.name,
        "display_name": p.display_name,
        "description": p.description,
        "type": p.type,
        "level": p.level,
        "allow_dept": json.loads(p.allow_dept) if p.allow_dept else [],
        "allow_role": json.loads(p.allow_role) if p.allow_role else [],
        "write": bool(p.write),
        "require_confirm": bool(p.require_confirm),
        "enabled": bool(p.enabled),
    }


async def _record_change(
    db: AsyncSession,
    *,
    name: str,
    action: str,
    before: Optional[dict],
    after: Optional[dict],
    operator: str,
    reason: str,
) -> None:
    db.add(
        PolicyChange(
            policy_name=name,
            action=action,
            before_value=json.dumps(before, ensure_ascii=False) if before else None,
            after_value=json.dumps(after, ensure_ascii=False) if after else None,
            changed_by=operator,
            changed_at=datetime.now(timezone.utc),
            reason=reason,
        )
    )


# ── Runtime checks ──────────────────────────────────────────────────────────

async def can_access(db: AsyncSession, user: UserCtx, resource: str) -> bool:
    """Return True if the user is allowed to access the named resource.

    admin role always passes. Unknown / disabled resources are denied (default-deny).
    """
    if user.role == "admin":
        return True
    await _ensure_fresh(db)
    p = _cache.get(resource)
    if p is None or not p.enabled:
        return False
    if p.level == "public":
        return True
    if p.level == "internal":
        return bool(user.dept and user.dept in p.allow_dept)
    if p.level == "restricted":
        return bool(
            user.dept and user.dept in p.allow_dept and user.role in p.allow_role
        )
    return False


async def deny_reason(db: AsyncSession, user: UserCtx, resource: str) -> str:
    """Return a short reason string for a denied access (for audit logs)."""
    await _ensure_fresh(db)
    p = _cache.get(resource)
    if p is None:
        return "resource_not_registered"
    if not p.enabled:
        return "resource_disabled"
    if p.level == "internal" and (not user.dept or user.dept not in p.allow_dept):
        return "dept_mismatch"
    if p.level == "restricted":
        if not user.dept or user.dept not in p.allow_dept:
            return "dept_mismatch"
        if user.role not in p.allow_role:
            return "role_insufficient"
    return "denied"


async def requires_confirmation(db: AsyncSession, resource: str) -> bool:
    await _ensure_fresh(db)
    p = _cache.get(resource)
    return bool(p and p.enabled and p.require_confirm)


async def get_policy_index(db: AsyncSession) -> dict[str, Policy]:
    """Return the live policy cache (read-only view) for batch use."""
    await _ensure_fresh(db)
    return dict(_cache)


# ── Management API (admin-only; callers must enforce auth at the route layer) ─

async def list_policies(
    db: AsyncSession,
    *,
    type_: Optional[str] = None,
    level: Optional[str] = None,
    dept: Optional[str] = None,
) -> list[Policy]:
    stmt = select(ResourcePolicy)
    if type_:
        stmt = stmt.where(ResourcePolicy.type == type_)
    if level:
        stmt = stmt.where(ResourcePolicy.level == level)
    rows = (await db.execute(stmt)).scalars().all()
    out = [_row_to_policy(r) for r in rows]
    if dept:
        out = [p for p in out if dept in p.allow_dept or p.level == "public"]
    return out


async def get_policy(db: AsyncSession, name: str) -> Optional[Policy]:
    row = (
        await db.execute(select(ResourcePolicy).where(ResourcePolicy.name == name))
    ).scalar_one_or_none()
    return _row_to_policy(row) if row else None


def _validate_payload(data: dict, *, partial: bool = False) -> None:
    if not partial:
        for key in ("name", "display_name", "type", "level"):
            if not data.get(key):
                raise ValueError(f"missing required field: {key}")
    if "level" in data and data["level"] not in ("public", "internal", "restricted"):
        raise ValueError("level must be public|internal|restricted")
    if "type" in data and data["type"] not in ("tool", "skill", "knowledge_base"):
        raise ValueError("type must be tool|skill|knowledge_base")


async def create_policy(
    db: AsyncSession, data: dict, operator: str, reason: str
) -> Policy:
    if not reason:
        raise ValueError("reason is required")
    _validate_payload(data, partial=False)
    row = ResourcePolicy(
        name=data["name"],
        display_name=data["display_name"],
        description=data.get("description"),
        type=data["type"],
        level=data["level"],
        allow_dept=json.dumps(data.get("allow_dept") or [], ensure_ascii=False),
        allow_role=json.dumps(data.get("allow_role") or [], ensure_ascii=False),
        write=bool(data.get("write", False)),
        require_confirm=bool(data.get("require_confirm", False)),
        enabled=bool(data.get("enabled", True)),
        updated_by=operator,
    )
    db.add(row)
    await db.flush()
    await _record_change(
        db,
        name=row.name,
        action="create",
        before=None,
        after=_serialize_policy(row),
        operator=operator,
        reason=reason,
    )
    await _bump_version(db)
    await db.commit()
    return _row_to_policy(row)


async def update_policy(
    db: AsyncSession, name: str, changes: dict, operator: str, reason: str
) -> Policy:
    if not reason:
        raise ValueError("reason is required")
    _validate_payload(changes, partial=True)
    row = (
        await db.execute(select(ResourcePolicy).where(ResourcePolicy.name == name))
    ).scalar_one_or_none()
    if row is None:
        raise LookupError(f"policy {name!r} not found")
    before = _serialize_policy(row)
    field_map = {
        "display_name": "display_name",
        "description": "description",
        "type": "type",
        "level": "level",
        "write": "write",
        "require_confirm": "require_confirm",
        "enabled": "enabled",
    }
    for k, attr in field_map.items():
        if k in changes:
            setattr(row, attr, changes[k])
    if "allow_dept" in changes:
        row.allow_dept = json.dumps(changes["allow_dept"] or [], ensure_ascii=False)
    if "allow_role" in changes:
        row.allow_role = json.dumps(changes["allow_role"] or [], ensure_ascii=False)
    row.updated_by = operator
    row.updated_at = datetime.now(timezone.utc)
    after = _serialize_policy(row)
    await _record_change(
        db,
        name=name,
        action="update",
        before=before,
        after=after,
        operator=operator,
        reason=reason,
    )
    await _bump_version(db)
    await db.commit()
    return _row_to_policy(row)


async def delete_policy(
    db: AsyncSession, name: str, operator: str, reason: str
) -> bool:
    """Soft delete: set enabled=False and record change."""
    if not reason:
        raise ValueError("reason is required")
    row = (
        await db.execute(select(ResourcePolicy).where(ResourcePolicy.name == name))
    ).scalar_one_or_none()
    if row is None:
        return False
    before = _serialize_policy(row)
    row.enabled = False
    row.updated_by = operator
    row.updated_at = datetime.now(timezone.utc)
    after = _serialize_policy(row)
    await _record_change(
        db,
        name=name,
        action="delete",
        before=before,
        after=after,
        operator=operator,
        reason=reason,
    )
    await _bump_version(db)
    await db.commit()
    return True


async def toggle_policy(
    db: AsyncSession, name: str, enabled: bool, operator: str, reason: str
) -> Policy:
    if not reason:
        raise ValueError("reason is required")
    row = (
        await db.execute(select(ResourcePolicy).where(ResourcePolicy.name == name))
    ).scalar_one_or_none()
    if row is None:
        raise LookupError(f"policy {name!r} not found")
    before = _serialize_policy(row)
    row.enabled = bool(enabled)
    row.updated_by = operator
    row.updated_at = datetime.now(timezone.utc)
    after = _serialize_policy(row)
    await _record_change(
        db,
        name=name,
        action="enable" if enabled else "disable",
        before=before,
        after=after,
        operator=operator,
        reason=reason,
    )
    await _bump_version(db)
    await db.commit()
    return _row_to_policy(row)


async def get_change_history(
    db: AsyncSession,
    *,
    name: Optional[str] = None,
    limit: int = 50,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
) -> list[dict]:
    stmt = select(PolicyChange).order_by(PolicyChange.changed_at.desc())
    if name:
        stmt = stmt.where(PolicyChange.policy_name == name)
    if since:
        stmt = stmt.where(PolicyChange.changed_at >= since)
    if until:
        stmt = stmt.where(PolicyChange.changed_at <= until)
    stmt = stmt.limit(max(1, min(limit, 500)))
    rows = (await db.execute(stmt)).scalars().all()
    return [
        {
            "id": r.id,
            "policy_name": r.policy_name,
            "action": r.action,
            "before_value": json.loads(r.before_value) if r.before_value else None,
            "after_value": json.loads(r.after_value) if r.after_value else None,
            "changed_by": r.changed_by,
            "changed_at": r.changed_at.isoformat() if r.changed_at else None,
            "reason": r.reason,
        }
        for r in rows
    ]


async def get_current_version(db: AsyncSession) -> int:
    return await _get_db_version(db)


# ── Department CRUD ─────────────────────────────────────────────────────────

async def list_departments(db: AsyncSession) -> list[dict]:
    rows = (await db.execute(select(Department))).scalars().all()
    return [
        {"code": r.code, "name": r.name, "enabled": bool(r.enabled)} for r in rows
    ]


async def create_department(db: AsyncSession, code: str, name: str) -> dict:
    if not code or not name:
        raise ValueError("code and name are required")
    db.add(Department(code=code, name=name, enabled=True))
    await db.commit()
    return {"code": code, "name": name, "enabled": True}


async def update_department(
    db: AsyncSession, code: str, *, name: Optional[str] = None, enabled: Optional[bool] = None
) -> dict:
    row = (
        await db.execute(select(Department).where(Department.code == code))
    ).scalar_one_or_none()
    if row is None:
        raise LookupError(f"department {code!r} not found")
    if name is not None:
        row.name = name
    if enabled is not None:
        row.enabled = bool(enabled)
    await db.commit()
    return {"code": row.code, "name": row.name, "enabled": bool(row.enabled)}


async def delete_department(db: AsyncSession, code: str) -> bool:
    """Soft delete: enabled=False."""
    row = (
        await db.execute(select(Department).where(Department.code == code))
    ).scalar_one_or_none()
    if row is None:
        return False
    row.enabled = False
    await db.commit()
    return True


# Test helper: reset cache between tests
def _reset_cache_for_tests() -> None:
    global _cache, _cache_version
    _cache = {}
    _cache_version = -1
