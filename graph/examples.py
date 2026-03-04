"""图谱模块使用示例."""

from pathlib import Path

from graph import (
    EvidenceExplainer,
    GraphBuilder,
    GraphQueryInterface,
    Neo4jClient,
)


def example_1_connect_and_init():
    """示例 1: 连接数据库并初始化."""
    print("=" * 60)
    print("示例 1: 连接数据库并初始化")
    print("=" * 60)

    # 连接 Neo4j
    client = Neo4jClient(
        uri="bolt://localhost:7687",
        username="neo4j",
        password="password",
    )

    # 验证连接
    if client.verify_connectivity():
        print("✓ 数据库连接成功")
    else:
        print("✗ 数据库连接失败")
        return

    # 创建约束和索引
    print("\n创建约束和索引...")
    client.create_constraints()
    print("✓ 约束和索引创建完成")

    # 查看统计信息
    stats = client.get_statistics()
    print(f"\n当前图谱统计:")
    for key, value in stats.items():
        print(f"  {key}: {value}")

    client.close()


def example_2_build_graph():
    """示例 2: 构建知识图谱."""
    print("\n" + "=" * 60)
    print("示例 2: 构建知识图谱")
    print("=" * 60)

    client = Neo4jClient(
        uri="bolt://localhost:7687",
        username="neo4j",
        password="password",
    )

    if not client.verify_connectivity():
        print("✗ 数据库连接失败")
        return

    # 初始化构建器
    builder = GraphBuilder(client)

    # 从 metadata.json 构建图谱
    metadata_path = Path("rag/index/metadata.json")
    if not metadata_path.exists():
        print(f"✗ 文件不存在: {metadata_path}")
        client.close()
        return

    print(f"\n从 {metadata_path} 构建图谱...")
    stats = builder.build_from_metadata(metadata_path)

    print(f"\n✓ 图谱构建完成:")
    print(f"  文献: {stats['documents']}")
    print(f"  卷次: {stats['volumes']}")
    print(f"  页面: {stats['pages']}")
    print(f"  版式: {stats['layouts']}")
    print(f"  版本: {stats['editions']}")
    print(f"  馆藏: {stats['collections']}")
    print(f"  关系: {stats['relationships']}")

    # 构建相似关系
    embeddings_path = Path("rag/index/embeddings.npy")
    ids_path = Path("rag/index/ids.json")

    if embeddings_path.exists() and ids_path.exists():
        print(f"\n构建相似关系...")
        relation_count = builder.build_similarity_relations(
            embeddings_path,
            ids_path,
            top_k=10,
            threshold=0.8,
        )
        print(f"✓ 创建了 {relation_count} 个相似关系")

    client.close()


def example_3_basic_queries():
    """示例 3: 基础查询."""
    print("\n" + "=" * 60)
    print("示例 3: 基础查询")
    print("=" * 60)

    client = Neo4jClient(
        uri="bolt://localhost:7687",
        username="neo4j",
        password="password",
    )

    if not client.verify_connectivity():
        print("✗ 数据库连接失败")
        return

    query = GraphQueryInterface(client)

    # 查询文献统计
    print("\n文献统计:")
    doc_stats = query.get_document_statistics()
    for doc in doc_stats[:5]:
        print(
            f"  {doc['d.title']}: {doc['volume_count']} 卷, {doc['page_count']} 页")

    # 全文搜索
    print("\n全文搜索 '黃帝':")
    results = query.fulltext_search("黃帝", limit=5)
    for r in results:
        print(f"  {r['page_id']}: 评分 {r['score']:.2f}")

    # 版式统计
    print("\n版式分布:")
    layout_stats = query.get_layout_statistics()
    for layout in layout_stats[:5]:
        print(
            f"  {layout['l.column_count']}栏 {layout['l.border_color']}: {layout['page_count']} 页")

    client.close()


