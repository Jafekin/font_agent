"""轻量检索器：直接读取 numpy 索引，支持图片/文本相似度搜索。"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from rag.embeddings import get_image_embedding, get_text_embedding, MODEL_NAME

# 配置日志
logger = logging.getLogger(__name__)

_FAKE_MODE = os.getenv("RAG_FAKE_EMBEDDINGS") == "1"
_IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff")


class TxtaiRetriever:
    """兼容旧名称的检索器，但内部已改为 numpy + Chinese-CLIP。"""

    def __init__(self, index_path: str | None = None, *, model: str | None = None) -> None:
        self.index_path = Path(index_path) if index_path else None
        self.model = model or MODEL_NAME
        self.metadata_store: Dict[str, Dict[str, Any]] = {}
        self.doc_ids: List[str] = []
        self.embeddings: Optional[np.ndarray] = None
        self.dimension: Optional[int] = None
        self.config: Dict[str, Any] = {}

        if _FAKE_MODE:
            logger.warning("RAG_FAKE_EMBEDDINGS=1，检索器将返回伪造结果。")
            return

        if not self.index_path:
            logger.warning("未提供 index_path，将使用假结果。")
            return

        self._load_numpy_index(self.index_path)

    # ------------------------------------------------------------------
    # 索引加载
    # ------------------------------------------------------------------
    def _load_numpy_index(self, base_path: Path) -> None:
        emb_path = base_path / "embeddings.npy"
        ids_path = base_path / "ids.json"
        metadata_path = base_path / "metadata.json"
        config_path = base_path / "config.json"

        missing = [p.name for p in (
            emb_path, ids_path, metadata_path) if not p.exists()]
        if missing:
            logger.warning("索引文件缺失: %s", ", ".join(missing))
            return

        try:
            embeddings = np.load(emb_path)
        except Exception as exc:  # pragma: no cover - IO 错误
            logger.error("无法加载 embeddings.npy: %s", exc)
            return

        if embeddings.ndim != 2:
            logger.error("embeddings.npy 维度异常: %s", embeddings.shape)
            return

        self.embeddings = embeddings.astype("float32", copy=False)
        norms = np.linalg.norm(self.embeddings, axis=1, keepdims=True)
        norms[norms == 0] = 1
        self.embeddings = self.embeddings / norms
        self.dimension = int(self.embeddings.shape[1])

        with open(ids_path, "r", encoding="utf-8") as f:
            ids = json.load(f)
        if not isinstance(ids, list):
            logger.error("ids.json 格式错误，应为列表。")
            self.embeddings = None
            return

        if len(ids) != len(self.embeddings):
            logger.error("ids 数量 (%d) 与向量数量 (%d) 不匹配。",
                         len(ids), len(self.embeddings))
            self.embeddings = None
            return

        self.doc_ids = [str(doc_id) for doc_id in ids]

        with open(metadata_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)
        if isinstance(metadata, dict):
            self.metadata_store = metadata
        else:
            logger.warning("metadata.json 格式异常，期望字典。")
            self.metadata_store = {}

        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    self.config = json.load(f) or {}
            except Exception:  # pragma: no cover - 非关键字段
                logger.debug("读取 config.json 失败", exc_info=True)

        logger.info("已加载 numpy 索引: %s，共 %d 条", base_path, len(self.doc_ids))

    # ------------------------------------------------------------------
    # 内部辅助方法
    # ------------------------------------------------------------------
    @staticmethod
    def _fake_results(k: int, with_content: bool = True, seed: int = 42) -> List[Dict[str, Any]]:
        """生成假结果（用于测试）"""
        import numpy as np
        rng = np.random.default_rng(seed)
        results = []
        for i in range(k):
            results.append({
                "id": f"fake-{i}",
                "score": float(1.0 - i * 0.05),
                "content": f"假结果内容{i}" if with_content and i % 2 == 0 else "",
                "text_info": f"假文字信息{i}",
                "image_path": f"fake_image_{i}.jpg",
                "metadata": {
                    "filename": f"fake_image_{i}.jpg",
                    "type": "image"
                }
            })
        return results

    def _build_result(self, doc_id: str, score: float) -> Dict[str, Any]:
        metadata = self.metadata_store.get(doc_id, {}).copy()
        text_info = metadata.get("text_info", "")
        image_path = metadata.get("image_path", "")
        content = text_info or image_path or metadata.get("filename", doc_id)
        result = {
            "id": doc_id,
            "score": float(score),
            "text_info": text_info,
            "image_path": image_path,
            "metadata": metadata,
            "content": content,
        }
        if metadata.get("type") == "text":
            result["related_image_id"] = metadata.get("related_image_id", "")
        return result

    # ------------------------------------------------------------------
    # 公共API
    # ------------------------------------------------------------------
    def search(
        self,
        query: str,
        k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        语义搜索（支持文本或图片路径）

        Args:
            query: 查询文本或图片路径
            k: 返回top-k结果
            filters: 元数据过滤条件（txtai支持SQL-like过滤）

        Returns:
            搜索结果列表，每个结果包含：
            - id: 文档ID
            - score: 相似度分数
            - content: 原始内容（图片路径或文字）
            - text_info: 图片对应的文字信息
            - image_path: 图片路径
            - metadata: 元数据
        """
        if not query:
            raise ValueError("query必须非空")

        if not query:
            raise ValueError("query必须非空")

        if _FAKE_MODE or self.embeddings is None:
            return self._fake_results(k, seed=abs(hash(query)) % (2**32))

        is_image = os.path.exists(
            query) and query.lower().endswith(_IMAGE_EXTENSIONS)
        try:
            if is_image:
                vector = get_image_embedding(query)
            else:
                vector = get_text_embedding(query)
        except Exception as exc:
            logger.error("生成查询向量失败: %s", exc)
            return self._fake_results(k)

        return self.search_by_vector(vector, k=k, filters=filters)

    def search_by_vector(
        self,
        query_vector: List[float],
        k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        向量相似度搜索

        Args:
            query_vector: 预计算的查询向量
            k: 返回top-k结果

        Returns:
            搜索结果列表
        """
        if not query_vector:
            raise ValueError("query_vector必须非空")

        if _FAKE_MODE or self.embeddings is None:
            return self._fake_results(k, seed=len(query_vector))

        query = np.asarray(query_vector, dtype="float32")
        norm = np.linalg.norm(query)
        if norm == 0:
            logger.warning("查询向量范数为0，返回假结果。")
            return self._fake_results(k)
        query /= norm

        scores = self.embeddings @ query
        order = np.argsort(scores)[::-1]

        results: List[Dict[str, Any]] = []
        for idx in order:
            doc_id = self.doc_ids[idx]
            meta = self.metadata_store.get(doc_id, {})
            if filters and not self._matches_filters(meta, filters):
                continue
            results.append(self._build_result(doc_id, float(scores[idx])))
            if len(results) >= k:
                break

        if not results:
            logger.warning("未命中任何结果，返回假结果。")
            return self._fake_results(k)
        return results

    def search_by_image(
        self,
        image_path: str,
        k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        通过图片路径搜索相似图片

        Args:
            image_path: 查询图片路径
            k: 返回top-k结果
            filters: 元数据过滤条件

        Returns:
            搜索结果列表，每个结果包含对应的文字信息
        """
        if not image_path or not os.path.exists(image_path):
            raise ValueError(f"图片不存在: {image_path}")

        if _FAKE_MODE or self.embeddings is None:
            return self._fake_results(k, seed=abs(hash(image_path)) % (2**32))

        try:
            vector = get_image_embedding(image_path)
        except Exception as exc:
            logger.error("图片编码失败: %s", exc)
            return self._fake_results(k)

        return self.search_by_vector(vector, k=k, filters=filters)

    def batchsearch(
        self,
        queries: List[str],
        k: int = 5
    ) -> List[List[Dict[str, Any]]]:
        """
        批量搜索

        Args:
            queries: 查询列表（文本或图片路径）
            k: 每个查询返回top-k结果

        Returns:
            每个查询的结果列表
        """
        if not queries:
            raise ValueError("queries必须非空列表")

        results: List[List[Dict[str, Any]]] = []
        for q in queries:
            results.append(self.search(q, k=k))
        return results

    def cite(
        self,
        answer_text: str,
        k: int = 3
    ) -> List[Dict[str, Any]]:
        """
        为答案生成引用候选（将答案文本搜索回索引）

        Args:
            answer_text: 答案文本
            k: 返回top-k引用

        Returns:
            引用候选列表
        """
        if not answer_text:
            return []
        return self.search(answer_text, k=k)

    def _apply_filters(
        self,
        results: List[Dict[str, Any]],
        filters: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        应用元数据过滤

        Args:
            results: 搜索结果
            filters: 过滤条件

        Returns:
            过滤后的结果
        """
        filtered = []
        for result in results:
            metadata = result.get("metadata", {})
            if self._matches_filters(metadata, filters):
                filtered.append(result)
        return filtered

    @staticmethod
    def _matches_filters(metadata: Dict[str, Any], filters: Dict[str, Any]) -> bool:
        for key, value in filters.items():
            if metadata.get(key) != value:
                return False
        return True

    def is_ready(self) -> bool:
        """返回True如果真实的索引已加载（非假模式）"""
        return not _FAKE_MODE and self.embeddings is not None


# 向后兼容别名
class FaissRetriever(TxtaiRetriever):
    """已弃用的名称，保留用于向后兼容"""
    pass
