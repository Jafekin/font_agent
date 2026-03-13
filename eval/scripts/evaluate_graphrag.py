"""
GraphRAG 评估脚本 - 测试各项 RAG 指标.
"""

from rag.graph import GraphQueryInterface, GraphRetriever, Neo4jClient
import argparse
import json
import logging
import math
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# ================= 数据模型 =================


@dataclass
class RetrievalResult:
    query_id: str
    retrieved_ids: List[str]
    scores: List[float]
    ground_truth: List[str]
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EvaluationMetrics:
    precision_at_k: Dict[int, float] = field(default_factory=dict)
    recall_at_k: Dict[int, float] = field(default_factory=dict)
    f1_at_k: Dict[int, float] = field(default_factory=dict)
    ndcg_at_k: Dict[int, float] = field(default_factory=dict)
    hit_rate_at_k: Dict[int, float] = field(default_factory=dict)

    mrr: float = 0.0

    entity_relation_accuracy: float = 0.0
    edition_inference_accuracy: float = 0.0
    multi_hop_accuracy: float = 0.0

    total_queries: int = 0
    avg_path_length: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "precision_at_k": self.precision_at_k,
            "recall_at_k": self.recall_at_k,
            "f1_at_k": self.f1_at_k,
            "ndcg_at_k": self.ndcg_at_k,
            "hit_rate_at_k": self.hit_rate_at_k,
            "mrr": self.mrr,
            "entity_relation_accuracy": self.entity_relation_accuracy,
            "edition_inference_accuracy": self.edition_inference_accuracy,
            "multi_hop_accuracy": self.multi_hop_accuracy,
            "total_queries": self.total_queries,
            "avg_path_length": self.avg_path_length,
        }


# ================= 评估器 =================


class GraphRAGEvaluator:
    def __init__(self, neo4j_client: Neo4jClient, k_values: List[int] = None):
        self.client = neo4j_client
        self.retriever = GraphRetriever(neo4j_client)
        self.query_interface = GraphQueryInterface(neo4j_client)
        self.k_values = k_values or [1, 3, 5, 10]

    # -------- Precision --------

    def precision_at_k(self, retrieved: List[str], gt: Set[str], k: int) -> float:
        if k == 0:
            return 0.0
        retrieved = retrieved[:k]
        return sum(1 for r in retrieved if r in gt) / k

    def recall_at_k(self, retrieved: List[str], gt: Set[str], k: int) -> float:
        if not gt:
            return 0.0
        retrieved = retrieved[:k]
        return sum(1 for r in retrieved if r in gt) / len(gt)

    def f1_at_k(self, retrieved: List[str], gt: Set[str], k: int) -> float:
        p = self.precision_at_k(retrieved, gt, k)
        r = self.recall_at_k(retrieved, gt, k)
        if p + r == 0:
            return 0.0
        return 2 * p * r / (p + r)

    def mrr(self, retrieved: List[str], gt: Set[str]) -> float:
        for i, r in enumerate(retrieved, 1):
            if r in gt:
                return 1 / i
        return 0.0

    def ndcg_at_k(self, retrieved: List[str], gt: Set[str], k: int) -> float:
        dcg = 0.0
        for i, r in enumerate(retrieved[:k], 1):
            if r in gt:
                dcg += 1 / math.log2(i + 1)

        idcg = sum(
            1 / math.log2(i + 1)
            for i in range(1, min(len(gt), k) + 1)
        )

        if idcg == 0:
            return 0.0

        return dcg / idcg

    def hit_rate(self, retrieved: List[str], gt: Set[str], k: int) -> float:
        return 1.0 if set(retrieved[:k]) & gt else 0.0

    # -------- 主评估 --------

    def evaluate_retrieval_results(
        self,
        results: List[RetrievalResult],
    ) -> EvaluationMetrics:

        metrics = EvaluationMetrics()
        metrics.total_queries = len(results)

        if not results:
            return metrics

        precision_sum = defaultdict(float)
        recall_sum = defaultdict(float)
        f1_sum = defaultdict(float)
        ndcg_sum = defaultdict(float)
        hit_sum = defaultdict(float)
        mrr_sum = 0.0

        for r in results:
            gt = set(r.ground_truth)

            mrr_sum += self.mrr(r.retrieved_ids, gt)

            for k in self.k_values:
                precision_sum[k] += self.precision_at_k(r.retrieved_ids, gt, k)
                recall_sum[k] += self.recall_at_k(r.retrieved_ids, gt, k)
                f1_sum[k] += self.f1_at_k(r.retrieved_ids, gt, k)
                ndcg_sum[k] += self.ndcg_at_k(r.retrieved_ids, gt, k)
                hit_sum[k] += self.hit_rate(r.retrieved_ids, gt, k)

        n = len(results)

        metrics.mrr = mrr_sum / n

        for k in self.k_values:
            metrics.precision_at_k[k] = precision_sum[k] / n
            metrics.recall_at_k[k] = recall_sum[k] / n
            metrics.f1_at_k[k] = f1_sum[k] / n
            metrics.ndcg_at_k[k] = ndcg_sum[k] / n
            metrics.hit_rate_at_k[k] = hit_sum[k] / n

        return metrics

    def evaluate_edition_inference(
        self,
        test_cases: List[Dict[str, Any]],
    ) -> float:
        """评估版本推断准确率."""
        if not test_cases:
            return 0.0

        correct = 0
        for case in test_cases:
            page_id = case.get("page_id")
            expected = (case.get("expected_edition") or "").strip()

            if not page_id or not expected:
                continue

            query = """
            MATCH (p:Page {page_id: $page_id})-[:BELONGS_TO_EDITION]->(e:Edition)
            RETURN e.edition_name AS edition_name
            LIMIT 1
            """
            rows = self.client.execute_query(query, {"page_id": page_id})

            if not rows:
                continue

            actual = (rows[0].get("edition_name") or "").strip()
            if actual == expected:
                correct += 1

        return correct / len(test_cases)

    def evaluate_entity_relations(
        self,
        test_cases: List[Dict[str, Any]],
    ) -> float:
        """评估实体关系判断准确率."""
        if not test_cases:
            return 0.0

        correct = 0
        for case in test_cases:
            entity1 = case.get("entity1")
            entity2 = case.get("entity2")
            expected = bool(case.get("expected_relation", False))

            if not entity1 or not entity2:
                continue

            query = """
            MATCH (e1:Entity {entity_text: $entity1})-[r]-(e2:Entity {entity_text: $entity2})
            RETURN COUNT(r) > 0 AS has_relation
            """
            rows = self.client.execute_query(
                query,
                {"entity1": entity1, "entity2": entity2},
            )
            has_relation = bool(rows[0].get("has_relation", False)) if rows else False

            if has_relation == expected:
                correct += 1

        return correct / len(test_cases)


