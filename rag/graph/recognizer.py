"""图片识别接口：OCR → NaiveRAG → GraphRAG → 融合打分 → 结构化结果。

流程：
  1. OCR 识别图片文本
  2. NaiveRAG：图片向量检索 + OCR 文本检索，得到候选页面及得分
  3. GraphRAG：以 NaiveRAG 结果为种子做 BFS 混合检索，同时对 OCR 文本做全文检索
  4. 融合打分：对三路得分加权求和，归一化后排序
  5. 从 Neo4j 拉取 Top-K 页面的完整结构化信息（Document/Edition/Collection/Page/Layout/Entity）
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# 默认融合权重（三路之和应为 1.0）
_DEFAULT_WEIGHTS = {
    "naive": 0.70,       # NaiveRAG 图片+文本向量检索
    "graph_hybrid": 0.20, # GraphRAG BFS 混合检索
    "graph_text": 0.10,  # GraphRAG 全文检索
}


# ---------------------------------------------------------------------------
# 结果数据类
# ---------------------------------------------------------------------------

@dataclass
class ScoreBreakdown:
    naive: float = 0.0
    graph_hybrid: float = 0.0
    graph_text: float = 0.0
    final: float = 0.0


@dataclass
class RecognitionResult:
    """单页识别结果，包含完整图谱结构化信息。"""
    page_id: str
    score: ScoreBreakdown
    ocr_text: str                          # 本次 OCR 识别文本
    page: Dict[str, Any] = field(default_factory=dict)
    edition: Dict[str, Any] = field(default_factory=dict)
    document: Dict[str, Any] = field(default_factory=dict)
    collection: Dict[str, Any] = field(default_factory=dict)
    layout: Dict[str, Any] = field(default_factory=dict)
    entities: List[Dict[str, Any]] = field(default_factory=list)
    evidence: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# 主类
# ---------------------------------------------------------------------------

class ImageRecognizer:
    """
    图片识别接口，串联 OCR、NaiveRAG、GraphRAG 三个模块。

    Args:
        neo4j_client:  已连接的 Neo4jClient 实例（必须）
        index_path:    NaiveRAG 索引目录（可选，缺失时跳过向量检索）
        ocr_client:    KandiangujiOCRClient 实例（可选，缺失时跳过 OCR）
        weights:       融合权重字典，键为 naive/graph_hybrid/graph_text
    """

    def __init__(
        self,
        neo4j_client,
        index_path: Optional[str | Path] = None,
        ocr_client=None,
        weights: Optional[Dict[str, float]] = None,
    ) -> None:
        self.client = neo4j_client
        self.ocr_client = ocr_client
        self.weights = {**_DEFAULT_WEIGHTS, **(weights or {})}

        # 惰性初始化 NaiveRAG 检索器
        self._retriever = None
        if index_path:
            try:
                from rag.naive.retriever import TxtaiRetriever
                self._retriever = TxtaiRetriever(str(index_path))
                if not self._retriever.is_ready():
                    logger.warning("NaiveRAG 索引未就绪，向量检索将被跳过。")
                    self._retriever = None
            except Exception as exc:
                logger.warning("NaiveRAG 检索器初始化失败：%s", exc)
                self._retriever = None

        from rag.graph.retriever import GraphRetriever
        self._graph = GraphRetriever(neo4j_client)

    # ------------------------------------------------------------------
    # 公共接口
    # ------------------------------------------------------------------

    def recognize(
        self,
        image_path: str | Path,
        top_k: int = 5,
        naive_k: int = 8,
        bfs_depth: int = 1,
        text_limit: int = 8,
    ) -> List[RecognitionResult]:
        """
        对图片执行完整识别流程。

        Args:
            image_path:  图片路径
            top_k:       最终返回结果数
            naive_k:     NaiveRAG 每路检索数量
            bfs_depth:   GraphRAG BFS 扩展深度
            text_limit:  GraphRAG 全文检索数量

        Returns:
            按综合得分降序排列的 RecognitionResult 列表
        """
        image_path = Path(image_path)

        # 1. OCR
        ocr_text = self._run_ocr(image_path)

        # 2. NaiveRAG 检索 → {page_id: score}
        naive_scores = self._run_naive(image_path, ocr_text, k=naive_k)

        # 3. GraphRAG 检索
        graph_hybrid_scores, graph_text_scores = self._run_graph(
            naive_scores, ocr_text, bfs_depth=bfs_depth, text_limit=text_limit
        )

        # 4. 融合打分
        fused = self._fuse(naive_scores, graph_hybrid_scores, graph_text_scores)

        # 5. 取 Top-K，拉取完整元数据
        top_ids = sorted(fused, key=lambda x: fused[x].final, reverse=True)[:top_k]
        return self._build_results(top_ids, fused, ocr_text, naive_scores,
                                   graph_hybrid_scores, graph_text_scores)

    # ------------------------------------------------------------------
    # 内部步骤
    # ------------------------------------------------------------------

    def _run_ocr(self, image_path: Path) -> str:
        """调用 OCR 客户端识别图片，返回全文文本。"""
        if self.ocr_client is None:
            logger.debug("OCR 客户端未配置，跳过 OCR。")
            return ""
        try:
            result = self.ocr_client.recognize_image(str(image_path))
            text = result.get_full_text() if hasattr(result, "get_full_text") else ""
            logger.info("OCR 完成，识别字符数：%d", len(text))
            return text
        except Exception as exc:
            logger.warning("OCR 失败：%s", exc)
            return ""

    def _run_naive(
        self, image_path: Path, ocr_text: str, k: int
    ) -> Dict[str, float]:
        """NaiveRAG 图片向量检索 + 文本向量检索，返回 {page_id: max_score}。"""
        if self._retriever is None:
            return {}

        scores: Dict[str, float] = {}

        # 图片向量检索
        try:
            for r in self._retriever.search_by_image(str(image_path), k=k):
                pid = r.get("id", "")
                if pid:
                    scores[pid] = max(scores.get(pid, 0.0), float(r.get("score", 0.0)))
        except Exception as exc:
            logger.warning("NaiveRAG 图片检索失败：%s", exc)

        # OCR 文本向量检索
        if ocr_text.strip():
            try:
                for r in self._retriever.search(ocr_text, k=k):
                    pid = r.get("id", "")
                    if pid:
                        scores[pid] = max(scores.get(pid, 0.0), float(r.get("score", 0.0)))
            except Exception as exc:
                logger.warning("NaiveRAG 文本检索失败：%s", exc)

        logger.info("NaiveRAG 候选页面数：%d", len(scores))
        return scores

    def _run_graph(
        self,
        naive_scores: Dict[str, float],
        ocr_text: str,
        bfs_depth: int,
        text_limit: int,
    ) -> Tuple[Dict[str, float], Dict[str, float]]:
        """GraphRAG 混合检索 + 全文检索，返回两路 {page_id: score}。"""
        hybrid_scores: Dict[str, float] = {}
        text_scores: Dict[str, float] = {}

        # BFS 混合检索（以 NaiveRAG 结果为种子）
        if naive_scores:
            seeds = list(naive_scores.items())
            try:
                for r in self._graph.hybrid_search(seeds, bfs_depth=bfs_depth, top_k=50):
                    hybrid_scores[r.page_id] = max(
                        hybrid_scores.get(r.page_id, 0.0), r.score
                    )
            except Exception as exc:
                logger.warning("GraphRAG 混合检索失败：%s", exc)

        # 全文检索
        if ocr_text.strip():
            try:
                for r in self._graph.search_by_text(ocr_text, limit=text_limit):
                    text_scores[r.page_id] = max(
                        text_scores.get(r.page_id, 0.0), r.score
                    )
            except Exception as exc:
                logger.warning("GraphRAG 全文检索失败：%s", exc)

        logger.info(
            "GraphRAG 混合候选：%d，全文候选：%d",
            len(hybrid_scores), len(text_scores),
        )
        return hybrid_scores, text_scores

    def _fuse(
        self,
        naive: Dict[str, float],
        hybrid: Dict[str, float],
        text: Dict[str, float],
    ) -> Dict[str, ScoreBreakdown]:
        """三路得分归一化后加权融合。"""
        all_ids = set(naive) | set(hybrid) | set(text)
        if not all_ids:
            return {}

        def _norm(d: Dict[str, float]) -> Dict[str, float]:
            if not d:
                return {}
            mx = max(d.values())
            return {k: v / mx for k, v in d.items()} if mx > 0 else d

        n_naive = _norm(naive)
        n_hybrid = _norm(hybrid)
        n_text = _norm(text)

        w = self.weights
        result: Dict[str, ScoreBreakdown] = {}
        for pid in all_ids:
            s = ScoreBreakdown(
                naive=n_naive.get(pid, 0.0),
                graph_hybrid=n_hybrid.get(pid, 0.0),
                graph_text=n_text.get(pid, 0.0),
            )
            s.final = (
                s.naive * w["naive"]
                + s.graph_hybrid * w["graph_hybrid"]
                + s.graph_text * w["graph_text"]
            )
            result[pid] = s
        return result

    def _build_results(
        self,
        page_ids: List[str],
        fused: Dict[str, ScoreBreakdown],
        ocr_text: str,
        naive_scores: Dict[str, float],
        hybrid_scores: Dict[str, float],
        text_scores: Dict[str, float],
    ) -> List[RecognitionResult]:
        """批量拉取图谱元数据，组装最终结果。"""
        results = []
        for pid in page_ids:
            meta = self._fetch_full_meta(pid)
            evidence = self._build_evidence(
                pid, naive_scores, hybrid_scores, text_scores
            )
            results.append(RecognitionResult(
                page_id=pid,
                score=fused[pid],
                ocr_text=ocr_text,
                page=meta.get("page") or {},
                edition=meta.get("edition") or {},
                document=meta.get("document") or {},
                collection=meta.get("collection") or {},
                layout=meta.get("layout") or {},
                entities=meta.get("entities") or [],
                evidence=evidence,
            ))
        return results

    def _fetch_full_meta(self, page_id: str) -> Dict[str, Any]:
        """从 Neo4j 拉取页面完整结构化信息。"""
        try:
            rows = self.client.query(
                """
                MATCH (p:Page {page_id: $pid})
                OPTIONAL MATCH (e:Edition)-[:HAS_PAGE]->(p)
                OPTIONAL MATCH (d:Document)-[:HAS_EDITION]->(e)
                OPTIONAL MATCH (d)-[:STORED_IN]->(c:Collection)
                OPTIONAL MATCH (p)-[:HAS_LAYOUT]->(l:Layout)
                RETURN p, e, d, c, l
                """,
                {"pid": page_id},
            )
            if not rows:
                return {}
            r = rows[0]
            base = {
                "page": dict(r["p"]) if r.get("p") else {},
                "edition": dict(r["e"]) if r.get("e") else {},
                "document": dict(r["d"]) if r.get("d") else {},
                "collection": dict(r["c"]) if r.get("c") else {},
                "layout": dict(r["l"]) if r.get("l") else {},
            }
        except Exception as exc:
            logger.warning("拉取页面元数据失败 %s：%s", page_id, exc)
            return {}

        # 实体列表
        try:
            ent_rows = self.client.query(
                """
                MATCH (p:Page {page_id: $pid})-[:MENTIONS]->(ent:Entity)
                RETURN ent.entity_text AS text, ent.entity_type AS type
                """,
                {"pid": page_id},
            )
            base["entities"] = [
                {"text": r["text"], "type": r["type"]} for r in ent_rows
            ]
        except Exception as exc:
            logger.warning("拉取实体失败 %s：%s", page_id, exc)
            base["entities"] = []

        return base

    @staticmethod
    def _build_evidence(
        pid: str,
        naive: Dict[str, float],
        hybrid: Dict[str, float],
        text: Dict[str, float],
    ) -> List[str]:
        ev = []
        if pid in naive:
            ev.append(f"NaiveRAG 向量相似度 {naive[pid]:.4f}")
        if pid in hybrid:
            ev.append(f"GraphRAG BFS 得分 {hybrid[pid]:.4f}")
        if pid in text:
            ev.append(f"GraphRAG 全文得分 {text[pid]:.4f}")
        return ev
