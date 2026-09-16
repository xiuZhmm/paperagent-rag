"""
PPT 自动生成模块 v2（质量优化版）
核心改进：
  1. 用 RAG 按每个章节分别检索论文中最相关的内容（不再截断前 8000 字）
  2. 更详细的 Prompt，要求具体数字、方法名称、数据集名称
  3. 每个要点允许更长（~80字），信息密度更高
"""
import json
import re
import tempfile
from pathlib import Path

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

import config


# ============================================================
#  配色方案（学术风格：深蓝 + 白 + 浅灰）
# ============================================================

COLORS = {
    "primary":    RGBColor(0x1E, 0x27, 0x61),
    "secondary":  RGBColor(0x06, 0x5A, 0x82),
    "accent":     RGBColor(0x00, 0xA8, 0x96),
    "text_dark":  RGBColor(0x21, 0x21, 0x21),
    "text_light": RGBColor(0xFF, 0xFF, 0xFF),
    "bg_light":   RGBColor(0xF5, 0xF7, 0xFA),
    "bg_dark":    RGBColor(0x1E, 0x27, 0x61),
    "bullet":     RGBColor(0x06, 0x5A, 0x82),
}

# PPT 固定 10 页结构 + 每页的 RAG 检索关键词
SLIDE_TEMPLATE = [
    {"key": "title",       "title": "论文标题",   "layout": "cover",
     "search_queries": []},
    {"key": "background",  "title": "研究背景",   "layout": "content",
     "search_queries": ["研究背景 动机 问题", "background introduction motivation"]},
    {"key": "related_work","title": "相关工作",   "layout": "content",
     "search_queries": ["相关工作 文献综述", "related work prior art survey"]},
    {"key": "problem",     "title": "问题定义",   "layout": "content",
     "search_queries": ["问题定义 形式化 挑战", "problem formulation challenge definition"]},
    {"key": "method",      "title": "核心方法",   "layout": "content",
     "search_queries": ["方法 提出 框架 核心思想", "method proposed approach framework"]},
    {"key": "architecture","title": "模型结构",   "layout": "content",
     "search_queries": ["模型结构 网络架构 模块", "model architecture network module component"]},
    {"key": "algorithm",   "title": "算法流程",   "layout": "content",
     "search_queries": ["算法流程 步骤 伪代码", "algorithm procedure steps pipeline"]},
    {"key": "experiments", "title": "实验设置",   "layout": "content",
     "search_queries": ["实验设置 数据集 评估指标", "experiment dataset benchmark evaluation metric"]},
    {"key": "results",     "title": "实验结果",   "layout": "content",
     "search_queries": ["实验结果 性能对比 SOTA", "results performance comparison table SOTA"]},
    {"key": "conclusion",  "title": "总结与展望", "layout": "ending",
     "search_queries": ["结论 贡献 局限性 未来", "conclusion contribution limitation future work"]},
]


# ============================================================
#  第一步：用 RAG 为每个章节检索相关论文内容
# ============================================================

def retrieve_section_contexts(vectorstore, top_k_per_query: int = 3, source_filter: str = None) -> dict:
    """
    对每个 PPT 章节，用 RAG 从论文中检索最相关的内容。
    source_filter: 如果指定，只检索该来源的文本块。
    """
    section_contexts = {}

    for slide_info in SLIDE_TEMPLATE:
        key = slide_info["key"]
        queries = slide_info.get("search_queries", [])
        if not queries:
            section_contexts[key] = ""
            continue

        all_text = []
        for query in queries:
            results = vectorstore.search(query, top_k=top_k_per_query)
            for r in results:
                if source_filter:
                    src = r.get("source", r.get("metadata", {}).get("source", ""))
                    if src and source_filter not in str(src):
                        continue
                all_text.append(r["text"])

        # 去重（不同 query 可能检索到相同 chunk）
        seen = set()
        unique_texts = []
        for t in all_text:
            t_clean = t.strip()
            if t_clean and t_clean not in seen:
                seen.add(t_clean)
                unique_texts.append(t_clean)

        # 拼接，限制总长度避免超 token
        combined = "\n---\n".join(unique_texts)
        if len(combined) > 3000:
            combined = combined[:3000]

        section_contexts[key] = combined

    return section_contexts


# ============================================================
#  第二步：LLM 基于检索内容生成高质量 PPT 结构
# ============================================================

SECTION_PROMPT = """请根据以下关于「{section_title}」的论文原文内容，为 PPT 生成该页的要点。

【论文原文片段】
{section_context}

要求：
1. 提取 3-4 个关键要点，不要超过 4 个
2. 每个要点 15-35 个字，简洁有力，像 PPT 标语而非论文段落
3. 包含关键术语或数字，但不要长句解释
4. 必须基于原文内容，不要编造
5. 直接输出 JSON 数组，例如：["要点1", "要点2", "要点3"]
6. 只输出 JSON 数组"""

