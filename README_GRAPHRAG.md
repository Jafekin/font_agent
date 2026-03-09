# GraphRAG 模块使用快速指南

## 快速开始

### 1. 查看数据集统计

```bash
python scripts/build_graph_from_outputs.py --outputs-dir outputs --stats-only
```

### 2. 启动 Neo4j

```bash
docker run -d \
  --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/password \
  neo4j:latest
```

### 3. 构建知识图谱

```bash
# 基础图谱（不提取实体）
python scripts/build_graph_from_outputs.py --outputs-dir outputs

# 完整图谱（包含实体提取）
python scripts/build_graph_from_outputs.py --outputs-dir outputs --extract-entities

# 添加相似关系
python scripts/build_graph_from_outputs.py \
  --outputs-dir outputs \
  --extract-entities \
  --build-similarity \
  --embeddings-path rag/index/embeddings.npy \
  --ids-path rag/index/ids.json
```

## 测试模块

```bash
python scripts/test_graph_module.py
```

## 详细文档

- **使用指南**: `rag/graph/USAGE.md`
- **Schema 定义**: `rag/graph/SCHEMA.md`
- **查询示例**: `rag/graph/QUERIES.md`
- **优化总结**: `rag/graph/OPTIMIZATION_SUMMARY.md`
- **完成报告**: `rag/graph/COMPLETION_REPORT.md`

## 核心组件

- **OutputsDataLoader**: 从 outputs/ 目录加载 OCR 数据
- **EnhancedGraphBuilder**: 构建 Neo4j 知识图谱
- **GraphQueryInterface**: 图谱查询接口
- **EvidenceExplainer**: 证据路径解释器

## 图谱结构

- **8 种节点**: Document, Volume, Page, Edition, Collection, Layout, Entity, Seal
- **10 种关系**: HAS_VOLUME, HAS_PAGE, SIMILAR_TO, BELONGS_TO_EDITION, 等

## Python API

```python
from pathlib import Path
from rag.graph import Neo4jClient, EnhancedGraphBuilder, OutputsDataLoader

# 加载数据
loader = OutputsDataLoader(Path("outputs"))
stats = loader.get_statistics()
print(f"总页面数: {stats['total_pages']}")

# 构建图谱
client = Neo4jClient(uri="bolt://localhost:7687", username="neo4j", password="password")
client.create_constraints()

builder = EnhancedGraphBuilder(client)
result = builder.build_from_outputs(outputs_dir=Path("outputs"), extract_entities=True)
print(f"创建了 {result['pages']} 个页面节点")
```

## 支持

如有问题，请查看 `rag/graph/USAGE.md` 中的故障排除部分。
