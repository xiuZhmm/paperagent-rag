from .models import SearchResult


class CrossEncoderReranker:
    def __init__(self, model_name: str):
        from sentence_transformers import CrossEncoder

        self.model = CrossEncoder(model_name)

    def rerank(self, query: str, results: list[SearchResult], top_k: int = 4) -> list[SearchResult]:
        if not results:
            return []
        scores = self.model.predict([(query, row.chunk.text) for row in results])
        ranked = sorted(
            (SearchResult(row.chunk, float(score)) for row, score in zip(results, scores)),
            key=lambda row: row.score,
            reverse=True,
        )
        return ranked[:top_k]

