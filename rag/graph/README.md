# GraphRAG 模块

基于 Neo4j 的古籍知识图谱，支持结构化检索、BFS 混合检索与版本推断。

## 架构

```
rag/data/  →  NaiveDataLoader（PageData）
                ↓
           GraphBuilder  →  Neo4j
                ↓
           GraphRetriever                    ImageRecognizer
             ├── search_by_text()      ←───── OCR（看典古籍）
             ├── find_similar()               ↓
             ├── find_by_entity()       NaiveRAG 向量检索（图片+文本）
             ├── find_by_edition()            ↓
             ├── infer_edition()        GraphRAG BFS 混合检索
             ├── get_entity_cooccurrence()    ↓
             └── hybrid_search()        融合打分 → RecognitionResult
                                        （Document/Edition/Collection/
                                          Page/Layout/Entity）
```

**节点类型**：Document · Edition · Collection · Page · Layout · Entity

**关系类型**：HAS_EDITION · HAS_PAGE · HAS_COLLECTION · HAS_LAYOUT · MENTIONS · MENTIONS_ENTITY · SAME_EDITION · SIMILAR_TO

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
# 基础构建（含实体提取，构建前会提示确认清空数据库）
python -m rag.graph.scripts.build_graph --data-dir rag/data

# 含相似关系
python -m rag.graph.scripts.build_graph \
  --data-dir rag/data \
  --embeddings rag/naive/index/embeddings.npy \
  --ids rag/naive/index/ids.json \
  --sim-threshold 0.88

# 查看当前统计（不构建）
python -m rag.graph.scripts.build_graph --stats-only
```

### 3. 图片识别（OCR + NaiveRAG + GraphRAG）

```bash
# 基础识别（需 Neo4j + NaiveRAG 索引）
python -m rag.graph.scripts.recognize ocr/tests/test.jpg   --top-k 3

# 含 OCR + 自定义权重
python -m rag.graph.scripts.recognize image.jpg \
  --ocr-token YOUR_TOKEN \
  --index rag/naive/index \
  --weight-naive 0.4 --weight-hybrid 0.4 --weight-text 0.2 \
  --top-k 3

# JSON 输出
python -m rag.graph.scripts.recognize ocr/tests/test.jpg --json
```

### 4. 检索查询

```bash
# 全文检索
python -m rag.graph.scripts.query text "五帝本紀" --limit 5

# 视觉相似页
python -m rag.graph.scripts.query similar page_001 --min-score 0.88

# 实体关联页
python -m rag.graph.scripts.query entity "司马迁"

# 版本页面列表
python -m rag.graph.scripts.query edition edition_shiji_A

# 页面详情
python -m rag.graph.scripts.query page page_001

# 版本推断
python -m rag.graph.scripts.query infer page_unknown_001

# 实体共现
python -m rag.graph.scripts.query cooccur "司马迁" --limit 10

# 混合检索（向量种子 + BFS 图谱扩展）
python -m rag.graph.scripts.query hybrid page_001:0.92 page_007:0.85 --depth 2

# 图谱统计
python -m rag.graph.scripts.query stats

# JSON 输出（所有子命令均支持 --json）
python -m rag.graph.scripts.query text "本紀" --json
```

### 5. Python API

```python
from rag.graph import Neo4jClient, GraphBuilder, GraphRetriever, ImageRecognizer

with Neo4jClient(uri="bolt://localhost:7687", password="password") as client:
    client.create_schema()

    # 构建
    builder = GraphBuilder(client)
    stats = builder.build("rag/data", extract_entities=True)
    print(stats)  # {"documents": N, "editions": N, "pages": N, ...}

    retriever = GraphRetriever(client)

    # 全文检索
    results = retriever.search_by_text("五帝本紀", limit=5)

    # 相似页面
    similar = retriever.find_similar("page_001", min_score=0.88)

    # 版本推断
    inferred = retriever.infer_edition("page_unknown")
    # → {"edition_id": ..., "version_type": "A", "confidence": 0.91}

    # 实体查询
    pages = retriever.find_by_entity("司马迁")

    # 实体共现
    cooccur = retriever.get_entity_cooccurrence("司马迁", limit=10)

    # 混合检索（向量种子 + BFS 图谱扩展）
    seeds = [("page_001", 0.92), ("page_007", 0.85)]
    results = retriever.hybrid_search(seeds, bfs_depth=1, top_k=10)
    for r in results:
        print(r.page_id, r.score, r.evidence)

    # 图片识别（OCR → NaiveRAG → GraphRAG → 融合打分）
    recognizer = ImageRecognizer(
        neo4j_client=client,
        index_path="rag/naive/index",   # 可选，缺失时跳过向量检索
        ocr_client=None,                # 可选，传入 KandiangujiOCRClient
        weights={"naive": 0.4, "graph_hybrid": 0.4, "graph_text": 0.2},
    )
    results = recognizer.recognize("image.jpg", top_k=5)
    for r in results:
        print(r.page_id, r.score.final)
        print(r.document)   # {"title": ..., "dynasty": ..., "authors": ...}
        print(r.edition)    # {"edition_id": ..., "version_type": ..., "printer": ...}
        print(r.collection) # {"institution": ..., "call_number": ...}
        print(r.layout)     # {"line_count": ..., "has_annotation": ...}
        print(r.entities)   # [{"text": "司马迁", "type": "PERSON"}, ...]
        print(r.evidence)   # ["NaiveRAG 向量相似度 0.92", "GraphRAG BFS 得分 1.43", ...]
