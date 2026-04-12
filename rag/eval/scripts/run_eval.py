"""RAG 评估 CLI。

用法示例：
  # 评估 NaiveRAG
  python -m rag.eval.scripts.run_eval naive \
      --gt rag/eval/data/sample_gt.json \
      --index rag/naive/index \
      --k 5

  # 评估 GraphRAG
  python -m rag.eval.scripts.run_eval graph \
      --gt rag/eval/data/sample_gt.json \
      --k 5

  # 评估混合管道
  python -m rag.eval.scripts.run_eval hybrid \
      --gt rag/eval/data/sample_gt.json \
      --index rag/naive/index \
      --k 5 --bfs-depth 1

  # 同时评估三路并对比
  python -m rag.eval.scripts.run_eval all \
      --gt rag/eval/data/sample_gt.json \
      --index rag/naive/index \
      --k 5 --output rag/eval/results.json
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")

DEFAULT_INDEX = PROJECT_ROOT / "rag" / "naive" / "index"
DEFAULT_GT = PROJECT_ROOT / "rag" / "eval" / "data" / "sample_gt.json"


def _load_gt(path: str) -> list:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("ground truth 文件应为 JSON 数组。")
    return data


def _neo4j_client(args: argparse.Namespace):
    from rag.graph.client import Neo4jClient
    client = Neo4jClient(
        uri=args.neo4j_uri,
        username=args.neo4j_user,
        password=args.neo4j_password,
        database=args.neo4j_db,
    )
    if not client.verify_connectivity():
        print("错误：无法连接到 Neo4j。", file=sys.stderr)
        sys.exit(1)
    return client


def _save_report(report, path: str) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    existing = []
    if out.exists():
        with open(out, "r", encoding="utf-8") as f:
            existing = json.load(f)
    existing.append(report.to_dict())
    with open(out, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)
    print(f"结果已保存至 {out}")


def cmd_naive(args: argparse.Namespace) -> None:
    from rag.eval.evaluator import NaiveRAGEvaluator
    gt = _load_gt(args.gt)
    evaluator = NaiveRAGEvaluator(index_path=args.index, k=args.k)
    report = evaluator.evaluate(gt)
    report.pipeline = "naive"
    report.print_summary()
    if args.output:
        _save_report(report, args.output)


def cmd_graph(args: argparse.Namespace) -> None:
    from rag.eval.evaluator import GraphRAGEvaluator
    gt = _load_gt(args.gt)
    client = _neo4j_client(args)
    evaluator = GraphRAGEvaluator(neo4j_client=client, k=args.k)
    report = evaluator.evaluate(gt)
    report.pipeline = "graph"
    report.print_summary()
    client.close()
    if args.output:
        _save_report(report, args.output)


def cmd_hybrid(args: argparse.Namespace) -> None:
    from rag.eval.evaluator import HybridEvaluator
    gt = _load_gt(args.gt)
    client = _neo4j_client(args)
    evaluator = HybridEvaluator(
        neo4j_client=client,
        index_path=args.index,
        k=args.k,
        bfs_depth=args.bfs_depth,
    )
    report = evaluator.evaluate(gt)
    report.pipeline = "hybrid"
    report.print_summary()
    client.close()
    if args.output:
        _save_report(report, args.output)


def cmd_all(args: argparse.Namespace) -> None:
    from rag.eval.evaluator import NaiveRAGEvaluator, GraphRAGEvaluator, HybridEvaluator
    gt = _load_gt(args.gt)
    reports = []

    print(">>> 评估 NaiveRAG ...")
    naive_ev = NaiveRAGEvaluator(index_path=args.index, k=args.k)
    r = naive_ev.evaluate(gt)
    r.pipeline = "naive"
    r.print_summary()
    reports.append(r)

    client = _neo4j_client(args)

    print(">>> 评估 GraphRAG ...")
    graph_ev = GraphRAGEvaluator(neo4j_client=client, k=args.k)
    r = graph_ev.evaluate(gt)
    r.pipeline = "graph"
    r.print_summary()
    reports.append(r)

    print(">>> 评估 Hybrid ...")
    hybrid_ev = HybridEvaluator(
        neo4j_client=client,
        index_path=args.index,
        k=args.k,
        bfs_depth=args.bfs_depth,
    )
    r = hybrid_ev.evaluate(gt)
    r.pipeline = "hybrid"
    r.print_summary()
    reports.append(r)

    client.close()

    # 对比摘要
    print(f"\n{'─'*60}")
    print(f"{'Pipeline':<12} {'P@K':>7} {'R@K':>7} {'F1@K':>7} {'MRR':>7} {'NDCG':>7} {'Hit':>7}")
    print(f"{'─'*60}")
    for rep in reports:
        m = rep.retrieval
        print(f"{rep.pipeline:<12} {m.precision:>7.4f} {m.recall:>7.4f} "
              f"{m.f1:>7.4f} {m.mrr:>7.4f} {m.ndcg:>7.4f} {m.hit_rate:>7.4f}")
    print(f"{'─'*60}\n")

    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            json.dump([rep.to_dict() for rep in reports], f, ensure_ascii=False, indent=2)
        print(f"结果已保存至 {out}")


def _add_common(p: argparse.ArgumentParser) -> None:
    p.add_argument("--gt", default=str(DEFAULT_GT), help="ground truth JSON 路径")
    p.add_argument("--k", type=int, default=5, help="检索 Top-K（默认 5）")
    p.add_argument("--output", default=None, help="结果输出 JSON 路径（可选）")
    p.add_argument("-v", "--verbose", action="store_true")


def _add_neo4j(p: argparse.ArgumentParser) -> None:
    p.add_argument("--neo4j-uri", default="bolt://localhost:7687")
    p.add_argument("--neo4j-user", default="neo4j")
    p.add_argument("--neo4j-password", default="password")
    p.add_argument("--neo4j-db", default="neo4j")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="RAG 系统评估",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    # naive
    p = sub.add_parser("naive", help="评估 NaiveRAG")
    _add_common(p)
    p.add_argument("--index", default=str(DEFAULT_INDEX), help="NaiveRAG 索引目录")

    # graph
    p = sub.add_parser("graph", help="评估 GraphRAG")
    _add_common(p)
    _add_neo4j(p)

    # hybrid
    p = sub.add_parser("hybrid", help="评估混合管道")
    _add_common(p)
    p.add_argument("--index", default=str(DEFAULT_INDEX))
    p.add_argument("--bfs-depth", type=int, default=1)
    _add_neo4j(p)

    # all
    p = sub.add_parser("all", help="同时评估三路并对比")
    _add_common(p)
    p.add_argument("--index", default=str(DEFAULT_INDEX))
    p.add_argument("--bfs-depth", type=int, default=1)
    _add_neo4j(p)

    args = parser.parse_args()
    if args.verbose:
        logging.getLogger().setLevel(logging.INFO)

    dispatch = {
        "naive": cmd_naive,
        "graph": cmd_graph,
        "hybrid": cmd_hybrid,
        "all": cmd_all,
    }
    dispatch[args.cmd](args)


if __name__ == "__main__":
    main()
