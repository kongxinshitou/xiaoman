import os
from typing import List

from langchain_text_splitters import RecursiveCharacterTextSplitter


def _split_text(text: str, chunk_size: int = 500, chunk_overlap: int = 50) -> List[str]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", "。", "！", "？", ".", "!", "?", " ", ""],
    )
    return splitter.split_text(text)


def parse_txt(file_path: str, chunk_size: int = 500, chunk_overlap: int = 50) -> List[str]:
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        text = f.read()
    return _split_text(text, chunk_size, chunk_overlap)


def parse_pdf(file_path: str, chunk_size: int = 500, chunk_overlap: int = 50) -> List[str]:
    try:
        import PyPDF2
        text_parts = []
        with open(file_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                text = page.extract_text() or ""
                text_parts.append(text)
        full_text = "\n".join(text_parts)
        return _split_text(full_text, chunk_size, chunk_overlap)
    except Exception as e:
        return [f"[PDF解析错误] {str(e)}"]


def parse_docx(file_path: str, chunk_size: int = 500, chunk_overlap: int = 50) -> List[str]:
    try:
        from docx import Document
        doc = Document(file_path)
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        full_text = "\n".join(paragraphs)
        return _split_text(full_text, chunk_size, chunk_overlap)
    except Exception as e:
        return [f"[DOCX解析错误] {str(e)}"]


def parse_pptx(file_path: str, chunk_size: int = 500, chunk_overlap: int = 50) -> List[str]:
    try:
        from pptx import Presentation
        prs = Presentation(file_path)
        texts = []
        for slide in prs.slides:
            for shape in slide.shapes:
                if hasattr(shape, "text"):
                    texts.append(shape.text)
        full_text = "\n".join(texts)
        return _split_text(full_text, chunk_size, chunk_overlap)
    except Exception as e:
        return [f"[PPTX解析错误] {str(e)}"]


def parse_markdown(file_path: str, chunk_size: int = 500, chunk_overlap: int = 50) -> List[str]:
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        text = f.read()
    return _split_text(text, chunk_size, chunk_overlap)


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".gif", ".webp"}


def parse_document(file_path: str, chunk_size: int = 500, chunk_overlap: int = 50) -> List[str]:
    """Parse text-based documents. Images are handled separately via ocr_service."""
    ext = os.path.splitext(file_path)[1].lower()
    parsers = {
        ".txt": parse_txt,
        ".md": parse_markdown,
        ".pdf": parse_pdf,
        ".docx": parse_docx,
        ".pptx": parse_pptx,
    }
    parser = parsers.get(ext, parse_txt)
    return parser(file_path, chunk_size, chunk_overlap)
