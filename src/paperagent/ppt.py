from io import BytesIO


def build_presentation(outline: dict) -> bytes:
    """Render a structured outline into a deterministic 16:9 PowerPoint."""
    from pptx import Presentation
    from pptx.util import Inches, Pt

    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    slides = list(outline.get("slides", []))[:10]
    if not slides:
        raise ValueError("outline must contain at least one slide")
    for item in slides:
        slide = prs.slides.add_slide(prs.slide_layouts[1])
        slide.shapes.title.text = str(item.get("title", "未命名页面"))
        frame = slide.placeholders[1].text_frame
        frame.clear()
        for index, bullet in enumerate(item.get("bullets", [])):
            paragraph = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
            paragraph.text = str(bullet)
            paragraph.font.size = Pt(20)
    stream = BytesIO()
    prs.save(stream)
    return stream.getvalue()

