"""GraphRAG 检索 CLI。

用法示例：
  python -m rag.graph.scripts.query text "五帝本紀" --limit 5
  python -m rag.graph.scripts.query similar page_001 --min-score 0.88
  python -m rag.graph.scripts.query entity "司马迁"
  python -m rag.graph.scripts.query edition edition_shiji_A
  python -m rag.graph.scripts.query page page_001
  python -m rag.graph.scripts.query infer page_unknown_001
  python -m rag.graph.scripts.query cooccur "司马迁" --limit 10
  python -m rag.graph.scripts.query hybrid page_001:0.92 page_007:0.85 --depth 2
  python -m rag.graph.scripts.query stats
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from rag.graph.client import Neo4jClient  # noqa: E402
from rag.graph.retriever import GraphRetriever  # noqa: E402

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")


# ---------------------------------------------------------------------------
# 输出格式化
# ---------------------------------------------------------------------------

def _print_results(results: List[Any], json_out: bool) -> None:
    if json_out:
        rows = []
        for r in results:
            if hasattr(r, "__dict__"):
                rows.append(r.__dict__)
            else:
                rows.append(r)
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return

    if not results:
        print("（无结果）")
        return

    for r in results:
        if hasattr(r, "page_id"):
            meta = r.metadata or {}
            parts = [f"page_id={r.page_id}", f"score={r.score:.4f}"]
            if meta.get("title"):
                parts.append(f"title={meta['title']}")
            if meta.get("version_type"):
                parts.append(f"version={meta['version_type']}")
            if meta.get("edition_id"):
                parts.append(f"edition={meta['edition_id']}")
            evidence = " | ".join(r.evidence) if r.evidence else ""
            print("  " + "  ".join(parts))
            if evidence:
                print(f"    证据: {evidence}")
        else:
            print(" ", r)


def _print_dict(d: Dict[str, Any] | None, json_out: bool) -> None:
    if d is None:
        print("（无结果）")
        return
    if json_out:
        print(json.dumps(d, ensure_ascii=False, indent=2, default=str))
    else:
        for k, v in d.items():
            print(f"  {k}: {v}")


# ---------------------------------------------------------------------------
# 子命令处理
# ---------------------------------------------------------------------------

def cmd_text(retriever: GraphRetriever, args: argparse.Namespace) -> None:
    results = retriever.search_by_text(args.query, limit=args.limit)
    print(f"全文检索 {args.query}，共 {len(results)} 条结果：")
    _print_results(results, args.json)


def cmd_similar(retriever: GraphRetriever, args: argparse.Namespace) -> None:
    results = retriever.find_similar(args.page_id, min_score=args.min_score, limit=args.limit)
    print(f"与 {args.page_id} 相似的页面（min_score={args.min_score}），共 {len(results)} 条：")
    _print_results(results, args.json)


def cmd_entity(retriever: GraphRetriever, args: argparse.Namespace) -> None:
    results = retriever.find_by_entity(args.entity_text, limit=args.limit)
    print(f"提及实体 {args.entity_text} 的页面，共 {len(results)} 条：")
    _print_results(results, args.json)


def cmd_edition(retriever: GraphRetriever, args: argparse.Namespace) -> None:
    results = retriever.find_by_edition(args.edition_id, limit=args.limit)
    print(f"版本 {args.edition_id} 下的页面，共 {len(results)} 条：")
    _print_results(results, args.json)


def cmd_page(retriever: GraphRetriever, args: argparse.Namespace) -> None:
    result = retriever.get_page(args.page_id)
    print(f"页面详情 {args.page_id}：")
    _print_dict(result, args.json)


def cmd_infer(retriever: GraphRetriever, args: argparse.Namespace) -> None:
    result = retriever.infer_edition(args.page_id, min_score=args.min_score)
    print(f"版本推断 {args.page_id}：")
    _print_dict(result, args.json)


def cmd_cooccur(retriever: GraphRetriever, args: argparse.Namespace) -> None:
    results = retriever.get_entity_cooccurrence(args.entity_text, limit=args.limit)
    print(f"与 {args.entity_text} 共现的实体，共 {len(results)} 条：")
    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        for r in results:
            print(f"  {r.get('entity')}  共现次数={r.get('cooccur')}")


def cmd_hybrid(retriever: GraphRetriever, args: argparse.Namespace) -> None:
    seeds = []
    for s in args.seeds:
        if ":" in s:
            pid, score = s.rsplit(":", 1)
            seeds.append((pid, float(score)))
        else:
            seeds.append((s, 1.0))
    results = retriever.hybrid_search(seeds, bfs_depth=args.depth, top_k=args.top_k)
    print(f"混合检索（{len(seeds)} 个种子，BFS 深度={args.depth}），共 {len(results)} 条：")
    _print_results(results, args.json)


def cmd_stats(client: Neo4jClient, args: argparse.Namespace) -> None:
    stats = client.get_statistics()
    if args.json:
        print(json.dumps(stats, ensure_ascii=False, indent=2))
    else:
        print("图谱统计：")
        for k, v in stats.items():
            print(f"  {k}: {v}")


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--limit", type=int, default=10, help="返回结果数上限")
    parser.add_argument("--json", action="store_true", help="以 JSON 格式输出")


def _add_neo4j_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--neo4j-uri", default="bolt://localhost:7687")
    parser.add_argument("--neo4j-user", default="neo4j")
    parser.add_argument("--neo4j-password", default="password")
    parser.add_argument("--neo4j-db", default="neo4j")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="GraphRAG 检索 CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    _add_neo4j_args(parser)

    sub = parser.add_subparsers(dest="cmd", required=True)

    # text
    p = sub.add_parser("text", help="全文检索 OCR 文本")
    p.add_argument("query", help="检索关键词")
    _add_common(p)

    # similar
    p = sub.add_parser("similar", help="查找视觉相似页面")
    p.add_argument("page_id", help="源页面 ID")
    p.add_argument("--min-score", type=float, default=0.85)
    _add_common(p)

    # entity
    p = sub.add_parser("entity", help="查找提及某实体的页面")
    p.add_argument("entity_text", help="实体文本（如：司马迁）")
    _add_common(p)

    # edition
    p = sub.add_parser("edition", help="列出某版本下的所有页面")
    p.add_argument("edition_id", help="版本 ID")
    _add_common(p)

    # page
    p = sub.add_parser("page", help="查看页面详情")
    p.add_argument("page_id", help="页面 ID")
    p.add_argument("--json", action="store_true", help="以 JSON 格式输出")

    # infer
    p = sub.add_parser("infer", help="推断页面所属版本")
    p.add_argument("page_id", help="页面 ID")
    p.add_argument("--min-score", type=float, default=0.85)
    p.add_argument("--json", action="store_true", help="以 JSON 格式输出")

    # cooccur
    p = sub.add_parser("cooccur", help="查找实体共现")
    p.add_argument("entity_text", help="实体文本")
    _add_common(p)

    # hybrid
    p = sub.add_parser("hybrid", help="混合检索（向量种子 + BFS 图谱扩展）")
    p.add_argument("seeds", nargs="+", help="种子页面，格式 page_id 或 page_id:score")
    p.add_argument("--depth", type=int, default=1, help="BFS 扩展深度（默认 1）")
    p.add_argument("--top-k", type=int, default=10, help="返回结果数（默认 10）")
    p.add_argument("--json", action="store_true", help="以 JSON 格式输出")

    # stats
    p = sub.add_parser("stats", help="打印图谱统计信息")
    p.add_argument("--json", action="store_true", help="以 JSON 格式输出")

    args = parser.parse_args()

    with Neo4jClient(
        uri=args.neo4j_uri,
        username=args.neo4j_user,
        password=args.neo4j_password,
        database=args.neo4j_db,
    ) as client:
        if not client.verify_connectivity():
            print("错误：无法连接到 Neo4j，请检查连接参数。", file=sys.stderr)
            sys.exit(1)

        if args.cmd == "stats":
            cmd_stats(client, args)
            return

        retriever = GraphRetriever(client)
        dispatch = {
            "text": cmd_text,
            "similar": cmd_similar,
            "entity": cmd_entity,
            "edition": cmd_edition,
            "page": cmd_page,
            "infer": cmd_infer,
            "cooccur": cmd_cooccur,
            "hybrid": cmd_hybrid,
        }
        dispatch[args.cmd](retriever, args)


if __name__ == "__main__":
    main()
