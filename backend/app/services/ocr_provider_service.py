import base64
import io
import logging
from typing import Dict, List, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.ocr_provider import OCRProvider

logger = logging.getLogger(__name__)

OCR_PROVIDER_CONFIG: Dict[str, Dict[str, Any]] = {
    "openai": {"api_base": None},
    "anthropic": {"api_base": None},
    "qwen": {"api_base": "https://dashscope.aliyuncs.com/compatible-mode/v1"},
    "zhipu": {"api_base": "https://open.bigmodel.cn/api/paas/v4/"},
    "custom": {"api_base": None},
}

OCR_PROVIDER_FALLBACK_MODELS: Dict[str, List[str]] = {
    "openai": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"],
    "anthropic": ["claude-opus-4-5-20251101", "claude-sonnet-4-5-20251101", "claude-3-5-sonnet-20241022"],
    "qwen": ["qwen-vl-max", "qwen-vl-plus", "qwen-vl-max-0809"],
    "zhipu": ["glm-4v-plus", "glm-4v"],
    "custom": [],
}


def _make_test_image_b64() -> str:
    """Generate a small white PNG (16x16) for connection tests using Pillow."""
    try:
        from PIL import Image as PILImage
        img = PILImage.new("RGB", (16, 16), color=(255, 255, 255))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode()
    except Exception:
        # Fallback: minimal 1x1 white PNG
        return "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwADhQGAWjR9awAAAABJRU5ErkJggg=="


_TEST_IMAGE_B64 = _make_test_image_b64()


async def test_ocr_provider(provider: "OCRProvider") -> Dict[str, Any]:
    """Test OCR provider connection. Returns {"success": bool, "error": str | None}."""
    try:
        from app.services.encryption import decrypt

        api_key = decrypt(provider.encrypted_api_key)
        provider_cfg = OCR_PROVIDER_CONFIG.get(provider.provider_type, {"api_base": None})
        base_url = provider.base_url or provider_cfg.get("api_base")

        # Image must come before text — required by older Qwen VL models
        _messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{_TEST_IMAGE_B64}"},
                    },
                    {"type": "text", "text": "reply with the single word: ok"},
                ],
            }
        ]

        if provider.provider_type == "anthropic":
            import litellm
            await litellm.acompletion(
                model=f"anthropic/{provider.model_name}",
                messages=_messages,
                api_key=api_key,
                max_tokens=5,
            )
        else:
            # Use openai SDK directly for OpenAI-compatible providers (openai, qwen, zhipu, custom, etc.)
            # litellm has known issues with vision/multimodal messages on custom OpenAI-compatible endpoints
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=api_key, base_url=base_url)
            await client.chat.completions.create(
                model=provider.model_name,
                messages=_messages,  # type: ignore[arg-type]
                max_tokens=5,
            )

        return {"success": True, "error": None}
    except Exception as e:
        error_msg = str(e)
        if hasattr(e, 'message'):
            error_msg = e.message
        logger.error("OCR provider test failed for %s (type=%s, model=%s): %s",
                      provider.name, provider.provider_type, provider.model_name, error_msg)
        return {"success": False, "error": error_msg}
