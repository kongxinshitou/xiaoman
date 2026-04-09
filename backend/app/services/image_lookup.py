"""Image ID resolution helper.

LLMs frequently cite image markers with a truncated stable prefix (e.g.
``[IMG_运维知识100问电力_018]``) even though the stored ``DocumentImage`` row
carries a longer id with an appended description (e.g.
``IMG_运维知识100问电力_018_图片为一台智能…``). This helper takes a list of
cited ids, resolves them via:

    1. Exact match on ``DocumentImage.id``
    2. Prefix match where ``stored_id = cited_id`` OR ``stored_id`` starts with
       ``cited_id + "_"`` (the trailing underscore prevents false positives
       like ``_018`` matching ``_0180``).

Returns ``{cited_id: DocumentImage}``. Cited ids that have no match are
simply absent from the returned dict.
"""
from __future__ import annotations

from typing import Dict, List

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import DocumentImage


def _escape_like(value: str) -> str:
    """Escape LIKE wildcards so they're treated literally."""
    return value.replace("\\", "\\\\").replace("_", "\\_").replace("%", "\\%")


async def resolve_image_ids(
    cited_ids: List[str],
    db: AsyncSession,
) -> Dict[str, DocumentImage]:
    """Resolve a list of cited image ids to DocumentImage rows.

    Parameters
    ----------
    cited_ids:
        IDs as they appear inside ``[IMG_...]`` markers in LLM output.
    db:
        Active async SQLAlchemy session.

    Returns
    -------
    Mapping of ``cited_id -> DocumentImage``. Unmatched ids are omitted.
    """
    if not cited_ids:
        return {}

    resolved: Dict[str, DocumentImage] = {}

    # ── Pass 1: exact match ───────────────────────────────────────────────
    exact_result = await db.execute(
        select(DocumentImage).where(DocumentImage.id.in_(cited_ids))
    )
    for row in exact_result.scalars().all():
        if row.id in cited_ids:
            resolved[row.id] = row

    unmatched = [cid for cid in cited_ids if cid not in resolved]
    if not unmatched:
        return resolved

    # ── Pass 2: prefix match (cited_id is a prefix of stored_id) ──────────
    # Build OR of LIKE conditions, each escaping the cited id then appending
    # "\_%" so the match only succeeds when the next char is an underscore.
    like_conditions = []
    for cid in unmatched:
        escaped = _escape_like(cid)
        like_conditions.append(
            DocumentImage.id.like(escaped + "\\_%", escape="\\")
        )

    fuzzy_result = await db.execute(
        select(DocumentImage).where(or_(*like_conditions))
    )
    candidate_rows = list(fuzzy_result.scalars().all())

    # For each unmatched cited id, take the shortest matching row (closest
    # prefix match, avoids over-matching when multiple rows share a prefix).
    for cid in unmatched:
        needle = cid + "_"
        best: DocumentImage | None = None
        for row in candidate_rows:
            if row.id.startswith(needle):
                if best is None or len(row.id) < len(best.id):
                    best = row
        if best is not None:
            resolved[cid] = best

    return resolved
