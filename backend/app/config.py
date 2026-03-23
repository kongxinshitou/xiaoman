from pydantic_settings import BaseSettings
from typing import List
import secrets


class Settings(BaseSettings):
    secret_key: str = secrets.token_urlsafe(32)
    encryption_key: str = ""
    database_url: str = "sqlite+aiosqlite:///./xiaoman.db"
    milvus_host: str = "localhost"
    milvus_port: int = 19530
    use_milvus: bool = False
    embed_model: str = "text2vec-base-chinese"
    upload_dir: str = "./uploads"
    max_file_size_mb: int = 50
    allowed_origins: List[str] = ["http://localhost:5173", "http://localhost:3000"]
    feishu_app_id: str = ""
    feishu_app_secret: str = ""
    feishu_verification_token: str = ""

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
