"""Neo4j 图数据库客户端（轻量封装）."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable

logger = logging.getLogger(__name__)


class Neo4jClient:
    """Neo4j 轻量客户端，提供通用节点/关系操作。"""

    def __init__(
        self,
        uri: str = "bolt://localhost:7687",
        username: str = "neo4j",
        password: str = "password",
        database: str = "neo4j",
    ) -> None:
        self.database = database
        self.driver = GraphDatabase.driver(uri, auth=(username, password))

    def close(self) -> None:
        self.driver.close()

    def __enter__(self) -> Neo4jClient:
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    # ------------------------------------------------------------------
    # 基础查询
    # ------------------------------------------------------------------
    def query(
        self,
        cypher: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """执行只读 Cypher 查询，返回记录列表。"""
        with self.driver.session(database=self.database) as session:
            result = session.run(cypher, params or {})
            return [dict(r) for r in result]

    def write(
        self,
        cypher: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, int]:
        """执行写入 Cypher，返回变更计数。"""
        with self.driver.session(database=self.database) as session:
            result = session.run(cypher, params or {})
            s = result.consume()
            return {
                "nodes_created": s.counters.nodes_created,
                "relationships_created": s.counters.relationships_created,
                "properties_set": s.counters.properties_set,
            }

    # ------------------------------------------------------------------
    # 通用节点 / 关系操作
    # ------------------------------------------------------------------
    def merge_node(self, label: str, match_key: str, props: Dict[str, Any]) -> None:
        """MERGE 节点：按 match_key 匹配，ON CREATE/MATCH 设置全部属性。"""
        cypher = (
            f"MERGE (n:{label} {{{match_key}: ${match_key}}}) "
            f"SET n += $props"
        )
        self.write(cypher, {match_key: props[match_key], "props": props})

    def merge_relation(
        self,
        from_label: str,
        from_key: str,
        from_val: Any,
        rel_type: str,
        to_label: str,
        to_key: str,
        to_val: Any,
        rel_props: Optional[Dict[str, Any]] = None,
    ) -> None:
        """MERGE 有向关系，可选设置关系属性。"""
        set_clause = "SET r += $rp" if rel_props else ""
        cypher = (
            f"MATCH (a:{from_label} {{{from_key}: $fv}}) "
            f"MATCH (b:{to_label} {{{to_key}: $tv}}) "
            f"MERGE (a)-[r:{rel_type}]->(b) "
            f"{set_clause}"
        )
        self.write(cypher, {"fv": from_val, "tv": to_val, "rp": rel_props or {}})

    # ------------------------------------------------------------------
    # 初始化 Schema
    # ------------------------------------------------------------------
    def create_schema(self) -> None:
        """创建唯一约束与常用索引（幂等）。"""
        stmts = [
            "CREATE CONSTRAINT IF NOT EXISTS FOR (d:Document) REQUIRE d.doc_id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (e:Edition) REQUIRE e.edition_id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (c:Collection) REQUIRE c.collection_id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (p:Page) REQUIRE p.page_id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (l:Layout) REQUIRE l.layout_id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (e:Entity) REQUIRE e.entity_id IS UNIQUE",
            "CREATE INDEX IF NOT EXISTS FOR (d:Document) ON (d.title)",
            "CREATE INDEX IF NOT EXISTS FOR (e:Entity) ON (e.entity_text)",
            "CREATE FULLTEXT INDEX page_ocr_idx IF NOT EXISTS FOR (p:Page) ON EACH [p.ocr_text]",
        ]
        with self.driver.session(database=self.database) as session:
            for stmt in stmts:
                try:
                    session.run(stmt)
                except Exception as exc:
                    logger.debug("Schema stmt skipped: %s", exc)

    # ------------------------------------------------------------------
    # 管理工具
    # ------------------------------------------------------------------
    def verify_connectivity(self) -> bool:
        try:
            result = self.query("RETURN 1 AS n")
            return bool(result and result[0].get("n") == 1)
        except ServiceUnavailable:
            logger.error("无法连接到 Neo4j")
            return False

    def clear_database(self) -> None:
        """清空所有节点和关系（不可逆）。"""
        self.write("MATCH (n) DETACH DELETE n")
        logger.warning("数据库已清空。")

    def get_statistics(self) -> Dict[str, int]:
        labels = ["Document", "Edition", "Collection", "Page", "Layout", "Entity"]
        stats: Dict[str, int] = {}
        for label in labels:
            rows = self.query(f"MATCH (n:{label}) RETURN count(n) AS c")
            stats[label.lower() + "s"] = rows[0]["c"] if rows else 0
        rows = self.query("MATCH ()-[r]->() RETURN count(r) AS c")
        stats["relationships"] = rows[0]["c"] if rows else 0
        return stats
