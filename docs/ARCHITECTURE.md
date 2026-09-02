# Architecture

`PDF -> page extraction -> 500/100 chunks -> embedding + L2 normalization -> FAISS IndexFlatIP Top-20 -> CrossEncoder Top-4 -> grounded Qwen answer`

Every chunk stores `file_name`, `page`, and `chunk_id`. The model receives only reranked evidence and is instructed to preserve source markers. PPT generation uses structured JSON and a deterministic `python-pptx` renderer; it does not screenshot or copy the paper.

## Design choices

- Inner-product search after L2 normalization is cosine-similarity search.
- Retrieval and reranking are separated so a fast bi-encoder preserves recall before a slower cross-encoder improves ordering.
- Page-level provenance is retained before chunking; citations can therefore be audited against the PDF.
- Retrieval quality should be measured with labelled questions using Recall@K and MRR, not with a few visually convincing examples.