```

## 图片识别流程（ImageRecognizer）

```
图片输入
  ↓
OCR（看典古籍，可选）→ 识别文本
  ↓
NaiveRAG
  ├── 图片向量检索（Chinese-CLIP）
  └── OCR 文本向量检索
  ↓ Top-K 候选 + 得分
GraphRAG
  ├── BFS 混合检索（SAME_EDITION×1.0 / MENTIONS_ENTITY×0.7 / SIMILAR_TO×0.5）
  └── OCR 文本全文检索
  ↓
融合打分（三路归一化加权求和）
  naive×0.4 + graph_hybrid×0.4 + graph_text×0.2
  ↓
Top-K 页面 → 从 Neo4j 拉取完整结构化信息
  → RecognitionResult（Document / Edition / Collection / Page / Layout / Entity）
```

## 混合检索流程

```
向量 Top-K 种子
    ↓
BFS 扩展（每层）
    ├── SAME_EDITION     同版本相邻页     权重 1.0
    ├── MENTIONS_ENTITY  共享命名实体页   权重 0.7
    └── SIMILAR_TO       视觉相似页       权重 0.5
    ↓
综合得分 = seed_score + Σ(edge_score × edge_weight × 0.6^depth)
    ↓
Top-K 排序输出（含图谱关系路径）
```

## CLI 参数

### recognize

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `image` | — | 待识别图片路径（必填） |
| `--top-k` | 5 | 返回结果数 |
| `--naive-k` | 8 | NaiveRAG 每路检索数量 |
| `--bfs-depth` | 1 | GraphRAG BFS 扩展深度 |
| `--text-limit` | 8 | GraphRAG 全文检索数量 |
| `--index` | `rag/naive/index` | NaiveRAG 索引目录 |
| `--no-naive` | False | 跳过 NaiveRAG 向量检索 |
| `--ocr-token` | — | 看典古籍 OCR Token |
| `--ocr-email` | — | 看典古籍 OCR 邮箱 |
| `--weight-naive` | 0.40 | NaiveRAG 融合权重 |
| `--weight-hybrid` | 0.40 | GraphRAG BFS 融合权重 |
| `--weight-text` | 0.20 | GraphRAG 全文融合权重 |
| `--json` | False | JSON 格式输出 |
| `-v` | False | 显示详细日志 |

### build_graph

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `--data-dir` | `rag/data` | 数据目录 |
| `--neo4j-uri` | `bolt://localhost:7687` | Neo4j 地址 |
| `--neo4j-user` | `neo4j` | 用户名 |
| `--neo4j-password` | `password` | 密码 |
| `--neo4j-db` | `neo4j` | 数据库名 |
| `--entities` | True | 提取命名实体 |
| `--embeddings` | — | embeddings.npy 路径 |
| `--ids` | — | ids.json 路径 |
| `--sim-threshold` | 0.88 | 相似度阈值 |
| `--sim-top-k` | 10 | 每页保留的相似关系数 |
| `--clear` | True | 构建前清空数据库（需确认） |
| `--stats-only` | False | 仅打印统计，不构建 |

### query（子命令）

| 子命令 | 必填参数 | 可选参数 | 说明 |
| --- | --- | --- | --- |
| `text` | `query` | `--limit` | 全文检索 OCR 文本 |
| `similar` | `page_id` | `--min-score`, `--limit` | 视觉相似页 |
| `entity` | `entity_text` | `--limit` | 实体关联页 |
| `edition` | `edition_id` | `--limit` | 版本页面列表 |
| `page` | `page_id` | | 页面详情 |
| `infer` | `page_id` | `--min-score` | 版本推断 |
| `cooccur` | `entity_text` | `--limit` | 实体共现统计 |
| `hybrid` | `seeds...` | `--depth`, `--top-k` | 混合检索 |
| `stats` | | | 图谱统计 |

所有子命令均支持 `--json` 输出，以及 `--neo4j-uri/user/password/db` 连接参数。

## Schema 摘要

| 节点 | 主键 | 关键属性 |
| --- | --- | --- |
| Document | `doc_id` | title, dynasty, authors, annotators, total_juan |
| Edition | `edition_id` | version_type, annotation_system, printer, extant_juan |
| Collection | `collection_id` | institution, call_number |
| Page | `page_id` | image_path, ocr_text, ocr_confidence, is_vertical |
| Layout | `layout_id` | line_count, has_annotation |
| Entity | `entity_id` | entity_text, entity_type (PERSON/PLACE/WORK/DYNASTY) |

## 依赖

```
neo4j >= 5.0
numpy >= 1.20
```
