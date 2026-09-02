"""
PaperAgent v2.0 — Streamlit 界面
新增：Reranker 重排序、页码引用、PPT 自动生成
"""
import streamlit as st
import os
import time
from pathlib import Path

import config
from rag.rag_engine import process_documents, query_paper

# ==================== 页面配置 ====================
st.set_page_config(
    page_title="PaperAgent v2.0 - 论文智能问答",
    page_icon="📄",
    layout="wide",
)

# ==================== Session State ====================
if "vectorstore" not in st.session_state:
    st.session_state.vectorstore = None
if "initialized" not in st.session_state:
    st.session_state.initialized = False
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "stats" not in st.session_state:
    st.session_state.stats = {}
if "paper_text" not in st.session_state:
    st.session_state.paper_text = ""
if "paper_list" not in st.session_state:
    st.session_state.paper_list = []
if "paper_texts" not in st.session_state:
    st.session_state.paper_texts = {}


# ==================== 侧边栏 ====================
with st.sidebar:
    st.title("PaperAgent v2.0")
    st.caption("论文智能问答 | Reranker + 页码引用 + PPT 生成")
    st.markdown("---")

    # ---- 上传区 ----
    st.subheader("上传论文")
    uploaded_files = st.file_uploader(
        "上传 PDF 文件（支持多篇）",
        type=["pdf"],
        accept_multiple_files=True,
    )

    if uploaded_files:
        os.makedirs(config.DATA_DIR, exist_ok=True)
        for f in uploaded_files:
            save_path = os.path.join(config.DATA_DIR, f.name)
            with open(save_path, "wb") as fp:
                fp.write(f.getbuffer())

        st.session_state.initialized = False
        st.session_state.vectorstore = None
        st.session_state.chat_history = []
        st.session_state.paper_text = ""
        st.success(f"已上传 {len(uploaded_files)} 个文件")

    # ---- 构建知识库 ----
    pdf_count = len(list(Path(config.DATA_DIR).glob("*.pdf"))) if os.path.exists(config.DATA_DIR) else 0

    if pdf_count > 0 and not st.session_state.initialized:
        with st.spinner("正在处理论文，构建知识库..."):
            try:
                vs, stats = process_documents()
                st.session_state.vectorstore = vs
                st.session_state.initialized = True
                st.session_state.stats = stats

                # 保存论文全文和论文列表（用于 PPT 生成）
                from rag.pdf_loader import load_pdfs_from_dir
                docs = load_pdfs_from_dir(config.DATA_DIR)
                st.session_state.paper_text = "\n".join(d["text"] for d in docs)
                st.session_state.paper_list = [d["name"] for d in docs]
                st.session_state.paper_texts = {d["name"]: d["text"] for d in docs}

            except Exception as e:
                st.error(f"处理失败: {e}")

    # ---- 知识库状态 ----
    if st.session_state.initialized:
        st.success("知识库已就绪")
        stats = st.session_state.stats
        reranker_status = "已启用" if config.RERANKER_ENABLED else "未启用"
        st.info(
            f"论文: {stats.get('num_documents', '?')} 篇\n\n"
            f"文本块: {stats.get('num_chunks', '?')} 个\n\n"
            f"Reranker: {reranker_status}"
        )

        if st.button("清空知识库", use_container_width=True):
            st.session_state.vectorstore = None
            st.session_state.initialized = False
            st.session_state.chat_history = []
            st.session_state.paper_text = ""
            st.rerun()
    elif pdf_count == 0:
        st.warning("请先上传论文 PDF")

    st.markdown("---")

    # ---- PPT 生成 ----
    if st.session_state.initialized and st.session_state.paper_text:
        st.subheader("生成 PPT")

        if not st.session_state.paper_list:
            from rag.pdf_loader import load_pdfs_from_dir
            docs = load_pdfs_from_dir(config.DATA_DIR)
            st.session_state.paper_list = [d["source"] for d in docs]
            st.session_state.paper_texts = {d["source"]: d["text"] for d in docs}

        paper_options = ["全部论文（综合）"] + st.session_state.paper_list
        selected_paper = st.selectbox("选择生成哪篇论文的 PPT", paper_options)

        if st.button("一键生成论文汇报 PPT", use_container_width=True, type="primary"):
            with st.spinner("正在逐章节检索论文内容并生成 PPT（约 1-2 分钟）..."):
                try:
                    from rag.ppt_generator import generate_paper_ppt

                    if selected_paper == "全部论文（综合）":
                        ppt_paper_text = st.session_state.paper_text
                        source_filter = None
                    else:
                        ppt_paper_text = st.session_state.paper_texts.get(selected_paper, "")
                        source_filter = selected_paper

                    safe_name = selected_paper.replace(".pdf", "").replace(" ", "_")[:30]
                    output_path = os.path.join(config.DATA_DIR, "..", f"{safe_name}_summary.pptx")
                    ppt_path = generate_paper_ppt(
                        paper_text=ppt_paper_text,
                        vectorstore=st.session_state.vectorstore,
                        output_path=output_path,
                        source_filter=source_filter,
                    )
                    st.session_state.ppt_path = ppt_path
                    st.success(f"PPT 生成完成! ({selected_paper})")
                except Exception as e:
                    st.error(f"PPT 生成失败: {e}")

        if hasattr(st.session_state, "ppt_path") and os.path.exists(st.session_state.ppt_path):
            with open(st.session_state.ppt_path, "rb") as f:
                st.download_button(
                    label="下载 PPT 文件",
                    data=f.read(),
                    file_name="paper_summary.pptx",
                    mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                    use_container_width=True,
                )

    st.markdown("---")
    st.caption("技术栈: LangChain + FAISS + Reranker + Qwen")


