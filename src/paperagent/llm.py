import json

from .models import SearchResult


def build_context(results: list[SearchResult]) -> str:
    return "\n\n".join(f"{row.citation}\n{row.chunk.text}" for row in results)


class ChatClient:
    def __init__(self, api_key: str, base_url: str, model: str):
        from openai import OpenAI

        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model

    def answer(self, question: str, results: list[SearchResult]) -> str:
        context = build_context(results)
        response = self.client.chat.completions.create(
            model=self.model,
            temperature=0.1,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "只依据给定论文片段回答。每个关键结论后使用原样引用标记，如[paper.pdf, p.3]。"
                        "若证据不足，明确回答不知道，不得编造。"
                    ),
                },
                {"role": "user", "content": f"论文片段：\n{context}\n\n问题：{question}"},
            ],
        )
        return response.choices[0].message.content or ""

    def presentation_outline(self, topic: str, results: list[SearchResult]) -> dict:
        schema_hint = {"title": topic, "slides": [{"title": "研究背景", "bullets": ["要点"]}]}
        response = self.client.chat.completions.create(
            model=self.model,
            temperature=0.1,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": "基于材料生成恰好10页中文汇报提纲。只输出JSON；每页3至5个要点，不得编造数据。",
                },
                {
                    "role": "user",
                    "content": f"格式示例：{json.dumps(schema_hint, ensure_ascii=False)}\n主题：{topic}\n材料：{build_context(results)}",
                },
            ],
        )
        return json.loads(response.choices[0].message.content or "{}")

