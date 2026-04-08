# GraphRAG 模块

基于 Neo4j 的古籍知识图谱，支持结构化检索与版本推断。

## 架构

```
rag/data/  →  NaiveDataLoader（PageData）
                ↓
           GraphBuilder  →  Neo4j
                ↓
           GraphRetriever  →  检索 / 版本推断 / 实体查询
```

**节点类型**：Document · Edition · Collection · Page · Layout · Entity

**关系类型**：HAS_EDITION · HAS_PAGE · STORED_IN · HAS_LAYOUT · MENTIONS · SIMILAR_TO

## 快速上手

### 1. 启动 Neo4j

```bash
docker run -d --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/password \
  neo4j:latest
```

### 2. 构建图谱

```bash
# 基础构建
python -m rag.graph.scripts.build_graph --data-dir rag/data

# 含实体提取 + 相似关系
python -m rag.graph.scripts.build_graph \
  --data-dir rag/data \
  --entities \
  --embeddings rag/naive/index/embeddings.npy \
  --ids rag/naive/index/ids.json \
  --sim-threshold 0.88

# 查看当前统计
python -m rag.graph.scripts.build_graph --stats-only
```

### 3. Python API

```python
from rag.graph import Neo4jClient, GraphBuilder, GraphRetriever

with Neo4jClient(uri="bolt://localhost:7687", password="password") as client:
    client.create_schema()

    # 构建
    builder = GraphBuilder(client)
    stats = builder.build("rag/data", extract_entities=True)
    print(stats)  # {"documents": N, "editions": N, "pages": N, ...}

    # 检索
    retriever = GraphRetriever(client)

    # 全文检索
    results = retriever.search_by_text("五帝本紀", limit=5)

    # 相似页面
    similar = retriever.find_similar("page_001", min_score=0.88)

    # 版本推断
    inferred = retriever.infer_edition("page_unknown")
    # → {"edition_id": ..., "version_type": "A", "confidence": 0.91}

    # 实���查询
    pages = retriever.find_by_entity("司马迁")

    # 统计
    print(retriever.get_edition_stats())
```

## CLI 参数

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `--data-dir` | `rag/data` | 数据目录 |
| `--neo4j-uri` | `bolt://localhost:7687` | Neo4j 地址 |
| `--neo4j-password` | `password` | 密码 |
| `--entities` | False | 提取命名实体 |
| `--embeddings` | — | embeddings.npy 路径 |
| `--ids` | — | ids.json 路径 |
| `--sim-threshold` | 0.88 | 相似度阈值 |
| `--sim-top-k` | 10 | 每页保留的相似关系数 |
| `--clear` | False | 构建前清空数据库 |
| `--stats-only` | False | 仅打印统计，不构建 |

## Schema 摘要

| 节点 | 主键 | 关键属性 |
| --- | --- | --- |
| Document | `doc_id` | title, dynasty, authors, annotators, total_juan |
| Edition | `edition_id` | version_type, annotation_system, printer, extant_juan |
| Collection | `collection_id` | institution, call_number |
| Page | `page_id` | image_path, ocr_text, ocr_confidence, is_vertical |
| Layout | `layout_id` | line_count, has_annotation |
| Entity | `entity_id` | entity_text, entity_type (PERSON/PLACE) |

## 依赖

```
neo4j >= 5.0
numpy >= 1.20
```
