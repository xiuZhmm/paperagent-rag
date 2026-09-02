from pathlib import Path


def load_pdf_pages(path: str | Path) -> list[tuple[str, int, str]]:
    """Extract text page-by-page so every retrieval result remains citable."""
    import fitz

    pdf_path = Path(path)
    rows: list[tuple[str, int, str]] = []
    with fitz.open(pdf_path) as document:
        for page_no, page in enumerate(document, start=1):
            text = page.get_text("text").strip()
            if text:
                rows.append((pdf_path.name, page_no, text))
    return rows

