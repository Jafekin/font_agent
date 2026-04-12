"""图片识别 CLI：OCR → NaiveRAG → GraphRAG → 融合打分 → 结构化输出。

用法示例：
  python -m rag.graph.scripts.recognize image.jpg
  python -m rag.graph.scripts.recognize image.jpg --top-k 3 --json
  python -m rag.graph.scripts.recognize image.jpg \\
      --index rag/naive/index \\
      --ocr-token YOUR_TOKEN \\
      --weight-naive 0.4 --weight-hybrid 0.4 --weight-text 0.2
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from rag.graph.client import Neo4jClient          # noqa: E402
from rag.graph.recognizer import ImageRecognizer  # noqa: E402

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")

DEFAULT_INDEX = PROJECT_ROOT / "rag" / "naive" / "index"


def _print_result(r, json_out: bool) -> None:
    if json_out:
        import dataclasses
        def _serial(obj):
            if dataclasses.is_dataclass(obj):
                return dataclasses.asdict(obj)
            return str(obj)
        print(json.dumps(dataclasses.asdict(r), ensure_ascii=False, indent=2, default=_serial))
        return

    print(f"\n{'─'*60}")
    print(f"page_id : {r.page_id}")
    print(f"得分    : final={r.score.final:.4f}  naive={r.score.naive:.4f}"
          f"  hybrid={r.score.graph_hybrid:.4f}  text={r.score.graph_text:.4f}")

    doc = r.document
    if doc:
        print(f"文献    : {doc.get('title', '—')}  朝代={doc.get('dynasty', '—')}"
              f"  著者={doc.get('authors', '—')}")
    ed = r.edition
    if ed:
        print(f"版本    : {ed.get('edition_id', '—')}  类型={ed.get('version_type', '—')}"
              f"  刻工={ed.get('printer', '—')}")
    col = r.collection
    if col:
        print(f"馆藏    : {col.get('institution', '—')}  索书号={col.get('call_number', '—')}")
    lay = r.layout
    if lay:
        print(f"版式    : 行数={lay.get('line_count', '—')}  有注={lay.get('has_annotation', '—')}")
    if r.entities:
        ents = "  ".join(f"{e['text']}({e['type']})" for e in r.entities[:8])
        print(f"实体    : {ents}")
    if r.evidence:
        print(f"证据    : {' | '.join(r.evidence)}")
    if r.ocr_text:
        preview = r.ocr_text[:80].replace("\n", " ")
        print(f"OCR预览 : {preview}{'…' if len(r.ocr_text) > 80 else ''}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="图片识别：OCR + NaiveRAG + GraphRAG 融合检索",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("image", help="待识别图片路径")
    parser.add_argument("--top-k", type=int, default=5, help="返回结果数（默认 5）")
    parser.add_argument("--naive-k", type=int, default=8,
                        help="NaiveRAG 每路检索数量（默认 8）")
    parser.add_argument("--bfs-depth", type=int, default=1,
                        help="GraphRAG BFS 扩展深度（默认 1）")
    parser.add_argument("--text-limit", type=int, default=8,
                        help="GraphRAG 全文检索数量（默认 8）")
    parser.add_argument("--index", default=str(DEFAULT_INDEX),
                        help="NaiveRAG 索引目录（默认 rag/naive/index）")
    parser.add_argument("--no-naive", action="store_true",
                        help="跳过 NaiveRAG 向量检索")
    # OCR
    parser.add_argument("--ocr-token", default=None, help="看典古籍 OCR Token")
    parser.add_argument("--ocr-email", default=None, help="看典古籍 OCR 邮箱")
    # 融合权重
    parser.add_argument("--weight-naive", type=float, default=0.40)
    parser.add_argument("--weight-hybrid", type=float, default=0.40)
    parser.add_argument("--weight-text", type=float, default=0.20)
    # Neo4j
    parser.add_argument("--neo4j-uri", default="bolt://localhost:7687")
    parser.add_argument("--neo4j-user", default="neo4j")
    parser.add_argument("--neo4j-password", default="password")
    parser.add_argument("--neo4j-db", default="neo4j")
    # 输出
    parser.add_argument("--json", action="store_true", help="JSON 格式输出")
    parser.add_argument("-v", "--verbose", action="store_true", help="显示详细日志")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.INFO)

    image_path = Path(args.image)
    if not image_path.exists():
        print(f"错误：图片不存在：{image_path}", file=sys.stderr)
        sys.exit(1)

    # OCR 客户端（可选）
    ocr_client = None
    if args.ocr_token or args.ocr_email:
        try:
            from ocr.client import KandiangujiOCRClient, OCRConfig
            cfg = OCRConfig(token=args.ocr_token or "", email=args.ocr_email or "")
            ocr_client = KandiangujiOCRClient(cfg)
        except Exception as exc:
            print(f"警告：OCR 客户端初始化失败：{exc}", file=sys.stderr)

    weights = {
        "naive": args.weight_naive,
        "graph_hybrid": args.weight_hybrid,
        "graph_text": args.weight_text,
    }

    with Neo4jClient(
        uri=args.neo4j_uri,
        username=args.neo4j_user,
        password=args.neo4j_password,
        database=args.neo4j_db,
    ) as client:
        if not client.verify_connectivity():
            print("错误：无法连接到 Neo4j。", file=sys.stderr)
            sys.exit(1)

        recognizer = ImageRecognizer(
            neo4j_client=client,
            index_path=None if args.no_naive else args.index,
            ocr_client=ocr_client,
            weights=weights,
        )

        results = recognizer.recognize(
            image_path=image_path,
            top_k=args.top_k,
            naive_k=args.naive_k,
            bfs_depth=args.bfs_depth,
            text_limit=args.text_limit,
        )

    if not results:
        print("（无结果）")
        return

    if args.json:
        import dataclasses
        print(json.dumps(
            [dataclasses.asdict(r) for r in results],
            ensure_ascii=False, indent=2,
        ))
    else:
        print(f"识别结果（共 {len(results)} 条，图片：{image_path.name}）：")
        for r in results:
            _print_result(r, json_out=False)
        print()


if __name__ == "__main__":
    main()
