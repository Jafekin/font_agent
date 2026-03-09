# 古籍知识图谱模块

基于 Neo4j 的古籍文献知识图谱系统，支持 GraphRAG 检索和证据路径解释。

## 概述

本模块实现了完整的古籍知识图谱建模、构建和查询功能，包括：

- **8 种核心实体**: Document（文献）、Volume（卷次）、Page（页面）、Edition（版本）、Collection（馆藏）、Layout（版式）、Seal（钤印）、Entity（实体词条）
- **10 种关系类型**: HAS_VOLUME、HAS_PAGE、SIMILAR_TO、BELONGS_TO_EDITION、STORED_IN、HAS_LAYOUT、HAS_SEAL、MENTIONS、RELATED_TO、CITES
- **证据路径解释**: 自动生成可解释的查询证据链
- **典型查询用例**: 50+ 个预定义查询模板

---

## 快速开始

### 1. 安装依赖

```bash
pip install neo4j numpy
```

### 2. 启动 Neo4j

```bash
# 使用 Docker
docker run -d \
  --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/password \
  neo4j:latest

# 访问 http://localhost:7474 验证
```

### 3. 初始化图谱

```python
from graph import Neo4jClient

# 连接数据库
client = Neo4jClient(
    uri="bolt://localhost:7687",
    username="neo4j",
    password="password",
)

# 验证连接
if client.verify_connectivity():
    print("✓ 连接成功")

# 创建约束和索引
client.create_constraints()
```

### 4. 构建图谱

```python
from pathlib import Path
from graph import GraphBuilder

# 初始化构建器
builder = GraphBuilder(client)

# 从 metadata.json 构建图谱
stats = builder.build_from_metadata(
    metadata_path=Path("rag/index/metadata.json"),
)

print(f"构建完成: {stats}")
# 输出: {'documents': 10, 'volumes': 50, 'pages': 1000, ...}

# 构建相似关系
relation_count = builder.build_similarity_relations(
    embeddings_path=Path("rag/index/embeddings.npy"),
    ids_path=Path("rag/index/ids.json"),
    top_k=10,
    threshold=0.8,
)

print(f"创建了 {relation_count} 个相似关系")
```

### 5. 查询图谱

```python
from graph import GraphQueryInterface

# 初始化查询接口
query = GraphQueryInterface(client)

# 查询文献的所有卷次
volumes = query.get_document_volumes("doc_shiji")
print(f"找到 {len(volumes)} 卷")

# 全文搜索
results = query.fulltext_search("黃帝", limit=10)
for r in results:
    print(f"{r['page_id']}: {r['score']:.2f}")

# 查询相似页面
similar = query.get_similar_pages("page_001", limit=5)
for s in similar:
    print(f"{s['p2.page_id']}: {s['r.similarity_score']:.2%}")

# 版本推断（带证据链）
inference = query.infer_edition_by_similarity("page_unknown_001")
print(inference['explanation'])
```

---

## 核心功能

### 1. 图谱建模

详见 [SCHEMA.md](SCHEMA.md)

**核心实体**:
- Document: 文献（书名、作者、朝代）
- Volume: 卷次（卷号、标题）
- Page: 页面（图片、OCR 文本、置信度）
- Edition: 版本（刻本、抄本、出版信息）
- Collection: 馆藏（机构、索书号）
- Layout: 版式（列数、边框、鱼尾）
- Seal: 钤印（印文、所有者）
- Entity: 实体（人名、地名、官职）

**核心关系**:
- HAS_VOLUME: 文献→卷次
- HAS_PAGE: 卷次→页面
- SIMILAR_TO: 页面↔页面（相似度）
- BELONGS_TO_EDITION: 页面→版本
- MENTIONS: 页面→实体

### 2. 典型查询

详见 [QUERIES.md](QUERIES.md)

**基础查询**:
```python
# 获取文献卷次
volumes = query.get_document_volumes("doc_shiji")

# 全文搜索
results = query.fulltext_search("黃帝")

# 查询特定版本的页面
pages = query.get_pages_by_edition("ed_song")
```

**版本推断**:
```python
# 通过相似页面推断版本
inference = query.infer_edition_by_similarity("page_unknown_001")
print(f"推断版本: {inference['inferred_edition']}")
print(f"置信度: {inference['confidence']:.2%}")
print(f"证据数量: {inference['evidence_count']}")
```

**实体关系**:
```python
# 查询提及某人物的页面
pages = query.get_pages_mentioning_entity("司馬遷", entity_type="PERSON")

# 查询实体共现
co_entities = query.get_entity_co_occurrence("司馬遷", entity_type="PERSON")

# 查询实体关系路径
path = query.find_entity_relation_path("司馬遷", "孔安國")
print(path['explanation'])
```

