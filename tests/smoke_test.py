"""无需 API Key 的最小烟雾测试。"""
import os

from rag.ppt_generator import TITLE_PROMPT, _extract_json, build_pptx


def main():
    formatted = TITLE_PROMPT.format(context="demo")
    assert '"title"' in formatted

    parsed = _extract_json('{"title": "A", "subtitle": "B"}')
    assert parsed == {"title": "A", "subtitle": "B"}

    structure = {
        "title": "PaperAgent smoke test",
        "subtitle": "local verification",
        "background": ["background"],
        "related_work": ["related work"],
        "problem": ["problem"],
        "method": ["method"],
        "architecture": ["architecture"],
        "algorithm": ["algorithm"],
        "experiments": ["experiments"],
        "results": ["results"],
        "conclusion": ["conclusion"],
    }
    path = build_pptx(structure)
    assert os.path.exists(path)
    assert os.path.getsize(path) > 0
    os.unlink(path)

    print("SMOKE_TEST_OK")


if __name__ == "__main__":
    main()
