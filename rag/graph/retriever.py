"""GraphRAG 检索器 - 基于图遍历的检索能力."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from .neo4j_client import Neo4jClient

logger = logging.getLogger(__name__)


@dataclass
class GraphSearchResult:
    """图检索结果."""

    page_id: str
    score: float
    evidence_path: List[Dict[str, Any]]
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典."""
        return {
            "page_id": self.page_id,
            "score": self.score,
            "evidence_path": self.evidence_path,
            "metadata": self.metadata,
        }


class GraphRetriever:
    """基于知识图谱的检索器."""

    def __init__(self, neo4j_client: Neo4jClient):
        """初始化检索器.

        Args:
            neo4j_client: Neo4j 客户端实例
        """
        self.client = neo4j_client

    # ==================== 基础检索方法 ====================

    def search_by_page_id(self, page_id: str) -> Optional[Dict[str, Any]]:
        """根据页面 ID 检索完整信息.

        Args:
            page_id: 页面 ID

        Returns:
            页面信息及其关联的文献、卷次、版本等
        """
        query = """
        MATCH (p:Page {page_id: $page_id})
        OPTIONAL MATCH (v:Volume)-[:HAS_PAGE]->(p)
        OPTIONAL MATCH (d:Document)-[:HAS_VOLUME]->(v)
        OPTIONAL MATCH (p)-[:BELONGS_TO_EDITION]->(e:Edition)
        OPTIONAL MATCH (p)-[:HAS_LAYOUT]->(l:Layout)
        RETURN p, v, d, e, l
        """
        results = self.client.execute_query(query, {"page_id": page_id})

        if not results:
            return None

        result = results[0]
        return {
            "page": result.get("p"),
            "volume": result.get("v"),
            "document": result.get("d"),
            "edition": result.get("e"),
            "layout": result.get("l"),
        }

    def search_by_document_title(
        self,
        title: str,
        fuzzy: bool = True,
    ) -> List[Dict[str, Any]]:
        """根据文献标题检索.

        Args:
            title: 文献标题
            fuzzy: 是否模糊匹配

        Returns:
            匹配的文献列表
        """
        if fuzzy:
            query = """
            MATCH (d:Document)
            WHERE d.title CONTAINS $title
            RETURN d
            ORDER BY d.title
            """
        else:
            query = """
            MATCH (d:Document {title: $title})
            RETURN d
            """

        results = self.client.execute_query(query, {"title": title})
        return [r["d"] for r in results]

    def search_by_fulltext(
        self,
        text: str,
        limit: int = 10,
    ) -> List[GraphSearchResult]:
        """全文搜索页面内容.

        Args:
            text: 搜索文本
            limit: 返回结果数量

        Returns:
            检索结果列表
        """
        query = """
        CALL db.index.fulltext.queryNodes('page_ocr_text_idx', $text)
        YIELD node, score
        MATCH (node:Page)
        OPTIONAL MATCH (v:Volume)-[:HAS_PAGE]->(node)
        OPTIONAL MATCH (d:Document)-[:HAS_VOLUME]->(v)
        RETURN node.page_id AS page_id, score, node, v, d
        ORDER BY score DESC
        LIMIT $limit
        """

        results = self.client.execute_query(
            query,
            {"text": text, "limit": limit},
        )

        search_results = []
        for r in results:
            evidence_path = [
                {"type": "Document", "data": r.get("d")},
                {"type": "Volume", "data": r.get("v")},
                {"type": "Page", "data": r.get("node")},
            ]

            search_results.append(
                GraphSearchResult(
                    page_id=r["page_id"],
                    score=r["score"],
                    evidence_path=evidence_path,
                    metadata={
                        "search_type": "fulltext",
                        "query": text,
                    },
                )
            )

        return search_results

    # ==================== 关系路径检索 ====================

    def find_similar_pages(
        self,
        page_id: str,
        min_similarity: float = 0.8,
        limit: int = 10,
    ) -> List[GraphSearchResult]:
        """查找相似页面.

        Args:
            page_id: 源页面 ID
            min_similarity: 最小相似度阈值
            limit: 返回结果数量

        Returns:
            相似页面列表
        """
        query = """
        MATCH (p1:Page {page_id: $page_id})-[r:SIMILAR_TO]->(p2:Page)
        WHERE r.similarity_score >= $min_similarity
        OPTIONAL MATCH (v:Volume)-[:HAS_PAGE]->(p2)
        OPTIONAL MATCH (d:Document)-[:HAS_VOLUME]->(v)
        RETURN p2.page_id AS page_id, r.similarity_score AS score, p2, v, d, r
        ORDER BY score DESC
        LIMIT $limit
        """

        results = self.client.execute_query(
            query,
            {
                "page_id": page_id,
                "min_similarity": min_similarity,
                "limit": limit,
            },
        )

        search_results = []
        for r in results:
            evidence_path = [
                {"type": "Page", "id": page_id, "relation": "SIMILAR_TO"},
                {"type": "Page", "data": r.get("p2")},
                {"type": "Volume", "data": r.get("v")},
                {"type": "Document", "data": r.get("d")},
            ]

            search_results.append(
                GraphSearchResult(
                    page_id=r["page_id"],
                    score=r["score"],
                    evidence_path=evidence_path,
                    metadata={
                        "search_type": "similarity",
                        "source_page": page_id,
                        "similarity_type": r.get("r", {}).get("similarity_type", "visual"),
                    },
                )
            )

        return search_results

    def find_pages_by_edition(
        self,
        edition_id: str,
        limit: int = 50,
    ) -> List[GraphSearchResult]:
        """查找特定版本的所有页面.

        Args:
            edition_id: 版本 ID
            limit: 返回结果数量

        Returns:
            页面列表
        """
        query = """
        MATCH (p:Page)-[r:BELONGS_TO_EDITION]->(e:Edition {edition_id: $edition_id})
        OPTIONAL MATCH (v:Volume)-[:HAS_PAGE]->(p)
        OPTIONAL MATCH (d:Document)-[:HAS_VOLUME]->(v)
        RETURN p.page_id AS page_id, r.confidence AS score, p, v, d, e
        ORDER BY v.volume_number, p.page_number
        LIMIT $limit
        """

        results = self.client.execute_query(
            query,
            {"edition_id": edition_id, "limit": limit},
        )

        search_results = []
        for r in results:
            evidence_path = [
                {"type": "Edition", "data": r.get("e")},
                {"type": "Page", "data": r.get("p")},
                {"type": "Volume", "data": r.get("v")},
                {"type": "Document", "data": r.get("d")},
            ]

            search_results.append(
                GraphSearchResult(
                    page_id=r["page_id"],
                    score=r.get("score", 1.0),
                    evidence_path=evidence_path,
                    metadata={
                        "search_type": "edition",
                        "edition_id": edition_id,
                    },
                )
            )

        return search_results

    def find_pages_by_layout(
        self,
        column_count: Optional[int] = None,
        border_type: Optional[str] = None,
        border_color: Optional[str] = None,
        limit: int = 50,
    ) -> List[GraphSearchResult]:
        """根据版式特征查找页面.

        Args:
            column_count: 列数
            border_type: 边框类型
            border_color: 边框颜色
            limit: 返回结果数量

        Returns:
            匹配的页面列表
        """
        conditions = []
        params = {"limit": limit}

        if column_count is not None:
            conditions.append("l.column_count = $column_count")
            params["column_count"] = column_count

        if border_type is not None:
            conditions.append("l.border_type = $border_type")
            params["border_type"] = border_type

        if border_color is not None:
            conditions.append("l.border_color = $border_color")
            params["border_color"] = border_color

        where_clause = " AND ".join(conditions) if conditions else "true"

        query = f"""
        MATCH (p:Page)-[:HAS_LAYOUT]->(l:Layout)
        WHERE {where_clause}
        OPTIONAL MATCH (v:Volume)-[:HAS_PAGE]->(p)
        OPTIONAL MATCH (d:Document)-[:HAS_VOLUME]->(v)
        RETURN p.page_id AS page_id, p, l, v, d
        ORDER BY d.title, v.volume_number, p.page_number
        LIMIT $limit
        """

        results = self.client.execute_query(query, params)

        search_results = []
        for r in results:
            evidence_path = [
                {"type": "Layout", "data": r.get("l")},
                {"type": "Page", "data": r.get("p")},
                {"type": "Volume", "data": r.get("v")},
                {"type": "Document", "data": r.get("d")},
            ]

            search_results.append(
                GraphSearchResult(
                    page_id=r["page_id"],
                    score=1.0,
                    evidence_path=evidence_path,
                    metadata={
                        "search_type": "layout",
                        "filters": {
                            "column_count": column_count,
                            "border_type": border_type,
                            "border_color": border_color,
                        },
                    },
                )
            )

        return search_results
