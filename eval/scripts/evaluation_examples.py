#!/usr/bin/env python3
"""
GraphRAG 评估系统 - 完整使用示例

演示如何使用评估系统的所有功能。
"""

import json
from pathlib import Path


def print_section(title: str):
    """打印章节标题."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80 + "\n")


def example_1_quick_demo():
    """示例 1: 快速评估演示."""
    print_section("示例 1: 快速评估演示")

    print("这是最简单的使用方式，无需准备测试数据。\n")

    print("运行命令:")
    print("  python scripts/quick_evaluation_demo.py\n")

    print("功能:")
    print("  ✓ 自动连接 Neo4j")
    print("  ✓ 检查图谱状态")
    print("  ✓ 运行简单检索测试")
    print("  ✓ 显示评估结果")
    print("  ✓ 给出优化建议\n")

    print("适用场景:")
    print("  - 快速验证系统是否正常")
    print("  - 了解当前图谱质量")
    print("  - 开发调试")


def example_2_generate_test_data():
    """示例 2: 生成测试数据."""
    print_section("示例 2: 生成测试数据")

    print("从现有图谱自动生成标准测试数据集。\n")

    print("运行命令:")
    print(
        """  python scripts/generate_graphrag_test_data.py \
    --neo4j-uri bolt://localhost:7687 \
    --neo4j-user neo4j \
    --neo4j-password password \
    --output tests/graphrag_test_data.json \
    --num-retrieval 20 \
    --num-edition 10 \
    --num-entity 10 \
    --num-multi-hop 10
"""
    )

    print("生成的测试数据包括:")
    print("  ✓ 检索查询（文献标题、实体、版式、相似度）")
    print("  ✓ 版本推断用例")
    print("  ✓ 实体关系用例")
    print("  ✓ 多跳推理用例")
    print("  ✓ 推荐系统用例\n")

    print("测试数据格式示例:")

    sample = {
        "retrieval_queries": [
            {
                "query_id": "q1",
                "query_text": "史记卷一",
                "query_type": "fulltext",
                "ground_truth": ["page_001", "page_002"],
            }
        ],
        "edition_inference": [
            {
                "page_id": "page_test_001",
                "expected_edition": "宋刻本",
            }
        ],
    }

    print(json.dumps(sample, ensure_ascii=False, indent=2))


def example_3_run_evaluation():
    """示例 3: 运行完整评估."""
    print_section("示例 3: 运行完整评估")

    print("使用测试数据运行完整的评估流程。\n")

    print("运行命令:")
    print(
        """  python scripts/evaluate_graphrag.py \
    --neo4j-uri bolt://localhost:7687 \
    --neo4j-user neo4j \
    --neo4j-password password \
    --test-data tests/graphrag_test_data.json \
    --output-dir evaluation_results
"""
    )

    print("评估内容:")
    print("  ✓ 检索质量指标（Precision, Recall, F1, MRR, NDCG, Hit Rate）")
    print("  ✓ 版本推断准确率")
    print("  ✓ 实体关系准确率")
    print("  ✓ 多跳推理准确率\n")

    print("输出文件:")
    print("  - evaluation_results/evaluation_report_YYYYMMDD_HHMMSS.txt")
    print("  - evaluation_results/evaluation_metrics_YYYYMMDD_HHMMSS.json\n")

    print("评估报告示例:")

    print(
        """
===============
GraphRAG 评估报告
==================
生成时间: 2026-03-13 12:00:00
总查询数: 20

检索质量指标
----------------------
MRR: 0.7850

K = 5:
  Precision@5: 0.7200
  Recall@5: 0.8100
  F1@5: 0.7625
  NDCG@5: 0.8150
  Hit Rate@5: 0.9500

GraphRAG 特有指标
-------------------------
版本推断准确率: 0.9200
实体关系准确率: 0.8700
多跳推理准确率: 0.7800
平均路径长度: 2.40
=================
"""
    )


def example_4_visualize_results():
    """示例 4: 可视化结果."""
    print_section("示例 4: 可视化结果")

    print("生成评估结果的可视化图表。\n")

    print("运行命令:")
    print(
        """  python scripts/visualize_evaluation_results.py \
    --metrics-file evaluation_results/evaluation_metrics_20260313_120000.json \
    --output-dir evaluation_results/plots
"""
    )

    print("生成的图表:")
    print("  ✓ precision_recall_f1.png - Precision/Recall/F1 曲线")
    print("  ✓ ndcg_hit_rate.png - NDCG 和 Hit Rate 对比")
    print("  ✓ graphrag_radar.png - GraphRAG 指标雷达图")
    print("  ✓ metrics_summary.png - 综合指标汇总\n")

    print("图表特点:")
    print("  - 支持中文显示")
    print("  - 高分辨率（300 DPI）")
    print("  - 专业配色方案")
    print("  - 多维度对比")


def main():
    """主函数."""
    print("\n" + "=" * 80)
    print("  GraphRAG 评估系统 - 完整使用示例")
    print("=" * 80)

    examples = [
        ("快速评估演示", example_1_quick_demo),
        ("生成测试数据", example_2_generate_test_data),
        ("运行完整评估", example_3_run_evaluation),
        ("可视化结果", example_4_visualize_results),
    ]

    print("\n可用示例:")
    for i, (name, _) in enumerate(examples, 1):
        print(f"  {i}. {name}")

    print("\n" + "=" * 80)

    for _, func in examples:
        func()

    print_section("总结")

    print("GraphRAG 评估系统提供了完整的工具链：\n")
    print("  ✓ 快速评估 - 无需准备，一键运行")
    print("  ✓ 自动化测试数据生成 - 从图谱提取标准测试集")
    print("  ✓ 多维度指标评估 - 检索质量 + GraphRAG 特有能力")
    print("  ✓ 结果可视化 - 专业图表，直观展示")
    print("  ✓ 持续优化 - 建立基线，跟踪改进\n")

    print("开始使用:")
    print("  python scripts/quick_evaluation_demo.py\n")

    print("=" * 80)


if __name__ == "__main__":
    main()
