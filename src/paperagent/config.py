from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    llm_api_key: str = ""
    llm_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    llm_model: str = "qwen-plus"
    embedding_mode: str = "local"
    embedding_model: str = "BAAI/bge-m3"
    embedding_api_key: str = ""
    embedding_base_url: str = ""
    reranker_model: str = "BAAI/bge-reranker-v2-m3"
    chunk_size: int = 500
    chunk_overlap: int = 100
    retrieval_top_k: int = 20
    rerank_top_k: int = 4

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            llm_api_key=os.getenv("LLM_API_KEY", ""),
            llm_base_url=os.getenv("LLM_BASE_URL", cls.llm_base_url),
            llm_model=os.getenv("LLM_MODEL", cls.llm_model),
            embedding_mode=os.getenv("EMBEDDING_MODE", cls.embedding_mode),
            embedding_model=os.getenv("EMBEDDING_MODEL", cls.embedding_model),
            embedding_api_key=os.getenv("EMBEDDING_API_KEY", ""),
            embedding_base_url=os.getenv("EMBEDDING_BASE_URL", ""),
            reranker_model=os.getenv("RERANKER_MODEL", cls.reranker_model),
            chunk_size=int(os.getenv("CHUNK_SIZE", "500")),
            chunk_overlap=int(os.getenv("CHUNK_OVERLAP", "100")),
            retrieval_top_k=int(os.getenv("RETRIEVAL_TOP_K", "20")),
            rerank_top_k=int(os.getenv("RERANK_TOP_K", "4")),
        )