TITLE_PROMPT = """根据以下论文内容，提取论文标题和副标题信息。

【论文内容】
{context}

输出 JSON 格式：
{{"title": "论文完整标题", "subtitle": "作者 / 会议或期刊 / 年份"}}

只输出 JSON，不要输出其他内容。"""


def _call_llm(prompt_str: str, max_tokens: int = 1500) -> str:
    llm = ChatOpenAI(
        model=config.LLM_MODEL,
        api_key=config.LLM_API_KEY,
        base_url=config.LLM_BASE_URL,
        temperature=0.2,
        max_tokens=max_tokens,
    )
    response = llm.invoke([
        SystemMessage(content="你是学术论文分析专家，擅长提取论文核心信息。只输出 JSON。"),
        HumanMessage(content=prompt_str),
    ])
    return response.content


def _extract_json(text: str):
    """从 LLM 输出中提取 JSON"""
    # 尝试提取 ```json ... ``` 代码块
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if match:
        text = match.group(1).strip()
    # 尝试提取 [...] 或 {...}
    for start, end in [("[", "]"), ("{", "}")]:
        s = text.find(start)
        e = text.rfind(end)
        if s != -1 and e != -1 and e > s:
            candidate = text[s:e+1]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                continue
    return None


def generate_ppt_structure(vectorstore=None, paper_text: str = "", source_filter: str = None) -> dict:
    """
    生成高质量 PPT 结构化内容。
    优先使用 vectorstore（RAG 检索），回退到截断全文。
    source_filter: 指定论文文件名，只从该论文检索。
    """
    structure = {}

    # ---- 标题页 ----
    print("  [PPT 1/10] 提取标题...")
    title_context = paper_text[:2000] if paper_text else ""
    if vectorstore:
        results = vectorstore.search("title abstract author", top_k=2)
        title_context = "\n".join(r["text"] for r in results)

    raw = _call_llm(TITLE_PROMPT.format(context=title_context), max_tokens=300)
    parsed = _extract_json(raw)
    if parsed:
        structure["title"] = parsed.get("title", "论文标题")
        structure["subtitle"] = parsed.get("subtitle", "")
    else:
        structure["title"] = "论文标题"
        structure["subtitle"] = ""

    # ---- 内容页（2-9）：用 RAG 按章节检索 ----
    if vectorstore:
        print("  [PPT] 使用 RAG 逐章节检索论文内容...")
        section_contexts = retrieve_section_contexts(vectorstore, top_k_per_query=3, source_filter=source_filter)
    else:
        # 回退：截断全文
        section_contexts = {}
        truncated = paper_text[:12000] if paper_text else ""
        for slide_info in SLIDE_TEMPLATE:
            section_contexts[slide_info["key"]] = truncated

    slide_keys = [s["key"] for s in SLIDE_TEMPLATE if s["layout"] != "cover"]

    for idx, slide_info in enumerate(SLIDE_TEMPLATE):
        if slide_info["layout"] == "cover":
            continue

        key = slide_info["key"]
        title = slide_info["title"]
        context = section_contexts.get(key, "")

        slide_num = SLIDE_TEMPLATE.index(slide_info) + 1
        print(f"  [PPT {slide_num}/10] 生成「{title}」...")

        if not context:
            structure[key] = [f"（未检索到「{title}」相关内容）"]
            continue

        prompt = SECTION_PROMPT.format(section_title=title, section_context=context)
        raw = _call_llm(prompt, max_tokens=800)
        parsed = _extract_json(raw)

        if parsed and isinstance(parsed, list) and len(parsed) > 0:
            structure[key] = parsed
        else:
            structure[key] = [f"（{title}内容解析失败）"]

    return structure


def _add_background(slide, color):
    background = slide.background
    fill = background.fill
    fill.solid()
    fill.fore_color.rgb = color


def _add_accent_bar(slide, left, top, width, height, color):
    shape = slide.shapes.add_shape(1, left, top, width, height)
    shape.fill.solid()
    shape.fill.fore_color.rgb = color
    shape.line.fill.background()


def _add_text_box(slide, left, top, width, height, text, font_size=14,
                  bold=False, color=None, alignment=PP_ALIGN.LEFT,
                  font_name="Calibri", line_spacing=1.0):
    txbox = slide.shapes.add_textbox(left, top, width, height)
    tf = txbox.text_frame
    tf.word_wrap = True
    tf.auto_size = None
    p = tf.paragraphs[0]
    p.text = text
    p.font.size = Pt(font_size)
    p.font.bold = bold
    p.font.color.rgb = color or COLORS["text_dark"]
    p.font.name = font_name
    p.alignment = alignment
    if line_spacing != 1.0:
        p.line_spacing = line_spacing
    return txbox


