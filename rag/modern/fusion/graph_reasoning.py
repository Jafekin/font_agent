"""GraphRAG图推理模块 - 在元数据关系图上做多跳检索."""

import logging
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, Any, List, Tuple


logger = logging.getLogger(__name__)


@dataclass
class GraphHit:
    """图检索命中结果."""

    doc_id: str
    score: float
    hop: int
    reason: str
    metadata: Dict[str, Any]


class GraphReasoning:
    """基于属性图的轻量GraphRAG推理器.

    说明:
    - 节点: 文献页 (doc_id)
    - 边: 共享 edition_type/dynasty/institution/volume_number
    - 查询: 先做种子打分，再进行多跳扩散
    """

    EDGE_WEIGHTS = {
        "edition_type": 0.45,
        "dynasty": 0.30,
        "institution": 0.25,
        "volume_number": 0.15,
    }

    QUERY_MATCH_WEIGHTS = {
        "edition_type": 0.50,
        "dynasty": 0.35,
        "institution": 0.25,
        "volume_number": 0.15,
    }

    def __init__(self, max_hops: int = 2, decay: float = 0.6):
        self.max_hops = max_hops
        self.decay = decay
        self._metadata_by_id: Dict[str, Dict[str, Any]] = {}
        self._graph: Dict[str, List[Tuple[str, float, str]]
                          ] = defaultdict(list)

    def build_graph(self, records: List[Dict[str, Any]]) -> None:
        """从索引元数据构建图结构.

        Args:
            records: [{"doc_id": str, "metadata": {...}}, ...]
        """
        self._metadata_by_id = {}
        self._graph = defaultdict(list)

        for item in records:
            doc_id = item.get("doc_id")
            metadata = item.get("metadata", {})
            if not doc_id:
                continue
            self._metadata_by_id[doc_id] = metadata

        buckets: Dict[Tuple[str, str], List[str]] = defaultdict(list)
        for doc_id, metadata in self._metadata_by_id.items():
            for field in self.EDGE_WEIGHTS:
                value = metadata.get(field)
                if value is None or value == "":
                    continue
                buckets[(field, str(value))].append(doc_id)

        for (field, _), doc_ids in buckets.items():
            weight = self.EDGE_WEIGHTS[field]
            reason = f"共享{field}"
            for i in range(len(doc_ids)):
                for j in range(i + 1, len(doc_ids)):
                    left = doc_ids[i]
                    right = doc_ids[j]
                    self._graph[left].append((right, weight, reason))
                    self._graph[right].append((left, weight, reason))

        logger.info("GraphRAG建图完成: nodes=%d", len(self._metadata_by_id))

    def query(self, query_metadata: Dict[str, Any], top_k: int = 20) -> List[GraphHit]:
        """执行图检索.

        Args:
            query_metadata: 查询元数据
            top_k: 返回数量
        """
        if not query_metadata or not self._metadata_by_id:
            return []

        seed_scores: Dict[str, float] = {}
        seed_reasons: Dict[str, str] = {}

        for doc_id, metadata in self._metadata_by_id.items():
            score = 0.0
            reasons: List[str] = []

            for field, w in self.QUERY_MATCH_WEIGHTS.items():
                qv = query_metadata.get(field)
                mv = metadata.get(field)
                if qv is None or qv == "" or mv is None or mv == "":
                    continue
                if str(qv) == str(mv):
                    score += w
                    reasons.append(f"{field}匹配")

            if score > 0:
                seed_scores[doc_id] = score
                seed_reasons[doc_id] = "、".join(reasons)

        if not seed_scores:
            return []

        ranked_seed_ids = sorted(
            seed_scores, key=seed_scores.get, reverse=True)
        ranked_seed_ids = ranked_seed_ids[: min(30, len(ranked_seed_ids))]

        best_score: Dict[str, float] = dict(seed_scores)
        best_hop: Dict[str, int] = {doc_id: 0 for doc_id in seed_scores}
        best_reason: Dict[str, str] = dict(seed_reasons)
        frontier: List[Tuple[str, float, int]] = [
            (doc_id, seed_scores[doc_id], 0) for doc_id in ranked_seed_ids
        ]

        while frontier:
            current_id, current_score, current_hop = frontier.pop(0)
            if current_hop >= self.max_hops:
                continue

            for neighbor_id, edge_weight, edge_reason in self._graph.get(current_id, []):
                propagated = current_score * edge_weight * \
                    (self.decay ** (current_hop + 1))
                if propagated <= 0:
                    continue

                prev = best_score.get(neighbor_id, 0.0)
                if propagated > prev:
                    best_score[neighbor_id] = propagated
                    best_hop[neighbor_id] = current_hop + 1
                    best_reason[neighbor_id] = edge_reason
                    frontier.append((neighbor_id, propagated, current_hop + 1))

        hits: List[GraphHit] = []
        for doc_id, score in best_score.items():
            hits.append(
                GraphHit(
                    doc_id=doc_id,
                    score=float(score),
                    hop=best_hop.get(doc_id, 0),
                    reason=best_reason.get(doc_id, "图关系推断"),
                    metadata=self._metadata_by_id.get(doc_id, {}),
                )
            )

        hits.sort(key=lambda x: x.score, reverse=True)
        return hits[:top_k]
