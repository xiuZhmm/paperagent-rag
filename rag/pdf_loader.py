"""
PDF 加载模块（v2 - 支持页码追踪）
使用 PyMuPDF (fitz) 提取 PDF 文本内容，同时记录每段文本的页码
"""
import fitz  # PyMuPDF
from pathlib import Path


def load_pdf(pdf_path: str) -> str:
    """
    读取单个 PDF 文件，返回全文文本（兼容旧接口）。
    """
    pages = load_pdf_with_pages(pdf_path)
    return "\n".join(p["text"] for p in pages)


def load_pdf_with_pages(pdf_path: str) -> list[dict]:
    """
    读取 PDF，按页返回文本和页码。
    返回: [{"page": 1, "text": "..."}, {"page": 2, "text": "..."}, ...]
    """
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF 文件不存在: {pdf_path}")
    if path.suffix.lower() != ".pdf":
        raise ValueError(f"不是 PDF 文件: {pdf_path}")

    doc = fitz.open(str(path))
    pages = []
    for i, page in enumerate(doc):
        page_text = page.get_text()
        if page_text.strip():
            pages.append({"page": i + 1, "text": page_text})
    doc.close()

    if not pages:
        raise ValueError(f"PDF 内容为空（可能是扫描件）: {pdf_path}")

    return pages


def load_pdfs_from_dir(dir_path: str) -> list[dict]:
    """
    读取目录下所有 PDF 文件（兼容旧接口，不含页码）。
    返回: [{"name": "paper.pdf", "text": "..."}, ...]
    """
    results_with_pages = load_pdfs_from_dir_with_pages(dir_path)
    results = []
    for doc in results_with_pages:
        full_text = "\n".join(p["text"] for p in doc["pages"])
        results.append({"name": doc["name"], "text": full_text})
    return results


def load_pdfs_from_dir_with_pages(dir_path: str) -> list[dict]:
    """
    读取目录下所有 PDF 文件，保留页码信息。
    返回: [{"name": "paper.pdf", "pages": [{"page": 1, "text": "..."}, ...]}, ...]
    """
    path = Path(dir_path)
    if not path.exists():
        raise FileNotFoundError(f"目录不存在: {dir_path}")

    results = []
    for pdf_file in sorted(path.glob("*.pdf")):
        try:
            pages = load_pdf_with_pages(str(pdf_file))
            results.append({"name": pdf_file.name, "pages": pages})
            total_chars = sum(len(p["text"]) for p in pages)
            print(f"  [OK] {pdf_file.name}  ({len(pages)} 页, {total_chars} 字符)")
        except Exception as e:
            print(f"  [跳过] {pdf_file.name}: {e}")

    return results
