"""GraphRAG 检索器：基于 Neo4j 图遍历的检索与查询接口。"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .client import Neo4jClient

logger = logging.getLogger(__name__)


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
                metadata={"title": r.get("title"), "version_type": r.get("version_type")},
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
