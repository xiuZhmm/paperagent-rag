"""
PaperAgent 配置文件
所有可调参数集中管理，通过 .env 文件或环境变量覆盖
"""
import os
from dotenv import load_dotenv

load_dotenv()


# ==================== LLM 配置 ====================
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.siliconflow.cn/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "Qwen/Qwen3.6-35B-A3B")

# ==================== Embedding 配置 ====================
# 方式一（推荐）：API 模式，无需下载模型，需要 SiliconFlow API Key
# 方式二：local 模式，使用本地 sentence-transformers，需下载模型
EMBEDDING_SOURCE = os.getenv("EMBEDDING_SOURCE", "local")  # "api" 或 "local"
FASTEMBED_MODEL_DIR = os.getenv('FASTEMBED_MODEL_DIR', os.path.join(os.path.dirname(__file__),'.cache','models','fast-all-MiniLM-L6-v2'))

# API 模式配置（SiliconFlow）
EMBEDDING_API_KEY = os.getenv("EMBEDDING_API_KEY", "")
EMBEDDING_API_BASE = os.getenv(
    "EMBEDDING_API_BASE", "https://api.siliconflow.cn/v1/embeddings"
)
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")

# 本地模式配置
LOCAL_EMBEDDING_MODEL = os.getenv("LOCAL_EMBEDDING_MODEL", "all-MiniLM-L6-v2")

# ==================== Reranker 配置 ====================
RERANKER_ENABLED = os.getenv("RERANKER_ENABLED", "true").lower() == "true"
RERANKER_MODEL = os.getenv("RERANKER_MODEL", "BAAI/bge-reranker-v2-m3")
RERANKER_TOP_N = int(os.getenv("RERANKER_TOP_N", "4"))      # 重排后保留几条
RERANKER_CANDIDATES = int(os.getenv("RERANKER_CANDIDATES", "20"))  # FAISS 粗筛几条

# ==================== RAG 参数 ====================
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "500"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "100"))
TOP_K = int(os.getenv("TOP_K", "4"))
RETRIEVAL_MODE = os.getenv('RETRIEVAL_MODE', 'dense')
HYBRID_DENSE_WEIGHT = float(os.getenv('HYBRID_DENSE_WEIGHT', '0.5'))
HYBRID_POOL = int(os.getenv('HYBRID_POOL', '100'))

# ==================== 路径 ====================
DATA_DIR = os.getenv("DATA_DIR", "data/papers")
