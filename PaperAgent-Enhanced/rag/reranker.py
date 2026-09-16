"""
Reranker 重排序模块（v2 新增）
两阶段检索：FAISS 粗筛 top-N → CrossEncoder 精排 top-K

原理：
  - FAISS 用的是"双编码器"（bi-encoder），query 和 doc 分别编码再算相似度，速度快但精度一般
  - Reranker 用的是"交叉编码器"（cross-encoder），把 query 和 doc 拼在一起送进模型打分，精度高但慢
  - 所以先用 FAISS 快速筛出 20 个候选，再用 Reranker 精排出最好的 4 个
"""
import config

# 全局单例，避免重复加载模型
_reranker_model = None


def get_reranker():
    """获取或加载 Reranker 模型（单例模式）"""
    global _reranker_model
    if _reranker_model is None:
        from sentence_transformers import CrossEncoder
        print(f"  加载 Reranker 模型: {config.RERANKER_MODEL}")
        _reranker_model = CrossEncoder(config.RERANKER_MODEL)
        print("  Reranker 加载完成")
    return _reranker_model


def rerank(query: str, candidates: list[dict]) -> list[dict]:
    """
    对候选文本进行重排序。

    参数:
        query: 用户问题
        candidates: FAISS 粗筛结果列表
            [{"text": "...", "score": 0.8, "source": "...", "page": 3}, ...]

    返回:
        重排后的列表，按相关性从高到低，保留 top-K 条
    """
    if not candidates:
        return []

    if not config.RERANKER_ENABLED:
        # 未启用 Reranker，直接截断返回
        return candidates[: config.RERANKER_TOP_N]

    model = get_reranker()

    # 构造 query-document 对
    pairs = [[query, c["text"]] for c in candidates]

    # CrossEncoder outputs may be uncalibrated logits, not probabilities.
    scores = model.predict(pairs)

    # 把 Reranker 分数写回候选列表
    for i, score in enumerate(scores):
        candidates[i]["reranker_score"] = float(score)

    # 按 reranker_score 降序排列
    candidates.sort(key=lambda x: x["reranker_score"], reverse=True)

    # 保留 top-K
    return candidates[: config.RERANKER_TOP_N]
