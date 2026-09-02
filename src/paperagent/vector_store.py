import numpy as np

from .embeddings import Embedder, l2_normalize
from .models import Chunk, SearchResult


class FaissStore:
    def __init__(self, embedder: Embedder):
        self.embedder = embedder
        self.chunks: list[Chunk] = []
        self.index = None

    def build(self, chunks: list[Chunk]) -> None:
        if not chunks:
            raise ValueError("cannot build an index without chunks")
        import faiss

        vectors = l2_normalize(self.embedder.encode([chunk.text for chunk in chunks]))
        self.index = faiss.IndexFlatIP(vectors.shape[1])
        self.index.add(np.ascontiguousarray(vectors))
        self.chunks = list(chunks)

    def search(self, query: str, top_k: int = 20) -> list[SearchResult]:
        if self.index is None:
            raise RuntimeError("index has not been built")
        vector = l2_normalize(self.embedder.encode([query]))
        scores, indices = self.index.search(np.ascontiguousarray(vector), min(top_k, len(self.chunks)))
        return [
            SearchResult(self.chunks[index], float(score))
            for score, index in zip(scores[0], indices[0])
            if index >= 0
        ]

