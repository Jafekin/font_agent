"""Cross-Attention融合模块 - 动态加权多源证据."""

import logging
from typing import List, Dict, Any, Optional
import numpy as np

logger = logging.getLogger(__name__)


class AttentionFusion:
    """使用Cross-Attention机制融合多源检索结果."""

    def __init__(self, temperature: float = 0.1):
        """初始化融合器.

        Args:
            temperature: softmax温度参数，控制注意力分布的平滑度
        """
        self.temperature = temperature
        logger.info(f"初始化AttentionFusion (temperature={temperature})")

    def compute_attention_scores(
        self,
        query_embedding: np.ndarray,
        context_embeddings: List[np.ndarray],
    ) -> np.ndarray:
        """计算注意力分数.

        Args:
            query_embedding: 查询向量 (d,)
            context_embeddings: 上下文向量列表 [(d,), ...]

        Returns:
            注意力权重 (n,)
        """
        if not context_embeddings:
            return np.array([])

        # 归一化 query
        query_norm = query_embedding / (np.linalg.norm(query_embedding) + 1e-8)

        similarities = []
        for ctx_emb in context_embeddings:
            ctx_norm = ctx_emb / (np.linalg.norm(ctx_emb) + 1e-8)
            sim = np.dot(query_norm, ctx_norm)
            similarities.append(sim)

        similarities = np.array(similarities)

        # Softmax with temperature
        exp_scores = np.exp(similarities / self.temperature)
        attention_weights = exp_scores / (np.sum(exp_scores) + 1e-8)

        return attention_weights

    def fuse_retrieval_results(
        self,
        query_embedding: np.ndarray,
        retrieval_results: List[Dict[str, Any]],
        base_weights: Optional[Dict[str, float]] = None,
    ) -> List[Dict[str, Any]]:
        """融合多路检索结果.

        Args:
            query_embedding: 查询向量
            retrieval_results: 检索结果列表
            base_weights: 基础权重 {source: weight}

        Returns:
            融合后的结果列表
        """
        if not retrieval_results:
            return []

        # 默认基础权重
        if base_weights is None:
            base_weights = {"vector": 0.4, "text": 0.3, "graph": 0.3}

        # 提取上下文 embedding
        context_embeddings = []
        for result in retrieval_results:
            emb = result.get("embedding")

            if emb is not None:
                context_embeddings.append(emb)
            else:
                context_embeddings.append(np.zeros_like(query_embedding))

        # 计算注意力
        attention_weights = self.compute_attention_scores(
            query_embedding, context_embeddings
        )

        fused_results = []

        for i, result in enumerate(retrieval_results):
            source = result.get("source", "unknown")
            base_weight = base_weights.get(source, 0.3)

            attention_weight = (
                attention_weights[i] if i < len(attention_weights) else 0.0
            )

            original_score = result.get("score", 0.0)

            # 融合公式
            fused_score = base_weight * original_score + 0.3 * attention_weight

            fused_result = result.copy()
            fused_result["fused_score"] = float(fused_score)
            fused_result["attention_weight"] = float(attention_weight)
            fused_result["original_score"] = original_score

            fused_results.append(fused_result)

        # 排序
        fused_results.sort(key=lambda x: x["fused_score"], reverse=True)

        logger.info(f"融合完成: {len(fused_results)} 条结果")

        return fused_results

    def compute_context_vector(
        self,
        query_embedding: np.ndarray,
        context_embeddings: List[np.ndarray],
    ) -> np.ndarray:
        """计算加权上下文向量.

        Args:
            query_embedding: 查询向量
            context_embeddings: 上下文向量列表

        Returns:
            加权上下文向量
        """
        if not context_embeddings:
            return np.zeros_like(query_embedding)

        attention_weights = self.compute_attention_scores(
            query_embedding, context_embeddings
        )

        context_vector = np.zeros_like(query_embedding)

        for i, ctx_emb in enumerate(context_embeddings):
            if i < len(attention_weights):
                context_vector += attention_weights[i] * ctx_emb

        return context_vector


def main():
    """测试示例."""

    fusion = AttentionFusion(temperature=0.1)

    # 模拟 query embedding
    query_emb = np.random.randn(512)
    query_emb = query_emb / np.linalg.norm(query_emb)

    results = [
        {
            "doc_id": "doc1",
            "score": 0.85,
            "source": "vector",
            "embedding": np.random.randn(512),
        },
        {
            "doc_id": "doc2",
            "score": 0.75,
            "source": "text",
            "embedding": np.random.randn(512),
        },
        {
            "doc_id": "doc3",
            "score": 0.65,
            "source": "graph",
            "embedding": np.random.randn(512),
        },
    ]

    # 归一化 embedding
    for r in results:
        r["embedding"] = r["embedding"] / np.linalg.norm(r["embedding"])

    fused = fusion.fuse_retrieval_results(query_emb, results)

    print("融合结果:")
    for r in fused:
        print(
            f"  {r['doc_id']}: 原始={r['original_score']:.3f}, "
            f"注意力={r['attention_weight']:.3f}, 融合={r['fused_score']:.3f}"
        )


if __name__ == "__main__":
    main()
