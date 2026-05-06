"""Test fixtures: isolated in-memory SQLite + clean policy cache per test."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

# Ensure backend/ is on sys.path so `import app...` works regardless of CWD.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Force a fresh, file-backed SQLite per test session (in-memory async + multi-conn
# is fragile). We use a unique temp file and tear it down at session end.
import tempfile  # noqa: E402

_DB_FILE = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_DB_FILE.close()
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_DB_FILE.name}"

# Build a settings override before the app imports its own settings.
from app.config import settings  # noqa: E402

settings.database_url = os.environ["DATABASE_URL"]

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from app.database import Base  # noqa: E402
import app.models.user  # noqa: F401, E402
import app.models.session  # noqa: F401, E402
import app.models.knowledge  # noqa: F401, E402
import app.models.llm_provider  # noqa: F401, E402
import app.models.embed_provider  # noqa: F401, E402
import app.models.ocr_provider  # noqa: F401, E402
import app.models.mcp_tool  # noqa: F401, E402
import app.models.feishu_config  # noqa: F401, E402
import app.models.system_setting  # noqa: F401, E402
import app.models.policy  # noqa: F401, E402

from app.core.permissions import policy as policy_svc  # noqa: E402
from app.core.permissions import confirm as perm_confirm  # noqa: E402


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture()
async def engine():
    eng = create_async_engine(os.environ["DATABASE_URL"], echo=False)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    # Reset module-level caches between tests
    policy_svc._reset_cache_for_tests()
    perm_confirm._clear_for_tests()
    try:
        yield eng
    finally:
        await eng.dispose()


@pytest_asyncio.fixture()
async def db(engine):
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as session:
        yield session


def pytest_sessionfinish(session, exitstatus):
    try:
        os.unlink(_DB_FILE.name)
    except Exception:
        pass
