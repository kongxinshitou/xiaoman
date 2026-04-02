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

PROVIDER_FALLBACK_MODELS: Dict[str, List[str]] = {
    "openai": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-4", "gpt-3.5-turbo"],
    "anthropic": [
        "claude-opus-4-5-20251101", "claude-sonnet-4-5-20251101", "claude-haiku-4-5-20251001",
        "claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022", "claude-3-opus-20240229",
    ],
    "qwen": ["qwen-max", "qwen-plus", "qwen-turbo", "qwen-long", "qwen2.5-72b-instruct", "qwen2.5-14b-instruct"],
    "doubao": ["doubao-1-5-pro-32k-250115", "doubao-1-5-lite-32k-250115", "doubao-pro-32k", "doubao-lite-32k"],
    "zhipu": ["glm-4-plus", "glm-4", "glm-4-long", "glm-4-flash", "glm-4-air"],
    "moonshot": ["moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"],
    "deepseek": ["deepseek-chat", "deepseek-reasoner"],
    "minimax": ["abab6.5-chat", "abab6.5s-chat", "abab5.5-chat", "abab5.5s-chat"],
    "baichuan": ["Baichuan4", "Baichuan3-Turbo", "Baichuan3-Turbo-128k", "Baichuan2-Turbo"],
    "custom": [],
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
    tools: Optional[List[Dict[str, Any]]] = None,
) -> AsyncGenerator:
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
        if tools:
            kwargs["tools"] = tools

        response = await litellm.acompletion(**kwargs)

        # Accumulate tool call fragments across chunks
        tool_call_acc: Dict[int, Dict[str, Any]] = {}

        async for chunk in response:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta

            # Handle text content
            if delta.content:
                yield delta.content

            # Handle thinking/reasoning content (DeepSeek-R1 and compatible models)
            if hasattr(delta, 'reasoning_content') and delta.reasoning_content:
                yield {"type": "thinking", "delta": delta.reasoning_content}

            # Handle tool calls (streaming fragments)
            if hasattr(delta, "tool_calls") and delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index if hasattr(tc, "index") else 0
                    if idx not in tool_call_acc:
                        tool_call_acc[idx] = {"id": "", "name": "", "arguments": ""}
                    if hasattr(tc, "id") and tc.id:
                        tool_call_acc[idx]["id"] = tc.id
                    if hasattr(tc, "function") and tc.function:
                        if tc.function.name:
                            tool_call_acc[idx]["name"] += tc.function.name
                        if tc.function.arguments:
                            tool_call_acc[idx]["arguments"] += tc.function.arguments

            # Check finish reason for tool_calls
            finish_reason = chunk.choices[0].finish_reason
            if finish_reason == "tool_calls" and tool_call_acc:
                for idx in sorted(tool_call_acc.keys()):
                    tc_data = tool_call_acc[idx]
                    try:
                        args = json.loads(tc_data["arguments"]) if tc_data["arguments"] else {}
                    except json.JSONDecodeError:
                        args = {}
                    yield {
                        "type": "tool_call",
                        "id": tc_data["id"],
                        "name": tc_data["name"],
                        "arguments": args,
                    }
                tool_call_acc.clear()

    except Exception as e:
        error_msg = f"[LLM错误] {str(e)}"
        for char in error_msg:
            yield char
            await asyncio.sleep(0.01)
    except BaseException as e:
        if isinstance(e, (GeneratorExit, KeyboardInterrupt, SystemExit)):
            raise
        # Python 3.12+: asyncio.TaskGroup wraps CancelledError into BaseExceptionGroup
        if hasattr(e, 'exceptions'):
            causes = [ex for ex in e.exceptions if not isinstance(ex, asyncio.CancelledError)]
            msg = str(causes[0]) if causes else str(e)
        else:
            msg = str(e)
        error_msg = f"[LLM错误] {msg}"
        for char in error_msg:
            yield char
            await asyncio.sleep(0.01)


async def test_provider(provider: LLMProvider) -> bool:
    try:
        api_key = decrypt(provider.encrypted_api_key)
        provider_cfg = PROVIDER_CONFIG.get(provider.provider_type, {"api_base": None})
        base_url = provider.base_url or provider_cfg.get("api_base")

        if provider.provider_type == "anthropic":
            import litellm
            await litellm.acompletion(
                model=f"anthropic/{provider.model_name}",
                messages=[{"role": "user", "content": "hi"}],
                stream=False,
                api_key=api_key,
                max_tokens=5,
            )
        else:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=api_key, base_url=base_url)
            await client.chat.completions.create(
                model=provider.model_name,
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=5,
            )
        return True
    except Exception:
        return False
