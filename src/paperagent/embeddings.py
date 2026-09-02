from typing import Protocol

import numpy as np


class Embedder(Protocol):
    def encode(self, texts: list[str]) -> np.ndarray: ...


def l2_normalize(vectors: np.ndarray) -> np.ndarray:
    vectors = np.asarray(vectors, dtype="float32")
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    return vectors / np.maximum(norms, 1e-12)


class LocalEmbedder:
    def __init__(self, model_name: str):
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(model_name)

    def encode(self, texts: list[str]) -> np.ndarray:
        vectors = self.model.encode(texts, show_progress_bar=False, convert_to_numpy=True)
        return l2_normalize(vectors)


class APIEmbedder:
    def __init__(self, model_name: str, api_key: str, base_url: str):
        from openai import OpenAI

        self.model_name = model_name
        self.client = OpenAI(api_key=api_key, base_url=base_url or None)

    def encode(self, texts: list[str]) -> np.ndarray:
        response = self.client.embeddings.create(model=self.model_name, input=texts)
        return l2_normalize(np.asarray([row.embedding for row in response.data], dtype="float32"))

