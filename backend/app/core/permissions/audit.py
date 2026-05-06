"""Audit log: append-only JSONL writer for every permissioned tool call.

Writes to logs/audit.jsonl with daily rotation. Failures fall back to standard
logger.error so that a broken disk never blocks a tool call (per plan risk row).
"""

from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime, timezone
from logging.handlers import TimedRotatingFileHandler
from typing import Optional

from app.config import settings  # noqa: F401  (kept for config access if extended later)

_LOG_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    "logs",
)
_AUDIT_PATH = os.path.join(_LOG_DIR, "audit.jsonl")

_logger = logging.getLogger("app.audit")
_logger.propagate = False
_logger.setLevel(logging.INFO)
_handler_lock = threading.Lock()
_initialized = False


def _ensure_handler() -> None:
    global _initialized
    if _initialized:
        return
    with _handler_lock:
        if _initialized:
            return
        os.makedirs(_LOG_DIR, exist_ok=True)
        try:
            handler = TimedRotatingFileHandler(
                _AUDIT_PATH, when="midnight", interval=1, backupCount=30, encoding="utf-8"
            )
            handler.setFormatter(logging.Formatter("%(message)s"))
            _logger.addHandler(handler)
        except Exception as e:
            logging.getLogger(__name__).error("audit handler init failed: %s", e)
        _initialized = True


def _truncate(value: object, limit: int = 1000) -> object:
    if isinstance(value, str) and len(value) > limit:
        return value[:limit] + f"...(truncated {len(value) - limit} chars)"
    return value


def log(
    *,
    user_id: str,
    resource: str,
    action: str,                      # "read" | "write"
    params: Optional[dict] = None,
    result_summary: str = "",
    allowed: bool,
    reason_if_denied: Optional[str] = None,
) -> None:
    """Append one audit entry. Never raises."""
    try:
        _ensure_handler()
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_id": user_id,
            "resource_name": resource,
            "action": action,
            "params": {k: _truncate(v) for k, v in (params or {}).items()},
            "result_summary": _truncate(result_summary, 500),
            "allowed": bool(allowed),
            "reason_if_denied": reason_if_denied,
        }
        _logger.info(json.dumps(record, ensure_ascii=False))
    except Exception as e:  # noqa: BLE001 — audit must never block a call
        logging.getLogger(__name__).error("audit_log_failed: %s", e)