# ================= 检索评估 =================


def run_retrieval_evaluation(
    evaluator: GraphRAGEvaluator,
    test_queries: List[Dict[str, Any]],
) -> List[RetrievalResult]:

    results = []

    for q in test_queries:

        query_id = q["query_id"]
        text = q["query_text"]
        gt = q["ground_truth"]

        logger.info(f"评估查询 {query_id}: {text}")

        try:
            search = evaluator.query_interface.fulltext_search(text, limit=10)

            retrieved = [r["page_id"] for r in search]
            scores = [r["score"] for r in search]

            results.append(
                RetrievalResult(
                    query_id=query_id,
                    retrieved_ids=retrieved,
                    scores=scores,
                    ground_truth=gt,
                )
            )

        except Exception as e:
            logger.error(f"查询失败 {query_id}: {e}")

    return results


# ================= 报告 =================


def generate_evaluation_report(metrics: EvaluationMetrics, output: Path):

    report = []

    report.append("=" * 70)
    report.append("GraphRAG 评估报告")
    report.append("=" * 70)
    report.append(f"时间: {datetime.now()}")
    report.append(f"查询数: {metrics.total_queries}")
    report.append("")

    report.append(f"MRR: {metrics.mrr:.4f}")

    for k in metrics.precision_at_k:

        report.append("")
        report.append(f"K = {k}")
        report.append(f"Precision@{k}: {metrics.precision_at_k[k]:.4f}")
        report.append(f"Recall@{k}: {metrics.recall_at_k[k]:.4f}")
        report.append(f"F1@{k}: {metrics.f1_at_k[k]:.4f}")
        report.append(f"NDCG@{k}: {metrics.ndcg_at_k[k]:.4f}")
        report.append(f"Hit@{k}: {metrics.hit_rate_at_k[k]:.4f}")

    report_text = "\n".join(report)

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report_text, encoding="utf-8")

    print(report_text)


# ================= 主函数 =================


def main():

    parser = argparse.ArgumentParser()

    parser.add_argument("--neo4j-uri", default="bolt://localhost:7687")
    parser.add_argument("--neo4j-user", default="neo4j")
    parser.add_argument("--neo4j-password", default="password")

    parser.add_argument("--test-data", type=Path)

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("evaluation_results"),
    )

    args = parser.parse_args()

    if args.test_data:
        test_data = json.loads(args.test_data.read_text())
    else:
        raise RuntimeError("必须提供测试数据")

    client = Neo4jClient(
        uri=args.neo4j_uri,
        username=args.neo4j_user,
        password=args.neo4j_password,
    )

    evaluator = GraphRAGEvaluator(client)

    results = run_retrieval_evaluation(
        evaluator,
        test_data["retrieval_queries"],
    )

    metrics = evaluator.evaluate_retrieval_results(results)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    report_path = args.output_dir / f"evaluation_report_{ts}.txt"

    generate_evaluation_report(metrics, report_path)

    json_path = args.output_dir / f"evaluation_metrics_{ts}.json"
    json_path.write_text(
        json.dumps(metrics.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    logger.info("评估完成")

    client.close()


if __name__ == "__main__":
    main()
