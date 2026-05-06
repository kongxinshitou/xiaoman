"""Gatekeeper: the single choke-point that filters capabilities for the LLM and
provides a runtime decorator that hard-blocks unauthorized tool execution.

The LLM only ever sees tools/skills/KBs that pass `can_access`. The decorator is
defense-in-depth for direct callers and historic tool_call replay.
"""

from __future__ import annotations

import functools
import logging
from typing import Awaitable, Callable, Iterable

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import audit
from app.core.permissions.policy import (
    PermissionDenied,
    UserCtx,
    can_access,
    deny_reason,
)

logger = logging.getLogger(__name__)


def _tool_name(t: dict) -> str:
    """Extract the function name from an OpenAI-style tool descriptor."""
    if isinstance(t, dict):
        if "function" in t and isinstance(t["function"], dict):
            return t["function"].get("name", "")
        return t.get("name", "")
    return ""


async def filter_capabilities(
    db: AsyncSession,
    user: UserCtx,
    all_tools: list[dict],
    all_skills: list[dict] | None = None,
    all_kbs: Iterable[str] | None = None,
) -> tuple[list[dict], list[dict], list[str]]:
    """Return capabilities the user is allowed to see.

    Anything not yet registered as a policy is **default-denied** for non-admin
    users. Admins always pass. Drops are silent (LLM should not learn the
    capability exists at all).
    """
    out_tools: list[dict] = []
    for t in all_tools or []:
        name = _tool_name(t)
        if not name:
            continue
        if await can_access(db, user, name):
            out_tools.append(t)
        else:
            audit.log(
                user_id=user.user_id,
                resource=name,
                action="read",
                params={"phase": "filter_capabilities"},
                result_summary="hidden_from_llm",
                allowed=False,
                reason_if_denied=await deny_reason(db, user, name),
            )

    out_skills: list[dict] = []
    for s in all_skills or []:
        name = _tool_name(s) if isinstance(s, dict) else str(s)
        if not name:
            continue
        if await can_access(db, user, name):
            out_skills.append(s)

    out_kbs: list[str] = []
    for kb in all_kbs or []:
        if await can_access(db, user, str(kb)):
            out_kbs.append(str(kb))

    logger.info(
        "filter_capabilities user=%s role=%s dept=%s tools=%d/%d kbs=%d",
        user.user_id, user.role, user.dept,
        len(out_tools), len(all_tools or []),
        len(out_kbs),
    )
    return out_tools, out_skills, out_kbs


def require_permission(resource_name: str, *, action: str = "write"):
    """Decorator for tool execution functions.

    Expects the wrapped coroutine to receive `user: UserCtx` and `db: AsyncSession`
    as keyword args (or first two positional args). Raises PermissionDenied and
    writes an audit row on rejection.
    """

    def decorator(func: Callable[..., Awaitable]):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            user: UserCtx | None = kwargs.get("user")
            db: AsyncSession | None = kwargs.get("db")
            if user is None and args:
                user = args[0] if isinstance(args[0], UserCtx) else None
            if db is None:
                # second positional is conventionally db
                if len(args) >= 2 and hasattr(args[1], "execute"):
                    db = args[1]
            if user is None or db is None:
                raise RuntimeError(
                    "require_permission requires user: UserCtx and db: AsyncSession"
                )
            allowed = await can_access(db, user, resource_name)
            if not allowed:
                reason = await deny_reason(db, user, resource_name)
                audit.log(
                    user_id=user.user_id,
                    resource=resource_name,
                    action=action,
                    params={"args_count": len(args)},
                    result_summary="blocked",
                    allowed=False,
                    reason_if_denied=reason,
                )
                raise PermissionDenied(user.user_id, resource_name, reason)
            try:
                result = await func(*args, **kwargs)
            except Exception as e:
                audit.log(
                    user_id=user.user_id,
                    resource=resource_name,
                    action=action,
                    params={},
                    result_summary=f"error: {e}",
                    allowed=True,
                )
                raise
            audit.log(
                user_id=user.user_id,
                resource=resource_name,
                action=action,
                params={},
                result_summary=str(result)[:200] if result is not None else "ok",
                allowed=True,
            )
            return result

        return wrapper

    return decorator
