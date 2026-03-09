"""图谱查询接口 - 封装常用查询操作."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .explainer import EvidenceExplainer
from .neo4j_client import Neo4jClient

logger = logging.getLogger(__name__)


class GraphQueryInterface:
    """图谱查询接口."""

    def __init__(self, neo4j_client: Neo4jClient):
        """初始化查询接口.

        Args:
            neo4j_client: Neo4j 客户端实例
        """
        self.client = neo4j_client
        self.explainer = EvidenceExplainer()

    # ==================== 基础查询 ====================

    def get_document_volumes(self, doc_id: str) -> List[Dict[str, Any]]:
        """获取文献的所有卷次.

        Args:
            doc_id: 文献 ID

        Returns:
            卷次列表
        """
        query = """
        MATCH (d:Document {doc_id: $doc_id})-[:HAS_VOLUME]->(v:Volume)
        RETURN v.volume_id, v.volume_number, v.volume_title, v.page_count
        ORDER BY v.volume_number
        """
        return self.client.execute_query(query, {"doc_id": doc_id})

    def get_volume_pages(self, volume_id: str) -> List[Dict[str, Any]]:
        """获取卷次的所有页面.

        Args:
            volume_id: 卷次 ID

        Returns:
            页面列表
        """
        query = """
        MATCH (v:Volume {volume_id: $volume_id})-[:HAS_PAGE]->(p:Page)
        RETURN p.page_id, p.page_number, p.image_path, p.ocr_confidence
        ORDER BY p.page_number
        """
        return self.client.execute_query(query, {"volume_id": volume_id})

    def fulltext_search(
        self,
        keyword: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """全文搜索页面内容.

        Args:
            keyword: 搜索关键词
            limit: 返回数量限制

        Returns:
            搜索结果列表
        """
        query = """
        CALL db.index.fulltext.queryNodes('page_ocr_text_idx', $keyword)
        YIELD node, score
        RETURN node.page_id AS page_id,
               node.ocr_text AS ocr_text,
               score
        ORDER BY score DESC
        LIMIT $limit
        """
        return self.client.execute_query(
            query,
            {"keyword": keyword, "limit": limit},
        )

    # ==================== 版本与版式查询 ====================

    def get_pages_by_edition(
        self,
        edition_id: str,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """获取特定版本的所有页面.

        Args:
            edition_id: 版本 ID
            limit: 返回数量限制

        Returns:
            页面列表
        """
        query = """
        MATCH (p:Page)-[:BELONGS_TO_EDITION]->(e:Edition {edition_id: $edition_id})
        RETURN p.page_id, p.image_path, p.page_number
        ORDER BY p.page_number
        LIMIT $limit
        """
        return self.client.execute_query(
            query,
            {"edition_id": edition_id, "limit": limit},
        )

    def get_pages_by_layout(
        self,
        column_count: Optional[int] = None,
        border_color: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """根据版式特征查询页面.

        Args:
            column_count: 列数
            border_color: 边框颜色
            limit: 返回数量限制

        Returns:
            页面列表
        """
        conditions = []
        params = {"limit": limit}

        if column_count is not None:
            conditions.append("l.column_count = $column_count")
            params["column_count"] = column_count

        if border_color is not None:
            conditions.append("l.border_color = $border_color")
            params["border_color"] = border_color

        where_clause = " AND ".join(conditions) if conditions else "true"

        query = f"""
        MATCH (p:Page)-[:HAS_LAYOUT]->(l:Layout)
        WHERE {where_clause}
        RETURN p.page_id, p.image_path, l.column_count, l.border_type, l.border_color
        LIMIT $limit
        """
        return self.client.execute_query(query, params)

    def get_layout_statistics(self) -> List[Dict[str, Any]]:
        """统计不同版式的页面数量.

        Returns:
            版式统计列表
        """
        query = """
        MATCH (p:Page)-[:HAS_LAYOUT]->(l:Layout)
        RETURN
          l.column_count,
          l.border_type,
          l.border_color,
          count(p) AS page_count
        ORDER BY page_count DESC
        """
        return self.client.execute_query(query)

    # ==================== 相似页面检索 ====================

    def get_similar_pages(
        self,
        page_id: str,
        limit: int = 10,
        min_similarity: float = 0.8,
    ) -> List[Dict[str, Any]]:
        """获取相似页面.

        Args:
            page_id: 页面 ID
            limit: 返回数量限制
            min_similarity: 最小相似度阈值

        Returns:
            相似页面列表
        """
        query = """
        MATCH (p1:Page {page_id: $page_id})-[r:SIMILAR_TO]->(p2:Page)
        WHERE r.similarity_score >= $min_similarity
        RETURN p2.page_id, p2.image_path, r.similarity_score, r.similarity_type
        ORDER BY r.similarity_score DESC
        LIMIT $limit
        """
        return self.client.execute_query(
            query,
            {
                "page_id": page_id,
                "limit": limit,
                "min_similarity": min_similarity,
            },
        )

    def infer_edition_by_similarity(
        self,
        page_id: str,
        min_similarity: float = 0.85,
    ) -> Dict[str, Any]:
        """通过相似页面推断版本.

        Args:
            page_id: 页面 ID
            min_similarity: 最小相似度阈值

        Returns:
            推断结果（带证据链）
        """
        query = """
        MATCH (p1:Page {page_id: $page_id})-[r:SIMILAR_TO]->(p2:Page)-[:BELONGS_TO_EDITION]->(e:Edition)
        WHERE r.similarity_score >= $min_similarity
        RETURN
          e.edition_id,
          e.edition_name,
          count(p2) AS similar_page_count,
          avg(r.similarity_score) AS avg_similarity,
          collect({
            page_id: p2.page_id,
            similarity: r.similarity_score
          }) AS similar_pages
        ORDER BY similar_page_count DESC, avg_similarity DESC
        LIMIT 5
        """
        results = self.client.execute_query(
            query,
            {"page_id": page_id, "min_similarity": min_similarity},
        )

        if not results:
            return {
                "inferred_edition": None,
                "confidence": 0.0,
                "explanation": f"无法为 {page_id} 推断版本（缺少相似页面证据）",
            }

        # 使用证据解释器生成详细解释
        best_result = results[0]
        similar_pages = [
            {
                "page_id": sp["page_id"],
                "similarity": sp["similarity"],
                "edition": best_result["e.edition_name"],
            }
            for sp in best_result["similar_pages"]
        ]

        explained = self.explainer.explain_edition_inference(
            page_id,
            similar_pages,
            [],
            [],
        )

        return explained

    # ==================== 钤印与馆藏查询 ====================

    def get_pages_by_seal(self, seal_text: str) -> List[Dict[str, Any]]:
        """查询包含特定钤印的页面.

        Args:
            seal_text: 钤印文字

        Returns:
            页面列表
        """
        query = """
        MATCH (p:Page)-[:HAS_SEAL]->(s:Seal {seal_text: $seal_text})
        RETURN p.page_id, p.image_path, s.seal_type, s.owner
        ORDER BY p.page_id
        """
        return self.client.execute_query(query, {"seal_text": seal_text})

    def get_document_collections(self, doc_id: str) -> List[Dict[str, Any]]:
        """查询文献的馆藏信息.

        Args:
            doc_id: 文献 ID

        Returns:
            馆藏列表
        """
        query = """
        MATCH (d:Document {doc_id: $doc_id})-[r:STORED_IN]->(c:Collection)
        RETURN
          c.institution,
          c.call_number,
          c.condition,
          r.completeness
        """
        return self.client.execute_query(query, {"doc_id": doc_id})

    def get_seal_co_occurrence(
        self,
        seal_text: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """查询与某印章共现的其他印章.

        Args:
            seal_text: 钤印文字
            limit: 返回数量限制

        Returns:
            共现印章列表
        """
        query = """
        MATCH (p:Page)-[:HAS_SEAL]->(s1:Seal {seal_text: $seal_text})
        MATCH (p)-[:HAS_SEAL]->(s2:Seal)
        WHERE s1 <> s2
        RETURN
          s2.seal_text,
          s2.owner,
          count(p) AS co_occurrence_count
        ORDER BY co_occurrence_count DESC
        LIMIT $limit
        """
        return self.client.execute_query(
            query,
            {"seal_text": seal_text, "limit": limit},
        )

    # ==================== 实体关系查询 ====================

    def get_pages_mentioning_entity(
        self,
        entity_text: str,
        entity_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """查询提及特定实体的页面.

        Args:
            entity_text: 实体文本
            entity_type: 实体类型（可选）

        Returns:
            页面列表
        """
        params = {"entity_text": entity_text}
        type_condition = ""

        if entity_type:
            type_condition = "AND e.entity_type = $entity_type"
            params["entity_type"] = entity_type

        query = f"""
        MATCH (p:Page)-[r:MENTIONS]->(e:Entity {{entity_text: $entity_text}})
        WHERE true {type_condition}
        RETURN
          p.page_id,
          p.image_path,
          r.mention_count,
          r.context
        ORDER BY r.mention_count DESC
        """
        return self.client.execute_query(query, params)

    def get_entity_co_occurrence(
        self,
        entity_text: str,
        entity_type: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """查询与某实体共现的其他实体.

        Args:
            entity_text: 实体文本
            entity_type: 目标实体类型（可选）
            limit: 返回数量限制

        Returns:
            共现实体列表
        """
        params = {"entity_text": entity_text, "limit": limit}
        type_condition = ""

        if entity_type:
            type_condition = "AND e2.entity_type = $entity_type"
            params["entity_type"] = entity_type

        query = f"""
        MATCH (p:Page)-[:MENTIONS]->(e1:Entity {{entity_text: $entity_text}})
        MATCH (p)-[:MENTIONS]->(e2:Entity)
        WHERE e1 <> e2 {type_condition}
        RETURN
          e2.entity_text,
          e2.entity_type,
          e2.description,
          count(p) AS co_occurrence_count
        ORDER BY co_occurrence_count DESC
        LIMIT $limit
        """
        return self.client.execute_query(query, params)

    def find_entity_relation_path(
        self,
        entity1_text: str,
        entity2_text: str,
        max_depth: int = 3,
    ) -> Dict[str, Any]:
        """查询两个实体之间的关系路径.

        Args:
            entity1_text: 实体 1 文本
            entity2_text: 实体 2 文本
            max_depth: 最大路径深度

        Returns:
            关系路径（带解释）
        """
        query = f"""
        MATCH path = (e1:Entity {{entity_text: $entity1_text}})-[:RELATED_TO*1..{max_depth}]-(e2:Entity {{entity_text: $entity2_text}})
        RETURN path
        LIMIT 5
        """
        results = self.client.execute_query(
            query,
            {"entity1_text": entity1_text, "entity2_text": entity2_text},
        )

        if not results:
            return {
                "relation_found": False,
                "explanation": f"{entity1_text} 与 {entity2_text} 之间未发现关系路径",
            }

        # 使用证据解释器生成解释
        paths = [r["path"] for r in results]
        explained = self.explainer.explain_entity_relation(
            entity1_text,
            entity2_text,
            paths,
        )

        return explained

    # ==================== 推荐查询 ====================

    def recommend_related_pages(
        self,
        page_id: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """推荐相关页面.

        Args:
            page_id: 页面 ID
            limit: 返回数量限制

        Returns:
            推荐页面列表（带解释）
        """
        query = """
        MATCH (p:Page {page_id: $page_id})

        // 相似页面
        OPTIONAL MATCH (p)-[s:SIMILAR_TO]->(sp:Page)

        // 同版本页面
        OPTIONAL MATCH (p)-[:BELONGS_TO_EDITION]->(e:Edition)<-[:BELONGS_TO_EDITION]-(ep:Page)
        WHERE ep <> p

        // 提及相同实体的页面
        OPTIONAL MATCH (p)-[:MENTIONS]->(entity:Entity)<-[:MENTIONS]-(mp:Page)
        WHERE mp <> p

        WITH p,
             collect(DISTINCT {page: sp, score: s.similarity_score, reason: 'similar'}) AS similar_pages,
             collect(DISTINCT {page: ep, score: 0.8, reason: 'same_edition'}) AS edition_pages,
             collect(DISTINCT {page: mp, score: 0.6, reason: 'shared_entity'}) AS entity_pages

        UNWIND (similar_pages + edition_pages + entity_pages) AS recommendation
        WHERE recommendation.page IS NOT NULL
        RETURN
          recommendation.page.page_id AS page_id,
          recommendation.page.image_path AS image_path,
          recommendation.score AS score,
          recommendation.reason AS reason
        ORDER BY recommendation.score DESC
        LIMIT $limit
        """
        results = self.client.execute_query(
            query, {"page_id": page_id, "limit": limit})

        # 使用证据解释器添加解释
        explained = self.explainer.explain_recommendation(page_id, results)

        return explained

    # ==================== 统计查询 ====================

    def get_document_statistics(self) -> List[Dict[str, Any]]:
        """获取文献统计信息.

        Returns:
            文献统计列表
        """
        query = """
        MATCH (d:Document)
        OPTIONAL MATCH (d)-[:HAS_VOLUME]->(v:Volume)
        OPTIONAL MATCH (v)-[:HAS_PAGE]->(p:Page)
        RETURN
          d.title,
          d.author,
          d.dynasty,
          count(DISTINCT v) AS volume_count,
          count(DISTINCT p) AS page_count
        ORDER BY page_count DESC
        """
        return self.client.execute_query(query)

    def get_edition_distribution(self) -> List[Dict[str, Any]]:
        """获取版本分布统计.

        Returns:
            版本统计列表
        """
        query = """
        MATCH (p:Page)-[:BELONGS_TO_EDITION]->(e:Edition)
        RETURN
          e.edition_type,
          e.edition_name,
          count(p) AS page_count,
          avg(p.ocr_confidence) AS avg_confidence
        ORDER BY page_count DESC
        """
        return self.client.execute_query(query)

    def get_entity_type_distribution(self) -> List[Dict[str, Any]]:
        """获取实体类型分布.

        Returns:
            实体类型统计列表
        """
        query = """
        MATCH (e:Entity)
        RETURN
          e.entity_type,
          count(e) AS entity_count
        ORDER BY entity_count DESC
        """
        return self.client.execute_query(query)

    # ==================== 图谱维护 ====================

    def find_orphan_nodes(self) -> Dict[str, int]:
        """查找孤立节点（没有任何关系的节点）.

        Returns:
            孤立节点统计
        """
        query = """
        MATCH (n)
        WHERE NOT (n)--()
        RETURN labels(n)[0] AS node_type, count(n) AS count
        """
        results = self.client.execute_query(query)
        return {r["node_type"]: r["count"] for r in results}

    def find_duplicate_pages(self) -> List[Dict[str, Any]]:
        """查找重复页面（基于图片哈希）.

        Returns:
            重复页面列表
        """
        query = """
        MATCH (p:Page)
        WHERE p.image_hash IS NOT NULL
        WITH p.image_hash, collect(p) AS pages
        WHERE size(pages) > 1
        RETURN p.image_hash AS image_hash,
               [page IN pages | page.page_id] AS duplicate_pages
        """
        return self.client.execute_query(query)

    def delete_low_quality_similarities(
        self,
        threshold: float = 0.7,
    ) -> int:
        """删除低质量的相似关系.

        Args:
            threshold: 相似度阈值

        Returns:
            删除的关系数量
        """
        query = """
        MATCH ()-[r:SIMILAR_TO]->()
        WHERE r.similarity_score < $threshold
        DELETE r
        RETURN count(r) AS deleted_count
        """
        result = self.client.execute_query(query, {"threshold": threshold})
        return result[0]["deleted_count"] if result else 0