**推荐系统**:
```python
# 推荐相关页面
recommendations = query.recommend_related_pages("page_001", limit=10)
for rec in recommendations:
    print(f"{rec['page_id']}: {rec['explanation']}")
```

### 3. 证据路径解释

```python
from graph import EvidenceExplainer

explainer = EvidenceExplainer()

# 解释版本推断
inference = explainer.explain_edition_inference(
    target_page_id="page_unknown_001",
    similar_pages=[
        {"page_id": "page_001", "similarity": 0.92, "edition": "宋刻本"},
        {"page_id": "page_002", "similarity": 0.89, "edition": "宋刻本"},
    ],
    layout_matches=[],
    seal_matches=[],
)

print(inference['summary'])
# 输出:
# 版本推断结果: page_unknown_001 可能属于 宋刻本
# 置信度: 90.50%
# 证据数量: 2
#
# 证据来源:
#   - 相似页面: 2 条
```

---

## API 参考

### Neo4jClient

```python
from graph import Neo4jClient

client = Neo4jClient(
    uri="bolt://localhost:7687",
    username="neo4j",
    password="password",
    database="neo4j",
)

# 验证连接
client.verify_connectivity()

# 执行查询
results = client.execute_query(
    "MATCH (d:Document) RETURN d.title LIMIT 10"
)

# 创建节点
client.create_document({
    "doc_id": "doc_001",
    "title": "史記",
    "author": "司馬遷",
    "dynasty": "漢",
})

# 创建关系
client.create_has_volume_relation(
    doc_id="doc_001",
    volume_id="vol_001",
    sequence=1,
)

# 获取统计信息
stats = client.get_statistics()
print(stats)
```

### GraphBuilder

```python
from graph import GraphBuilder

builder = GraphBuilder(client)

# 从 metadata 构建图谱
stats = builder.build_from_metadata(
    metadata_path=Path("metadata.json"),
)

# 构建相似关系
relation_count = builder.build_similarity_relations(
    embeddings_path=Path("embeddings.npy"),
    ids_path=Path("ids.json"),
    top_k=10,
    threshold=0.8,
)
```

### GraphQueryInterface

```python
from graph import GraphQueryInterface

query = GraphQueryInterface(client)

# 基础查询
volumes = query.get_document_volumes("doc_001")
pages = query.get_volume_pages("vol_001")
results = query.fulltext_search("关键词")

# 版本查询
pages = query.get_pages_by_edition("ed_001")
pages = query.get_pages_by_layout(column_count=2, border_color="黑口")
stats = query.get_layout_statistics()

# 相似查询
similar = query.get_similar_pages("page_001", limit=10)
inference = query.infer_edition_by_similarity("page_001")

# 钤印查询
pages = query.get_pages_by_seal("天祿琳琅")
co_seals = query.get_seal_co_occurrence("天祿琳琅")

# 实体查询
pages = query.get_pages_mentioning_entity("司馬遷")
co_entities = query.get_entity_co_occurrence("司馬遷")
path = query.find_entity_relation_path("司馬遷", "孔安國")

# 推荐
recommendations = query.recommend_related_pages("page_001")

# 统计
doc_stats = query.get_document_statistics()
edition_dist = query.get_edition_distribution()
entity_dist = query.get_entity_type_distribution()

# 维护
orphans = query.find_orphan_nodes()
duplicates = query.find_duplicate_pages()
deleted = query.delete_low_quality_similarities(threshold=0.7)
```

### EvidenceExplainer

```python
from graph import EvidenceExplainer

explainer = EvidenceExplainer()

# 解释路径
evidence = explainer.explain_path(path_data, query_context="查询描述")

# 解释版本推断
inference = explainer.explain_edition_inference(
    target_page_id="page_001",
    similar_pages=[...],
    layout_matches=[...],
    seal_matches=[...],
)

# 解释实体关系
relation = explainer.explain_entity_relation(
    entity1_id="司馬遷",
    entity2_id="孔安國",
    paths=[...],
)

# 解释推荐
recommendations = explainer.explain_recommendation(
    target_id="page_001",
    recommendations=[...],
)
```

---

## 数据模型

### Document（文献）

```python
from graph.models import Document

doc = Document(
    doc_id="doc_shiji",
    title="史記",
    author="司馬遷",
    dynasty="漢",
    category="史部",
    description="中國第一部紀傳體通史",
)

# 转换为字典
doc_dict = doc.to_dict()

# 从字典创建
doc = Document.from_dict(doc_dict)
```

其他模型类似：`Volume`、`Page`、`Edition`、`Collection`、`Layout`、`Seal`、`Entity`

---

## 使用示例

### 示例 1: 构建完整图谱

