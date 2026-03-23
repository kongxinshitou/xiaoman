import os
from typing import List


CHUNK_SIZE = 512
CHUNK_OVERLAP = 64


def _split_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start += chunk_size - overlap
    return chunks


def parse_txt(file_path: str) -> List[str]:
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        text = f.read()
    return _split_text(text)


def parse_pdf(file_path: str) -> List[str]:
    try:
        import PyPDF2
        text_parts = []
        with open(file_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                text = page.extract_text() or ""
                text_parts.append(text)
        full_text = "\n".join(text_parts)
        return _split_text(full_text)
    except Exception as e:
        return [f"[PDF解析错误] {str(e)}"]


def parse_docx(file_path: str) -> List[str]:
    try:
        from docx import Document
        doc = Document(file_path)
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        full_text = "\n".join(paragraphs)
        return _split_text(full_text)
    except Exception as e:
        return [f"[DOCX解析错误] {str(e)}"]


def parse_pptx(file_path: str) -> List[str]:
    try:
        from pptx import Presentation
        prs = Presentation(file_path)
        texts = []
        for slide in prs.slides:
            for shape in slide.shapes:
                if hasattr(shape, "text"):
                    texts.append(shape.text)
        full_text = "\n".join(texts)
        return _split_text(full_text)
    except Exception as e:
        return [f"[PPTX解析错误] {str(e)}"]


def parse_markdown(file_path: str) -> List[str]:
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        text = f.read()
    return _split_text(text)


def parse_document(file_path: str) -> List[str]:
    ext = os.path.splitext(file_path)[1].lower()
    parsers = {
        ".txt": parse_txt,
        ".md": parse_markdown,
        ".pdf": parse_pdf,
        ".docx": parse_docx,
        ".pptx": parse_pptx,
    }
    parser = parsers.get(ext, parse_txt)
    return parser(file_path)