# ==================== 主区域：问答 ====================
st.header("论文问答")

# 快捷问题
if st.session_state.initialized:
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if st.button("总结论文核心贡献", use_container_width=True):
            st.session_state.pending_question = "请总结这篇论文的核心贡献和创新点"
    with col2:
        if st.button("解释研究方法", use_container_width=True):
            st.session_state.pending_question = "这篇论文使用了什么研究方法？"
    with col3:
        if st.button("分析实验结果", use_container_width=True):
            st.session_state.pending_question = "论文的实验结果如何？有哪些关键发现？"
    with col4:
        if st.button("指出局限性", use_container_width=True):
            st.session_state.pending_question = "这篇论文有哪些局限性和未来改进方向？"

# 聊天历史
for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg["role"] == "assistant" and "sources" in msg:
            with st.expander("查看引用来源"):
                for i, src in enumerate(msg["sources"], 1):
                    # v2: 显示页码
                    page_info = f" — 第 {src['page']} 页" if src.get("page") else ""
                    st.markdown(
                        f"**来源 {i}** — {src['source']}{page_info}  "
                        f"(相关度: {src['score']:.3f})\n\n"
                        f"> {src['text']}"
                    )

# 用户输入
question = st.chat_input("输入你的问题...", key="chat_input")

# 处理快捷问题
if hasattr(st.session_state, "pending_question") and st.session_state.pending_question:
    question = st.session_state.pending_question
    st.session_state.pending_question = None

# 执行问答
if question and st.session_state.vectorstore:
    st.session_state.chat_history.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("正在检索论文内容并生成回答..."):
            try:
                result = query_paper(st.session_state.vectorstore, question)
                st.markdown(result["answer"])

                if result["sources"]:
                    with st.expander("查看引用来源"):
                        for i, src in enumerate(result["sources"], 1):
                            page_info = f" — 第 {src['page']} 页" if src.get("page") else ""
                            st.markdown(
                                f"**来源 {i}** — {src['source']}{page_info}  "
                                f"(相关度: {src['score']:.3f})\n\n"
                                f"> {src['text']}"
                            )

                st.session_state.chat_history.append({
                    "role": "assistant",
                    "content": result["answer"],
                    "sources": result.get("sources", []),
                })
            except Exception as e:
                error_msg = f"查询出错: {e}"
                st.error(error_msg)
                st.session_state.chat_history.append({
                    "role": "assistant",
                    "content": error_msg,
                })

elif question and not st.session_state.vectorstore:
    st.warning("请先上传论文 PDF 并等待知识库构建完成")
