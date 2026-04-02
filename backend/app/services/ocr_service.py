import base64
import os
from typing import List, Optional, Any

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
