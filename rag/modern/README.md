# Modern RAG for Ancient Chinese Manuscripts

全新的古籍双模态RAG处理方案，基于2025年最佳实践。

## 核心设计理念

### 1. 多阶段推理（Multi-Stage Reasoning）
不再是简单的"检索→生成"，而是：
- **Stage 1**: 视觉理解（版式、字体、印章识别）
- **Stage 2**: 文本理解（OCR文本语义分析）
- **Stage 3**: 知识检索（多模态混合检索）
- **Stage 4**: 推理融合（版本溯源、时代推断）
- **Stage 5**: 结构化输出（编目报告生成）

### 2. 知识融合（Knowledge Fusion）
- 图像特征 + 文本语义 + 图谱关系 → 统一表示空间
- 使用Attention机制动态加权不同来源的证据

### 3. 可解释性优先
- 每个结论都有证据链
- 置信度评分
- 可视化推理过程

## 技术栈

- **视觉编码**: Qwen2-VL (7B) - 开源最强视觉语言模型
- **文本编码**: SikuBERT - 古汉语专用BERT
- **检索**: Milvus (向量) + Elasticsearch (文本) + Neo4j (图谱)
- **推理**: LangGraph - 多阶段推理编排
- **生成**: Qwen2.5-72B-Instruct - 开源最强指令模型

## 架构图

```
┌─────────────────────────────────────────────────────────┐
│                    输入处理层                            │
├─────────────────────────────────────────────────────────┤
│  图像 ──→ Qwen2-VL ──→ 视觉特征 (4096-dim)              │
│  OCR  ──→ SikuBERT ──→ 文本特征 (768-dim)               │
│  元数据 ──→ Embedding ──→ 属性特征 (256-dim)            │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│                  多路检索层（并行）                       │
├─────────────────────────────────────────────────────────┤
│  路径1: Milvus 向量检索 (视觉相似度)                     │
│  路径2: Elasticsearch BM25 (文本关键词)                  │
│  路径3: Neo4j 图谱查询 (版本关系链)                      │
│  路径4: 属性过滤 (时代/类型/馆藏)                        │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│                  知识融合层                              │
├─────────────────────────────────────────────────────────┤
│  Cross-Attention: 查询 × 检索结果 → 加权融合             │
│  图谱推理: 版本溯源、时代推断、缺失补全                   │
│  证据排序: 相关性 × 可信度 × 多样性                      │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│                  多阶段推理层                            │
├─────────────────────────────────────────────────────────┤
│  Agent 1: 版本判定（刻本/写本/活字本）                   │
│  Agent 2: 时代推断（基于字体、刻工、牌记）                │
│  Agent 3: 版式分析（行款、边栏、鱼尾）                   │
│  Agent 4: 内容分析（释文、翻译、关键词）                 │
│  Agent 5: 综合编目（整合所有信息）                       │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│                  输出验证层                              │
├─────────────────────────────────────────────────────────┤
│  格式校验: JSON Schema                                   │
│  事实核查: 与图谱交叉验证                                │
│  置信度评估: 每个字段的可信度分数                        │
│  引用溯源: 标注证据来源                                  │
└─────────────────────────────────────────────────────────┘
```

## 与旧方案的对比

| 维度 | 旧方案 (Naive RAG) | 新方案 (Modern RAG) |
|------|-------------------|-------------------|
| 检索策略 | 单路向量检索 | 多路混合检索 + 重排序 |
| 推理方式 | 一次性生成 | 多阶段推理 + Agent协作 |
| 知识利用 | 简单拼接 | 知识融合 + 图谱推理 |
| 可解释性 | 无 | 证据链 + 置信度评分 |
| 准确率 | ~65% | ~85% (预期) |
| 幻觉率 | ~35% | ~10% (预期) |

## 快速开始

```bash
# 安装依赖
pip install -r requirements-modern.txt

# 构建索引
python -m rag.modern.indexer --data-dir outputs/

# 运行推理
python -m rag.modern.pipeline --image test.jpg --output result.json
```

## GraphRAG 已接入

当前 [rag/modern/retrievers/hybrid_retriever.py](rag/modern/retrievers/hybrid_retriever.py) 已接入轻量 GraphRAG：
- 从 [rag/modern/indexes/metadata.json](rag/modern/indexes/metadata.json) 自动建图
- 节点是文献页，边基于 `edition_type`/`dynasty`/`institution`/`volume_number`
- 查询时先做元数据种子匹配，再进行最多 2-hop 图扩散
- 返回结果包含 `graph_reason` 与 `graph_hop`，便于解释证据来源

可选地在调用流程时传入元数据以触发图检索增强：

```python
from rag.modern.pipeline import ModernRAGPipeline

pipeline = ModernRAGPipeline()
result = pipeline.run(
    image_path="ocr/tests/test.jpg",
    metadata={"edition_type": "刻本", "dynasty": "明", "institution": "北京大学图书馆"},
)
```

命令行也可直接传入元数据：

```bash
python -m rag.modern.pipeline \
    --image ocr/tests/test.jpg \
    --edition-type 刻本 \
    --dynasty 明 \
    --institution 北京大学图书馆 \
    --output result.json
```

## 目录结构

```
rag/modern/
├── README.md                 # 本文件
├── config.py                 # 配置管理
├── encoders/                 # 编码器模块
│   ├── vision_encoder.py     # Qwen2-VL视觉编码
│   ├── text_encoder.py       # SikuBERT文本编码
│   └── metadata_encoder.py   # 元数据编码
├── retrievers/               # 检索器模块
│   ├── vector_retriever.py   # Milvus向量检索
│   ├── text_retriever.py     # Elasticsearch文本检索
│   ├── graph_retriever.py    # Neo4j图谱检索
│   └── hybrid_retriever.py   # 混合检索 + 重排序
├── fusion/                   # 知识融合模块
│   ├── attention_fusion.py   # Cross-Attention融合
│   └── graph_reasoning.py    # 图谱推理
├── agents/                   # 多阶段推理Agent
│   ├── version_agent.py      # 版本判定Agent
│   ├── dating_agent.py       # 时代推断Agent
│   ├── layout_agent.py       # 版式分析Agent
│   ├── content_agent.py      # 内容分析Agent
│   └── catalog_agent.py      # 综合编目Agent
├── pipeline.py               # 主流程编排
├── indexer.py                # 索引构建
└── validator.py              # 输出验证
```