def _smart_font_size(items, base_size=20):
    total_chars = sum(len(it) for it in items)
    n = len(items)
    if n <= 0:
        return base_size
    if n <= 3 and total_chars < 120:
        return base_size
    if n >= 5 or total_chars > 250:
        return base_size - 4
    if total_chars > 160:
        return base_size - 2
    return base_size


def _smart_title_size(title, base_size=40):
    n = len(title)
    if n < 25:
        return base_size
    if n < 50:
        return base_size - 6
    if n < 80:
        return base_size - 12
    return base_size - 18


def _add_bullet_list(slide, left, top, width, height, items,
                     font_size=20, dark_bg=False):
    if not items:
        return None
    font_size = _smart_font_size(items, font_size)
    text_color = COLORS["text_light"] if dark_bg else COLORS["text_dark"]
    bullet_color_hex = "00A896" if dark_bg else "065A82"
    indent_emu = Inches(0.35)

    txbox = slide.shapes.add_textbox(left, top, width, height)
    tf = txbox.text_frame
    tf.word_wrap = True

    for i, item in enumerate(items):
        if i == 0:
            p = tf.paragraphs[0]
        else:
            p = tf.add_paragraph()
        p.text = item
        p.font.size = Pt(font_size)
        p.font.color.rgb = text_color
        p.font.name = "Calibri"
        p.space_after = Pt(20)
        p.space_before = Pt(6)
        p.line_spacing = 1.35
        p.level = 0

        from pptx.oxml.ns import qn
        pPr = p._p.get_or_add_pPr()

        for existing in pPr.findall(qn("a:buChar")):
            pPr.remove(existing)
        for existing in pPr.findall(qn("a:buNone")):
            pPr.remove(existing)
        buChar = pPr.makeelement(qn("a:buChar"), {"char": "\u25AA"})
        pPr.append(buChar)

        for existing in pPr.findall(qn("a:buClr")):
            pPr.remove(existing)
        buClr = pPr.makeelement(qn("a:buClr"), {})
        srgb = buClr.makeelement(qn("a:srgbClr"), {"val": bullet_color_hex})
        buClr.append(srgb)
        pPr.insert(0, buClr)

        buSzPct = pPr.makeelement(qn("a:buSzPct"), {"val": "100000"})
        pPr.insert(1, buSzPct)

        buFont = pPr.makeelement(qn("a:buFont"), {"typeface": "Arial"})
        pPr.insert(2, buFont)

        pPr.set("indent", str(-indent_emu))
        pPr.set("marL", str(indent_emu))

    return txbox


def _add_page_number(slide, num, total):
    _add_text_box(
        slide, Inches(11.0), Inches(7.0), Inches(1.8), Inches(0.4),
        f"{num:02d} / {total:02d}", font_size=11,
        color=RGBColor(0xAA, 0xAA, 0xAA), alignment=PP_ALIGN.RIGHT,
    )


def _add_section_badge(slide, num, top, size=None):
    from pptx.enum.shapes import MSO_SHAPE
    if size is None:
        size = Inches(0.55)
    left = Inches(0.8)
    shape = slide.shapes.add_shape(
        MSO_SHAPE.OVAL, left, top, size, size)
    shape.fill.solid()
    shape.fill.fore_color.rgb = COLORS["accent"]
    shape.line.fill.background()
    tf = shape.text_frame
    tf.word_wrap = False
    p = tf.paragraphs[0]
    p.text = f"{num:02d}"
    badge_fs = 16
    if size >= Inches(0.65):
        badge_fs = 22
    p.font.size = Pt(badge_fs)
    p.font.bold = True
    p.font.color.rgb = COLORS["text_light"]
    p.font.name = "Georgia"
    p.alignment = PP_ALIGN.CENTER


