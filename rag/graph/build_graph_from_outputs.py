#!/usr/bin/env python3
"""批量导入脚本 - 从 outputs/ 目录构建知识图谱."""

from rag.graph.data_loader import OutputsDataLoader
from rag.graph.enhanced_builder import EnhancedGraphBuilder
from rag.graph.neo4j_client import Neo4jClient
import argparse
import logging
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    """主函数."""
    parser = argparse.ArgumentParser(
        description="从 outputs/ 目录构建古籍知识图谱"
    )
    parser.add_argument(
        "--outputs-dir",
        type=Path,
        default=Path("outputs"),
        help="outputs 目录路径（默认: outputs）",
    )
    parser.add_argument(
        "--neo4j-uri",
        default="bolt://localhost:7687",
        help="Neo4j URI（默认: bolt://localhost:7687）",
    )
    parser.add_argument(
        "--neo4j-user",
        default="neo4j",
        help="Neo4j 用户名（默认: neo4j）",
    )
    parser.add_argument(
        "--neo4j-password",
        default="password",
        help="Neo4j 密码（默认: password）",
    )
    parser.add_argument(
        "--neo4j-database",
        default="neo4j",
        help="Neo4j 数据库名（默认: neo4j）",
    )
    parser.add_argument(
        "--extract-entities",
        action="store_true",
        help="是否提取实体（人名、地名等）",
    )
    parser.add_argument(
        "--build-similarity",
        action="store_true",
        help="是否构建相似关系（需要提供 embeddings）",
    )
    parser.add_argument(
        "--embeddings-path",
        type=Path,
        help="embeddings.npy 文件路径",
    )
    parser.add_argument(
        "--ids-path",
        type=Path,
        help="ids.json 文件路径",
    )
    parser.add_argument(
        "--similarity-threshold",
        type=float,
        default=0.8,
        help="相似度阈值（默认: 0.8）",
    )
    parser.add_argument(
        "--similarity-top-k",
        type=int,
        default=10,
        help="每个页面保留的最相似页面数（默认: 10）",
    )
    parser.add_argument(
        "--clear-database",
        action="store_true",
        help="清空数据库（谨慎使用）",
    )
    parser.add_argument(
        "--stats-only",
        action="store_true",
        help="仅显示数据集统计信息，不构建图谱",
    )

    args = parser.parse_args()

    # 验证 outputs 目录
    if not args.outputs_dir.exists():
        logger.error(f"outputs 目录不存在: {args.outputs_dir}")
        return 1

    # 如果只显示统计信息
    if args.stats_only:
        logger.info("加载数据集统计信息...")
        loader = OutputsDataLoader(args.outputs_dir)
        stats = loader.get_statistics()

        print("\n" + "=" * 60)
        print("数据集统计信息")
        print("=" * 60)
        print(f"总页面数: {stats['total_pages']}")
        print(f"总文本行数: {stats['total_text_lines']}")
        print(f"平均置信度: {stats['average_confidence']:.2%}")

        print("\n版本分布:")
        for version, count in sorted(stats['version_distribution'].items()):
            print(f"  {version}: {count}")

        print("\n版本类型分布:")
        for edition, count in sorted(stats['edition_distribution'].items()):
            print(f"  {edition}: {count}")

        print("\n馆藏分布:")
        for institution, count in sorted(stats['institution_distribution'].items()):
            print(f"  {institution}: {count}")

        print("=" * 60)
        return 0

    # 连接 Neo4j
    logger.info(f"连接 Neo4j: {args.neo4j_uri}")
    client = Neo4jClient(
        uri=args.neo4j_uri,
        username=args.neo4j_user,
        password=args.neo4j_password,
        database=args.neo4j_database,
    )

    # 验证连接
    if not client.verify_connectivity():
        logger.error("无法连接到 Neo4j 数据库")
        return 1

    logger.info("✓ Neo4j 连接成功")

    # 清空数据库（如果指定）
    if args.clear_database:
        logger.warning("清空数据库...")
        confirm = input("确认清空数据库？(yes/no): ")
        if confirm.lower() == "yes":
            client.clear_database()
            logger.info("✓ 数据库已清空")
        else:
            logger.info("取消清空数据库")
            return 0

    # 创建约束和索引
    logger.info("创建约束和索引...")
    client.create_constraints()
    logger.info("✓ 约束和索引创建完成")

    # 构建图谱
    logger.info("开始构建图谱...")
    builder = EnhancedGraphBuilder(client)

    try:
        stats = builder.build_from_outputs(
            outputs_dir=args.outputs_dir,
            extract_entities=args.extract_entities,
        )

        print("\n" + "=" * 60)
        print("图谱构建完成")
        print("=" * 60)
        print(f"文献节点: {stats['documents']}")
        print(f"卷次节点: {stats['volumes']}")
        print(f"页面节点: {stats['pages']}")
        print(f"版式节点: {stats['layouts']}")
        print(f"版本节点: {stats['editions']}")
        print(f"馆藏节点: {stats['collections']}")
        print(f"实体节点: {stats['entities']}")
        print(f"关系数量: {stats['relationships']}")
        print("=" * 60)

    except Exception as e:
        logger.error(f"构建图谱失败: {e}", exc_info=True)
        return 1

    # 构建相似关系（如果指定）
    if args.build_similarity:
        if not args.embeddings_path or not args.ids_path:
            logger.error("构建相似关系需要提供 --embeddings-path 和 --ids-path")
            return 1

        if not args.embeddings_path.exists():
            logger.error(f"embeddings 文件不存在: {args.embeddings_path}")
            return 1

        if not args.ids_path.exists():
            logger.error(f"ids 文件不存在: {args.ids_path}")
            return 1

        logger.info("开始构建相似关系...")
        try:
            relation_count = builder.build_similarity_relations_from_embeddings(
                embeddings_path=args.embeddings_path,
                ids_path=args.ids_path,
                top_k=args.similarity_top_k,
                threshold=args.similarity_threshold,
            )

            print(f"\n✓ 创建了 {relation_count} 个相似关系")

        except Exception as e:
            logger.error(f"构建相似关系失败: {e}", exc_info=True)
            return 1

    # 显示最终统计
    logger.info("获取图谱统计信息...")
    final_stats = client.get_statistics()

    print("\n" + "=" * 60)
    print("最终图谱统计")
    print("=" * 60)
    print(f"总节点数: {final_stats['total_nodes']}")
    print(f"总关系数: {final_stats['total_relationships']}")
    print(f"文献: {final_stats['documents']}")
    print(f"卷次: {final_stats['volumes']}")
    print(f"页面: {final_stats['pages']}")
    print(f"版本: {final_stats['editions']}")
    print(f"馆藏: {final_stats['collections']}")
    print(f"版式: {final_stats['layouts']}")
    print(f"钤印: {final_stats['seals']}")
    print(f"实体: {final_stats['entities']}")
    print("=" * 60)

    client.close()
    logger.info("✓ 完成")
    return 0


if __name__ == "__main__":
    sys.exit(main())
