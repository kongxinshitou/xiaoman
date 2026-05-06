"""In-memory pending-confirmation token store.

A token is issued when a tool with require_confirm=True is about to execute. The
caller (typically the chat agent) emits the token to the user; on the next round
they must POST it back, where consume() returns the original params (or None on
miss / expiry / wrong user).

Process-local — restart drops all pending tokens. Acceptable per plan.
"""

from __future__ import annotations

import secrets
import threading
import time
from typing import Optional


_lock = threading.Lock()
_pending: dict[str, tuple[str, str, dict, float]] = {}
# token -> (user_id, resource, params, expires_at_epoch)


def _gc(now: float) -> None:
    expired = [t for t, (_, _, _, exp) in _pending.items() if exp <= now]
    for t in expired:
        _pending.pop(t, None)


def issue(user_id: str, resource: str, params: dict, ttl_sec: int = 300) -> str:
    """Create a pending-confirmation token, return its id."""
    token = secrets.token_urlsafe(16)
    expires = time.time() + max(10, int(ttl_sec))
    with _lock:
        _gc(time.time())
        _pending[token] = (user_id, resource, dict(params or {}), expires)
    return token


def consume(user_id: str, token: str) -> Optional[dict]:
    """Atomically pop and validate a token. Returns the saved params on success."""
    if not token:
        return None
    now = time.time()
    with _lock:
        _gc(now)
        entry = _pending.pop(token, None)
    if entry is None:
        return None
    saved_user, _resource, params, expires = entry
    if expires <= now or saved_user != user_id:
        return None
    return params


def peek(token: str) -> Optional[tuple[str, str, dict]]:
    """Read-only inspection (returns user_id, resource, params); useful for UIs/tests."""
    with _lock:
        entry = _pending.get(token)
    if entry is None:
        return None
    user_id, resource, params, expires = entry
    if expires <= time.time():
        return None
    return user_id, resource, dict(params)


def _clear_for_tests() -> None:
    with _lock:
        _pending.clear()
