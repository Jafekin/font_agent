"""
GraphRAG 评估模块测试

测试评估脚本的各个组件是否正常工作。
"""

from scripts.evaluate_graphrag import (
    EvaluationMetrics,
    GraphRAGEvaluator,
    RetrievalResult,
)
import sys
from pathlib import Path

import pytest

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestEvaluationMetrics:
    """测试评估指标计算."""

    def test_precision_at_k(self):
        """测试 Precision@K 计算."""
        retrieved = ["doc1", "doc2", "doc3", "doc4", "doc5"]
        ground_truth = {"doc1", "doc3", "doc5"}

        # 模拟评估器（不需要真实的 Neo4j 连接）
        class MockClient:
            pass

        evaluator = GraphRAGEvaluator(MockClient())

        # K=3: 3 个结果中有 2 个相关
        precision = evaluator.calculate_precision_at_k(
            retrieved, ground_truth, 3)
        assert abs(precision - 2 / 3) < 0.001

        # K=5: 5 个结果中有 3 个相关
        precision = evaluator.calculate_precision_at_k(
            retrieved, ground_truth, 5)
        assert abs(precision - 3 / 5) < 0.001

    def test_recall_at_k(self):
        """测试 Recall@K 计算."""
        retrieved = ["doc1", "doc2", "doc3", "doc4", "doc5"]
        ground_truth = {"doc1", "doc3", "doc5", "doc6", "doc7"}

        class MockClient:
            pass

        evaluator = GraphRAGEvaluator(MockClient())

        # K=3: 检索到 2 个，总共 5 个相关
        recall = evaluator.calculate_recall_at_k(retrieved, ground_truth, 3)
        assert abs(recall - 2 / 5) < 0.001

        # K=5: 检索到 3 个，总共 5 个相关
        recall = evaluator.calculate_recall_at_k(retrieved, ground_truth, 5)
        assert abs(recall - 3 / 5) < 0.001

    def test_f1_at_k(self):
        """测试 F1@K 计算."""
        retrieved = ["doc1", "doc2", "doc3"]
        ground_truth = {"doc1", "doc3", "doc4"}

        class MockClient:
            pass

        evaluator = GraphRAGEvaluator(MockClient())

        # Precision = 2/3, Recall = 2/3, F1 = 2/3
        f1 = evaluator.calculate_f1_at_k(retrieved, ground_truth, 3)
        assert abs(f1 - 2 / 3) < 0.001

    def test_mrr(self):
        """测试 MRR 计算."""

        class MockClient:
            pass

        evaluator = GraphRAGEvaluator(MockClient())

        # 第一个结果就相关
        retrieved = ["doc1", "doc2", "doc3"]
        ground_truth = {"doc1"}
        mrr = evaluator.calculate_mrr(retrieved, ground_truth)
        assert abs(mrr - 1.0) < 0.001

        # 第三个结果相关
        retrieved = ["doc1", "doc2", "doc3"]
        ground_truth = {"doc3"}
        mrr = evaluator.calculate_mrr(retrieved, ground_truth)
        assert abs(mrr - 1 / 3) < 0.001

        # 没有相关结果
        retrieved = ["doc1", "doc2", "doc3"]
        ground_truth = {"doc4"}
        mrr = evaluator.calculate_mrr(retrieved, ground_truth)
        assert abs(mrr - 0.0) < 0.001

    def test_ndcg_at_k(self):
        """测试 NDCG@K 计算."""

        class MockClient:
            pass

        evaluator = GraphRAGEvaluator(MockClient())

        # 理想情况：所有相关文档都在前面
        retrieved = ["doc1", "doc2", "doc3"]
        ground_truth = {"doc1", "doc2", "doc3"}
        ndcg = evaluator.calculate_ndcg_at_k(retrieved, ground_truth, 3)
        assert abs(ndcg - 1.0) < 0.001

        # 最差情况：所有相关文档都不在结果中
        retrieved = ["doc4", "doc5", "doc6"]
        ground_truth = {"doc1", "doc2", "doc3"}
        ndcg = evaluator.calculate_ndcg_at_k(retrieved, ground_truth, 3)
        assert abs(ndcg - 0.0) < 0.001

    def test_hit_rate_at_k(self):
        """测试 Hit Rate@K 计算."""

        class MockClient:
            pass

        evaluator = GraphRAGEvaluator(MockClient())

        # 有命中
        retrieved = ["doc1", "doc2", "doc3"]
        ground_truth = {"doc2"}
        hit_rate = evaluator.calculate_hit_rate_at_k(
            retrieved, ground_truth, 3)
        assert abs(hit_rate - 1.0) < 0.001

        # 没有命中
        retrieved = ["doc1", "doc2", "doc3"]
        ground_truth = {"doc4"}
        hit_rate = evaluator.calculate_hit_rate_at_k(
            retrieved, ground_truth, 3)
        assert abs(hit_rate - 0.0) < 0.001


class TestRetrievalResult:
    """测试检索结果数据结构."""

    def test_retrieval_result_creation(self):
        """测试创建检索结果."""
        result = RetrievalResult(
            query_id="q1",
            retrieved_ids=["doc1", "doc2", "doc3"],
            scores=[0.9, 0.8, 0.7],
            ground_truth=["doc1", "doc3"],
            metadata={"query_type": "fulltext"},
        )

        assert result.query_id == "q1"
        assert len(result.retrieved_ids) == 3
        assert len(result.scores) == 3
        assert len(result.ground_truth) == 2
        assert result.metadata["query_type"] == "fulltext"


class TestEvaluationMetricsAggregation:
    """测试评估指标聚合."""

    def test_evaluate_retrieval_results(self):
        """测试批量评估检索结果."""

        class MockClient:
            pass

        evaluator = GraphRAGEvaluator(MockClient(), k_values=[1, 3, 5])

        results = [
            RetrievalResult(
                query_id="q1",
                retrieved_ids=["doc1", "doc2", "doc3"],
                scores=[0.9, 0.8, 0.7],
                ground_truth=["doc1", "doc3"],
            ),
            RetrievalResult(
                query_id="q2",
                retrieved_ids=["doc4", "doc5", "doc6"],
                scores=[0.95, 0.85, 0.75],
                ground_truth=["doc4", "doc5"],
            ),
        ]

        metrics = evaluator.evaluate_retrieval_results(results)

        assert metrics.total_queries == 2
        assert metrics.mrr > 0
        assert 1 in metrics.precision_at_k
        assert 3 in metrics.precision_at_k
        assert 5 in metrics.precision_at_k


class TestEvaluationMetricsToDict:
    """测试评估指标序列化."""

    def test_metrics_to_dict(self):
        """测试指标转换为字典."""
        metrics = EvaluationMetrics()
        metrics.precision_at_k = {1: 0.8, 5: 0.6}
        metrics.recall_at_k = {1: 0.3, 5: 0.7}
        metrics.mrr = 0.75
        metrics.total_queries = 10

        result = metrics.to_dict()

        assert isinstance(result, dict)
        assert result["mrr"] == 0.75
        assert result["total_queries"] == 10
        assert result["precision_at_k"][1] == 0.8
        assert result["recall_at_k"][5] == 0.7


def test_imports():
    """测试所有必要的导入."""
    from scripts.evaluate_graphrag import (
        EvaluationMetrics,
        GraphRAGEvaluator,
        RetrievalResult,
        TestQuery,
        generate_sample_test_data,
    )

    assert EvaluationMetrics is not None
    assert GraphRAGEvaluator is not None
    assert RetrievalResult is not None
    assert TestQuery is not None
    assert generate_sample_test_data is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
