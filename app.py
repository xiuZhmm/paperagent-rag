from pathlib import Path
import tempfile

import streamlit as st
from dotenv import load_dotenv

from paperagent.chunking import chunk_pages
from paperagent.config import Settings
from paperagent.embeddings import APIEmbedder, LocalEmbedder
from paperagent.llm import ChatClient
from paperagent.pdf_loader import load_pdf_pages
from paperagent.ppt import build_presentation
from paperagent.reranker import CrossEncoderReranker
from paperagent.vector_store import FaissStore


load_dotenv()
settings = Settings.from_env()
st.set_page_config(page_title="PaperAgent", layout="wide")
st.title("PaperAgent · 论文检索、问答与汇报生成")
st.caption("回答仅基于上传论文；请核对引用页码后再用于正式写作。")


@st.cache_resource(show_spinner="加载向量模型…")
def get_embedder():
    if settings.embedding_mode == "api":
        return APIEmbedder(settings.embedding_model, settings.embedding_api_key, settings.embedding_base_url)
    return LocalEmbedder(settings.embedding_model)


@st.cache_resource(show_spinner="加载重排模型…")
def get_reranker():
    return CrossEncoderReranker(settings.reranker_model)


uploads = st.file_uploader("上传一篇或多篇 PDF", type=["pdf"], accept_multiple_files=True)
if st.button("建立知识库", disabled=not uploads):
    pages = []
    with tempfile.TemporaryDirectory() as tmp:
        for upload in uploads:
            path = Path(tmp) / Path(upload.name).name
            path.write_bytes(upload.getvalue())
            pages.extend(load_pdf_pages(path))
    chunks = chunk_pages(pages, settings.chunk_size, settings.chunk_overlap)
    store = FaissStore(get_embedder())
    store.build(chunks)
    st.session_state.store = store
    st.success(f"已建立索引：{len(pages)} 页，{len(chunks)} 个文本块")

question = st.text_input("问题")
if st.button("检索并回答", disabled=not question or "store" not in st.session_state):
    candidates = st.session_state.store.search(question, settings.retrieval_top_k)
    evidence = get_reranker().rerank(question, candidates, settings.rerank_top_k)
    if not settings.llm_api_key:
        st.error("请先在 .env 中配置 LLM_API_KEY")
    else:
        client = ChatClient(settings.llm_api_key, settings.llm_base_url, settings.llm_model)
        answer = client.answer(question, evidence)
        st.markdown(answer)
        with st.expander("查看检索证据"):
            for row in evidence:
                st.markdown(f"**{row.citation} · {row.score:.4f}**\n\n{row.chunk.text}")
        st.session_state.last_evidence = evidence

topic = st.text_input("汇报主题", value="论文方法与实验解读")
if st.button("生成 10 页 PPT", disabled="last_evidence" not in st.session_state):
    if not settings.llm_api_key:
        st.error("请先配置 LLM_API_KEY")
    else:
        client = ChatClient(settings.llm_api_key, settings.llm_base_url, settings.llm_model)
        outline = client.presentation_outline(topic, st.session_state.last_evidence)
        pptx_bytes = build_presentation(outline)
        st.download_button("下载 PPTX", pptx_bytes, "paperagent_report.pptx")

