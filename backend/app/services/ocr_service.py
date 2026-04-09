import base64
import os
from typing import List, Optional, Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

MIME_MAP = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".bmp": "image/bmp",
    ".tiff": "image/tiff",
    ".gif": "image/gif",
    ".webp": "image/webp",
}

CHUNK_SIZE = 512
CHUNK_OVERLAP = 64


def _split_text(text: str) -> List[str]:
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + CHUNK_SIZE, len(text))
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start += CHUNK_SIZE - CHUNK_OVERLAP
    return chunks


async def ocr_image(
    file_path: str,
    provider: Optional[Any],  # accepts LLMProvider or OCRProvider
) -> List[str]:
    """
    Extract text from an image using a provider's vision API.
    Provider can be an LLMProvider or OCRProvider — both have the same fields needed.
    Returns chunked text ready for indexing.
    """
    if provider is None:
        return ["[OCR失败] 未配置视觉模型供应商，请在「设置 → OCR 视觉模型」中添加提供商"]

    ext = os.path.splitext(file_path)[1].lower()
    mime = MIME_MAP.get(ext, "image/jpeg")

    with open(file_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode()

    try:
        import litellm
        from app.services.encryption import decrypt
        from app.services.ocr_provider_service import OCR_PROVIDER_CONFIG

        api_key = decrypt(provider.encrypted_api_key)
        provider_type = getattr(provider, "provider_type", "custom")
        provider_base_url = getattr(provider, "base_url", None)

        provider_cfg = OCR_PROVIDER_CONFIG.get(provider_type, {"api_base": None})
        base_url = provider_base_url or provider_cfg.get("api_base")

        model = provider.model_name
        if provider_type == "anthropic":
            model = f"anthropic/{provider.model_name}"
        elif provider_type not in ("openai",):
            model = f"openai/{provider.model_name}"

        kwargs = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "请提取图片中的所有文字内容，保持原有段落和换行格式，不要添加任何额外说明。如果图片中没有文字，请回复「[图片无文字内容]」。",
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime};base64,{img_b64}"},
                        },
                    ],
                }
            ],
            "api_key": api_key,
            "max_tokens": 4096,
        }
        if base_url:
            kwargs["api_base"] = base_url

        response = await litellm.acompletion(**kwargs)
        text = response.choices[0].message.content or ""

        if not text.strip():
            return [f"[图片OCR结果为空，文件: {os.path.basename(file_path)}]"]

        return _split_text(text)

    except Exception as e:
        err = str(e)
        if "vision" in err.lower() or "image" in err.lower() or "multimodal" in err.lower():
            return [f"[OCR失败] 当前模型「{provider.model_name}」不支持视觉识别，请配置支持视觉的模型（如 gpt-4o、qwen-vl-max、claude-3-5-sonnet）"]
        return [f"[OCR失败] {err}"]


# ── Vision description helpers (use OCR provider as the vision model) ────────

async def get_default_ocr_provider(db: AsyncSession):
    """Return the default-or-first active OCR provider, or None if none configured."""
    from app.models.ocr_provider import OCRProvider
    result = await db.execute(
        select(OCRProvider).where(
            OCRProvider.is_default == True,
            OCRProvider.is_active == True,
        ).limit(1)
    )
    p = result.scalar_one_or_none()
    if p:
        return p
    result = await db.execute(
        select(OCRProvider).where(OCRProvider.is_active == True).limit(1)
    )
    return result.scalar_one_or_none()


def _build_litellm_kwargs(provider: Any, prompt: str, data_url: str, max_tokens: int = 800) -> dict:
    """Construct litellm kwargs for a vision request via an OCR/LLM provider."""
    from app.services.encryption import decrypt
    from app.services.ocr_provider_service import OCR_PROVIDER_CONFIG

    api_key = decrypt(provider.encrypted_api_key)
    provider_type = getattr(provider, "provider_type", "custom")
    provider_base_url = getattr(provider, "base_url", None)
    provider_cfg = OCR_PROVIDER_CONFIG.get(provider_type, {"api_base": None})
    base_url = provider_base_url or provider_cfg.get("api_base")

    model = provider.model_name
    if provider_type == "anthropic":
        model = f"anthropic/{provider.model_name}"
    elif provider_type not in ("openai",):
        model = f"openai/{provider.model_name}"

    kwargs: dict = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        ],
        "api_key": api_key,
        "max_tokens": max_tokens,
    }
    if base_url:
        kwargs["api_base"] = base_url
    return kwargs


async def describe_image_bytes(
    image_bytes: bytes,
    image_ext: str,
    provider: Optional[Any],
    prompt: Optional[str] = None,
) -> str:
    """Generate a natural-language description of an image using a vision provider.

    Used by the document parser to caption embedded images. Returns "图片" on
    failure rather than raising, so document indexing can continue.
    """
    if provider is None:
        return "图片"

    mime = MIME_MAP.get(image_ext.lower(), "image/png")
    img_b64 = base64.b64encode(image_bytes).decode()
    data_url = f"data:{mime};base64,{img_b64}"

    desc_prompt = prompt or (
        "请用中文简洁描述这张图片的主要内容、关键信息和可能的用途，控制在100字以内。"
        "如果是图表请说明图表类型和数据趋势；如果含文字请提及关键文字。"
    )

    try:
        import litellm
        kwargs = _build_litellm_kwargs(provider, desc_prompt, data_url, max_tokens=400)
        response = await litellm.acompletion(**kwargs)
        text = (response.choices[0].message.content or "").strip()
        return text[:300] if text else "图片"
    except Exception as e:
        return f"图片(解析失败: {str(e)[:60]})"


async def describe_image_data_url(
    data_url: str,
    provider: Optional[Any],
    prompt: Optional[str] = None,
) -> str:
    """Describe an image given as a data URL via a vision provider.

    Used by the chat flow to convert a user-uploaded image into text before
    sending to the main LLM. Raises on failure so the caller can decide how
    to surface the error.
    """
    if provider is None:
        raise RuntimeError("未配置 OCR 视觉模型，无法解析图片")

    desc_prompt = prompt or (
        "请用中文详细描述这张图片的所有可见内容：包括主要元素、文字、数据、人物、场景等。"
        "如果是图表，请说明类型并解读数据；如果包含文字，请尽量完整提取关键文字。"
        "描述要客观准确，控制在300字以内。"
    )

    import litellm
    kwargs = _build_litellm_kwargs(provider, desc_prompt, data_url, max_tokens=800)
    response = await litellm.acompletion(**kwargs)
    text = (response.choices[0].message.content or "").strip()
    return text[:1000]