def example_4_edition_inference():
    """示例 4: 版本推断."""
    print("\n" + "=" * 60)
    print("示例 4: 版本推断")
    print("=" * 60)

    client = Neo4jClient(
        uri="bolt://localhost:7687",
        username="neo4j",
        password="password",
    )

    if not client.verify_connectivity():
        print("✗ 数据库连接失败")
        return

    query = GraphQueryInterface(client)

    # 假设有一个未知版本的页面
    page_id = "page_unknown_001"

    print(f"\n为 {page_id} 推断版本...")
    inference = query.infer_edition_by_similarity(page_id, min_similarity=0.85)

    if inference['inferred_edition']:
        print(f"\n✓ 推断结果: {inference['inferred_edition']}")
        print(f"  置信度: {inference['confidence']:.2%}")
        print(f"  证据数量: {inference['evidence_count']}")
        print(f"  证据类型: {', '.join(inference['evidence_types'])}")

        print(f"\n证据链（前 3 条）:")
        for chain in inference['evidence_chains'][:3]:
            print(f"  - {chain['explanation']}")

        print(f"\n{inference['summary']}")
    else:
        print("✗ 无法推断版本（缺少证据）")

    client.close()


def example_5_entity_queries():
    """示例 5: 实体查询."""
    print("\n" + "=" * 60)
    print("示例 5: 实体查询")
    print("=" * 60)

    client = Neo4jClient(
        uri="bolt://localhost:7687",
        username="neo4j",
        password="password",
    )

    if not client.verify_connectivity():
        print("✗ 数据库连接失败")
        return

    query = GraphQueryInterface(client)

    # 查询提及某人物的页面
    entity_text = "司馬遷"
    print(f"\n查询提及 '{entity_text}' 的页面:")
    pages = query.get_pages_mentioning_entity(
        entity_text, entity_type="PERSON")
    print(f"  找到 {len(pages)} 个页面")
    for page in pages[:3]:
        print(f"    {page['p.page_id']}: 提及 {page['r.mention_count']} 次")

    # 查询实体共现
    print(f"\n与 '{entity_text}' 共现的人物:")
    co_entities = query.get_entity_co_occurrence(
        entity_text, entity_type="PERSON", limit=5)
    for entity in co_entities:
        print(
            f"  {entity['e2.entity_text']}: 共现 {entity['co_occurrence_count']} 次")

    # 查询实体关系路径
    entity1 = "司馬遷"
    entity2 = "孔安國"
    print(f"\n查询 '{entity1}' 与 '{entity2}' 的关系路径:")
    path = query.find_entity_relation_path(entity1, entity2, max_depth=3)

    if path['relation_found']:
        print(f"  ✓ 找到关系路径（{path['path_length']} 步）")
        print(f"  {path['explanation']}")
    else:
        print(f"  ✗ 未找到关系路径")

    client.close()


def example_6_recommendations():
    """示例 6: 推荐系统."""
    print("\n" + "=" * 60)
    print("示例 6: 推荐系统")
    print("=" * 60)

    client = Neo4jClient(
        uri="bolt://localhost:7687",
        username="neo4j",
        password="password",
    )

    if not client.verify_connectivity():
        print("✗ 数据库连接失败")
        return

    query = GraphQueryInterface(client)

    # 推荐相关页面
    page_id = "page_shiji_001_001"
    print(f"\n为 {page_id} 推荐相关页面:")
    recommendations = query.recommend_related_pages(page_id, limit=10)

    for i, rec in enumerate(recommendations, 1):
        print(f"\n  {i}. {rec['page_id']}")
        print(f"     评分: {rec['confidence']:.2f}")
        print(f"     {rec['explanation']}")

    client.close()


