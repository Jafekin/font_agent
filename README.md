<div align="center">

# 古文字识别分析智能体

### Agentic GraphRAG for Ancient Chinese Script Analysis

*把历史文献里的细小纹理交给机器看见，把识别到的故事交还给人*

[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-4.2+-092E20?style=for-the-badge&logo=django&logoColor=white)](https://www.djangoproject.com/)
[![Neo4j](https://img.shields.io/badge/Neo4j-5.0+-008CC1?style=for-the-badge&logo=neo4j&logoColor=white)](https://neo4j.com/)

**基于 Agentic GraphRAG 的古文字研究工具链**，融合 Chinese-CLIP 嵌入、知识图谱推理与大模型分析，将甲骨文、敦煌文书、金石拓片转化为结构化的学术报告。

</div>

---

## 当前里程碑

| 状态 | 里程碑 |
| --- | --- |
| ✅ | Naive RAG baseline（嵌入检索 → Prompt → LLM） |
| ✅ | 数据索引系统（Chinese-CLIP 向量索引） |
| ✅ | OCR 版式识别（看典古籍 API） |
| ✅ | GraphRAG（Neo4j 知识图谱构建与检索） |
| ⏳ | Agentic 推理架构（多步工具规划） |

---

## 系统架构

<div align="center">
  <img src="doc/系统架构.jpg" alt="系统架构" width="85%">
</div>

### 核心模块

| 模块 | 功能 |
| --- | --- |
| `app/views.py` | HTTP 入口、文件解析、结果持久化 |
| `rag/naive/embeddings.py` | Chinese-CLIP 惰性加载，输出 512 维向量 |
| `rag/naive/retriever.py` | NumPy 索引余弦相似度 Top-K 检索 |
| `rag/naive/prompt.py` | 根据检索上下文构造结构化 Prompt |
| `rag/naive/pipeline.py` | 检索 → Prompt → LLM 推理流水线 |
| `rag/graph/` | GraphRAG 知识图谱构建与查询 |
| `ocr/` | 看典古籍 OCR API 客户端 |

---

## 快速上手

> **环境要求**: Python 3.10+，推荐使用 [uv](https://github.com/astral-sh/uv)

```bash
# 克隆并安装
git clone --recursive https://github.com/Jafekin/font.git && cd font
uv sync

# 初始化数据库
uv run manage.py migrate

# 启动开发服务器
uv run manage.py runserver 0.0.0.0:8000
```

访问：[前台界面](http://localhost:8000) · [管理后台](http://localhost:8000/admin)

---

## 环境变量

将 `.env.example` 复制为 `.env` 并配置：

| 变量名 | 说明 |
| --- | --- |
| `SECRET_KEY` | Django 密钥（生产环境请生成随机字符串） |
| `DEBUG` | 开发 `True`，生产 `False` |
| `OPENAI_API_KEY` | 大模型 API Key |
| `OPENAI_BASE_URL` | 默认 `https://aistudio.baidu.com/llm/lmapi/v3` |
| `ALLOWED_HOSTS` | 允许访问的域名（逗号分隔） |
| `KANDIANGUJI_TOKEN` | 看典古籍 OCR API 令牌（可选） |
| `KANDIANGUJI_EMAIL` | 看典古籍 OCR API 邮箱（可选） |
| `RAG_FAKE_EMBEDDINGS=1` | 跳过模型加载，返回假结果（测试用） |

---

## 运行与调试

### 测试

```bash
python -m pytest tests/
```

### 构建 NaiveRAG 索引

```bash
python rag/naive/scripts/build_index.py \
  --data-dir rag/data \
  --index-path rag/naive/index \
  --image-weight 0.65
```

### 构建 GraphRAG 知识图谱

```bash
# 启动 Neo4j
docker run -d --name neo4j -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/password neo4j:latest

# 构建图谱
python -m rag.graph.scripts.build_graph \
  --data-dir rag/data \
  --entities \
  --embeddings rag/naive/index/embeddings.npy \
  --ids rag/naive/index/ids.json
```

### OCR 识别

```bash
python -m ocr.cli recognize data/example.jpg --save-all --output-dir rag/data
python -m ocr.cli batch images/*.jpg --output-dir rag/data
python -m ocr.cli status
```

---

## API

| Endpoint | 方法 | 说明 |
| --- | --- | --- |
| `/` | GET | 首页上传界面 |
| `/api/analyze` | POST | 上传图片，返回 Markdown 报告 |
| `/api/analyze-base64` | POST | Base64 图片分析 |
| `/api/history` | GET | 最近 20 条分析记录 |

```python
import requests

with open("tests/image/22.jpg", "rb") as f:
    r = requests.post(
        "http://localhost:8000/api/analyze",
        files={"image": f},
        data={"script_type": "汉文古籍", "hint": "宋刻本"},
    )
print(r.json())
```

---

## RAG 工作流

```
图片输入 → Chinese-CLIP 编码 → NumPy 余弦检索
       → Prompt 拼装 → LLM 生成 → 结构化报告
```

```python
from rag.naive.pipeline import RAGPipeline

pipeline = RAGPipeline(index_path="rag/naive/index")
result = pipeline.run(
    image_path="media/uploads/example.png",
    script_type="汉文古籍",
    hint="宋刻本",
    k=3,
)
print(result["analysis"])           # 生成报告
print(result["retrieved_references"])  # 引用页面 ID
```

---

## 项目结构

```
font/
├── app/              # Django 应用（Models、Views、API）
├── config/           # Django 设置与路由
├── ocr/              # 看典古籍 OCR 客户端
├── rag/
│   ├── naive/        # NaiveRAG（嵌入检索）
│   │   └── scripts/  # build_index.py
│   ├── graph/        # GraphRAG（Neo4j 知识图谱）
│   │   └── scripts/  # build_graph.py
│   └── scripts/      # 数据处理与分析工具
├── doc/              # 架构图与文档
├── media/            # 用户上传影像
├── tests/            # 测试用例
├── CLAUDE.md         # 开发指南
└── pyproject.toml    # 依赖与配置
```

---

## 常见问题

**`OpenAI library is not installed`**：运行 `uv sync` 并确认在激活的虚拟环境中。

**上传报 500**：检查 `.env` 中 `OPENAI_API_KEY` 与 `OPENAI_BASE_URL` 是否正确。

**检索结果为空**：确认 `rag/naive/index/` 中存在 `embeddings.npy`，必要时重建索引。

---

<div align="center">

版权所有 © Jafekin, 大连理工大学 · [提交 Issue](https://github.com/Jafekin/font/issues) · [查看开发指南](./CLAUDE.md)

</div>
