from fastapi import APIRouter
from app.api.v1 import auth, chat, knowledge, llm_providers, skills, mcp_tools, system, feishu

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/v1/auth", tags=["auth"])
api_router.include_router(chat.router, prefix="/v1/chat", tags=["chat"])
api_router.include_router(knowledge.router, prefix="/v1/knowledge", tags=["knowledge"])
api_router.include_router(llm_providers.router, prefix="/v1/llm-providers", tags=["llm-providers"])
api_router.include_router(skills.router, prefix="/v1/skills", tags=["skills"])
api_router.include_router(mcp_tools.router, prefix="/v1/mcp-tools", tags=["mcp-tools"])
api_router.include_router(feishu.router, prefix="/v1/feishu", tags=["feishu"])
api_router.include_router(system.router, prefix="/v1/system", tags=["system"])
