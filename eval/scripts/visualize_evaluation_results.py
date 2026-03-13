"""可视化 GraphRAG 评估结果.

生成评估指标的可视化图表，包括：
- 检索质量指标对比图
- K 值对比曲线
- GraphRAG 特有指标雷达图
- 混淆矩阵
"""

import argparse
import json
import logging
from pathlib import Path
from typing import Any, Dict

import matplotlib.pyplot as plt
import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# 设置中文字体
plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False


class EvaluationVisualizer:
    """评估结果可视化器."""

    def __init__(self, metrics: Dict[str, Any], output_dir: Path):
        self.metrics = metrics
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def plot_precision_recall_f1(self) -> None:
        """绘制 Precision / Recall / F1 曲线."""
        logger.info("绘制 Precision/Recall/F1 对比图...")

        k_values = sorted([int(k)
                          for k in self.metrics["precision_at_k"].keys()])
        precision = [self.metrics["precision_at_k"][str(k)] for k in k_values]
        recall = [self.metrics["recall_at_k"][str(k)] for k in k_values]
        f1 = [self.metrics["f1_at_k"][str(k)] for k in k_values]

        plt.figure(figsize=(10, 6))

        plt.plot(k_values, precision, marker="o",
                 label="Precision@K", linewidth=2)
        plt.plot(k_values, recall, marker="s", label="Recall@K", linewidth=2)
        plt.plot(k_values, f1, marker="^", label="F1@K", linewidth=2)

        plt.xlabel("K", fontsize=12)
        plt.ylabel("Score", fontsize=12)
        plt.title("检索质量指标 (Precision / Recall / F1)",
                  fontsize=14, fontweight="bold")

        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.xticks(k_values)
        plt.ylim(0, 1.05)

        output_path = self.output_dir / "precision_recall_f1.png"
        plt.savefig(output_path, dpi=300, bbox_inches="tight")
        plt.close()

        logger.info(f"已保存: {output_path}")

    def plot_ndcg_hit_rate(self) -> None:
        """绘制 NDCG 与 Hit Rate 曲线."""
        logger.info("绘制 NDCG / Hit Rate 对比图...")

        k_values = sorted([int(k) for k in self.metrics["ndcg_at_k"].keys()])
        ndcg = [self.metrics["ndcg_at_k"][str(k)] for k in k_values]
        hit_rate = [self.metrics["hit_rate_at_k"][str(k)] for k in k_values]

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

        ax1.plot(k_values, ndcg, marker="o", linewidth=2)
        ax1.set_title("NDCG@K")
        ax1.set_xlabel("K")
        ax1.set_ylabel("NDCG")
        ax1.set_xticks(k_values)
        ax1.set_ylim(0, 1.05)
        ax1.grid(True, alpha=0.3)

        ax2.plot(k_values, hit_rate, marker="s", linewidth=2)
        ax2.set_title("Hit Rate@K")
        ax2.set_xlabel("K")
        ax2.set_ylabel("Hit Rate")
        ax2.set_xticks(k_values)
        ax2.set_ylim(0, 1.05)
        ax2.grid(True, alpha=0.3)

        plt.tight_layout()

        output_path = self.output_dir / "ndcg_hit_rate.png"
        plt.savefig(output_path, dpi=300, bbox_inches="tight")
        plt.close()

        logger.info(f"已保存: {output_path}")

    def plot_graphrag_metrics_radar(self) -> None:
        """绘制 GraphRAG 指标雷达图."""
        logger.info("绘制 GraphRAG 雷达图...")

        categories = ["版本推断", "实体关系", "多跳推理", "MRR"]

        values = [
            self.metrics.get("edition_inference_accuracy", 0),
            self.metrics.get("entity_relation_accuracy", 0),
            self.metrics.get("multi_hop_accuracy", 0),
            self.metrics.get("mrr", 0),
        ]

        values += values[:1]

        angles = np.linspace(0, 2 * np.pi, len(categories),
                             endpoint=False).tolist()
        angles += angles[:1]

        fig, ax = plt.subplots(
            figsize=(8, 8), subplot_kw=dict(projection="polar"))

        ax.plot(angles, values, "o-", linewidth=2)
        ax.fill(angles, values, alpha=0.25)

        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(categories)

        ax.set_ylim(0, 1)

        ax.set_title("GraphRAG 特有指标", pad=20)

        output_path = self.output_dir / "graphrag_radar.png"
        plt.savefig(output_path, dpi=300, bbox_inches="tight")
        plt.close()

        logger.info(f"已保存: {output_path}")

    def plot_all_metrics_summary(self) -> None:
        """绘制指标汇总图."""
        logger.info("绘制指标汇总图...")

        fig, axes = plt.subplots(2, 2, figsize=(14, 10))

        metrics_names = ["Precision", "Recall", "F1", "NDCG", "Hit Rate"]

        k5_values = [
            self.metrics["precision_at_k"].get("5", 0),
            self.metrics["recall_at_k"].get("5", 0),
            self.metrics["f1_at_k"].get("5", 0),
            self.metrics["ndcg_at_k"].get("5", 0),
            self.metrics["hit_rate_at_k"].get("5", 0),
        ]

        axes[0, 0].bar(metrics_names, k5_values)
        axes[0, 0].set_title("检索指标 @K=5")
        axes[0, 0].set_ylim(0, 1.05)

        k_values = sorted([int(k) for k in self.metrics["f1_at_k"].keys()])
        f1_values = [self.metrics["f1_at_k"][str(k)] for k in k_values]

        axes[0, 1].plot(k_values, f1_values, marker="o")
        axes[0, 1].set_title("F1@K 曲线")
        axes[0, 1].set_ylim(0, 1.05)
        axes[0, 1].set_xticks(k_values)

        graphrag_names = ["版本推断", "实体关系", "多跳推理"]

        graphrag_values = [
            self.metrics.get("edition_inference_accuracy", 0),
            self.metrics.get("entity_relation_accuracy", 0),
            self.metrics.get("multi_hop_accuracy", 0),
        ]

        axes[1, 0].barh(graphrag_names, graphrag_values)
        axes[1, 0].set_xlim(0, 1.05)
        axes[1, 0].set_title("GraphRAG 指标")

        key_metrics = ["MRR", "P@5", "R@5", "NDCG@5"]

        key_values = [
            self.metrics.get("mrr", 0),
            self.metrics["precision_at_k"].get("5", 0),
            self.metrics["recall_at_k"].get("5", 0),
            self.metrics["ndcg_at_k"].get("5", 0),
        ]

        axes[1, 1].bar(key_metrics, key_values)
        axes[1, 1].set_ylim(0, 1.05)
        axes[1, 1].set_title("关键指标")

        plt.tight_layout()

        output_path = self.output_dir / "metrics_summary.png"
        plt.savefig(output_path, dpi=300, bbox_inches="tight")
        plt.close()

        logger.info(f"已保存: {output_path}")

    def generate_all_plots(self) -> None:
        """生成所有图表."""
        logger.info("开始生成可视化图表...")

        self.plot_precision_recall_f1()
        self.plot_ndcg_hit_rate()
        self.plot_graphrag_metrics_radar()
        self.plot_all_metrics_summary()

        logger.info(f"所有图表已保存到: {self.output_dir}")


def main():
    """主函数."""
    parser = argparse.ArgumentParser(description="可视化 GraphRAG 评估结果")

    parser.add_argument(
        "--metrics-file",
        type=Path,
        required=True,
        help="评估指标 JSON 文件路径",
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("evaluation_results/plots"),
        help="输出目录",
    )

    args = parser.parse_args()

    if not args.metrics_file.exists():
        logger.error(f"文件不存在: {args.metrics_file}")
        return

    with open(args.metrics_file, encoding="utf-8") as f:
        metrics = json.load(f)

    logger.info(f"已加载评估指标: {args.metrics_file}")

    visualizer = EvaluationVisualizer(metrics, args.output_dir)
    visualizer.generate_all_plots()

    logger.info("可视化完成")


if __name__ == "__main__":
    main()