def build_pptx(structure: dict, output_path: str = None) -> str:
    if output_path is None:
        tmp = tempfile.NamedTemporaryFile(suffix=".pptx", delete=False)
        output_path = tmp.name
        tmp.close()

    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    total_slides = len(SLIDE_TEMPLATE)
    content_slides = [s for s in SLIDE_TEMPLATE if s["layout"] == "content"]

    for i, slide_info in enumerate(SLIDE_TEMPLATE):
        slide_layout = prs.slide_layouts[6]
        slide = prs.slides.add_slide(slide_layout)
        key = slide_info["key"]
        layout = slide_info["layout"]
        page_num = i + 1

        if layout == "cover":
            _add_background(slide, COLORS["bg_dark"])

            _add_accent_bar(slide, Inches(0), Inches(0), Inches(13.333), Pt(5), COLORS["accent"])
            _add_accent_bar(slide, Inches(0), Inches(7.45), Inches(13.333), Pt(5), COLORS["accent"])

            _add_accent_bar(slide, Inches(1.5), Inches(2.6), Inches(1.8), Pt(5), COLORS["accent"])

            title_text = structure.get("title", "论文标题")
            title_fs = _smart_title_size(title_text, 44)
            _add_text_box(
                slide, Inches(1.5), Inches(2.9), Inches(10.5), Inches(1.8),
                title_text,
                font_size=title_fs, bold=True, color=COLORS["text_light"],
                font_name="Georgia", line_spacing=1.15,
            )
            _add_text_box(
                slide, Inches(1.5), Inches(4.8), Inches(10.5), Inches(0.8),
                structure.get("subtitle", ""),
                font_size=20, color=RGBColor(0xCA, 0xDC, 0xFC), font_name="Calibri",
            )
            _add_text_box(
                slide, Inches(1.5), Inches(6.5), Inches(5), Inches(0.5),
                "Generated by PaperAgent", font_size=12,
                color=RGBColor(0x8A, 0x9A, 0xCC), font_name="Calibri",
            )

        elif layout == "ending":
            _add_background(slide, COLORS["bg_dark"])
            _add_accent_bar(slide, Inches(0), Inches(0), Inches(13.333), Pt(5), COLORS["accent"])

            _add_text_box(
                slide, Inches(1.5), Inches(1.3), Inches(10), Inches(1),
                slide_info["title"],
                font_size=40, bold=True, color=COLORS["text_light"],
                font_name="Georgia",
            )
            _add_accent_bar(slide, Inches(1.5), Inches(2.4), Inches(1.8), Pt(5), COLORS["accent"])

            bullets = structure.get(key, [])
            if bullets:
                _add_bullet_list(
                    slide, Inches(1.5), Inches(2.8), Inches(10), Inches(3.2),
                    bullets, font_size=18, dark_bg=True,
                )
            _add_text_box(
                slide, Inches(3.5), Inches(6.3), Inches(6), Inches(0.7),
                "Thank You", font_size=28, bold=True,
                color=COLORS["accent"], alignment=PP_ALIGN.CENTER,
                font_name="Georgia",
            )

        else:
            _add_background(slide, COLORS["bg_light"])

            _add_accent_bar(slide, Inches(0), Inches(0), Pt(10), Inches(7.5), COLORS["accent"])

            _add_accent_bar(slide, Inches(0), Inches(0), Inches(13.333), Inches(1.5), COLORS["bg_dark"])

            section_idx = content_slides.index(slide_info) + 1
            _add_section_badge(slide, section_idx, Inches(0.4), size=Inches(0.7))

            _add_text_box(
                slide, Inches(1.7), Inches(0.35), Inches(10), Inches(0.8),
                slide_info["title"],
                font_size=34, bold=True, color=COLORS["text_light"],
                font_name="Georgia",
            )

            _add_accent_bar(slide, Inches(0), Inches(1.5), Inches(13.333), Pt(3), COLORS["accent"])

            bullets = structure.get(key, [])
            if bullets:
                _add_bullet_list(
                    slide, Inches(1.5), Inches(2.0), Inches(10.5), Inches(4.8),
                    bullets, font_size=20,
                )
            else:
                _add_text_box(
                    slide, Inches(1.5), Inches(3.5), Inches(10), Inches(1),
                    "（此部分内容待补充）",
                    font_size=18, color=RGBColor(0xAA, 0xAA, 0xAA),
                )
            _add_page_number(slide, page_num, total_slides)

    prs.save(output_path)
    return output_path


# ============================================================
#  一键生成（对外接口，接受 vectorstore）
# ============================================================

def generate_paper_ppt(paper_text: str = "", vectorstore=None, output_path: str = None, source_filter: str = None) -> str:
    """
    一键生成论文 PPT（v2 质量优化版）：
    1. RAG 按章节检索论文相关内容
    2. LLM 逐页生成高质量要点
    3. python-pptx 渲染为 .pptx

    参数:
        paper_text: 论文全文（备用）
        vectorstore: PaperVectorStore 实例（优先使用）
        output_path: 输出路径
        source_filter: 指定论文文件名，只从该论文检索

    返回:
        .pptx 文件路径
    """
    print(f"[PPT] 正在生成高质量论文 PPT... {f'(来源: {source_filter})' if source_filter else '(全部)'}")
    structure = generate_ppt_structure(vectorstore=vectorstore, paper_text=paper_text, source_filter=source_filter)

    print(f"[PPT] 标题: {structure.get('title', 'N/A')}")
    print(f"[PPT] 正在渲染 PPT 文件...")

    path = build_pptx(structure, output_path)
    print(f"[PPT] 完成: {path}")
    return path
