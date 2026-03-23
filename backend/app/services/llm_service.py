from typing import AsyncGenerator, Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.llm_provider import LLMProvider
from app.services.encryption import decrypt
import json
import asyncio

PROVIDER_CONFIG: Dict[str, Dict[str, Any]] = {
    "openai": {"api_base": None},
    "anthropic": {"api_base": None},
    "qwen": {"api_base": "https://dashscope.aliyuncs.com/compatible-mode/v1"},
    "doubao": {"api_base": "https://ark.cn-beijing.volces.com/api/v3"},
    "zhipu": {"api_base": "https://open.bigmodel.cn/api/paas/v4/"},
    "moonshot": {"api_base": "https://api.moonshot.cn/v1"},
    "deepseek": {"api_base": "https://api.deepseek.com"},
    "minimax": {"api_base": "https://api.minimax.chat/v1"},
    "baichuan": {"api_base": "https://api.baichuan-ai.com/v1"},
    "custom": {"api_base": None},
}

MOCK_RESPONSES = [
    "你好！我是晓曼，您的智能运维助手。",
    "我已收到您的消息，正在处理中...",
    "很高兴为您服务！请问有什么我可以帮助您的？",
    "我是晓曼AI助手，目前未配置LLM提供商，这是模拟响应。",
    "请在设置页面配置您的LLM提供商以获得真实的AI响应。",
]

_mock_idx = 0


async def get_default_provider(db: AsyncSession, provider_id: Optional[str] = None) -> Optional[LLMProvider]:
    if provider_id:
        result = await db.execute(select(LLMProvider).where(LLMProvider.id == provider_id))
        return result.scalar_one_or_none()
    result = await db.execute(
        select(LLMProvider).where(LLMProvider.is_default == True, LLMProvider.is_active == True)
    )
    provider = result.scalar_one_or_none()
    if not provider:
        result = await db.execute(select(LLMProvider).where(LLMProvider.is_active == True).limit(1))
        provider = result.scalar_one_or_none()
    return provider


async def stream_chat(
    messages: List[Dict[str, str]],
    provider: Optional[LLMProvider],
    db: AsyncSession,
) -> AsyncGenerator[str, None]:
    global _mock_idx

    if provider is None:
        # Mock streaming response
        mock = MOCK_RESPONSES[_mock_idx % len(MOCK_RESPONSES)]
        _mock_idx += 1
        for char in mock:
            yield char
            await asyncio.sleep(0.02)
        return

    try:
        import litellm

        api_key = decrypt(provider.encrypted_api_key)
        provider_cfg = PROVIDER_CONFIG.get(provider.provider_type, {"api_base": None})
        base_url = provider.base_url or provider_cfg.get("api_base")

        # Build model string for litellm
        model = provider.model_name
        if provider.provider_type == "openai":
            model = provider.model_name
        elif provider.provider_type == "anthropic":
            model = f"anthropic/{provider.model_name}"
        elif provider.provider_type in ("qwen", "doubao", "zhipu", "moonshot", "deepseek", "minimax", "baichuan"):
            model = f"openai/{provider.model_name}"
        elif provider.provider_type == "custom":
            model = f"openai/{provider.model_name}"

        kwargs: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": True,
            "api_key": api_key,
        }
        if base_url:
            kwargs["api_base"] = base_url

        response = await litellm.acompletion(**kwargs)
        async for chunk in response:
            delta = chunk.choices[0].delta.content if chunk.choices else None
            if delta:
                yield delta
    except Exception as e:
        error_msg = f"[LLM错误] {str(e)}"
        for char in error_msg:
            yield char
            await asyncio.sleep(0.01)


async def test_provider(provider: LLMProvider) -> bool:
    try:
        import litellm

        api_key = decrypt(provider.encrypted_api_key)
        provider_cfg = PROVIDER_CONFIG.get(provider.provider_type, {"api_base": None})
        base_url = provider.base_url or provider_cfg.get("api_base")

        model = provider.model_name
        if provider.provider_type not in ("openai", "anthropic"):
            model = f"openai/{provider.model_name}"

        kwargs: Dict[str, Any] = {
            "model": model,
            "messages": [{"role": "user", "content": "hi"}],
            "stream": False,
            "api_key": api_key,
            "max_tokens": 5,
        }
        if base_url:
            kwargs["api_base"] = base_url

        await litellm.acompletion(**kwargs)
        return True
    except Exception:
        return False