```python
from pathlib import Path
from graph import Neo4jClient, GraphBuilder

# 1. 连接数据库
client = Neo4jClient(
    uri="bolt://localhost:7687",
    username="neo4j",
    password="password",
)

# 2. 创建约束
client.create_constraints()

# 3. 构建图谱
builder = GraphBuilder(client)

stats = builder.build_from_metadata(
    metadata_path=Path("rag/index/metadata.json"),
)

print(f"✓ 创建了 {stats['documents']} 个文献")
print(f"✓ 创建了 {stats['volumes']} 个卷次")
print(f"✓ 创建了 {stats['pages']} 个页面")

# 4. 构建相似关系
relation_count = builder.build_similarity_relations(
    embeddings_path=Path("rag/index/embeddings.npy"),
    ids_path=Path("rag/index/ids.json"),
)

print(f"✓ 创建了 {relation_count} 个相似关系")

# 5. 查看统计
stats = client.get_statistics()
print(f"\n图谱统计:")
for key, value in stats.items():
    print(f"  {key}: {value}")
```

### 示例 2: 版本推断

```python
from graph import GraphQueryInterface

query = GraphQueryInterface(client)

# 推断未知页面的版本
page_id = "page_unknown_001"
inference = query.infer_edition_by_similarity(page_id, min_similarity=0.85)

if inference['inferred_edition']:
    print(f"推断结果: {inference['inferred_edition']}")
    print(f"置信度: {inference['confidence']:.2%}")
    print(f"\n{inference['summary']}")

    print(f"\n证据链:")
    for chain in inference['evidence_chains'][:3]:
        print(f"  - {chain['explanation']}")
else:
    print("无法推断版本")
```

### 示例 3: 实体关系探索

```python
# 查询提及"司馬遷"的页面
pages = query.get_pages_mentioning_entity("司馬遷", entity_type="PERSON")
print(f"找到 {len(pages)} 个页面提及司馬遷")

# 查询与"司馬遷"共现的人物
co_entities = query.get_entity_co_occurrence("司馬遷", entity_type="PERSON", limit=10)
print(f"\n与司馬遷共现的人物:")
for entity in co_entities:
    print(f"  - {entity['e2.entity_text']}: {entity['co_occurrence_count']} 次")

# 查询"司馬遷"与"孔安國"的关系路径
path = query.find_entity_relation_path("司馬遷", "孔安國", max_depth=3)
if path['relation_found']:
    print(f"\n关系路径:")
    print(path['explanation'])
```

### 示例 4: 页面推荐

```python
# 获取相关页面推荐
page_id = "page_shiji_001_001"
recommendations = query.recommend_related_pages(page_id, limit=10)

print(f"为 {page_id} 推荐的相关页面:")
for rec in recommendations:
    print(f"  {rec['page_id']}")
    print(f"    评分: {rec['confidence']:.2f}")
    print(f"    原因: {rec['explanation']}")
```

---

## 性能优化

### 1. 使用索引

确保创建了所有必要的索引：

```python
client.create_constraints()
```

### 2. 批量操作

使用 UNWIND 进行批量插入：

```cypher
UNWIND $batch AS item
CREATE (p:Page {
    page_id: item.page_id,
    page_number: item.page_number,
    image_path: item.image_path
})
```

### 3. 限制结果集

始终使用 LIMIT 限制返回数量：

```python
results = query.get_similar_pages("page_001", limit=10)
```

### 4. 分析查询性能

使用 PROFILE 分析慢查询：

```cypher
PROFILE
MATCH (d:Document)-[:HAS_VOLUME]->(v:Volume)
RETURN d.title, count(v)
```

---

## 故障排除

### 连接失败

```python
# 检查 Neo4j 是否运行
docker ps | grep neo4j

# 验证连接
if not client.verify_connectivity():
    print("连接失败，请检查:")
    print("  1. Neo4j 是否启动")
    print("  2. URI 是否正确")
    print("  3. 用户名密码是否正确")
```

### 内存不足

```python
# 分批处理大数据集
batch_size = 100
for i in range(0, len(data), batch_size):
    batch = data[i:i+batch_size]
    # 处理批次
```

### 查询超时

```python
# 增加超时时间
client = Neo4jClient(
    uri="bolt://localhost:7687",
    username="neo4j",
    password="password",
)
# 在查询中添加 LIMIT
```

---

## 文档

- [SCHEMA.md](SCHEMA.md) - 完整的图谱 Schema 定义
- [QUERIES.md](QUERIES.md) - 50+ 个查询用例
- [examples/](examples/) - 更多使用示例

---

## 依赖

- Python 3.10+
- neo4j >= 5.0
- numpy >= 1.20

---

## 许可证

MIT License

---

**版本**: v1.0.0 (2026-03-04)
