#!/usr/bin/env python3
"""GraphRAG 评估快速示例.

演示如何快速运行 GraphRAG 评估并查看结果。
"""

import json
import sys
from pathlib import Path

# 兼容两种运行方式：
# 1) python -m eval.scripts.quick_evaluation_demo
# 2) python eval/scripts/quick_evaluation_demo.py
if __package__ in (None, ""):
    project_root = Path(__file__).resolve().parents[2]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    from eval.scripts.evaluate_graphrag import (
        GraphRAGEvaluator,
        EvaluationMetrics,
        RetrievalResult,
    )
else:
    from .evaluate_graphrag import (
        GraphRAGEvaluator,
        EvaluationMetrics,
        RetrievalResult,
    )

from rag.graph import Neo4jClient


def quick_evaluation_demo():
    """快速评估演示."""
    print("=" * 80)
    print("GraphRAG 快速评估示例")
    print("=" * 80)

    # 1. 连接 Neo4j
    print("\n[1/5] 连接 Neo4j...")
    client = Neo4jClient(
        uri="bolt://localhost:7687",
        username="neo4j",
        password="password",
    )

    if not client.verify_connectivity():
        print("❌ 无法连接到 Neo4j，请确保：")
        print("  - Neo4j 正在运行")
        print("  - 端口 7687 可访问")
        print("  - 用户名和密码正确")
        return

    print("✓ Neo4j 连接成功")

    # 2. 检查图谱状态
    print("\n[2/5] 检查图谱状态...")
    stats = client.get_statistics()
    print(f"  节点总数: {stats.get('total_nodes', 0)}")
    print(f"  关系总数: {stats.get('total_relationships', 0)}")

    if stats.get("total_nodes", 0) == 0:
        print("❌ 图谱为空，请先构建图谱：")
        print("  python scripts/build_graph_from_outputs.py --outputs-dir outputs")
        client.close()
        return

    print("✓ 图谱数据正常")

    # 3. 创建评估器
    print("\n[3/5] 初始化评估器...")
    evaluator = GraphRAGEvaluator(client, k_values=[1, 3, 5, 10])
    print("✓ 评估器初始化完成")

    # 4. 运行简单的检索测试
    print("\n[4/5] 运行检索测试...")

    query = """
    MATCH (p:Page)
    RETURN p.page_id
    LIMIT 5
    """
    pages = client.execute_query(query)

    if not pages:
        print("❌ 未找到页面数据")
        client.close()
        return

    test_page_ids = [p["p.page_id"] for p in pages]
    print(f"  使用 {len(test_page_ids)} 个页面进行测试")

    results = []

    for i, page_id in enumerate(test_page_ids[:3]):
        similar_query = """
        MATCH (p1:Page {page_id: $page_id})-[r:SIMILAR_TO]->(p2:Page)
        RETURN p2.page_id, r.similarity_score
        ORDER BY r.similarity_score DESC
        LIMIT 10
        """

        similar_pages = client.execute_query(
            similar_query, {"page_id": page_id})

        if similar_pages:
            retrieved_ids = [sp["p2.page_id"] for sp in similar_pages]
            scores = [sp["r.similarity_score"] for sp in similar_pages]

            # 假设前 3 个是相关的
            ground_truth = retrieved_ids[:3]

            results.append(
                RetrievalResult(
                    query_id=f"test_{i+1}",
                    retrieved_ids=retrieved_ids,
                    scores=scores,
                    ground_truth=ground_truth,
                )
            )

    if not results:
        print("⚠️  未找到相似关系，跳过检索评估")
        print("  提示：运行以下命令构建相似关系：")
        print("  python scripts/build_graph_from_outputs.py --build-similarity")
    else:
        print(f"✓ 完成 {len(results)} 个检索测试")

    # 5. 计算指标
    print("\n[5/5] 计算评估指标...")
    metrics = evaluator.evaluate_retrieval_results(results)

    print("\n" + "=" * 80)
    print("评估结果")
    print("=" * 80)

    if metrics.total_queries > 0:
        print(f"\n总查询数: {metrics.total_queries}")
        print(f"MRR: {metrics.mrr:.4f}")

        print("\n检索质量指标:")

        for k in [1, 3, 5, 10]:
            if k in metrics.precision_at_k:
                print(f"\nK = {k}:")
                print(f"  Precision@{k}: {metrics.precision_at_k[k]:.4f}")
                print(f"  Recall@{k}: {metrics.recall_at_k[k]:.4f}")
                print(f"  F1@{k}: {metrics.f1_at_k[k]:.4f}")
                print(f"  NDCG@{k}: {metrics.ndcg_at_k[k]:.4f}")
                print(f"  Hit Rate@{k}: {metrics.hit_rate_at_k[k]:.4f}")
    else:
        print("⚠️  没有可评估的查询结果")

    # 6. 测试版本推断
    print("\n" + "-" * 80)
    print("测试版本推断能力...")

    edition_query = """
    MATCH (p:Page)-[:BELONGS_TO_EDITION]->(e:Edition)
    WHERE e.edition_name IS NOT NULL
    RETURN p.page_id, e.edition_name
    LIMIT 3
    """

    edition_pages = client.execute_query(edition_query)

    if edition_pages:
        test_cases = [
            {
                "page_id": ep["p.page_id"],
                "expected_edition": ep["e.edition_name"],
            }
            for ep in edition_pages
        ]

        accuracy = evaluator.evaluate_edition_inference(test_cases)
        print(f"✓ 版本推断准确率: {accuracy:.4f} ({len(test_cases)} 个测试用例)")
    else:
        print("⚠️  未找到版本数据，跳过版本推断测试")

    # 7. 测试实体关系
    print("\n" + "-" * 80)
    print("测试实体关系查询...")

    entity_query = """
    MATCH (e1:Entity)-[:RELATED_TO]-(e2:Entity)
    WHERE e1.entity_text < e2.entity_text
    RETURN e1.entity_text AS entity1, e2.entity_text AS entity2
    LIMIT 3
    """

    entity_pairs = client.execute_query(entity_query)

    if entity_pairs:
        test_cases = [
            {
                "entity1": ep["entity1"],
                "entity2": ep["entity2"],
                "expected_relation": True,
            }
            for ep in entity_pairs
        ]

        accuracy = evaluator.evaluate_entity_relations(test_cases)
        print(f"✓ 实体关系准确率: {accuracy:.4f} ({len(test_cases)} 个测试用例)")
    else:
        print("⚠️  未找到实体关系数据，跳过实体关系测试")

    print("\n" + "=" * 80)
    print("评估完成！")
    print("=" * 80)

    print("\n💡 下一步:")
    print("  1. 生成完整测试数据:")
    print("     python scripts/generate_graphrag_test_data.py")

    print("\n  2. 运行完整评估:")
    print(
        "     python scripts/evaluate_graphrag.py "
        "--test-data tests/graphrag_test_data.json"
    )

    print("\n  3. 可视化结果:")
    print(
        "     python scripts/visualize_evaluation_results.py "
        "--metrics-file evaluation_results/evaluation_metrics_*.json"
    )

    client.close()


