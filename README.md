# PaperAgent RAG

A citation-aware assistant for multi-PDF question answering and automatic PowerPoint generation. The implementation keeps file/page provenance throughout retrieval and exposes the evidence used for each answer.

> Portfolio reconstruction: the original source tree was unavailable when this repository was prepared. See [PROJECT_PROVENANCE.md](PROJECT_PROVENANCE.md). No benchmark number is claimed here until the evaluation is rerun.

## What is implemented

- Multi-PDF, page-level extraction with PyMuPDF
- Overlapping 500/100 character chunks with traceable metadata
- Local or OpenAI-compatible embeddings, L2 normalization, FAISS `IndexFlatIP`
- Top-20 recall followed by `BAAI/bge-reranker-v2-m3` Top-4 reranking
- OpenAI-compatible Qwen chat with evidence-only prompting and page citations
- Structured JSON outline and deterministic 10-page PPTX rendering
- Retrieval metrics for labelled question sets: Recall@K and MRR

## Quick start

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env  # macOS/Linux: cp .env.example .env
pip install -e .
streamlit run app.py
```

Configure the model endpoint in `.env`. For a CPU-only demo, choose a smaller embedding model; `BAAI/bge-m3` and the reranker can require several GB of memory and are downloaded on first use.

## Test

```bash
python -m unittest discover -s tests -v
```

## Repository map

- `app.py`: Streamlit interface
- `src/paperagent/`: PDF parsing, chunking, retrieval, reranking, LLM and PPT modules
- `docs/ARCHITECTURE.md`: design decisions and data flow
- `docs/SECURITY.md`: prompt-injection, privacy and validation notes
- `tests/`: offline unit tests that do not call an LLM

## Known limitations

No OCR, no persistent/vector-index versioning, and no automatic factuality guarantee. The current PPT layout is intentionally fixed and simple. Evaluation labels must be created for the user's own paper collection.

