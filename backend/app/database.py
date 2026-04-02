from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.config import settings
import os

os.makedirs(settings.upload_dir, exist_ok=True)

engine = create_async_engine(settings.database_url, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def create_tables():
    from app.models import user, session, knowledge, llm_provider, mcp_tool, dc_device, dc_inspection, feishu_config  # noqa: F401
    import app.models.embed_provider  # noqa: F401
    import app.models.ocr_provider  # noqa: F401
    import app.models.system_setting  # noqa: F401
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db():
    async with AsyncSessionLocal() as db:
        try:
            yield db
        finally:
            await db.close()
