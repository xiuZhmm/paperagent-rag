"""
RAG 核心引擎 v2
文本切块 → Embedding → FAISS 向量库 → Reranker 重排序 → LLM 问答
新增：页码追踪、Reranker 精排
"""
import requests
import numpy as np
import faiss
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

import config


# ============================================================
#  Embedding 封装
# ============================================================

class APIEmbeddings:
    """
    兼容 LangChain 接口的自定义 Embedding 类。
    调用 SiliconFlow / DashScope 等 OpenAI 兼容的 Embedding API。
    """

    def __init__(self, api_key: str, api_base: str, model: str):
        self.api_key = api_key
        self.api_base = api_base
        self.model = model
        self._dimension = None

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        resp = requests.post(
            self.api_base,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={"model": self.model, "input": texts},
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        embeddings = [item["embedding"] for item in data["data"]]
        if self._dimension is None:
            self._dimension = len(embeddings[0])
        return embeddings

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]

    @property
    def dimension(self) -> int:
        if self._dimension is None:
            self.embed_query("dimension probe")
        return self._dimension


def get_embeddings():
    """根据配置返回 Embedding 实例。"""
    if config.EMBEDDING_SOURCE == "api":
        if not config.EMBEDDING_API_KEY or config.EMBEDDING_API_KEY == "sk-xxxxx":
            raise ValueError(
                "请在 .env 中设置 EMBEDDING_API_KEY，\n"
                "或将 EMBEDDING_SOURCE 改为 local（需 pip install sentence-transformers）"
            )
        emb = APIEmbeddings(
            api_key=config.EMBEDDING_API_KEY,
            api_base=config.EMBEDDING_API_BASE,
            model=config.EMBEDDING_MODEL,
        )
        _ = emb.dimension
        return emb
    else:
        try:
            from langchain_huggingface import HuggingFaceEmbeddings
        except ImportError:
            from langchain_community.embeddings import HuggingFaceEmbeddings

        return HuggingFaceEmbeddings(
            model_name=config.LOCAL_EMBEDDING_MODEL,
            encode_kwargs={"normalize_embeddings": True},
        )


# ============================================================
#  FAISS 向量库（v2: 支持页码元数据）
# ============================================================

class PaperVectorStore:
    """
    轻量级向量库封装：
    - numpy + faiss 管理索引
    - 存储原始文本 chunk 和页码信息
    """

    def __init__(self, embeddings, index, chunks, metadata):
        self.embeddings = embeddings
        self.index = index
        self.chunks = chunks
        self.metadata = metadata

    @classmethod
    def from_texts(cls, texts, metadata, embeddings):
        """从文本列表构建 FAISS 索引"""
        vectors = embeddings.embed_documents(texts)
        vectors_np = np.array(vectors, dtype="float32")

        dim = vectors_np.shape[1]
        index = faiss.IndexFlatIP(dim)
        faiss.normalize_L2(vectors_np)
        index.add(vectors_np)

        return cls(embeddings=embeddings, index=index, chunks=texts, metadata=metadata)

    def search(self, query: str, top_k: int = None) -> list[dict]:
        """
        检索最相似的文本块。
        v2: 返回结果包含 page 页码信息。
        """
        k = top_k or config.RERANKER_CANDIDATES  # 粗筛多一些，留给 Reranker
        query_vec = self.embeddings.embed_query(query)
        query_np = np.array([query_vec], dtype="float32")
        faiss.normalize_L2(query_np)

        scores, indices = self.index.search(query_np, min(k, len(self.chunks)))

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0:
                continue
            results.append({
                "text": self.chunks[idx],
                "score": float(score),
                "source": self.metadata[idx].get("source", "unknown"),
                "page": self.metadata[idx].get("page", None),
            })
        return results


# ============================================================
#  LLM 问答链
# ============================================================

def create_llm() -> ChatOpenAI:
    """创建 LLM 实例"""
    if not config.LLM_API_KEY or config.LLM_API_KEY == "sk-xxxxx":
        raise ValueError(
            "请在 .env 中设置 LLM_API_KEY，\n"
            "注册地址: https://cloud.siliconflow.cn"
        )
    return ChatOpenAI(
        model=config.LLM_MODEL,
        api_key=config.LLM_API_KEY,
        base_url=config.LLM_BASE_URL,
        temperature=0.3,
        max_tokens=2048,
    )


