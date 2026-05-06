"""Post-retrieval filter for KB chunks.

Each chunk dict (from rag_service.search) carries optional ``dept`` and
``level`` keys (set at index time). We treat them as a synthetic resource
and reuse the same access rules:

- ``level == "public"`` → keep
- ``level == "internal"`` and chunk has dept → keep iff user.dept matches
- ``level == "restricted"`` → require dept match AND role allow_role check
  (look up the per-resource policy if a name is provided; otherwise default-deny)
- chunk missing both dept and level → treat as ``internal`` with no allowed
  dept → admin-only (forces explicit tagging)
"""

from __future__ import annotations

import logging
from typing import Iterable

from app.core.permissions.policy import Policy, UserCtx

logger = logging.getLogger(__name__)


def filter_chunks(
    user: UserCtx,
    chunks: list[dict],
    policy_index: dict[str, Policy] | None = None,
) -> list[dict]:
    """Drop chunks the user is not allowed to see.

    ``policy_index`` is optional — when supplied, a chunk whose ``kb_id`` matches
    a registered policy name gets that policy's allow_role check applied for
    restricted level. Without it, restricted chunks fall back to dept match only.
    """
    if user.role == "admin":
        return list(chunks or [])

    out: list[dict] = []
    dropped = 0
    for c in chunks or []:
        if _allow(user, c, policy_index or {}):
            out.append(c)
        else:
            dropped += 1
    if dropped:
        logger.info(
            "kb_filter user=%s role=%s dept=%s kept=%d dropped=%d",
            user.user_id, user.role, user.dept, len(out), dropped,
        )
    return out


def _allow(user: UserCtx, chunk: dict, policy_index: dict[str, Policy]) -> bool:
    dept = chunk.get("dept")
    level = chunk.get("level")

    # Untagged content is treated as internal/no-dept → admin-only.
    if not level and not dept:
        return False

    if level == "public":
        return True

    if level == "internal" or level is None:
        return bool(user.dept and dept and user.dept == dept)

    if level == "restricted":
        if not (user.dept and dept and user.dept == dept):
            return False
        kb_id = chunk.get("kb_id") or ""
        policy = policy_index.get(kb_id)
        if policy is None:
            return False
        return user.role in (policy.allow_role or [])

    return False
