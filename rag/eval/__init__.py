"""rag.eval — RAG 系统评估模块。"""

from .metrics import (
    RetrievalMetrics,
    GenerationMetrics,
    compute_retrieval_metrics,
    compute_generation_metrics,
    aggregate_retrieval_metrics,
    aggregate_generation_metrics,
)
from .evaluator import (
    NaiveRAGEvaluator,
    GraphRAGEvaluator,
    HybridEvaluator,
    EvalReport,
    QueryEvalResult,
)

__all__ = [
    "RetrievalMetrics",
    "GenerationMetrics",
    "compute_retrieval_metrics",
    "compute_generation_metrics",
    "aggregate_retrieval_metrics",
    "aggregate_generation_metrics",
    "NaiveRAGEvaluator",
    "GraphRAGEvaluator",
    "HybridEvaluator",
    "EvalReport",
    "QueryEvalResult",
]
