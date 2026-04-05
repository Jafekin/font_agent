"""混合检索器 - 融合向量、文本、图谱三路检索."""
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
import numpy as np
from dataclasses import dataclass

from ..fusion import GraphReasoning

logger = logging.getLogger(__name__)


@dataclass
class RetrievalResult:
    """检索结果."""
    doc_id: str
    score: float
    source: str  # vector, text, graph
    metadata: Dict[str, Any]
    image_path: Optional[str] = None
    ocr_text: Optional[str] = None


class HybridRetriever:
    """混合检索器，融合多路检索结果."""

    def __init__(
        self,
        index_dir: Path,
        vector_weight: float = 0.4,
        text_weight: float = 0.3,
        graph_weight: float = 0.3
    ):
        """初始化混合检索器.

        Args:
            index_dir: 索引目录
            vector_weight: 向量检索权重
            text_weight: 文本检索权重
            graph_weight: 图谱检索权重
        """
        self.index_dir = Path(index_dir)
        self.vector_weight = vector_weight
        self.text_weight = text_weight
        self.graph_weight = graph_weight

        # 延迟加载各个检索器
        self._vector_index = None
        self._text_index = None
        self._graph_client = None
        self._graph_reasoner = None

        logger.info(
            f"初始化混合检索器: vector={vector_weight}, text={text_weight}, graph={graph_weight}")

    def _load_vector_index(self):
        """加载向量索引."""
        if self._vector_index is not None:
            return

        import json

        embeddings_path = self.index_dir / "embeddings.npy"
        ids_path = self.index_dir / "ids.json"
        metadata_path = self.index_dir / "metadata.json"

        if not embeddings_path.exists():
            logger.warning("向量索引不存在，跳过向量检索")
            return

        with open(ids_path, "r", encoding="utf-8") as f:
            ids = json.load(f)
        with open(metadata_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)

        self._vector_index = {
            "embeddings": np.load(embeddings_path),
            "ids": ids,
            "metadata": metadata,
        }

        # 归一化
        norms = np.linalg.norm(
            self._vector_index["embeddings"], axis=1, keepdims=True)
        norms[norms == 0] = 1
        self._vector_index["embeddings"] = self._vector_index["embeddings"] / norms

        # 构建GraphRAG关系图（基于索引元数据）
        records = [
            {"doc_id": doc_id, "metadata": meta}
            for doc_id, meta in zip(self._vector_index["ids"], self._vector_index["metadata"])
        ]
        self._graph_reasoner = GraphReasoning(max_hops=2, decay=0.6)
        self._graph_reasoner.build_graph(records)

        logger.info(f"加载向量索引: {len(self._vector_index['ids'])} 条记录")

    def retrieve_by_vector(
        self,
        query_embedding: np.ndarray,
        top_k: int = 50,
        threshold: float = 0.7
    ) -> List[RetrievalResult]:
        """向量检索.

        Args:
            query_embedding: 查询向量
            top_k: 返回前K个结果
            threshold: 相似度阈值

        Returns:
            检索结果列表
        """
        self._load_vector_index()

        if self._vector_index is None:
            return []

        # 归一化查询向量
        query_embedding = query_embedding / np.linalg.norm(query_embedding)

        # 计算相似度
        similarities = np.dot(
            self._vector_index["embeddings"], query_embedding)

        # 获取Top-K
        top_indices = np.argsort(similarities)[::-1][:top_k]

        results = []
        for idx in top_indices:
            score = float(similarities[idx])
            if score < threshold:
                continue

            doc_id = self._vector_index["ids"][idx]
            metadata = self._vector_index["metadata"][idx]

            results.append(RetrievalResult(
                doc_id=doc_id,
                score=score,
                source="vector",
                metadata=metadata,
                image_path=metadata.get("image_path"),
                ocr_text=metadata.get("text_info")
            ))

        logger.info(f"向量检索返回 {len(results)} 条结果")
        return results

    def retrieve_by_text(
        self,
        query_text: str,
        top_k: int = 30
    ) -> List[RetrievalResult]:
        """文本检索（BM25）.

        Args:
            query_text: 查询文本
            top_k: 返回前K个结果

        Returns:
            检索结果列表
        """
        # 简化实现：基于关键词匹配
        self._load_vector_index()

        if self._vector_index is None:
            return []

        results = []
        query_chars = set(query_text)

        for idx, metadata in enumerate(self._vector_index["metadata"]):
            text_info = metadata.get("text_info", "")
            if not text_info:
                continue

            # 计算字符重叠度
            text_chars = set(text_info)
            overlap = len(query_chars & text_chars)
            score = overlap / max(len(query_chars), 1)

            if score > 0:
                results.append(RetrievalResult(
                    doc_id=self._vector_index["ids"][idx],
                    score=score,
                    source="text",
                    metadata=metadata,
                    image_path=metadata.get("image_path"),
                    ocr_text=text_info
                ))

        # 排序并返回Top-K
        results.sort(key=lambda x: x.score, reverse=True)
        results = results[:top_k]

        logger.info(f"文本检索返回 {len(results)} 条结果")
        return results

    def retrieve_by_graph(
        self,
        query_metadata: Dict[str, Any],
        top_k: int = 20
    ) -> List[RetrievalResult]:
        """图谱检索（基于版本关系）.

        Args:
            query_metadata: 查询元数据（版本类型、时代等）
            top_k: 返回前K个结果

        Returns:
            检索结果列表
        """
        self._load_vector_index()

        if self._vector_index is None or self._graph_reasoner is None:
            return []

        hits = self._graph_reasoner.query(query_metadata, top_k=top_k)
        results = [
            RetrievalResult(
                doc_id=hit.doc_id,
                score=hit.score,
                source="graph",
                metadata={**hit.metadata, "graph_reason": hit.reason,
                          "graph_hop": hit.hop},
                image_path=hit.metadata.get("image_path"),
                ocr_text=hit.metadata.get("text_info"),
            )
            for hit in hits
        ]

        logger.info(f"图谱检索返回 {len(results)} 条结果")
        return results

    def hybrid_retrieve(
        self,
        query_embedding: Optional[np.ndarray] = None,
        query_text: Optional[str] = None,
        query_metadata: Optional[Dict[str, Any]] = None,
        top_k: int = 10
    ) -> List[RetrievalResult]:
        """混合检索，融合三路结果.

        Args:
            query_embedding: 查询向量
            query_text: 查询文本
            query_metadata: 查询元数据
            top_k: 最终返回前K个结果

        Returns:
            融合后的检索结果
        """
        all_results = {}

        # 向量检索
        if query_embedding is not None:
            vector_results = self.retrieve_by_vector(query_embedding, top_k=50)
            for result in vector_results:
                if result.doc_id not in all_results:
                    all_results[result.doc_id] = result
                    result.score *= self.vector_weight
                else:
                    all_results[result.doc_id].score += result.score * \
                        self.vector_weight

        # 文本检索
        if query_text:
            text_results = self.retrieve_by_text(query_text, top_k=30)
            for result in text_results:
                if result.doc_id not in all_results:
                    all_results[result.doc_id] = result
                    result.score *= self.text_weight
                else:
                    all_results[result.doc_id].score += result.score * \
                        self.text_weight

        # 图谱检索
        if query_metadata:
            graph_results = self.retrieve_by_graph(query_metadata, top_k=20)
            for result in graph_results:
                if result.doc_id not in all_results:
                    all_results[result.doc_id] = result
                    result.score *= self.graph_weight
                else:
                    all_results[result.doc_id].score += result.score * \
                        self.graph_weight

        # 排序并返回Top-K
        final_results = sorted(all_results.values(),
                               key=lambda x: x.score, reverse=True)[:top_k]

        logger.info(f"混合检索返回 {len(final_results)} 条结果")
        return final_results

    def rerank(self, results: List[RetrievalResult], query_text: str) -> List[RetrievalResult]:
        """重排序（使用Cross-Encoder）.

        Args:
            results: 初步检索结果
            query_text: 查询文本

        Returns:
            重排序后的结果
        """
        # TODO: 实现Cross-Encoder重排序
        # 当前简单返回原结果
        return results
