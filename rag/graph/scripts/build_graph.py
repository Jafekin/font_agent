"""从 rag/data/ 构建 Neo4j 知识图谱的 CLI 脚本。

用法示例：
  python -m rag.graph.scripts.build_graph --data-dir rag/data
  python -m rag.graph.scripts.build_graph --data-dir rag/data \\
      --embeddings rag/naive/index/embeddings.npy \\
      --ids rag/naive/index/ids.json \\
      --sim-threshold 0.88 --entities
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from rag.graph.client import Neo4jClient  # noqa: E402
from rag.graph.builder import GraphBuilder  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

DEFAULT_DATA_DIR = PROJECT_ROOT / "rag" / "data"
DEFAULT_EMBEDDINGS = PROJECT_ROOT / "rag" / "naive" / "index" / "embeddings.npy"
DEFAULT_IDS = PROJECT_ROOT / "rag" / "naive" / "index" / "ids.json"


def main() -> None:
    parser = argparse.ArgumentParser(description="构建 GraphRAG 知识图谱")
    parser.add_argument("--data-dir", default=str(DEFAULT_DATA_DIR),
                        help="rag/data/ 目录路径")
    parser.add_argument("--neo4j-uri", default="bolt://localhost:7687",
                        help="Neo4j URI")
    parser.add_argument("--neo4j-user", default="neo4j", help="Neo4j 用户名")
    parser.add_argument("--neo4j-password", default="password", help="Neo4j 密码")
    parser.add_argument("--neo4j-db", default="neo4j", help="Neo4j 数据库名")
    parser.add_argument("--entities", action="store_true", default=True,
                        help="是否从 OCR 文本提取命名实体")
    parser.add_argument("--embeddings", default=None,
                        help="embeddings.npy 路径（构建 SIMILAR_TO 关系）")
    parser.add_argument("--ids", default=None,
                        help="ids.json 路径（与 --embeddings 配合使用）")
    parser.add_argument("--sim-threshold", type=float, default=0.88,
                        help="相似度阈值（默认 0.88）")
    parser.add_argument("--sim-top-k", type=int, default=10,
                        help="每页最多保留的相似关系数（默认 10）")
    parser.add_argument("--clear", action="store_true", default=True,
                        help="构建前清空数据库（不可逆）")
    parser.add_argument("--stats-only", action="store_true", default=False,
                        help="仅打印当前图谱统计信息，不执行构建")

    args = parser.parse_args()

    with Neo4jClient(
        uri=args.neo4j_uri,
        username=args.neo4j_user,
        password=args.neo4j_password,
        database=args.neo4j_db,
    ) as client:
        if not client.verify_connectivity():
            logger.error("无法连接到 Neo4j，请检查连接参数。")
            sys.exit(1)

        if args.stats_only:
            stats = client.get_statistics()
            print("当前图谱统计：")
            for k, v in stats.items():
                print(f"  {k}: {v}")
            return

        if args.clear:
            answer = input("确认清空数据库？输入 yes 继续：").strip().lower()
            if answer != "yes":
                print("已取消。")
                return
            client.clear_database()

        client.create_schema()

        builder = GraphBuilder(client)
        result = builder.build(
            data_dir=args.data_dir,
            extract_entities=args.entities,
            embeddings_path=args.embeddings,
            ids_path=args.ids,
            similarity_threshold=args.sim_threshold,
            similarity_top_k=args.sim_top_k,
        )

        print("\n构建完成：")
        for k, v in result.items():
            print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
