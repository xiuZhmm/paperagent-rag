from dataclasses import dataclass


@dataclass(frozen=True)
class Chunk:
    text: str
    file_name: str
    page: int
    chunk_id: str


@dataclass(frozen=True)
class SearchResult:
    chunk: Chunk
    score: float

    @property
    def citation(self) -> str:
        return f"[{self.chunk.file_name}, p.{self.chunk.page}]"

