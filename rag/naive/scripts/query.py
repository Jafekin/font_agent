"""NaiveRAG 检索 CLI：文本/图片向量检索，输出 metadata。

用法示例：
  python -m rag.naive.scripts.query text "五帝本紀" --limit 5
  python -m rag.naive.scripts.query image path/to/image.jpg --limit 3
  python -m rag.naive.scripts.query text "司马迁" --json
  python -m rag.naive.scripts.query image img.jpg --filter type=image
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from rag.naive.retriever import TxtaiRetriever  # noqa: E402

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")

DEFAULT_INDEX = PROJECT_ROOT / "rag" / "naive" / "index"


def _parse_filters(filter_args: list[str]) -> dict:
    """将 key=value 列表解析为过滤字典。"""
    filters = {}
    for f in filter_args or []:
        if "=" in f:
            k, v = f.split("=", 1)
            filters[k.strip()] = v.strip()
    return filters


def _print_result(r: dict, json_out: bool) -> None:
    if json_out:
        print(json.dumps(r, ensure_ascii=False, indent=2, default=str))
        return

    print(f"\n  id     : {r.get('id', '—')}")
    print(f"  score  : {r.get('score', 0):.4f}")

    meta = r.get("metadata") or {}
    text_info = r.get("text_info") or meta.get("text_info", "")
    image_path = r.get("image_path") or meta.get("image_path", "")

    if text_info:
        preview = text_info[:100].replace("\n", " ")
        print(f"  text   : {preview}{'…' if len(text_info) > 100 else ''}")
    if image_path:
        print(f"  image  : {image_path}")

    # 输出所有 metadata 字段
    skip = {"text_info", "image_path"}
    for k, v in meta.items():
        if k not in skip and v not in (None, "", []):
            print(f"  {k:<10}: {v}")


def cmd_text(retriever: TxtaiRetriever, args: argparse.Namespace) -> None:
    filters = _parse_filters(args.filter)
    results = retriever.search(args.query, k=args.limit, filters=filters or None)
    if not args.json:
        print(f"文本检索 '{args.query}'，共 {len(results)} 条结果：")
    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2, default=str))
    else:
        for r in results:
            _print_result(r, json_out=False)
        print()


def cmd_image(retriever: TxtaiRetriever, args: argparse.Namespace) -> None:
    image_path = Path(args.image)
    if not image_path.exists():
        print(f"错误：图片不存在：{image_path}", file=sys.stderr)
        sys.exit(1)
    filters = _parse_filters(args.filter)
    results = retriever.search_by_image(str(image_path), k=args.limit, filters=filters or None)
    if not args.json:
        print(f"图片检索 {image_path.name}，共 {len(results)} 条结果：")
    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2, default=str))
    else:
        for r in results:
            _print_result(r, json_out=False)
        print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="NaiveRAG 检索 CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--index", default=str(DEFAULT_INDEX),
                        help="索引目录（默认 rag/naive/index）")
    parser.add_argument("-v", "--verbose", action="store_true", help="显示详细日志")

    sub = parser.add_subparsers(dest="cmd", required=True)

    # text
    p = sub.add_parser("text", help="文本向量检索")
    p.add_argument("query", help="检索关键词")
    p.add_argument("--limit", type=int, default=5, help="返回结果数（默认 5）")
    p.add_argument("--filter", nargs="*", metavar="key=value",
                   help="元数据过滤，如 --filter type=image")
    p.add_argument("--json", action="store_true", help="JSON 格式输出")

    # image
    p = sub.add_parser("image", help="图片向量检索")
    p.add_argument("image", help="查询图片路径")
    p.add_argument("--limit", type=int, default=5, help="返回结果数（默认 5）")
    p.add_argument("--filter", nargs="*", metavar="key=value",
                   help="元数据过滤，如 --filter type=image")
    p.add_argument("--json", action="store_true", help="JSON 格式输出")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.INFO)

    retriever = TxtaiRetriever(args.index)
    if not retriever.is_ready():
        print(f"警告：索引未就绪（{args.index}），将返回假结果。", file=sys.stderr)

    if args.cmd == "text":
        cmd_text(retriever, args)
    elif args.cmd == "image":
        cmd_image(retriever, args)


if __name__ == "__main__":
    main()
