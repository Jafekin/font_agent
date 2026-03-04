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

    def __init__(self, neo4j_client: Neo4jClient):
        """初始化检索器.

        Args:
            neo4j_client: Neo4j 客户端实例
        """
        self.client = neo4j_client

    # ==================== 基础检索方法 ====================

    def retrieve_by_page_id(self, page_id: str) -> Optional[Dict[str, Any]]:
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
        OPTIONAL MATCH (p)-[:HAS_SEAL]->(s:Seal)
        RETURN p, v, d, e, l, collect(DISTINCT s) as seals
        """
        results = self.client.execute_query(query, {"page_id": page_id})

        if not results:
            return None

        result = results[0]
        return {
            "page": dict(result["p"]) if result["p"] else None,
            "volume": dict(result["v"]) if result["v"] else None,
            "document": dict(result["d"]) if result["d"] else None,
            "edition": dict(result["e"]) if result["e"] else None,
            "layout": dict(result["l"]) if result["l"] else None,
            "seals": [dict(s) for s in result["seals"]] if result["seals"] else [],
        }

    def retrieve_similar_pages(
        self,
        page_id: str,
        min_similarity: float = 0.8,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """检索相似页面.

        Args:
            page_id: 页面 ID
            min_similarity: 最小相似度阈值
            limit: 返回数量限制

        Returns:
            相似页面列表，包含相似度分数和证据路径
        """
        query = """
        MATCH (p1:Page {page_id: $page_id})-[r:SIMILAR_TO]->(p2:Page)
        WHERE r.similarity_score >= $min_similarity
        OPTIONAL MATCH (v:Volume)-[:HAS_PAGE]->(p2)
        OPTIONAL MATCH (d:Document)-[:HAS_VOLUME]->(v)
        OPTIONAL MATCH (p2)-[:BELONGS_TO_EDITION]->(e:Edition)
        RETURN p2, r.similarity_score as similarity, v, d, e
        ORDER BY similarity DESC
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

        similar_pages = []
        for result in results:
            similar_pages.append(
                {
                    "page": dict(result["p2"]),
                    "similarity": result["similarity"],
                    "volume": dict(result["v"]) if result["v"] else None,
                    "document": dict(result["d"]) if result["d"] else None,
                    "edition": dict(result["e"]) if result["e"] else None,
                    "evidence_path": f"{page_id} --[SIMILAR_TO({result['similarity']:.2%})]-> {result['p2']['page_id']}",
                }
            )

        return similar_pages

    def retrieve_by_layout(
        self,
        column_count: Optional[int] = None,
        border_type: Optional[str] = None,
        border_color: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """根据版式特征检索页面.

        Args:
            column_count: 列数
            border_type: 边框类型
            border_color: 边框颜色
            limit: 返回数量限制

        Returns:
            匹配的页面列表
        """
        # 构建动态查询条件
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
        RETURN p, l, v, d
        LIMIT $limit
        """

        results = self.client.execute_query(query, params)

        pages = []
        for result in results:
            pages.append(
                {
                    "page": dict(result["p"]),
                    "layout": dict(result["l"]),
                    "volume": dict(result["v"]) if result["v"] else None,
                    "document": dict(result["d"]) if result["d"] else None,
                }
            )

        return pages

    def retrieve_by_edition(
        self,
        edition_id: Optional[str] = None,
        edition_type: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """根据版本检索页面.

        Args:
            edition_id: 版本 ID
            edition_type: 版本类型
            limit: 返回数量限制

        Returns:
            匹配的页面列表
        """
        conditions = []
        params = {"limit": limit}

        if edition_id is not None:
            conditions.append("e.edition_id = $edition_id")
            params["edition_id"] = edition_id

        if edition_type is not None:
            conditions.append("e.edition_type = $edition_type")
            params["edition_type"] = edition_type

        where_clause = " AND ".join(conditions) if conditions else "true"

        query = f"""
        MATCH (p:Page)-[r:BELONGS_TO_EDITION]->(e:Edition)
        WHERE {where_clause}
        OPTIONAL MATCH (v:Volume)-[:HAS_PAGE]->(p)
        OPTIONAL MATCH (d:Document)-[:HAS_VOLUME]->(v)
        RETURN p, e, r.confidence as confidence, v, d
        ORDER BY confidence DESC
        LIMIT $limit
        """

        results = self.client.execute_query(query, params)

        pages = []
        for result in results:
            pages.append(
                {
                    "page": dict(result["p"]),
                    "edition": dict(result["e"]),
                    "confidence": result["confidence"],
                    "volume": dict(result["v"]) if result["v"] else None,
                    "document": dict(result["d"]) if result["d"] else None,
                }
            )

        return pages

    # ==================== 多跳推理方法 ====================

    def find_related_pages_by_path(
        self,
        page_id: str,
        max_hops: int = 3,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """通过多跳路径查找相关页面.

        Args:
            page_id: 起始页面 ID
            max_hops: 最大跳数
            limit: 返回数量限制

        Returns:
            相关页面列表，包含路径信息
        """
        query = """
        MATCH path = (p1:Page {page_id: $page_id})-[*1..$max_hops]-(p2:Page)
        WHERE p1 <> p2
        WITH p2, path, length(path) as path_length
        ORDER BY path_length ASC
        LIMIT $limit
        OPTIONAL MATCH (v:Volume)-[:HAS_PAGE]->(p2)
        OPTIONAL MATCH (d:Document)-[:HAS_VOLUME]->(v)
        RETURN p2, path, path_length, v, d
        """

        results = self.client.execute_query(
            query,
            {
                "page_id": page_id,
                "max_hops": max_hops,
                "limit": limit,
            },
        )

        related_pages = []
        for result in results:
            # 提取路径信息
            path_nodes = []
            path_rels = []

            if result["path"]:
                for node in result["path"].nodes:
                    path_nodes.append(
                        {
                            "id": node.get("page_id") or node.get("volume_id") or node.get("doc_id"),
                            "type": list(node.labels)[0] if node.labels else "Unknown",
                        }
                    )

                for rel in result["path"].relationships:
                    path_rels.append(
                        {
                            "type": rel.type,
                            "properties": dict(rel),
                        }
                    )

            related_pages.append(
                {
                    "page": dict(result["p2"]),
                    "path_length": result["path_length"],
                    "path_nodes": path_nodes,
                    "path_relationships": path_rels,
                    "volume": dict(result["v"]) if result["v"] else None,
                    "document": dict(result["d"]) if result["d"] else None,
                }
            )

        return related_pages

    def infer_edition_by_similarity(
        self,
        page_id: str,
        min_similarity: float = 0.85,
        min_votes: int = 3,
    ) -> Optional[Dict[str, Any]]:
        """通过相似页面推断版本.

        Args:
            page_id: 目标页面 ID
            min_similarity: 最小相似度阈值
            min_votes: 最小投票数

        Returns:
            推断的版本信息及证据链
        """
        query = """
        MATCH (p1:Page {page_id: $page_id})-[r:SIMILAR_TO]->(p2:Page)
        WHERE r.similarity_score >= $min_similarity
        MATCH (p2)-[:BELONGS_TO_EDITION]->(e:Edition)
        WITH e, collect({
            page_id: p2.page_id,
            similarity: r.similarity_score
        }) as evidence_pages, avg(r.similarity_score) as avg_similarity, count(p2) as vote_count
        WHERE vote_count >= $min_votes
        RETURN e, evidence_pages, avg_similarity, vote_count
        ORDER BY vote_count DESC, avg_similarity DESC
        LIMIT 1
        """

        results = self.client.execute_query(
            query,
            {
                "page_id": page_id,
                "min_similarity": min_similarity,
                "min_votes": min_votes,
            },
        )

        if not results:
            return None

        result = results[0]
        return {
            "inferred_edition": dict(result["e"]),
            "confidence": result["avg_similarity"],
            "vote_count": result["vote_count"],
            "evidence_pages": result["evidence_pages"],
            "explanation": f"基于 {result['vote_count']} 个相似页面（平均相似度 {result['avg_similarity']:.2%}）推断版本",
        }

    # ==================== 全文搜索方法 ====================

    def fulltext_search(
        self,
        query_text: str,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """全文搜索页面内容.

        Args:
            query_text: 搜索文本
            limit: 返回数量限制

        Returns:
            匹配的页面列表
        """
        query = """
        CALL db.index.fulltext.queryNodes('page_ocr_text_idx', $query_text)
        YIELD node, score
        OPTIONAL MATCH (v:Volume)-[:HAS_PAGE]->(node)
        OPTIONAL MATCH (d:Document)-[:HAS_VOLUME]->(v)
        RETURN node as p, score, v, d
        ORDER BY score DESC
        LIMIT $limit
        """

        results = self.client.execute_query(
            query,
            {
                "query_text": query_text,
                "limit": limit,
            },
        )

        pages = []
        for result in results:
            pages.append(
                {
                    "page": dict(result["p"]),
                    "relevance_score": result["score"],
                    "volume": dict(result["v"]) if result["v"] else None,
                    "document": dict(result["d"]) if result["d"] else None,
                }
            )

        return pages

    # ==================== 属性过滤方法 ====================

    def retrieve_with_filters(
        self,
        dynasty: Optional[str] = None,
        author: Optional[str] = None,
        edition_type: Optional[str] = None,
        column_count: Optional[int] = None,
        border_color: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """多维度属性过滤检索.

        Args:
            dynasty: 朝代
            author: 作者
            edition_type: 版本类型
            column_count: 列数
            border_color: 边框颜色
            limit: 返回数量限制

        Returns:
            匹配的页面列表
        """
        conditions = []
        params = {"limit": limit}

        # 构建查询条件
        if dynasty is not None:
            conditions.append("d.dynasty = $dynasty")
            params["dynasty"] = dynasty

        if author is not None:
            conditions.append("d.author = $author")
            params["author"] = author

        if edition_type is not None:
            conditions.append("e.edition_type = $edition_type")
            params["edition_type"] = edition_type

        if column_count is not None:
            conditions.append("l.column_count = $column_count")
            params["column_count"] = column_count

        if border_color is not None:
            conditions.append("l.border_color = $border_color")
            params["border_color"] = border_color

        where_clause = " AND ".join(conditions) if conditions else "true"

        query = f"""
        MATCH (p:Page)
        OPTIONAL MATCH (v:Volume)-[:HAS_PAGE]->(p)
        OPTIONAL MATCH (d:Document)-[:HAS_VOLUME]->(v)
        OPTIONAL MATCH (p)-[:BELONGS_TO_EDITION]->(e:Edition)
        OPTIONAL MATCH (p)-[:HAS_LAYOUT]->(l:Layout)
        WHERE {where_clause}
        RETURN p, v, d, e, l
        LIMIT $limit
        """

        results = self.client.execute_query(query, params)

        pages = []
        for result in results:
            pages.append(
                {
                    "page": dict(result["p"]),
                    "volume": dict(result["v"]) if result["v"] else None,
                    "document": dict(result["d"]) if result["d"] else None,
                    "edition": dict(result["e"]) if result["e"] else None,
                    "layout": dict(result["l"]) if result["l"] else None,
                }
            )

        return pages

    # ==================== 证据路径生成 ====================

    def get_evidence_path(
        self,
        source_page_id: str,
        target_page_id: str,
        max_hops: int = 5,
    ) -> Optional[Dict[str, Any]]:
        """获取两个页面之间的证据路径.

        Args:
            source_page_id: 源页面 ID
            target_page_id: 目标页面 ID
            max_hops: 最大跳数

        Returns:
            证据路径信息
        """
        query = """
        MATCH path = shortestPath(
            (p1:Page {page_id: $source_page_id})-[*1..$max_hops]-(p2:Page {page_id: $target_page_id})
        )
        RETURN path, length(path) as path_length
        """

        results = self.client.execute_query(
            query,
            {
                "source_page_id": source_page_id,
                "target_page_id": target_page_id,
                "max_hops": max_hops,
            },
        )

        if not results:
            return None

        result = results[0]
        path = result["path"]

        # 提取路径详情
        nodes = []
        relationships = []

        for node in path.nodes:
            nodes.append(
                {
                    "id": node.get("page_id") or node.get("volume_id") or node.get("doc_id"),
                    "type": list(node.labels)[0] if node.labels else "Unknown",
                    "properties": dict(node),
                }
            )

        for rel in path.relationships:
            relationships.append(
                {
                    "type": rel.type,
                    "properties": dict(rel),
                }
            )

        return {
            "path_length": result["path_length"],
            "nodes": nodes,
            "relationships": relationships,
            "explanation": self._generate_path_explanation(nodes, relationships),
        }

    def _generate_path_explanation(
        self,
        nodes: List[Dict[str, Any]],
        relationships: List[Dict[str, Any]],
    ) -> str:
        """生成路径解释文本.

        Args:
            nodes: 节点列表
            relationships: 关系列表

        Returns:
            路径解释文本
        """
        if not nodes or not relationships:
            return "无有效路径"

        explanation_parts = []
        for i, rel in enumerate(relationships):
            source = nodes[i]
            target = nodes[i + 1]

            rel_type = rel["type"]
            rel_props = rel.get("properties", {})

            if rel_type == "SIMILAR_TO":
                similarity = rel_props.get("similarity_score", 0)
                explanation_parts.append(
                    f"{source['id']} 与 {target['id']} 相似（相似度: {similarity:.2%}）"
                )
            elif rel_type == "HAS_PAGE":
                explanation_parts.append(f"{source['id']} 包含页面 {target['id']}")
            elif rel_type == "HAS_VOLUME":
                explanation_parts.append(f"{source['id']} 包含卷次 {target['id']}")
            elif rel_type == "BELONGS_TO_EDITION":
                confidence = rel_props.get("confidence", 1.0)
                explanation_parts.append(
                    f"{source['id']} 属于版本 {target['id']}（置信度: {confidence:.2%}）"
                )
            else:
                explanation_parts.append(
                    f"{source['id']} --[{rel_type}]-> {target['id']}")

        return " → ".join(explanation_parts)