def query_paper(vectorstore: PaperVectorStore, question: str) -> dict:
    """
    RAG 问答主流程 v2：
    1. FAISS 粗筛 top-20
    2. Reranker 精排 top-4
    3. 拼接上下文 → LLM 生成回答
    返回: {"answer": str, "sources": [...]}
    """
    # 1. FAISS 粗筛
    candidates = vectorstore.search(question)
    if not candidates:
        return {"answer": "未找到相关内容，请尝试换个问法。", "sources": []}

    # 2. Reranker 精排
    from rag.reranker import rerank
    relevant_chunks = rerank(question, candidates)

    if not relevant_chunks:
        return {"answer": "未找到相关内容，请尝试换个问法。", "sources": []}

    # 3. 拼接上下文，同时把来源与页码显式提供给 LLM。
    #    如果只传文本而不传页码，模型无法可靠地生成 [第X页] 引用。
    context_blocks = []
    for chunk in relevant_chunks:
        page = chunk.get("page")
        page_label = f"第{page}页" if page else "页码未知"
        context_blocks.append(
            f"[来源: {chunk['source']}，{page_label}]\n{chunk['text']}"
        )
    context = "\n\n---\n\n".join(context_blocks)

    prompt = ChatPromptTemplate.from_messages([
        ("system", (
            "你是一个专业的学术论文分析助手。\n"
            "请严格根据以下论文内容回答用户问题。\n"
            "如果论文内容中没有相关信息，请如实说明，不要编造。\n"
            "回答时请标注引用来源的页码（如 [第X页]）。\n\n"
            "【论文相关内容】\n{context}"
        )),
        ("human", "{question}"),
    ])

    llm = create_llm()
    chain = prompt | llm | StrOutputParser()
    answer = chain.invoke({"context": context, "question": question})

    return {
        "answer": answer,
        "sources": [
            {
                "text": c["text"][:300] + "...",
                "score": c.get("reranker_score", c["score"]),
                "source": c["source"],
                "page": c.get("page"),
            }
            for c in relevant_chunks
        ],
    }


# ============================================================
#  文档处理流水线 v2（支持页码追踪）
# ============================================================

def process_documents(pdf_dir: str = None) -> tuple:
    """
    完整处理流程 v2：
    PDF → 按页提取 → 切块（带页码） → Embedding → FAISS

    返回: (vectorstore, stats)
    """
    from rag.pdf_loader import load_pdfs_from_dir_with_pages

    pdf_dir = pdf_dir or config.DATA_DIR

    # 1. 加载 PDF（按页）
    print("[1/4] 加载 PDF 文件...")
    documents = load_pdfs_from_dir_with_pages(pdf_dir)
    if not documents:
        raise FileNotFoundError(f"在 {pdf_dir} 下未找到 PDF 文件。")

    # 2. 按页切块（保留页码）
    print("[2/4] 文本切块（含页码追踪）...")
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=config.CHUNK_SIZE,
        chunk_overlap=config.CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    all_chunks = []
    all_metadata = []
    for doc in documents:
        for page_info in doc["pages"]:
            page_num = page_info["page"]
            page_text = page_info["text"]
            chunks = splitter.split_text(page_text)
            for chunk in chunks:
                all_chunks.append(chunk)
                all_metadata.append({
                    "source": doc["name"],
                    "page": page_num,
                })

    print(f"      共切分为 {len(all_chunks)} 个文本块")

    # 3. Embedding + FAISS
    print("[3/4] 生成 Embedding 并构建向量库...")
    embeddings = get_embeddings()
    vectorstore = PaperVectorStore.from_texts(all_chunks, all_metadata, embeddings)

    # 4. 统计
    stats = {
        "num_documents": len(documents),
        "num_chunks": len(all_chunks),
        "embedding_dim": embeddings.dimension if hasattr(embeddings, "dimension") else "N/A",
    }
    print(f"[4/4] 完成!  {stats['num_documents']} 篇论文, {stats['num_chunks']} 个文本块")

    return vectorstore, stats
