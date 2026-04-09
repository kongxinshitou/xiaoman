from pathlib import Path
from pydantic_settings import BaseSettings
from typing import List
import secrets

# Resolve paths relative to this file so they are correct regardless of CWD.
# backend/app/config.py → parent = backend/app → parent = backend → parent = project root
_ROOT = Path(__file__).parent.parent.parent      # project root (where .env lives)
_BACKEND = Path(__file__).parent.parent           # backend/ (where data files live)


class Settings(BaseSettings):
    secret_key: str = secrets.token_urlsafe(32)
    encryption_key: str = ""
    database_url: str = f"sqlite+aiosqlite:///{_BACKEND / 'xiaoman.db'}"
    milvus_host: str = "localhost"
    milvus_port: int = 19530
    use_milvus: bool = False
    embed_model: str = "text2vec-base-chinese"
    chroma_persist_dir: str = str(_BACKEND / "chroma_data")
    upload_dir: str = str(_BACKEND / "uploads")
    max_file_size_mb: int = 50
    allowed_origins: List[str] = ["http://localhost:5173", "http://localhost:3000"]
    xiaoman_chat_log_level: str = "DEBUG"

    model_config = {"env_file": str(_ROOT / ".env"), "extra": "ignore"}


settings = Settings()