def example_7_evidence_explanation():
    """示例 7: 证据路径解释."""
    print("\n" + "=" * 60)
    print("示例 7: 证据路径解释")
    print("=" * 60)

    explainer = EvidenceExplainer()

    # 模拟版本推断的证据
    target_page_id = "page_unknown_001"
    similar_pages = [
        {"page_id": "page_001", "similarity": 0.92, "edition": "宋刻本"},
        {"page_id": "page_002", "similarity": 0.89, "edition": "宋刻本"},
        {"page_id": "page_003", "similarity": 0.87, "edition": "宋刻本"},
    ]

    layout_matches = [
        {
            "page_id": "page_004",
            "layout_id": "layout_001",
            "layout_desc": "2栏黑口",
            "edition": "宋刻本",
        }
    ]

    seal_matches = [
        {
            "page_id": "page_005",
            "seal_id": "seal_001",
            "seal_text": "天祿琳琅",
            "edition": "宋刻本",
        }
    ]

    # 生成解释
    inference = explainer.explain_edition_inference(
        target_page_id,
        similar_pages,
        layout_matches,
        seal_matches,
    )

    print(f"\n{inference['summary']}")

    print(f"\n详细证据链:")
    for i, chain in enumerate(inference['evidence_chains'], 1):
        print(f"\n  {i}. 类型: {chain['type']}")
        print(f"     置信度: {chain['confidence']:.2%}")
        print(f"     {chain['explanation']}")
        print(f"     路径: {chain['path']}")


def example_8_maintenance():
    """示例 8: 图谱维护."""
    print("\n" + "=" * 60)
    print("示例 8: 图谱维护")
    print("=" * 60)

    client = Neo4jClient(
        uri="bolt://localhost:7687",
        username="neo4j",
        password="password",
    )

    if not client.verify_connectivity():
        print("✗ 数据库连接失败")
        return

    query = GraphQueryInterface(client)

    # 查找孤立节点
    print("\n查找孤立节点:")
    orphans = query.find_orphan_nodes()
    if orphans:
        for node_type, count in orphans.items():
            print(f"  {node_type}: {count} 个")
    else:
        print("  ✓ 没有孤立节点")

    # 查找重复页面
    print("\n查找重复页面:")
    duplicates = query.find_duplicate_pages()
    if duplicates:
        print(f"  找到 {len(duplicates)} 组重复页面")
        for dup in duplicates[:3]:
            print(f"    哈希: {dup['image_hash'][:16]}...")
            print(f"    页面: {', '.join(dup['duplicate_pages'])}")
    else:
        print("  ✓ 没有重复页面")

    # 删除低质量相似关系
    print("\n删除低质量相似关系（阈值 < 0.7）:")
    deleted = query.delete_low_quality_similarities(threshold=0.7)
    print(f"  删除了 {deleted} 个关系")

    # 最终统计
    print("\n最终图谱统计:")
    stats = client.get_statistics()
    for key, value in stats.items():
        print(f"  {key}: {value}")

    client.close()


def main():
    """运行所有示例."""
    print("\n" + "=" * 60)
    print("图谱模块使用示例")
    print("=" * 60)

    examples = [
        ("连接数据库并初始化", example_1_connect_and_init),
        ("构建知识图谱", example_2_build_graph),
        ("基础查询", example_3_basic_queries),
        ("版本推断", example_4_edition_inference),
        ("实体查询", example_5_entity_queries),
        ("推荐系统", example_6_recommendations),
        ("证据路径解释", example_7_evidence_explanation),
        ("图谱维护", example_8_maintenance),
    ]

    print("\n可用示例:")
    for i, (name, _) in enumerate(examples, 1):
        print(f"  {i}. {name}")

    print("\n提示: 修改代码以运行特定示例")
    print("=" * 60)

    # 运行示例（取消注释以运行）
    # example_1_connect_and_init()
    # example_2_build_graph()
    # example_3_basic_queries()
    # example_4_edition_inference()
    # example_5_entity_queries()
    # example_6_recommendations()
    # example_7_evidence_explanation()
    # example_8_maintenance()


if __name__ == "__main__":
    main()
