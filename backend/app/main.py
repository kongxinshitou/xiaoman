import logging
import os
from contextlib import asynccontextmanager
from logging.handlers import TimedRotatingFileHandler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import create_tables, AsyncSessionLocal, engine
from app.api.router import api_router
from app.config import settings
from app.core.exceptions import register_exception_handlers
# Ensure all models are imported so SQLAlchemy creates their tables
import app.models.embed_provider  # noqa: F401
import app.models.ocr_provider  # noqa: F401
import app.models.system_setting  # noqa: F401
import app.models.feishu_config  # noqa: F401
import app.models.knowledge  # noqa: F401  (includes DocumentImage)


# ── Logging Setup ──────────────────────────────────────────────────────────────

_LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")


def _enforce_log_size_limit(log_dir: str, max_bytes: int = 1024 ** 3) -> None:
    """Delete oldest log files when total directory size exceeds max_bytes."""
    try:
        files = []
        for root, _, fnames in os.walk(log_dir):
            for fn in fnames:
                fp = os.path.join(root, fn)
                files.append((os.path.getmtime(fp), fp))
        files.sort()
        total = sum(os.path.getsize(fp) for _, fp in files)
        while total > max_bytes and files:
            _, oldest = files.pop(0)
            size = os.path.getsize(oldest)
            try:
                os.remove(oldest)
            except Exception:
                pass
            total -= size
    except Exception:
        pass


def configure_logging() -> None:
    """Configure application logging: console + daily rotating file, 7-day retention."""
    os.makedirs(_LOG_DIR, exist_ok=True)
    os.makedirs(os.path.join(_LOG_DIR, "frontend"), exist_ok=True)

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root = logging.getLogger()
    if root.handlers:
        return  # Already configured (e.g., by uvicorn reload)

    # Resolve chat/LLM module log level first so handlers can be set permissively
    # enough to actually emit those records. Other modules inherit root=INFO and
    # won't produce DEBUG records, so this won't introduce noise.
    _chat_log_level_name = (settings.xiaoman_chat_log_level or "INFO").upper()
    if _chat_log_level_name not in ("DEBUG", "INFO", "WARNING", "ERROR"):
        _chat_log_level_name = "INFO"
    _chat_log_level = getattr(logging, _chat_log_level_name)
    # Handlers must allow the most verbose level we want to see anywhere.
    _handler_level = min(logging.INFO, _chat_log_level)

    root.setLevel(logging.INFO)

    # Console
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    ch.setLevel(_handler_level)
    root.addHandler(ch)

    # Daily rotating file, keep 7 days
    fh = TimedRotatingFileHandler(
        os.path.join(_LOG_DIR, "app.log"),
        when="midnight",
        interval=1,
        backupCount=7,
        encoding="utf-8",
    )
    fh.setFormatter(fmt)
    fh.setLevel(_handler_level)
    root.addHandler(fh)

    # Suppress noisy libraries
    for lib in ("uvicorn.access", "httpx", "chromadb", "LiteLLM"):
        logging.getLogger(lib).setLevel(logging.WARNING)

    # Elevate chat/LLM module loggers to capture messages arrays, tool args/outputs.
    # Set XIAOMAN_CHAT_LOG_LEVEL=DEBUG in .env (or config.py) for full agent tracing.
    logging.getLogger("app.services.chat_service").setLevel(_chat_log_level)
    logging.getLogger("app.services.llm_service").setLevel(_chat_log_level)
    logging.getLogger("app.services.mcp_service").setLevel(_chat_log_level)

    _enforce_log_size_limit(_LOG_DIR)


configure_logging()


async def migrate_db():
    """Add new columns to existing tables if they don't exist (SQLite safe)."""
    new_columns = [
        ("knowledge_bases", "embed_api_key_encrypted", "TEXT"),
        ("knowledge_bases", "embed_base_url", "VARCHAR(500)"),
        ("document_chunks", "embedding", "TEXT"),
        ("document_chunks", "image_ids", "TEXT"),
        ("llm_providers", "supports_vision", "BOOLEAN DEFAULT 0"),
        ("knowledge_bases", "embed_provider_id", "VARCHAR(36)"),
        ("knowledge_bases", "ocr_provider_id", "VARCHAR(36)"),
        ("knowledge_bases", "chunk_size", "INTEGER DEFAULT 500"),
        ("knowledge_bases", "chunk_overlap", "INTEGER DEFAULT 50"),
        ("knowledge_bases", "top_k", "INTEGER DEFAULT 5"),
        ("feishu_config", "connection_mode", "VARCHAR(20) DEFAULT 'webhook'"),
    ]
    async with engine.begin() as conn:
        for table, column, col_type in new_columns:
            try:
                await conn.exec_driver_sql(
                    f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"
                )
            except Exception:
                pass  # Column already exists


async def seed_default_data():
    from sqlalchemy import select
    from app.models.user import User
    from app.services.auth_service import hash_password

    async with AsyncSessionLocal() as db:
        # Create default admin user
        result = await db.execute(select(User).where(User.username == "admin"))
        admin = result.scalar_one_or_none()
        if not admin:
            admin = User(
                username="admin",
                email="admin@xiaoman.ai",
                hashed_password=hash_password("admin123"),
                role="admin",
                is_active=True,
            )
            db.add(admin)
            await db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_tables()
    await migrate_db()
    await seed_default_data()
    # Start Feishu WebSocket client if configured
    from app.services import feishu_service
    await feishu_service.maybe_start_ws(AsyncSessionLocal)
    yield
    # Shutdown: stop WS client gracefully
    feishu_service.stop_ws_client()


app = FastAPI(
    title="晓曼 Xiaoman API",
    description="智能运维助手 AI Ops Assistant",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — wildcard "*" disables credentials (frontend uses Bearer token, not cookies)
_origins = settings.allowed_origins
_wildcard = _origins == ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=not _wildcard,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register exception handlers
register_exception_handlers(app)

# Include routers
app.include_router(api_router, prefix="/api")


@app.get("/")
async def root():
    return {"message": "晓曼 Xiaoman API is running", "docs": "/docs"}
