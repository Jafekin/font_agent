"""GraphRAG 检索器：基于 Neo4j 图遍历的检索与查询接口。"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from .client import Neo4jClient

logger = logging.getLogger(__name__)

# 边类型语义权重（越高表示关联越强）
_EDGE_WEIGHTS: Dict[str, float] = {
    "SAME_EDITION": 1.0,    # 同版本前后页
    "MENTIONS_ENTITY": 0.7,  # 共享命名实体
    "SIMILAR_TO": 0.1,      # 版式视觉相似
}


@dataclass
class GraphSearchResult:
    """图检索结果。"""
    page_id: str
    score: float
    metadata: Dict[str, Any]
    evidence: List[str]  # 简洁的证据链描述


class GraphRetriever:
    """基于知识图谱的检索器，合并了原 retriever + query_interface 的核心功能。"""

    def __init__(self, client: Neo4jClient) -> None:
        self.client = client

    # ------------------------------------------------------------------
    # 基础检索
    # ------------------------------------------------------------------
    def get_page(self, page_id: str) -> Optional[Dict[str, Any]]:
        """按 page_id 获取页面及关联信息。"""
        rows = self.client.query(
            """
            MATCH (p:Page {page_id: $pid})
            OPTIONAL MATCH (e:Edition)-[:HAS_PAGE]->(p)
            OPTIONAL MATCH (d:Document)-[:HAS_EDITION]->(e)
            OPTIONAL MATCH (p)-[:HAS_LAYOUT]->(l:Layout)
            RETURN p, e, d, l
            """,
            {"pid": page_id},
        )
        if not rows:
            return None
        r = rows[0]
        return {"page": r.get("p"), "edition": r.get("e"),
                "document": r.get("d"), "layout": r.get("l")}

    def search_by_text(
        self, text: str, limit: int = 10
    ) -> List[GraphSearchResult]:
        """全文检索 OCR 文本（使用 Neo4j fulltext 索引）。"""
        rows = self.client.query(
            """
            CALL db.index.fulltext.queryNodes('page_ocr_idx', $text)
            YIELD node, score
            OPTIONAL MATCH (e:Edition)-[:HAS_PAGE]->(node)
            OPTIONAL MATCH (d:Document)-[:HAS_EDITION]->(e)
            RETURN node.page_id AS page_id, score,
                   node.ocr_text AS ocr_text,
                   e.version_type AS version_type,
                   d.title AS title
            ORDER BY score DESC LIMIT $limit
            """,
            {"text": text, "limit": limit},
        )
        return [
            GraphSearchResult(
                page_id=r["page_id"],
                score=r["score"],
                metadata={"title": r.get(
                    "title"), "version_type": r.get("version_type")},
                evidence=[f"全文匹配：得分 {r['score']:.3f}"],
            )
            for r in rows
        ]

    def find_similar(
        self, page_id: str, min_score: float = 0.85, limit: int = 10
    ) -> List[GraphSearchResult]:
        """通过 SIMILAR_TO 关系查找相似页面。"""
        rows = self.client.query(
            """
            MATCH (p:Page {page_id: $pid})-[r:SIMILAR_TO]->(p2:Page)
            WHERE r.score >= $min_score
            OPTIONAL MATCH (e:Edition)-[:HAS_PAGE]->(p2)
            RETURN p2.page_id AS page_id, r.score AS score,
                   e.version_type AS version_type
            ORDER BY r.score DESC LIMIT $limit
            """,
            {"pid": page_id, "min_score": min_score, "limit": limit},
        )
        return [
            GraphSearchResult(
                page_id=r["page_id"],
                score=r["score"],
                metadata={"version_type": r.get("version_type")},
                evidence=[f"视觉相似度 {r['score']:.3f}（来自 {page_id}）"],
            )
            for r in rows
        ]

    def find_by_edition(self, edition_id: str, limit: int = 100) -> List[GraphSearchResult]:
        """查找同一版本下的所有页面。"""
        rows = self.client.query(
            """
            MATCH (e:Edition {edition_id: $eid})-[:HAS_PAGE]->(p:Page)
            RETURN p.page_id AS page_id
            ORDER BY p.page_id LIMIT $limit
            """,
            {"eid": edition_id, "limit": limit},
        )
        return [
            GraphSearchResult(
                page_id=r["page_id"],
                score=1.0,
                metadata={"edition_id": edition_id},
                evidence=[f"同版本 {edition_id}"],
            )
            for r in rows
        ]

    def find_by_entity(self, entity_text: str, limit: int = 20) -> List[GraphSearchResult]:
        """查找提及某实体的所有页面。"""
        rows = self.client.query(
            """
            MATCH (p:Page)-[:MENTIONS]->(ent:Entity {entity_text: $et})
            OPTIONAL MATCH (e:Edition)-[:HAS_PAGE]->(p)
            RETURN p.page_id AS page_id, e.version_type AS version_type
            LIMIT $limit
            """,
            {"et": entity_text, "limit": limit},
        )
        return [
            GraphSearchResult(
                page_id=r["page_id"],
                score=1.0,
                metadata={"version_type": r.get("version_type")},
                evidence=[f"提及实体：{entity_text}"],
            )
            for r in rows
        ]

    # ------------------------------------------------------------------
    # 版本推断
    # ------------------------------------------------------------------
    def infer_edition(
        self, page_id: str, min_score: float = 0.85
    ) -> Optional[Dict[str, Any]]:
        """通过相似页面投票推断未知页面所属版本。"""
        rows = self.client.query(
            """
            MATCH (p:Page {page_id: $pid})-[r:SIMILAR_TO]->(p2:Page)
            WHERE r.score >= $min_score
            MATCH (e:Edition)-[:HAS_PAGE]->(p2)
            RETURN e.edition_id AS edition_id,
                   e.version_type AS version_type,
                   count(p2) AS votes,
                   avg(r.score) AS avg_score
            ORDER BY votes DESC, avg_score DESC
            LIMIT 1
            """,
            {"pid": page_id, "min_score": min_score},
        )
        if not rows:
            return None
        r = rows[0]
        return {
            "edition_id": r["edition_id"],
            "version_type": r["version_type"],
            "votes": r["votes"],
            "avg_score": r["avg_score"],
            "confidence": min(1.0, r["votes"] / 5 * r["avg_score"]),
        }

    # ------------------------------------------------------------------
    # 统计与运维
    # ------------------------------------------------------------------
    def get_edition_stats(self) -> List[Dict[str, Any]]:
        """返回各版本的页面数量统计。"""
        return self.client.query(
            """
            MATCH (e:Edition)-[:HAS_PAGE]->(p:Page)
            RETURN e.edition_id AS edition_id,
                   e.version_type AS version_type,
                   count(p) AS page_count
            ORDER BY page_count DESC
            """
        )

    # ------------------------------------------------------------------
    # 混合检索（向量种子 + 图谱 BFS 扩展）
    # ------------------------------------------------------------------
    def hybrid_search(
        self,
        seeds: List[Tuple[str, float]],
        *,
        bfs_depth: int = 1,
        top_k: int = 10,
        sim_threshold: float = 0.5,
    ) -> List[GraphSearchResult]:
        """基于向量检索种子，在图谱中执行 BFS 扩展并按综合得分排序。

        Args:
            seeds: 向量检索返回的 (page_id, vector_score) 列表，作为 BFS 起点。
            bfs_depth: BFS 扩展层数（默认 1 层）。
            top_k: 最终返回结果数。
            sim_threshold: SIMILAR_TO 边的最低分数阈值。

        Returns:
            按综合关联度排序的 GraphSearchResult 列表，含图谱关系路径。
        """
        if not seeds:
            return []

        # 累积得分表：page_id -> (score, evidence列表)
        scores: Dict[str, float] = {}
        evidence_map: Dict[str, List[str]] = {}

        def _add(pid: str, delta: float, ev: str) -> None:
            scores[pid] = scores.get(pid, 0.0) + delta
            evidence_map.setdefault(pid, []).append(ev)

        seed_ids = set()
        for pid, vscore in seeds:
            _add(pid, vscore, f"向量相似度 {vscore:.3f}")
            seed_ids.add(pid)

        frontier = list(seed_ids)
        for _depth in range(bfs_depth):
            if not frontier:
                break
            next_frontier: List[str] = []
            for pid in frontier:
                neighbors = self._expand_one_hop(pid, sim_threshold)
                for npid, edge_type, edge_score in neighbors:
                    weight = _EDGE_WEIGHTS.get(edge_type, 0.3)
                    # 衰减：非种子节点得分乘以层级衰减因子
                    decay = 0.6 ** (_depth + 1)
                    delta = edge_score * weight * decay
                    _add(npid, delta,
                         f"{edge_type}({pid}→{npid}, w={weight:.1f})")
                    if npid not in seed_ids:
                        next_frontier.append(npid)
            frontier = list(dict.fromkeys(next_frontier))  # 去重保序

        # 排序并取 top_k
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[
            :top_k]

        # 批量查询元数据
        page_ids = [pid for pid, _ in ranked]
        meta_map = self._fetch_page_meta(page_ids)

        return [
            GraphSearchResult(
                page_id=pid,
                score=round(sc, 4),
                metadata=meta_map.get(pid, {}),
                evidence=evidence_map.get(pid, []),
            )
            for pid, sc in ranked
        ]

    def _expand_one_hop(
        self, page_id: str, sim_threshold: float
    ) -> List[Tuple[str, str, float]]:
        """返回 page_id 的一跳邻居：(neighbor_page_id, edge_type, score)。"""
        rows = self.client.query(
            """
            MATCH (p:Page {page_id: $pid})

            // 同版本相邻页（前后页）
            OPTIONAL MATCH (e:Edition)-[:HAS_PAGE]->(p)
            OPTIONAL MATCH (e)-[:HAS_PAGE]->(sibling:Page)
            WHERE sibling.page_id <> $pid

            // 共享实体页面
            OPTIONAL MATCH (p)-[:MENTIONS]->(ent:Entity)<-[:MENTIONS]-(ep:Page)
            WHERE ep.page_id <> $pid

            // 视觉相似页面
            OPTIONAL MATCH (p)-[sr:SIMILAR_TO]->(sp:Page)
            WHERE sr.score >= $sim_threshold

            RETURN
              collect(DISTINCT {pid: sibling.page_id, type: 'SAME_EDITION', score: 1.0}) AS edition_neighbors,
              collect(DISTINCT {pid: ep.page_id,      type: 'MENTIONS_ENTITY', score: 1.0}) AS entity_neighbors,
              collect(DISTINCT {pid: sp.page_id,      type: 'SIMILAR_TO', score: sr.score}) AS sim_neighbors
            """,
            {"pid": page_id, "sim_threshold": sim_threshold},
        )
        if not rows:
            return []

        result: List[Tuple[str, str, float]] = []
        r = rows[0]
        for group in ("edition_neighbors", "entity_neighbors", "sim_neighbors"):
            for item in (r.get(group) or []):
                if item and item.get("pid"):
                    result.append(
                        (item["pid"], item["type"], float(item.get("score") or 1.0)))
        return result

    def _fetch_page_meta(self, page_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        """批量查询页面元数据。"""
        if not page_ids:
            return {}
        rows = self.client.query(
            """
            UNWIND $ids AS pid
            MATCH (p:Page {page_id: pid})
            OPTIONAL MATCH (e:Edition)-[:HAS_PAGE]->(p)
            OPTIONAL MATCH (d:Document)-[:HAS_EDITION]->(e)
            RETURN p.page_id AS page_id,
                   p.ocr_text AS ocr_text,
                   p.image_path AS image_path,
                   e.version_type AS version_type,
                   e.edition_id AS edition_id,
                   d.title AS title
            """,
            {"ids": page_ids},
        )
        return {
            r["page_id"]: {
                "title": r.get("title"),
                "version_type": r.get("version_type"),
                "edition_id": r.get("edition_id"),
                "ocr_text": r.get("ocr_text"),
                "image_path": r.get("image_path"),
            }
            for r in rows
            if r.get("page_id")
        }

    def get_entity_cooccurrence(
        self, entity_text: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """查找与某实体共现频率最高的其他实体。"""
        return self.client.query(
            """
            MATCH (p:Page)-[:MENTIONS]->(e1:Entity {entity_text: $et})
            MATCH (p)-[:MENTIONS]->(e2:Entity)
            WHERE e1 <> e2
            RETURN e2.entity_text AS entity, count(p) AS cooccur
            ORDER BY cooccur DESC LIMIT $limit
            """,
            {"et": entity_text, "limit": limit},
        )
