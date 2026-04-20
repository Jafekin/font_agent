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
import re
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

    @staticmethod
    def _join_nonempty(parts: List[str], sep: str = "，") -> str:
        return sep.join(p for p in parts if p)

    @staticmethod
    def _dedupe_keep_order(items: List[str]) -> List[str]:
        seen = set()
        result = []
        for item in items:
            if not item or item in seen:
                continue
            seen.add(item)
            result.append(item)
        return result

    def _summarize_records(
        self,
        query: Dict[str, Any],
        records: List[Dict[str, Any]],
    ) -> Optional[str]:
        """将检索到的页面元数据压缩为一个可评估的答案摘要。"""
        if not records:
            query_text = (query.get("query_text") or "").strip()
            if query_text:
                return f"该页与《史记》中“{query_text}”相关。"
            image_path = (query.get("query_image") or "").strip()
            if image_path:
                return "该图对应《史记》中的相关页面。"
            return None

        title = next((r.get("title", "") for r in records if r.get("title")), "《史记》")
        topics = self._dedupe_keep_order([r.get("topic", "") for r in records if r.get("topic")])
        version_types = self._dedupe_keep_order([r.get("version_type", "") for r in records if r.get("version_type")])
        annotation_systems = self._dedupe_keep_order(
            [r.get("annotation_system", "") for r in records if r.get("annotation_system")]
        )
        dynasties = self._dedupe_keep_order([r.get("dynasty", "") for r in records if r.get("dynasty")])
        institutions = self._dedupe_keep_order(
            [r.get("holding_institution", "") for r in records if r.get("holding_institution")]
        )
        authors = self._dedupe_keep_order([r.get("authors", "") for r in records if r.get("authors")])
        annotators = self._dedupe_keep_order([r.get("annotators", "") for r in records if r.get("annotators")])
        printers = self._dedupe_keep_order([r.get("printer", "") for r in records if r.get("printer")])

        count = len(records)
        query_text = (query.get("query_text") or "").strip()

        intro_target = "相关页"
        if topics:
            intro_target = f"{'、'.join(topics)}相关页"
        elif query_text:
            intro_target = f"与“{query_text}”相关的页面"

        intro = "该页" if count == 1 else f"{count}页"
        pieces = [f"{intro}为{title}{intro_target}"]

        if version_types or annotation_systems:
            edition_desc = self._join_nonempty([
                f"{'、'.join(version_types)}类版本" if version_types else "",
                "、".join(annotation_systems) if annotation_systems else "",
            ])
            if edition_desc:
                pieces.append(f"属{edition_desc}")

        author_desc = self._join_nonempty([
            "、".join(authors) if authors else "",
            f"{'、'.join(annotators)}注" if annotators else "",
        ])
        if author_desc:
            pieces.append(author_desc)

        if dynasties:
            pieces.append(f"时代信息为{'、'.join(dynasties)}")
        if printers:
            pieces.append(f"刻本信息含{'、'.join(printers)}")
        if institutions:
            pieces.append(f"{'、'.join(institutions)}藏")

        return "，".join(pieces) + "。"

    @staticmethod
    def _extract_topic_from_text(text: str) -> str:
        if not text:
            return ""
        for marker in ("本页文字节选:", "OCR预览:", "ocr_text:"):
            if marker in text:
                text = text.split(marker, 1)[1]
                break
        text = " ".join(text.split())
        for pattern in (
            r"([^\s，。；：]{1,20}(?:本紀|本纪|列傳|列传|世家|書|书|表))",
            r"(五帝本紀第[^\s，。；：]{0,4})",
            r"(五帝纪[^\s，。；：]{0,4})",
        ):
            match = re.search(pattern, text)
            if match:
                return match.group(1)
        return text[:20]

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

    def _generate(self, query: Dict[str, Any], retrieved_ids: List[str]) -> Optional[str]:
        records: List[Dict[str, Any]] = []
        for pid in retrieved_ids[: self.k]:
            meta = self._meta.get(pid, {})
            if not meta:
                continue
            records.append({
                "title": "《史记》",
                "topic": self._extract_topic_from_text(meta.get("text_info", "")),
                "version_type": meta.get("version_type", ""),
                "annotation_system": meta.get("annotation_system", ""),
                "dynasty": meta.get("dynasty_period", ""),
                "holding_institution": meta.get("holding_institution", ""),
                "authors": meta.get("authors", ""),
                "annotators": meta.get("annotators", ""),
                "printer": meta.get("printer", ""),
            })
        return self._summarize_records(query, records)


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

    def _generate(self, query: Dict[str, Any], retrieved_ids: List[str]) -> Optional[str]:
        if not retrieved_ids:
            return None
        try:
            rows = self._client.query(
                """
                UNWIND $ids AS pid
                MATCH (p:Page {page_id: pid})
                OPTIONAL MATCH (e:Edition)-[:HAS_PAGE]->(p)
                OPTIONAL MATCH (d:Document)-[:HAS_EDITION]->(e)
                OPTIONAL MATCH (d)-[:STORED_IN]->(c:Collection)
                RETURN pid,
                       p.ocr_text AS ocr_text,
                       d.title AS title,
                       d.authors AS authors,
                       d.annotators AS annotators,
                       e.version_type AS version_type,
                       e.annotation_system AS annotation_system,
                       e.dynasty AS dynasty,
                       e.printer AS printer,
                       c.institution AS holding_institution
                """,
                {"ids": retrieved_ids[: self.k]},
            )
        except Exception as exc:
            logger.warning("生成答案时拉取图谱元数据失败：%s", exc)
            return None

        rows_by_id = {r["pid"]: r for r in rows if r.get("pid")}
        records: List[Dict[str, Any]] = []
        for pid in retrieved_ids[: self.k]:
            row = rows_by_id.get(pid)
            if not row:
                continue
            records.append({
                "title": row.get("title") or "《史记》",
                "topic": self._extract_topic_from_text(row.get("ocr_text") or ""),
                "version_type": row.get("version_type") or "",
                "annotation_system": row.get("annotation_system") or "",
                "dynasty": row.get("dynasty") or "",
                "holding_institution": row.get("holding_institution") or "",
                "authors": row.get("authors") or "",
                "annotators": row.get("annotators") or "",
                "printer": row.get("printer") or "",
            })
        return self._summarize_records(query, records)


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

    def _generate(self, query: Dict[str, Any], retrieved_ids: List[str]) -> Optional[str]:
        if not retrieved_ids:
            return None
        try:
            rows = self._client.query(
                """
                UNWIND $ids AS pid
                MATCH (p:Page {page_id: pid})
                OPTIONAL MATCH (e:Edition)-[:HAS_PAGE]->(p)
                OPTIONAL MATCH (d:Document)-[:HAS_EDITION]->(e)
                OPTIONAL MATCH (d)-[:STORED_IN]->(c:Collection)
                RETURN pid,
                       p.ocr_text AS ocr_text,
                       d.title AS title,
                       d.authors AS authors,
                       d.annotators AS annotators,
                       e.version_type AS version_type,
                       e.annotation_system AS annotation_system,
                       e.dynasty AS dynasty,
                       e.printer AS printer,
                       c.institution AS holding_institution
                """,
                {"ids": retrieved_ids[: self.k]},
            )
        except Exception as exc:
            logger.warning("生成答案时拉取混合检索元数据失败：%s", exc)
            return None

        rows_by_id = {r["pid"]: r for r in rows if r.get("pid")}
        records: List[Dict[str, Any]] = []
        for pid in retrieved_ids[: self.k]:
            row = rows_by_id.get(pid)
            if not row:
                continue
            records.append({
                "title": row.get("title") or "《史记》",
                "topic": self._extract_topic_from_text(row.get("ocr_text") or ""),
                "version_type": row.get("version_type") or "",
                "annotation_system": row.get("annotation_system") or "",
                "dynasty": row.get("dynasty") or "",
                "holding_institution": row.get("holding_institution") or "",
                "authors": row.get("authors") or "",
                "annotators": row.get("annotators") or "",
                "printer": row.get("printer") or "",
            })
        return self._summarize_records(query, records)
