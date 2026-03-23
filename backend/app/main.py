from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import create_tables, AsyncSessionLocal
from app.api.router import api_router
from app.config import settings
from app.core.exceptions import register_exception_handlers


async def seed_default_data():
    from sqlalchemy import select
    from app.models.user import User
    from app.models.skill import Skill
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

        # Create default skills
        default_skills = [
            {
                "name": "rag_search",
                "display_name": "RAG检索",
                "description": "从知识库中检索相关文档，增强AI回答质量",
                "skill_type": "rag",
                "config": '{"top_k": 5}',
                "trigger_keywords": '["怎么", "如何", "什么是", "查询", "查找"]',
                "priority": 10,
            },
            {
                "name": "mcp_execute",
                "display_name": "MCP执行",
                "description": "调用MCP工具执行运维操作、脚本和自动化任务",
                "skill_type": "mcp",
                "config": "{}",
                "trigger_keywords": '["执行", "运行", "启动", "run", "execute"]',
                "priority": 20,
            },
            {
                "name": "direct_chat",
                "display_name": "直接对话",
                "description": "直接与LLM对话，不使用知识库或工具",
                "skill_type": "llm",
                "config": "{}",
                "trigger_keywords": "[]",
                "priority": 100,
            },
        ]

        for skill_data in default_skills:
            result = await db.execute(
                select(Skill).where(Skill.name == skill_data["name"])
            )
            if not result.scalar_one_or_none():
                skill = Skill(**skill_data)
                db.add(skill)

        await db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_tables()
    await seed_default_data()
    yield


app = FastAPI(
    title="晓曼 Xiaoman API",
    description="智能运维助手 AI Ops Assistant",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
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
