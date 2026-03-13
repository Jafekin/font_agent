"""生成 GraphRAG 测试数据集.

从现有的 Neo4j 图谱中提取数据，生成标准的测试数据集。
"""

from rag.graph import GraphQueryInterface, Neo4jClient
import argparse
import json
import logging
import random
import sys
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).parent.parent))


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class TestDataGenerator:
    """测试数据生成器."""

    def __init__(self, neo4j_client: Neo4jClient):
        self.client = neo4j_client
        self.query_interface = GraphQueryInterface(neo4j_client)

    def generate_retrieval_queries(self, num_queries: int = 20) -> List[Dict[str, Any]]:
        """生成检索查询测试数据."""
        queries: List[Dict[str, Any]] = []

        # 1 文献标题查询
        logger.info("生成文献标题查询...")
        doc_stats = self.query_interface.get_document_statistics()

        for i, doc in enumerate(doc_stats[: min(5, num_queries // 4)]):
            title = doc.get("d.title", "")
            if not title:
                continue

            query = """
            MATCH (d:Document {title: $title})-[:HAS_VOLUME]->(v:Volume)-[:HAS_PAGE]->(p:Page)
            RETURN p.page_id
            LIMIT 10
            """

            results = self.client.execute_query(query, {"title": title})
            ground_truth = [r["p.page_id"] for r in results]

            if ground_truth:
                queries.append(
                    {
                        "query_id": f"retrieval_doc_{i+1}",
                        "query_text": title,
                        "query_type": "fulltext",
                        "ground_truth": ground_truth,
                        "metadata": {
                            "category": "document_title",
                            "document": title,
                        },
                    }
                )

        # 2 实体查询
        logger.info("生成实体查询...")
        entity_query = """
        MATCH (e:Entity)
        WHERE e.entity_type IN ['PERSON', 'LOCATION']
        RETURN e.entity_text, e.entity_type
        LIMIT 10
        """

        entities = self.client.execute_query(entity_query)

        for i, entity in enumerate(entities[: min(5, num_queries // 4)]):
            entity_text = entity.get("e.entity_text", "")
            entity_type = entity.get("e.entity_type", "")

            if not entity_text:
                continue

            pages = self.query_interface.get_pages_mentioning_entity(
                entity_text)
            ground_truth = [p["p.page_id"] for p in pages[:10]]

            if ground_truth:
                queries.append(
                    {
                        "query_id": f"retrieval_entity_{i+1}",
                        "query_text": entity_text,
                        "query_type": "fulltext",
                        "ground_truth": ground_truth,
                        "metadata": {
                            "category": "entity",
                            "entity_type": entity_type,
                            "entity": entity_text,
                        },
                    }
                )

        # 3 版式查询
        logger.info("生成版式查询...")
        layout_stats = self.query_interface.get_layout_statistics()

        for i, layout in enumerate(layout_stats[: min(3, num_queries // 4)]):
            column_count = layout.get("l.column_count")
            border_color = layout.get("l.border_color")

            if column_count is None:
                continue

            pages = self.query_interface.get_pages_by_layout(
                column_count=column_count,
                border_color=border_color,
                limit=10,
            )

            ground_truth = [p["p.page_id"] for p in pages]

            if ground_truth:
                queries.append(
                    {
                        "query_id": f"retrieval_layout_{i+1}",
                        "query_text": f"{column_count}栏 {border_color or ''}",
                        "query_type": "layout",
                        "ground_truth": ground_truth,
                        "metadata": {
                            "category": "layout",
                            "column_count": column_count,
                            "border_color": border_color,
                        },
                    }
                )

        # 4 相似度查询
        logger.info("生成相似度查询...")
        similarity_query = """
        MATCH (p1:Page)-[r:SIMILAR_TO]->(p2:Page)
        WHERE r.similarity_score >= 0.85
        RETURN p1.page_id AS source, collect(p2.page_id)[..10] AS similar_pages
        LIMIT 5
        """

        similar_results = self.client.execute_query(similarity_query)

        for i, result in enumerate(similar_results):
            source = result.get("source")
            similar_pages = result.get("similar_pages", [])

            if source and similar_pages:
                queries.append(
                    {
                        "query_id": f"retrieval_similar_{i+1}",
                        "query_text": source,
                        "query_type": "similarity",
                        "ground_truth": similar_pages,
                        "metadata": {
                            "category": "similarity",
                            "source_page": source,
                        },
                    }
                )

        logger.info(f"生成了 {len(queries)} 个检索查询")
        return queries

    def generate_edition_inference_cases(
        self, num_cases: int = 10
    ) -> List[Dict[str, Any]]:
        logger.info("生成版本推断测试用例...")

        query = """
        MATCH (p:Page)-[:BELONGS_TO_EDITION]->(e:Edition)
        WHERE e.edition_name IS NOT NULL
        RETURN p.page_id, e.edition_id, e.edition_name
        LIMIT $limit
        """

        results = self.client.execute_query(query, {"limit": num_cases * 2})

        cases = []
        for result in results[:num_cases]:
            cases.append(
                {
                    "page_id": result["p.page_id"],
                    "expected_edition": result["e.edition_name"],
                    "edition_id": result["e.edition_id"],
                }
            )

        logger.info(f"生成了 {len(cases)} 个版本推断用例")
        return cases

    def generate_multi_hop_cases(self, num_cases: int = 10) -> List[Dict[str, Any]]:
        logger.info("生成多跳推理测试用例...")

        query = """
        MATCH path = (p1:Page)-[:SIMILAR_TO*2..3]->(p2:Page)
        WHERE p1 <> p2
        RETURN p1.page_id AS start_page,
               p2.page_id AS target_page,
               length(path) AS hops
        LIMIT $limit
        """

        results = self.client.execute_query(query, {"limit": num_cases})

        cases = []
        for result in results:
            cases.append(
                {
                    "start_page": result["start_page"],
                    "expected_target": result["target_page"],
                    "max_hops": result["hops"],
                }
            )

        logger.info(f"生成了 {len(cases)} 个多跳推理用例")
        return cases

    def generate_recommendation_cases(
        self, num_cases: int = 10
    ) -> List[Dict[str, Any]]:
        logger.info("生成推荐测试用例...")

        query = """
        MATCH (p:Page)
        WHERE EXISTS((p)-[:SIMILAR_TO]->())
           OR EXISTS((p)-[:BELONGS_TO_EDITION]->())
           OR EXISTS((p)-[:MENTIONS]->())
        RETURN p.page_id
        LIMIT $limit
        """

        results = self.client.execute_query(query, {"limit": num_cases})

        cases = []
        for result in results:
            page_id = result["p.page_id"]

            recommendations = self.query_interface.recommend_related_pages(
                page_id, limit=10
            )

            expected_pages = []
            if recommendations:
                expected_pages = [rec["page_id"] for rec in recommendations]

            cases.append(
                {
                    "page_id": page_id,
                    "expected_recommendations": expected_pages[:5],
                    "min_expected_count": 3,
                }
            )

        logger.info(f"生成了 {len(cases)} 个推荐用例")
        return cases

    def generate_complete_test_dataset(
        self,
        num_retrieval: int = 20,
        num_edition: int = 10,
        num_entity: int = 10,
        num_multi_hop: int = 10,
        num_recommendation: int = 10,
    ) -> Dict[str, Any]:

        logger.info("开始生成完整测试数据集...")

        dataset = {
            "metadata": {
                "description": "GraphRAG 评估测试数据集",
            },
            "retrieval_queries": self.generate_retrieval_queries(num_retrieval),
            "edition_inference": self.generate_edition_inference_cases(num_edition),
            "multi_hop_reasoning": self.generate_multi_hop_cases(num_multi_hop),
            "recommendations": self.generate_recommendation_cases(num_recommendation),
        }

        total_cases = sum(
            [
                len(dataset["retrieval_queries"]),
                len(dataset["edition_inference"]),
                len(dataset["multi_hop_reasoning"]),
                len(dataset["recommendations"]),
            ]
        )

        logger.info(f"测试数据集生成完成，共 {total_cases} 个测试用例")
        return dataset


def main():
    parser = argparse.ArgumentParser(description="生成 GraphRAG 测试数据集")

    parser.add_argument("--neo4j-uri", default="bolt://localhost:7687")
    parser.add_argument("--neo4j-user", default="neo4j")
    parser.add_argument("--neo4j-password", default="password")

    parser.add_argument(
        "--output",
        type=Path,
        default=Path("tests/graphrag_test_data.json"),
    )

    args = parser.parse_args()

    logger.info(f"连接 Neo4j: {args.neo4j_uri}")

    client = Neo4jClient(
        uri=args.neo4j_uri,
        username=args.neo4j_user,
        password=args.neo4j_password,
    )

    if not client.verify_connectivity():
        logger.error("无法连接到 Neo4j 数据库")
        return

    generator = TestDataGenerator(client)

    dataset = generator.generate_complete_test_dataset()

    args.output.parent.mkdir(parents=True, exist_ok=True)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(dataset, f, ensure_ascii=False, indent=2)

    logger.info(f"测试数据已保存到: {args.output}")

    print("\n" + "=" * 60)
    print("测试数据集统计")
    print("=" * 60)
    print(f"检索查询: {len(dataset['retrieval_queries'])}")
    print(f"版本推断: {len(dataset['edition_inference'])}")
    print(f"多跳推理: {len(dataset['multi_hop_reasoning'])}")
    print(f"推荐系统: {len(dataset['recommendations'])}")
    print("=" * 60)

    client.close()


if __name__ == "__main__":
    main()
