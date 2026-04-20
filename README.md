<div align="center">

# 古文字识别分析智能体

### Agentic GraphRAG for Ancient Chinese Script Analysis

*把历史文献里的细小纹理交给机器看见，把识别到的故事交还给人*

[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-4.2+-092E20?style=for-the-badge&logo=django&logoColor=white)](https://www.djangoproject.com/)
[![Neo4j](https://img.shields.io/badge/Neo4j-5.0+-008CC1?style=for-the-badge&logo=neo4j&logoColor=white)](https://neo4j.com/)

</div>

**基于 Agentic GraphRAG 的古文字研究工具链**，一个围绕古籍影像分析搭建的 Django 项目，集成了 OCR、Naive RAG、GraphRAG、Agent 路由和评测工具链，目标是把古籍页面从“图片”变成可检索、可推理、可追溯的结构化研究对象。

项目当前包含两类能力：

- 在线分析：上传图片后，服务会走 `AgenticRAGPipeline`，自动决定调用 NaiveRAG、GraphRAG 或两者，并产出结构化中文分析结果。
- 离线构建：支持批量 OCR、向量索引构建、Neo4j 图谱构建、图谱检索、混合检索评测和结果导出。



## 核心能力

- Django Web 服务，提供上传分析、Base64 分析、历史记录接口。
- 看典古籍 OCR 客户端与 CLI，支持单图和批量识别。
- NaiveRAG：基于 Chinese-CLIP 的图片+文本融合向量检索。
- GraphRAG：基于 Neo4j 的文献、版本、馆藏、版式、实体知识图谱。
- Agentic 路由：通过 LangChain Agent 在 NaiveRAG 和 GraphRAG 间做工具选择。
- 评测框架：支持 Naive / Graph / Agent 三路检索与生成指标评估。

## 项目结构

```text
font/
├── app/                 # Django 应用：页面、API、数据模型
├── config/              # Django 配置
├── ocr/                 # 看典古籍 OCR 客户端、输出管理与 CLI
├── rag/
│   ├── agent/           # AgenticRAGPipeline 与工具封装
│   ├── naive/           # NaiveRAG：数据加载、嵌入、检索、提示词
│   ├── graph/           # GraphRAG：Neo4j 图谱构建、检索、识别
│   ├── eval/            # 评测器、指标与 CLI
│   └── scripts/         # 数据处理、导出、分析脚本
├── doc/                 # 架构图与补充文档
├── thirdparty/Chinese-CLIP/
├── manage.py
└── pyproject.toml
```

## 运行环境

- Python `3.12.8`
- 推荐使用 `uv`
- SQLite 作为默认 Web 侧数据库
- Neo4j 用于 GraphRAG
- OpenAI 兼容接口用于多模态分析与部分元数据/实体提取
- 看典古籍 OCR API 用于 OCR 能力

安装依赖：

```bash
uv sync
```

## 环境变量

项目会从 `.env` 读取配置，可按需创建：

```bash
SECRET_KEY=replace-me
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

OPENAI_API_KEY=your-api-key
OPENAI_BASE_URL=https://aistudio.baidu.com/llm/lmapi/v3

RAG_INDEX_PATH=rag/naive/index

NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password
NEO4J_DATABASE=neo4j

KANDIANGUJI_TOKEN=your-token
KANDIANGUJI_EMAIL=your-email

APP_LOG_LEVEL=INFO
DJANGO_LOG_LEVEL=WARNING
```

补充说明：

- `OPENAI_API_KEY` 是在线分析、批量元数据提取、图谱实体提取的关键依赖。
- `KANDIANGUJI_TOKEN` / `KANDIANGUJI_EMAIL` 主要用于 OCR 模块和部分 GraphRAG 图片识别链路。
- `RAG_INDEX_PATH` 未配置时，默认回退到 `rag/naive/index`。

## 快速启动 Web 服务

初始化数据库并启动 Django：

```bash
uv run manage.py migrate
uv run manage.py runserver 0.0.0.0:8000
```

默认入口：

- 首页：`http://127.0.0.1:8000/`
- 管理后台：`http://127.0.0.1:8000/admin/`

当前 API：

- `POST /api/analyze`
- `POST /api/analyze-base64`
- `GET /api/history`

### `POST /api/analyze`

表单字段：

- `image`: 上传图片
- `script_type`: 文字类型，默认 `甲骨文`
- `hint`: 辅助提示，可选

示例：

```python
import requests

with open("ocr/tests/test.jpg", "rb") as f:
    resp = requests.post(
        "http://127.0.0.1:8000/api/analyze",
        files={"image": f},
        data={"script_type": "汉文", "hint": "史记刻本页面"},
    )

print(resp.json())
```

返回结果中会包含：

- `result`: 分析文本
- `analysis_id`: 持久化记录 ID
- `rag`: 检索引用、分数、路由方式、是否 fallback 等信息

## 在线分析链路

Web 入口最终会调用 `app/views.py` 中的 `AgenticRAGPipeline`：

```text
图片上传
  -> 压缩到安全大小
  -> Agent 决定调用 NaiveRAG / GraphRAG / 两者
  -> 拼接最终 Prompt
  -> 多模态 LLM 输出分析结果
  -> 保存 ScriptAnalysis 历史记录
```

如果 RAG 链路失败，系统会退化为直接调用 LLM 做图片分析。

## OCR 工作流

`ocr/` 模块封装了看典古籍 OCR API，既可独立使用，也可作为 GraphRAG 的输入来源。

单图识别：

```bash
uv run python -m ocr.cli recognize ocr/tests/test.jpg --save-all --output-dir ocr/outputs
```

批量识别：

```bash
uv run python -m ocr.cli batch ocr/tests/test.jpg ocr/tests/test2.jpg --output-dir ocr/outputs
```

查看 token 状态：

```bash
uv run python -m ocr.cli status
```

典型输出目录：

```text
ocr/outputs/{image_name}/
├── {image_name}.json
├── metadata.json
├── raw/{image_name}_raw.json
├── text/{image_name}.txt
└── overlay/{image_name}_overlay.jpg
```

## NaiveRAG

NaiveRAG 依赖 `rag/data/` 中每页一个目录的数据组织形式，结合图片向量和文本向量构建索引。

### 1. 准备 `rag/data/`

项目中已有用于批量处理史记数据集的脚本：

```bash
uv run python rag/scripts/process_shiji_dataset.py \
  --data "data/名录 史记2025-11-6" \
  --output rag/data
```

按版本处理：

```bash
uv run python rag/scripts/process_shiji_dataset.py \
  --data "data/名录 史记2025-11-6" \
  --output rag/data \
  --version A
```

脚本会为每页生成 OCR 结果和 `extended_metadata.json`，供后续 RAG / GraphRAG 共用。

### 2. 构建向量索引

```bash
uv run python rag/naive/scripts/build_index.py \
  --data-dir rag/data \
  --index-path rag/naive/index \
  --image-weight 0.65
```

默认优先使用 overlay 图片进行向量化；如需关闭：

```bash
uv run python rag/naive/scripts/build_index.py \
  --data-dir rag/data \
  --index-path rag/naive/index \
  --no-overlay
```

索引产物：

```text
rag/naive/index/
├── embeddings.npy
├── ids.json
├── metadata.json
└── config.json
```

### 3. 检索或调用管道

```python
from rag.naive.pipeline import RAGPipeline

pipeline = RAGPipeline(index_path="rag/naive/index")
result = pipeline.run(
    image_path="ocr/tests/test.jpg",
    script_type="汉文",
    hint="史记页面",
    k=3,
)

print(result["analysis"])
print(result["retrieved_references"])
print(result["retrieval_scores"])
```

CLI 查询：

```bash
uv run python -m rag.naive.scripts.query text "五帝本紀" --limit 5
uv run python -m rag.naive.scripts.query image ocr/tests/test.jpg --limit 3
```

## GraphRAG

GraphRAG 使用 Neo4j 存储图结构，核心节点包括：

- `Document`
- `Edition`
- `Collection`
- `Page`
- `Layout`
- `Entity`

核心关系包括：

- `HAS_EDITION`
- `HAS_PAGE`
- `STORED_IN`
- `HAS_LAYOUT`
- `MENTIONS`
- `SAME_EDITION`
- `SIMILAR_TO`

### 1. 启动 Neo4j

```bash
docker run -d --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/password \
  neo4j:latest
```

### 2. 构建知识图谱

仅按结构化元数据和 OCR 文本构建：

```bash
uv run python -m rag.graph.scripts.build_graph --data-dir rag/data
```

如果希望同时写入 `SIMILAR_TO` 相似页关系，需传入 NaiveRAG 索引：

```bash
uv run python -m rag.graph.scripts.build_graph \
  --data-dir rag/data \
  --embeddings rag/naive/index/embeddings.npy \
  --ids rag/naive/index/ids.json \
  --sim-threshold 0.88
```

注意：脚本默认会要求确认清空数据库。

查看图谱统计：

```bash
uv run python -m rag.graph.scripts.build_graph --stats-only
```

### 3. GraphRAG 图片识别

```bash
uv run python -m rag.graph.scripts.recognize ocr/tests/test.jpg --top-k 3
```

JSON 输出：

```bash
uv run python -m rag.graph.scripts.recognize ocr/tests/test.jpg --json
```

携带 OCR 凭据和自定义权重：

```bash
uv run python -m rag.graph.scripts.recognize ocr/tests/test.jpg \
  --ocr-token YOUR_TOKEN \
  --ocr-email YOUR_EMAIL \
  --weight-naive 0.4 \
  --weight-hybrid 0.4 \
  --weight-text 0.2
```

### 4. Graph 查询 CLI

```bash
uv run python -m rag.graph.scripts.query text "五帝本紀" --limit 5
uv run python -m rag.graph.scripts.query similar page_001 --min-score 0.88
uv run python -m rag.graph.scripts.query entity "司马迁"
uv run python -m rag.graph.scripts.query edition edition_shiji_A
uv run python -m rag.graph.scripts.query page page_001 --json
uv run python -m rag.graph.scripts.query infer page_unknown_001 --json
uv run python -m rag.graph.scripts.query hybrid page_001:0.92 page_007:0.85 --depth 2
uv run python -m rag.graph.scripts.query stats
```

## AgenticRAG

`rag/agent/` 将 NaiveRAG 和 GraphRAG 封装成两个 LangChain tool：

- `naive_rag_skill`
- `graph_rag_skill`

路由策略大致是：

- 只需相似页和文本上下文时，偏向 NaiveRAG。
- 涉及版本、作者、馆藏、实体关系、同版本扩展时，偏向 GraphRAG。
- 复杂任务会组合两者，再统一喂给最终多模态 LLM 生成分析。

## 评测

评测入口在 `rag/eval/`，支持检索指标和生成指标。

默认示例集：

- `rag/eval/data/sample_gt.json`

评估 NaiveRAG：

```bash
uv run python -m rag.eval.scripts.run_eval naive \
  --gt rag/eval/data/sample_gt.json \
  --index rag/naive/index \
  --k 5
```

评估 GraphRAG：

```bash
uv run python -m rag.eval.scripts.run_eval graph \
  --gt rag/eval/data/sample_gt.json \
  --k 5
```

评估 Hybrid：

```bash
uv run python -m rag.eval.scripts.run_eval hybrid \
  --gt rag/eval/data/sample_gt.json \
  --index rag/naive/index \
  --k 5 \
  --bfs-depth 1
```

一次对比三路并输出结果：

```bash
uv run python -m rag.eval.scripts.run_eval all \
  --gt rag/eval/data/sample_gt.json \
  --index rag/naive/index \
  --k 5 \
  --output rag/eval/results.json
```

当前评测指标包括：

- 检索：`Precision@K`、`Recall@K`、`F1@K`、`MRR`、`NDCG@K`、`Hit Rate@K`
- 生成：`BLEU`、`ROUGE`、`Exact Match`、`Character F1`、`Answer Relevance`、`Faithfulness`

## 推荐使用顺序

如果你要从原始图片一路跑到网页分析，推荐顺序如下：

1. 配置 `.env` 中的 LLM、OCR、Neo4j 参数。
2. 用 `rag/scripts/process_shiji_dataset.py` 或 `ocr.cli` 生成 `rag/data/`。
3. 构建 `rag/naive/index`。
4. 启动 Neo4j 并构建 GraphRAG 图谱。
5. 启动 Django 服务，走 `/api/analyze` 或网页上传。
6. 如需对比效果，再运行 `rag/eval/scripts/run_eval.py`。

## 已知依赖与注意事项

- `rag/model/clip_cn_vit-b-16.pt` 和 `thirdparty/Chinese-CLIP/` 体积较大，向量构建依赖本地模型环境。
- GraphRAG 强依赖 Neo4j 正常可连通。
- 很多离线脚本依赖 `OPENAI_API_KEY`，不只是在线分析接口。
- `rag.graph.scripts.build_graph` 默认会清空数据库，执行前请确认目标环境。
- Web 服务默认使用 SQLite，适合本地开发，不适合直接作为生产部署方案。

## 参考文档

- [OCR 模块说明](ocr/README.md)
- [NaiveRAG 模块说明](rag/naive/README.md)
- [GraphRAG 模块说明](rag/graph/README.md)
- [数据处理脚本说明](rag/scripts/README.md)
- [系统流程文档](doc/architecture_flows.md)
