import re
from collections.abc import Iterable

from .models import Chunk


def _clean(text: str) -> str:
    return re.sub(r"[ \t]+", " ", re.sub(r"\n{3,}", "\n\n", text)).strip()


def split_text(text: str, chunk_size: int = 500, overlap: int = 100) -> list[str]:
    """Split text into overlapping character windows, preferring paragraph boundaries."""
    if chunk_size <= 0 or overlap < 0 or overlap >= chunk_size:
        raise ValueError("require chunk_size > overlap >= 0")
    text = _clean(text)
    if not text:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(text):
        hard_end = min(start + chunk_size, len(text))
        end = hard_end
        if hard_end < len(text):
            candidates = [text.rfind(sep, start + chunk_size // 2, hard_end) for sep in ("\n\n", "。", ". ")]
            boundary = max(candidates)
            if boundary > start:
                end = boundary + 1
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = max(start + 1, end - overlap)
    return chunks


def chunk_pages(
    pages: Iterable[tuple[str, int, str]], chunk_size: int = 500, overlap: int = 100
) -> list[Chunk]:
    """Convert (file_name, page_number, text) rows into traceable chunks."""
    output: list[Chunk] = []
    for file_name, page, text in pages:
        for index, part in enumerate(split_text(text, chunk_size, overlap)):
            output.append(Chunk(part, file_name, page, f"{file_name}:p{page}:c{index}"))
    return output

