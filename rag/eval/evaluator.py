"""RAG 系统评估器：对 NaiveRAG 和 GraphRAG 两路管道进行端到端评估。

Ground Truth 格式（JSON）：
[
  {
    "query_id": "q001",
    "query_text": "五帝本紀",          // 文本查询（可选）
    "query_image": "path/to/img.jpg",  // 图片查询（可选）
    "relevant_pages": ["page_001", "page_007"],  // 相关页面 ID
    "reference_answer": "..."          // 参考答案（用于生成指标，可选）
  }
]
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from rag.eval.metrics import (
    RetrievalMetrics,
    GenerationMetrics,
    compute_retrieval_metrics,
    compute_generation_metrics,
    aggregate_retrieval_metrics,
    aggregate_generation_metrics,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 结果数据类
# ---------------------------------------------------------------------------

@dataclass
class QueryEvalResult:
    query_id: str
    retrieval: RetrievalMetrics = field(default_factory=RetrievalMetrics)
    generation: Optional[GenerationMetrics] = None
    retrieved_ids: List[str] = field(default_factory=list)
    latency_ms: float = 0.0
    error: Optional[str] = None


@dataclass
class EvalReport:
    pipeline: str                          # "naive" | "graph" | "hybrid"
    k: int
    num_queries: int = 0
    retrieval: RetrievalMetrics = field(default_factory=RetrievalMetrics)
    generation: Optional[GenerationMetrics] = None
    avg_latency_ms: float = 0.0
    per_query: List[QueryEvalResult] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return d

    def print_summary(self) -> None:
        print(f"\n{'='*60}")
        print(f"Pipeline : {self.pipeline}  |  K={self.k}  |  Queries={self.num_queries}")
        print(f"{'─'*60}")
        r = self.retrieval
        print(f"检索指标（@{self.k}）")
        print(f"  Precision : {r.precision:.4f}")
        print(f"  Recall    : {r.recall:.4f}")
        print(f"  F1        : {r.f1:.4f}")
        print(f"  MRR       : {r.mrr:.4f}")
        print(f"  NDCG      : {r.ndcg:.4f}")
        print(f"  Hit Rate  : {r.hit_rate:.4f}")
        if self.generation:
            g = self.generation
            print(f"{'─'*60}")
            print("生成指标")
            print(f"  BLEU-1    : {g.bleu_1:.4f}")
            print(f"  BLEU-2    : {g.bleu_2:.4f}")
            print(f"  BLEU-4    : {g.bleu_4:.4f}")
            print(f"  ROUGE-1   : {g.rouge_1:.4f}")
            print(f"  ROUGE-2   : {g.rouge_2:.4f}")
            print(f"  ROUGE-L   : {g.rouge_l:.4f}")
            print(f"  Char-F1   : {g.char_f1:.4f}")
            print(f"  Exact Match: {g.exact_match:.4f}")
            print(f"  Relevance : {g.answer_relevance:.4f}")
            print(f"  Faithfulness: {g.faithfulness:.4f}")
        print(f"  Avg Latency: {self.avg_latency_ms:.1f} ms")
        print(f"{'='*60}\n")


# ---------------------------------------------------------------------------
# 基础评估器
# ---------------------------------------------------------------------------

class BaseEvaluator:
    """评估器基类，子类实现 _retrieve()。"""

    def __init__(self, k: int = 5) -> None:
        self.k = k

    def _retrieve(self, query: Dict[str, Any]) -> List[str]:
        """返回检索到的 page_id 列表（按相关性降序）。"""
        raise NotImplementedError

    def _generate(self, query: Dict[str, Any], retrieved_ids: List[str]) -> Optional[str]:
        """可选：返回生成的答案文本。"""
        return None

    def _get_contexts(self, retrieved_ids: List[str]) -> List[str]:
        """可选：返回检索到的文本上下文（用于 faithfulness）。"""
        return []

    def evaluate(self, ground_truth: List[Dict[str, Any]]) -> EvalReport:
        report = EvalReport(pipeline=self.__class__.__name__, k=self.k)
        retrieval_list: List[RetrievalMetrics] = []
        generation_list: List[GenerationMetrics] = []
        latencies: List[float] = []

        for item in ground_truth:
            qid = item.get("query_id", "?")
            relevant = set(item.get("relevant_pages", []))
            reference = item.get("reference_answer", "")

            t0 = time.perf_counter()
            try:
                retrieved = self._retrieve(item)
            except Exception as exc:
                logger.warning("检索失败 %s：%s", qid, exc)
                report.per_query.append(QueryEvalResult(query_id=qid, error=str(exc)))
                continue
            latency = (time.perf_counter() - t0) * 1000

            ret_metrics = compute_retrieval_metrics(retrieved, relevant, self.k)
            retrieval_list.append(ret_metrics)
            latencies.append(latency)

            gen_metrics = None
            if reference:
                answer = self._generate(item, retrieved)
                if answer:
                    contexts = self._get_contexts(retrieved)
                    gen_metrics = compute_generation_metrics(
                        hypothesis=answer,
                        reference=reference,
                        query=item.get("query_text", ""),
                        contexts=contexts,
                    )
                    generation_list.append(gen_metrics)

            report.per_query.append(QueryEvalResult(
                query_id=qid,
                retrieval=ret_metrics,
                generation=gen_metrics,
                retrieved_ids=retrieved,
                latency_ms=latency,
            ))

        report.num_queries = len(retrieval_list)
        report.retrieval = aggregate_retrieval_metrics(retrieval_list)
        if generation_list:
            report.generation = aggregate_generation_metrics(generation_list)
        report.avg_latency_ms = sum(latencies) / len(latencies) if latencies else 0.0
        return report


# ---------------------------------------------------------------------------
# NaiveRAG 评估器
# ---------------------------------------------------------------------------

class NaiveRAGEvaluator(BaseEvaluator):
    """评估 TxtaiRetriever 的检索质量。"""

    def __init__(self, index_path: str, k: int = 5) -> None:
        super().__init__(k)
        from rag.naive.retriever import TxtaiRetriever
        self.retriever = TxtaiRetriever(index_path)
        self._meta: Dict[str, Dict] = self.retriever.metadata_store

    def _retrieve(self, query: Dict[str, Any]) -> List[str]:
        image_path = query.get("query_image")
        query_text = query.get("query_text", "")

        scores: Dict[str, float] = {}

        if image_path and Path(image_path).exists():
            for r in self.retriever.search_by_image(image_path, k=self.k * 2):
                pid = r.get("id", "")
                if pid:
                    scores[pid] = max(scores.get(pid, 0.0), float(r.get("score", 0.0)))

        if query_text.strip():
            for r in self.retriever.search(query_text, k=self.k * 2):
                pid = r.get("id", "")
                if pid:
                    scores[pid] = max(scores.get(pid, 0.0), float(r.get("score", 0.0)))

        return sorted(scores, key=lambda x: scores[x], reverse=True)[: self.k]

    def _get_contexts(self, retrieved_ids: List[str]) -> List[str]:
        return [
            self._meta.get(pid, {}).get("text_info", "")
            for pid in retrieved_ids
            if self._meta.get(pid, {}).get("text_info")
        ]


# ---------------------------------------------------------------------------
# GraphRAG 评估器
# ---------------------------------------------------------------------------

class GraphRAGEvaluator(BaseEvaluator):
    """评估 GraphRetriever 的检索质量（需要 Neo4j 连接）。"""

    def __init__(self, neo4j_client, k: int = 5) -> None:
        super().__init__(k)
        from rag.graph.retriever import GraphRetriever
        self.retriever = GraphRetriever(neo4j_client)
        self._client = neo4j_client

    def _retrieve(self, query: Dict[str, Any]) -> List[str]:
        query_text = query.get("query_text", "")
        if not query_text.strip():
            return []
        results = self.retriever.search_by_text(query_text, limit=self.k)
        return [r.page_id for r in results]

    def _get_contexts(self, retrieved_ids: List[str]) -> List[str]:
        if not retrieved_ids:
            return []
        try:
            rows = self._client.query(
                "UNWIND $ids AS pid MATCH (p:Page {page_id: pid}) RETURN p.ocr_text AS t",
                {"ids": retrieved_ids},
            )
            return [r["t"] for r in rows if r.get("t")]
        except Exception:
            return []


# ---------------------------------------------------------------------------
# 混合评估器（NaiveRAG 种子 → GraphRAG BFS）
# ---------------------------------------------------------------------------

class HybridEvaluator(BaseEvaluator):
    """评估 ImageRecognizer 的端到端检索质量。"""

    def __init__(
        self,
        neo4j_client,
        index_path: str,
        k: int = 5,
        bfs_depth: int = 1,
    ) -> None:
        super().__init__(k)
        from rag.graph.recognizer import ImageRecognizer
        self.recognizer = ImageRecognizer(
            neo4j_client=neo4j_client,
            index_path=index_path,
        )
        self._client = neo4j_client
        self.bfs_depth = bfs_depth

    def _retrieve(self, query: Dict[str, Any]) -> List[str]:
        image_path = query.get("query_image")
        if not image_path or not Path(image_path).exists():
            return []
        results = self.recognizer.recognize(
            image_path=image_path,
            top_k=self.k,
            bfs_depth=self.bfs_depth,
        )
        return [r.page_id for r in results]

    def _get_contexts(self, retrieved_ids: List[str]) -> List[str]:
        if not retrieved_ids:
            return []
        try:
            rows = self._client.query(
                "UNWIND $ids AS pid MATCH (p:Page {page_id: pid}) RETURN p.ocr_text AS t",
                {"ids": retrieved_ids},
            )
            return [r["t"] for r in rows if r.get("t")]
        except Exception:
            return []
