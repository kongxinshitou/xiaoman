from typing import Dict, List, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.embed_provider import EmbedProvider

EMBED_PROVIDER_CONFIG: Dict[str, Dict[str, Any]] = {
    "openai": {"api_base": None},
    "qwen": {"api_base": "https://dashscope.aliyuncs.com/compatible-mode/v1"},
    "zhipu": {"api_base": "https://open.bigmodel.cn/api/paas/v4/"},
    "baichuan": {"api_base": "https://api.baichuan-ai.com/v1"},
    "custom": {"api_base": None},
}

EMBED_PROVIDER_FALLBACK_MODELS: Dict[str, List[str]] = {
    "openai": ["text-embedding-3-small", "text-embedding-3-large", "text-embedding-ada-002"],
    "qwen": ["text-embedding-v3", "text-embedding-async-v2", "text-embedding-v1"],
    "zhipu": ["embedding-3", "embedding-2"],
    "baichuan": ["Baichuan-Text-Embedding"],
    "custom": [],
}


async def test_embed_provider(provider: "EmbedProvider") -> bool:
    try:
        from app.services.encryption import decrypt

        api_key = decrypt(provider.encrypted_api_key)
        provider_cfg = EMBED_PROVIDER_CONFIG.get(provider.provider_type, {"api_base": None})
        base_url = provider.base_url or provider_cfg.get("api_base")

        if provider.provider_type == "openai":
            import litellm
            await litellm.aembedding(model=provider.model_name, input=["test connection"], api_key=api_key)
        else:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=api_key, base_url=base_url)
            await client.embeddings.create(model=provider.model_name, input=["test connection"])
        return True
    except Exception:
        return False