def show_sample_test_data():
    """显示示例测试数据格式."""
    print("\n" + "=" * 80)
    print("示例测试数据格式")
    print("=" * 80)

    sample = {
        "retrieval_queries": [
            {
                "query_id": "q1",
                "query_text": "史记卷一",
                "query_type": "fulltext",
                "ground_truth": [
                    "page_shiji_001_001",
                    "page_shiji_001_002",
                ],
                "metadata": {"document": "史记", "volume": 1},
            }
        ],
        "edition_inference": [
            {"page_id": "page_test_001", "expected_edition": "宋刻本"}
        ],
        "entity_relations": [
            {
                "entity1": "司馬遷",
                "entity2": "孔安國",
                "expected_relation": True,
            }
        ],
        "multi_hop_reasoning": [
            {
                "start_page": "page_shiji_001",
                "expected_target": "page_shiji_001_010",
                "max_hops": 3,
            }
        ],
    }

    print(json.dumps(sample, ensure_ascii=False, indent=2))


def main():
    """主函数."""
    import argparse

    parser = argparse.ArgumentParser(description="GraphRAG 评估快速示例")
    parser.add_argument(
        "--show-sample",
        action="store_true",
        help="显示示例测试数据格式",
    )

    args = parser.parse_args()

    if args.show_sample:
        show_sample_test_data()
    else:
        try:
            quick_evaluation_demo()
        except KeyboardInterrupt:
            print("\n\n⚠️  评估已中断")
        except Exception as e:
            print(f"\n\n❌ 评估失败: {e}")
            import traceback

            traceback.print_exc()


if __name__ == "__main__":
    main()
