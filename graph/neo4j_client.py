"""Neo4j 图数据库客户端."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from neo4j import GraphDatabase, Session
from neo4j.exceptions import ServiceUnavailable

logger = logging.getLogger(__name__)


class Neo4jClient:
    """Neo4j 图数据库客户端."""

    def __init__(
        self,
        uri: str = "bolt://localhost:7687",
        username: str = "neo4j",
        password: str = "password",
        database: str = "neo4j",
    ):
        """初始化 Neo4j 客户端.

        Args:
            uri: Neo4j 连接 URI
            username: 用户名
            password: 密码
            database: 数据库名称
        """
        self.uri = uri
        self.username = username
        self.database = database
        self.driver = GraphDatabase.driver(uri, auth=(username, password))

    def close(self):
        """关闭连接."""
        if self.driver:
            self.driver.close()

    def __enter__(self):
        """上下文管理器入口."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口."""
        self.close()

    def verify_connectivity(self) -> bool:
        """验证数据库连接.

        Returns:
            连接是否成功
        """
        try:
            with self.driver.session(database=self.database) as session:
                result = session.run("RETURN 1 AS num")
                record = result.single()
                return record["num"] == 1
        except ServiceUnavailable:
            logger.error("无法连接到 Neo4j 数据库")
            return False

    def execute_query(
        self,
        query: str,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """执行 Cypher 查询.

        Args:
            query: Cypher 查询语句
            parameters: 查询参数

        Returns:
            查询结果列表
        """
        with self.driver.session(database=self.database) as session:
            result = session.run(query, parameters or {})
            return [dict(record) for record in result]

    def execute_write(
        self,
        query: str,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """执行写入操作.

        Args:
            query: Cypher 写入语句
            parameters: 查询参数

        Returns:
            执行结果统计
        """
        with self.driver.session(database=self.database) as session:
            result = session.run(query, parameters or {})
            summary = result.consume()
            return {
                "nodes_created": summary.counters.nodes_created,
                "relationships_created": summary.counters.relationships_created,
                "properties_set": summary.counters.properties_set,
            }

    def create_constraints(self):
        """创建图谱约束和索引."""
        constraints = [
            # 唯一性约束
            "CREATE CONSTRAINT doc_id_unique IF NOT EXISTS FOR (d:Document) REQUIRE d.doc_id IS UNIQUE",
            "CREATE CONSTRAINT volume_id_unique IF NOT EXISTS FOR (v:Volume) REQUIRE v.volume_id IS UNIQUE",
            "CREATE CONSTRAINT page_id_unique IF NOT EXISTS FOR (p:Page) REQUIRE p.page_id IS UNIQUE",
            "CREATE CONSTRAINT edition_id_unique IF NOT EXISTS FOR (e:Edition) REQUIRE e.edition_id IS UNIQUE",
            "CREATE CONSTRAINT collection_id_unique IF NOT EXISTS FOR (c:Collection) REQUIRE c.collection_id IS UNIQUE",
            "CREATE CONSTRAINT layout_id_unique IF NOT EXISTS FOR (l:Layout) REQUIRE l.layout_id IS UNIQUE",
            "CREATE CONSTRAINT seal_id_unique IF NOT EXISTS FOR (s:Seal) REQUIRE s.seal_id IS UNIQUE",
            "CREATE CONSTRAINT entity_id_unique IF NOT EXISTS FOR (e:Entity) REQUIRE e.entity_id IS UNIQUE",
        ]

        indexes = [
            # 属性索引
            "CREATE INDEX doc_title_idx IF NOT EXISTS FOR (d:Document) ON (d.title)",
            "CREATE INDEX doc_author_idx IF NOT EXISTS FOR (d:Document) ON (d.author)",
            "CREATE INDEX doc_dynasty_idx IF NOT EXISTS FOR (d:Document) ON (d.dynasty)",
            "CREATE INDEX page_number_idx IF NOT EXISTS FOR (p:Page) ON (p.page_number)",
            "CREATE INDEX page_hash_idx IF NOT EXISTS FOR (p:Page) ON (p.image_hash)",
            "CREATE INDEX entity_type_idx IF NOT EXISTS FOR (e:Entity) ON (e.entity_type)",
            "CREATE INDEX entity_text_idx IF NOT EXISTS FOR (e:Entity) ON (e.entity_text)",
            "CREATE INDEX layout_column_idx IF NOT EXISTS FOR (l:Layout) ON (l.column_count)",
        ]

        fulltext_indexes = [
            # 全文索引
            "CREATE FULLTEXT INDEX page_ocr_text_idx IF NOT EXISTS FOR (p:Page) ON EACH [p.ocr_text]",
            "CREATE FULLTEXT INDEX entity_description_idx IF NOT EXISTS FOR (e:Entity) ON EACH [e.entity_text, e.description]",
        ]

        with self.driver.session(database=self.database) as session:
            # 创建约束
            for constraint in constraints:
                try:
                    session.run(constraint)
                    logger.info(f"创建约束: {constraint[:50]}...")
                except Exception as e:
                    logger.warning(f"约束创建失败（可能已存在）: {e}")

            # 创建索引
            for index in indexes:
                try:
                    session.run(index)
                    logger.info(f"创建索引: {index[:50]}...")
                except Exception as e:
                    logger.warning(f"索引创建失败（可能已存在）: {e}")

            # 创建全文索引
            for index in fulltext_indexes:
                try:
                    session.run(index)
                    logger.info(f"创建全文索引: {index[:50]}...")
                except Exception as e:
                    logger.warning(f"全文索引创建失败（可能已存在）: {e}")

    def clear_database(self):
        """清空数据库（谨慎使用）."""
        query = "MATCH (n) DETACH DELETE n"
        with self.driver.session(database=self.database) as session:
            result = session.run(query)
            summary = result.consume()
            logger.warning(f"已删除 {summary.counters.nodes_deleted} 个节点")

    def get_statistics(self) -> Dict[str, Any]:
        """获取图谱统计信息.

        Returns:
            统计信息字典
        """
        queries = {
            "total_nodes": "MATCH (n) RETURN count(n) AS count",
            "total_relationships": "MATCH ()-[r]->() RETURN count(r) AS count",
            "documents": "MATCH (d:Document) RETURN count(d) AS count",
            "volumes": "MATCH (v:Volume) RETURN count(v) AS count",
            "pages": "MATCH (p:Page) RETURN count(p) AS count",
            "editions": "MATCH (e:Edition) RETURN count(e) AS count",
            "collections": "MATCH (c:Collection) RETURN count(c) AS count",
            "layouts": "MATCH (l:Layout) RETURN count(l) AS count",
            "seals": "MATCH (s:Seal) RETURN count(s) AS count",
            "entities": "MATCH (e:Entity) RETURN count(e) AS count",
        }

        stats = {}
        with self.driver.session(database=self.database) as session:
            for key, query in queries.items():
                result = session.run(query)
                record = result.single()
                stats[key] = record["count"] if record else 0

        return stats

    # ==================== 节点创建方法 ====================

    def create_document(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        """创建文献节点.

        Args:
            doc: 文献属性字典

        Returns:
            创建结果
        """
        query = """
        CREATE (d:Document {
            doc_id: $doc_id,
            title: $title,
            author: $author,
            dynasty: $dynasty,
            category: $category,
            description: $description,
            created_at: datetime(),
            updated_at: datetime()
        })
        RETURN d
        """
        return self.execute_write(query, doc)

    def create_volume(self, volume: Dict[str, Any]) -> Dict[str, Any]:
        """创建卷次节点.

        Args:
            volume: 卷次属性字典

        Returns:
            创建结果
        """
        query = """
        CREATE (v:Volume {
            volume_id: $volume_id,
            volume_number: $volume_number,
            volume_title: $volume_title,
            page_count: $page_count,
            description: $description
        })
        RETURN v
        """
        return self.execute_write(query, volume)

    def create_page(self, page: Dict[str, Any]) -> Dict[str, Any]:
        """创建页面节点.

        Args:
            page: 页面属性字典

        Returns:
            创建结果
        """
        query = """
        CREATE (p:Page {
            page_id: $page_id,
            page_number: $page_number,
            image_path: $image_path,
            image_hash: $image_hash,
            ocr_text: $ocr_text,
            ocr_confidence: $ocr_confidence,
            text_direction: $text_direction,
            width: $width,
            height: $height,
            created_at: datetime()
        })
        RETURN p
        """
        return self.execute_write(query, page)

    def create_edition(self, edition: Dict[str, Any]) -> Dict[str, Any]:
        """创建版本节点.

        Args:
            edition: 版本属性字典

        Returns:
            创建结果
        """
        query = """
        CREATE (e:Edition {
            edition_id: $edition_id,
            edition_type: $edition_type,
            edition_name: $edition_name,
            publisher: $publisher,
            publish_year: $publish_year,
            publish_place: $publish_place,
            description: $description
        })
        RETURN e
        """
        return self.execute_write(query, edition)

    def create_collection(self, collection: Dict[str, Any]) -> Dict[str, Any]:
        """创建馆藏节点.

        Args:
            collection: 馆藏属性字典

        Returns:
            创建结果
        """
        query = """
        CREATE (c:Collection {
            collection_id: $collection_id,
            institution: $institution,
            call_number: $call_number,
            location: $location,
            acquisition_date: $acquisition_date,
            condition: $condition,
            notes: $notes
        })
        RETURN c
        """
        return self.execute_write(query, collection)

    def create_layout(self, layout: Dict[str, Any]) -> Dict[str, Any]:
        """创建版式节点.

        Args:
            layout: 版式属性字典

        Returns:
            创建结果
        """
        query = """
        CREATE (l:Layout {
            layout_id: $layout_id,
            column_count: $column_count,
            line_count: $line_count,
            chars_per_line: $chars_per_line,
            border_type: $border_type,
            border_color: $border_color,
            has_fish_tail: $has_fish_tail,
            has_annotation: $has_annotation,
            annotation_position: $annotation_position
        })
        RETURN l
        """
        return self.execute_write(query, layout)

    def create_seal(self, seal: Dict[str, Any]) -> Dict[str, Any]:
        """创建钤印节点.

        Args:
            seal: 钤印属性字典

        Returns:
            创建结果
        """
        query = """
        CREATE (s:Seal {
            seal_id: $seal_id,
            seal_text: $seal_text,
            seal_type: $seal_type,
            owner: $owner,
            shape: $shape,
            color: $color,
            position: $position
        })
        RETURN s
        """
        return self.execute_write(query, seal)

    def create_entity(self, entity: Dict[str, Any]) -> Dict[str, Any]:
        """创建实体节点.

        Args:
            entity: 实体属性字典

        Returns:
            创建结果
        """
        query = """
        CREATE (e:Entity {
            entity_id: $entity_id,
            entity_text: $entity_text,
            entity_type: $entity_type,
            normalized_name: $normalized_name,
            description: $description,
            aliases: $aliases,
            birth_year: $birth_year,
            death_year: $death_year,
            dynasty: $dynasty
        })
        RETURN e
        """
        return self.execute_write(query, entity)

    # ==================== 关系创建方法 ====================

    def create_has_volume_relation(
        self,
        doc_id: str,
        volume_id: str,
        sequence: int,
    ) -> Dict[str, Any]:
        """创建文献-卷次关系.

        Args:
            doc_id: 文献 ID
            volume_id: 卷次 ID
            sequence: 顺序

        Returns:
            创建结果
        """
        query = """
        MATCH (d:Document {doc_id: $doc_id})
        MATCH (v:Volume {volume_id: $volume_id})
        CREATE (d)-[r:HAS_VOLUME {sequence: $sequence, created_at: datetime()}]->(v)
        RETURN r
        """
        return self.execute_write(
            query,
            {"doc_id": doc_id, "volume_id": volume_id, "sequence": sequence},
        )

    def create_has_page_relation(
        self,
        volume_id: str,
        page_id: str,
        sequence: int,
    ) -> Dict[str, Any]:
        """创建卷次-页面关系.

        Args:
            volume_id: 卷次 ID
            page_id: 页面 ID
            sequence: 顺序

        Returns:
            创建结果
        """
        query = """
        MATCH (v:Volume {volume_id: $volume_id})
        MATCH (p:Page {page_id: $page_id})
        CREATE (v)-[r:HAS_PAGE {sequence: $sequence, created_at: datetime()}]->(p)
        RETURN r
        """
        return self.execute_write(
            query,
            {"volume_id": volume_id, "page_id": page_id, "sequence": sequence},
        )

    def create_similar_to_relation(
        self,
        page_id1: str,
        page_id2: str,
        similarity_score: float,
        similarity_type: str = "visual",
    ) -> Dict[str, Any]:
        """创建页面相似关系.

        Args:
            page_id1: 页面 1 ID
            page_id2: 页面 2 ID
            similarity_score: 相似度分数
            similarity_type: 相似类型

        Returns:
            创建结果
        """
        query = """
        MATCH (p1:Page {page_id: $page_id1})
        MATCH (p2:Page {page_id: $page_id2})
        CREATE (p1)-[r:SIMILAR_TO {
            similarity_score: $similarity_score,
            similarity_type: $similarity_type,
            computed_at: datetime()
        }]->(p2)
        RETURN r
        """
        return self.execute_write(
            query,
            {
                "page_id1": page_id1,
                "page_id2": page_id2,
                "similarity_score": similarity_score,
                "similarity_type": similarity_type,
            },
        )

    def create_belongs_to_edition_relation(
        self,
        page_id: str,
        edition_id: str,
        confidence: float = 1.0,
        identified_by: str = "manual",
    ) -> Dict[str, Any]:
        """创建页面-版本关系.

        Args:
            page_id: 页面 ID
            edition_id: 版本 ID
            confidence: 置信度
            identified_by: 判定方式

        Returns:
            创建结果
        """
        query = """
        MATCH (p:Page {page_id: $page_id})
        MATCH (e:Edition {edition_id: $edition_id})
        CREATE (p)-[r:BELONGS_TO_EDITION {
            confidence: $confidence,
            identified_by: $identified_by,
            created_at: datetime()
        }]->(e)
        RETURN r
        """
        return self.execute_write(
            query,
            {
                "page_id": page_id,
                "edition_id": edition_id,
                "confidence": confidence,
                "identified_by": identified_by,
            },
        )

    def create_stored_in_relation(
        self,
        doc_id: str,
        collection_id: str,
        completeness: str = "完整",
    ) -> Dict[str, Any]:
        """创建文献-馆藏关系.

        Args:
            doc_id: 文献 ID
            collection_id: 馆藏 ID
            completeness: 完整性

        Returns:
            创建结果
        """
        query = """
        MATCH (d:Document {doc_id: $doc_id})
        MATCH (c:Collection {collection_id: $collection_id})
        CREATE (d)-[r:STORED_IN {
            completeness: $completeness,
            created_at: datetime()
        }]->(c)
        RETURN r
        """
        return self.execute_write(
            query,
            {
                "doc_id": doc_id,
                "collection_id": collection_id,
                "completeness": completeness,
            },
        )

    def create_has_layout_relation(
        self,
        page_id: str,
        layout_id: str,
    ) -> Dict[str, Any]:
        """创建页面-版式关系.

        Args:
            page_id: 页面 ID
            layout_id: 版式 ID

        Returns:
            创建结果
        """
        query = """
        MATCH (p:Page {page_id: $page_id})
        MATCH (l:Layout {layout_id: $layout_id})
        CREATE (p)-[r:HAS_LAYOUT {created_at: datetime()}]->(l)
        RETURN r
        """
        return self.execute_write(
            query,
            {"page_id": page_id, "layout_id": layout_id},
        )

    def create_has_seal_relation(
        self,
        page_id: str,
        seal_id: str,
        position_x: int,
        position_y: int,
        confidence: float = 1.0,
    ) -> Dict[str, Any]:
        """创建页面-钤印关系.

        Args:
            page_id: 页面 ID
            seal_id: 钤印 ID
            position_x: X 坐标
            position_y: Y 坐标
            confidence: 置信度

        Returns:
            创建结果
        """
        query = """
        MATCH (p:Page {page_id: $page_id})
        MATCH (s:Seal {seal_id: $seal_id})
        CREATE (p)-[r:HAS_SEAL {
            position_x: $position_x,
            position_y: $position_y,
            confidence: $confidence,
            created_at: datetime()
        }]->(s)
        RETURN r
        """
        return self.execute_write(
            query,
            {
                "page_id": page_id,
                "seal_id": seal_id,
                "position_x": position_x,
                "position_y": position_y,
                "confidence": confidence,
            },
        )

    def create_mentions_relation(
        self,
        page_id: str,
        entity_id: str,
        mention_count: int = 1,
        context: str = "",
    ) -> Dict[str, Any]:
        """创建页面-实体关系.

        Args:
            page_id: 页面 ID
            entity_id: 实体 ID
            mention_count: 提及次数
            context: 上下文

        Returns:
            创建结果
        """
        query = """
        MATCH (p:Page {page_id: $page_id})
        MATCH (e:Entity {entity_id: $entity_id})
        CREATE (p)-[r:MENTIONS {
            mention_count: $mention_count,
            context: $context,
            created_at: datetime()
        }]->(e)
        RETURN r
        """
        return self.execute_write(
            query,
            {
                "page_id": page_id,
                "entity_id": entity_id,
                "mention_count": mention_count,
                "context": context,
            },
        )
