<div align="center">

# 📜 Agentic GraphRAG 古文字识别分析智能体

*“把历史文献里的细小纹理交给机器看见，把识别到的故事交还给人。”*

[![Python](https://img.shields.io/badge/Python-3.12.8-blue.svg?style=flat-square&logo=python)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-4.2.7-092E20.svg?style=flat-square&logo=django)](https://www.djangoproject.com/)
[![License](https://img.shields.io/badge/License-Proprietary-red.svg?style=flat-square)](#-许可证)

本项目是一套基于 **Agentic GraphRAG** 实现的古文字研究工具链智能体。当前版本已完成 **Naive RAG** 基线：利用 Chinese-CLIP 嵌入、轻量 NumPy 检索与结构化 Prompt，可将甲骨文、敦煌文书、金石拓片转化为带引用的 Markdown 或 JSON 报告。下一阶段将演进为 Agentic GraphRAG，让知识图谱与智能体协作支撑更可靠的比勘、判读与修复建议。

</div>

<br/>

<details>
<summary><b>📚 展开查看目录</b></summary>

- [✨ 功能亮点](#-功能亮点)
- [🎯 当前里程碑](#-当前里程碑)
- [🏗️ 系统架构](#️-系统架构)
- [📸 运行样例](#-运行样例)
- [🚀 快速上手](#-快速上手)
- [⚙️ 环境变量](#️-环境变量)
- [🛠️ 运行与调试](#️-运行与调试)
- [🔌 API 速览](#-api-速览)
- [🔍 OCR 与版式识别子模块](#-ocr-与版式识别子模块)
- [🌊 RAG 工作流](#-rag-工作流)
- [🗺️ Agentic GraphRAG 目标](#️-agentic-graphrag-目标)
- [⏳ 未完成事项 (TODO)](#-未完成事项-todo)
- [🗂️ 项目结构](#️-项目结构)
- [❓ 常见问题](#-常见问题)
- [📊 GraphRAG 评估](#-graphrag-评估)
- [📄 许可证](#-许可证)

</details>

---

## ✨ 功能亮点

| 功能特性 | 详情描述 |
| :--- | :--- |
| **🖼️ 多模态识别** | 上传 PNG/JPG 即刻触发大模型 (ERNIE-4.5-Turbo-VL 等)，返回结构化 Markdown/JSON 报告。 |
| **💡 提示增强** | 支持年代、出处等自定义提示词，指导模型聚焦正确语境。 |
| **⏳ 历史留痕** | 自动记录分析历史，方便专家复盘与比对。 |
| **📐 版式指纹** | PaddleOCR 驱动的布局实验室，输出列数、白口/黑口等版式指标，为版本比勘提供量化特征。 |
| **🔍 Naive RAG 管线** | Chinese-CLIP 向量、NumPy 检索与 Prompt 拼装组成的轻量 RAG，让大模型“带引用”地产出释读、版本判定和修复建议。 |

---

## 🎯 当前里程碑

- ✅ **完成 Naive RAG baseline**：`rag/pipeline.py` 串联嵌入、检索、Prompt 与 LLM，默认始终返回带引用的结构化报告。
- ✅ **数据 & 索引构建系统**：`scripts/build_index.py`、`scripts/bulk_ingest.py` 负责批量生成向量索引 `embeddings.npy` 和 `metadata.json`。
- ✅ **版式识别实验场**：`ocr/` 目录可独立调用，产出列数、白口/黑口等特征，供 RAG 上下文引用。
- ⏳ **Agentic GraphRAG（进行中）**：即将把版本、题名、馆藏等实体转成图谱节点，引入工具规划和回溯逻辑。

---

## 🏗️ 系统架构

<div align="center">
  <img src="doc/系统架构.jpg" alt="系统架构" width="80%">
</div>

**核心模块：**
- 📂 **app/views.py**：HTTP 入口、文件解析、结果持久化，串起 Web 上传与 API。
- 🧠 **rag/embeddings.py**：惰性加载 Chinese-CLIP，输出 512 维向量，是所有 RAG 变体的统一编码层。
- 🔎 **rag/retriever.py**：直接读取 `embeddings.npy`、`ids.json` 等 NumPy 索引，实现当前的 naive cosine 检索。
- 📝 **rag/prompt.py**：根据检索上下文构造结构化 Prompt，约束输出字段、置信度与引用格式。
- ⚙️ **rag/pipeline.py**：单次调用内完成检索、Prompt 拼装、LLM 推理，后续将被 Agentic 架构替换的流水线主干。

---

## 📸 运行样例

<details open>
<summary><b>点击查看执行样例与解析报告</b></summary>

<div align="center">
  <img src="doc/PixPin_2025-11-24_15-43-22.png" alt="运行样例" width="80%">
</div>

> **输入概览**
> - **文献类型**：汉文
> - **用户提示 (Hint)**：未提供
> - **检索到的上下文**：标题匹配《史记一百三十卷》，关联作者（司马迁等），识别版本（宋建安黄善夫家塾）、现藏（国家图书馆）等核心元数据。
>
> **模型生成分析（摘要）**
> - **文献与本书信息**：判别为汉文古籍（置信度 0.95），《史记》（置信度 0.98）、司马迁（置信度 0.98）。
> - **本页释文与翻译**：提取古文如《三皇本纪》的开篇部分，并提供了准确的现代白话文翻译。
> - **版本与出版信息**：判断为南宋建安黄善夫家塾刻本（置信度 0.92），并提供版本判定的依据和相似版本。
> - **实体识别与传承**：抽取关键实体如人名（裴骃、司马贞）、地名（雷泽、成纪），考证现藏于国家图书馆。
> - **修复与活化建议**：根据图像页面破损程度给出保护修复建议，并提供展签文案和相应的展览活化方案。

</details>

---

## 🚀 快速上手

> 运行环境要求：`Python 3.10+`，推荐使用 [uv](https://github.com/astral-sh/uv) 或标准的 `venv` 环境。

### 方式一：使用 uv (推荐)

```bash
# 1. 克隆项目
git clone --recursive https://github.com/Jafekin/font.git && cd font

# 2. 创建环境并同步依赖
uv sync

# 3. 初始化数据库
uv run manage.py migrate

# 4.（可选）创建管理员帐户
uv run manage.py createsuperuser

# 5. 启动开发服务器
uv run manage.py runserver 0.0.0.0:8000
```

### 方式二：使用 venv

```bash
# 1. 克隆项目
git clone --recursive https://github.com/Jafekin/font.git && cd font

# 2. 创建并激活虚拟环境
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scriptsctivate

# 3. 安装依赖
pip install -e .

# 4. 数据库初始化及启动
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
```

> **系统访问入口**：
> - 🌐 **前台界面**: http://localhost:8000
> - 🛡️ **管理后台**: http://localhost:8000/admin

---

## ⚙️ 环境变量

将根目录下的 `.env.example` 复制为 `.env` 并填入以下字段：

| 环境变量 | 示例值 | 参数说明 |
| :--- | :--- | :--- |
| `DEBUG` | `True` | 开发环境使用 `True`，生产环境务必改为 `False` |
| `SECRET_KEY` | `change-me` | Django 密钥，生产环境中请生成随机复杂字符串 |
| `OPENAI_API_KEY` | `your-api-key` | 大模型 API Key (对接文心或类 OpenAI 接口) |
| `OPENAI_BASE_URL` | `https://aistudio.baidu.com/llm/lmapi/v3` | 兼容 OpenAI 格式的模型 API 网关 |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1` | 允许访问的域名，用逗号分隔 |
| `KANDIANGUJI_TOKEN` | `your-ocr-token` | 看典古籍 OCR API 令牌（可选） |
| `KANDIANGUJI_EMAIL` | `your-email` | 看典古籍 OCR API 邮箱（可选） |
| `RAG_FAKE_EMBEDDINGS` | `1` | 使用假检索结果进行测试（可选） |

---

## 🛠️ 运行与调试

```bash
# 🧪 运行单元测试
python -m pytest tests/

# 🗃️ 构建/重建 Chinese-CLIP 图文向量索引（已弃用，使用新的 GraphRAG 构建）
# python scripts/build_index.py --image-dir media/uploads --index-path rag/index --image-weight 0.65

# 🔗 从 outputs/ 目录构建知识图谱
python scripts/build_graph_from_outputs.py --outputs-dir outputs --extract-entities

# 📊 GraphRAG 评估
python eval/scripts/quick_evaluation_demo.py
python eval/scripts/evaluate_graphrag.py --test-data tests/graphrag_test_data.json --output-dir evaluation_results

# 📈 批量处理
python scripts/batch_process.py --mode batch --batch-size 50 --delay 5.0
```

**常用 Django 管理命令：**
- `python manage.py shell`：进入交互式终端测试模型或 ORM。
- `python manage.py collectstatic`：生产部署前收集静态文件。
- `python manage.py dumpdata app.ScriptAnalysis > backup.json`：导出/备份历史分析记录。

---

## 🔌 API 速览

| Endpoint | 方法 | 功能说明 |
| :--- | :--- | :--- |
| `/` | `GET` | 渲染首页文件上传及 UI 界面 |
| `/api/analyze` | `POST` | (Multipart) 上传图片并触发分析，返回 Markdown 报告 |
| `/api/analyze-base64` | `POST` | (JSON) 传入 Base64 编码的图片进行分析，适合前端直传 |
| `/api/history` | `GET` | 获取最近 20 条系统分析记录 |

**API 调用示例：**

```python
import requests

with open("tests/image/22.jpg", "rb") as f:
    response = requests.post(
        "http://localhost:8000/api/analyze",
        files={"image": f},
        data={"script_type": "甲骨文", "hint": "商晚期 卜辞"}
    )
print(response.json())
```

---

## 🔍 OCR 与版式识别子模块

独立于 RAG 的**版式/形态识别基建** (`ocr/` 目录)，基于第三方 OCR API (看典古籍)，支持自动提取古籍影像特征（列数、行数、版心结构等），为文字识别与 RAG 提供先验知识。

### 模块结构
- `ocr/client.py`：OCR API 客户端，调用看典古籍服务。
- `ocr/models.py`：OCR 结果数据模型定义。
- `ocr/output.py`：输出格式化（JSON、TXT、标注图像）。
- `ocr/cli.py`：命令行工具。
- `ocr/config.py`：配置管理（token、email、输出路径）。

### 命令行快速体验

```bash
# 识别单张图片（版式分析）
python ocr/cli.py recognize data/example.jpg

# 保存所有输出格式
python ocr/cli.py recognize data/example.jpg --save-all --output-dir ocr/outputs

# 批量识别
python ocr/cli.py batch images/*.jpg --output-dir outputs

# 检查 token 状态
python ocr/cli.py status
```

> **输出内容：**
> 生成结构化 JSON 结果，包含文本行、字符位置、置信度等信息，以及纯文本和标注图像输出。

---

## 🌊 RAG 工作流

本系统的 RAG 主要使命：将“孤立的文献片段”放回其宏观上下文之中。当前基于简化的 Naive Pipeline 实现：

1. **向量嵌入 (Embed)**：`scripts/build_index.py` 处理素材库，借助 Chinese-CLIP 将图文转换为 `.npy` 向量文件。
2. **高速检索 (Retrieve)**：`rag/retriever.py` 基于 NumPy 执行余弦相似度 Top-K 检索。
3. **提示拼装 (Prompt)**：`rag/prompt.py` 融合检索得到的历史信息（出处、版本等）构建高级 Prompt。
4. **生成验证 (Generate)**：大模型基于检索证据进行“带引用的推断”。

```python
from rag.pipeline import RAGPipeline

pipeline = RAGPipeline(index_path="rag/index")
result = pipeline.run(
    image_path="media/uploads/example.png",
    script_type="甲骨文",
    hint="王卜辞"
)

print(result["analysis"])  # 输出生成报告
```

---

## 📊 GraphRAG 评估

项目包含完整的 GraphRAG 性能评估系统，支持检索质量和推理能力的量化测试：

### 快速评估演示

```bash
# 无需测试数据的快速演示
python eval/scripts/quick_evaluation_demo.py
```

### 生成测试数据

```bash
# 从现有图谱生成测试数据
python eval/scripts/generate_graphrag_test_data.py \
  --output tests/graphrag_test_data.json \
  --num-retrieval 20 \
  --num-edition 10
```

### 完整评估流程

```bash
# 运行完整评估
python eval/scripts/evaluate_graphrag.py \
  --test-data tests/graphrag_test_data.json \
  --output-dir evaluation_results

# 可视化结果
python eval/scripts/visualize_evaluation_results.py \
  --metrics-file evaluation_results/evaluation_metrics_*.json \
  --output-dir evaluation_results/plots
```

### 评估指标

- **检索质量**: Precision@K, Recall@K, F1@K, MRR, NDCG@K, Hit Rate@K
- **GraphRAG 特定**: 版本推断准确率、实体关系准确率、多跳推理能力
- **综合性能**: 端到端任务完成质量评估

详细文档请参考 `eval/README.md`。

---

## 🗺️ Agentic GraphRAG 目标

系统将持续进化，最终目标是结合图谱的 **Agentic GraphRAG 智能体**：

1. **知识图谱构建**：将版本、馆藏、批注提取为知识图谱（Neo4j / DuckDB 构建）。
2. **混合检索 (Hybrid Retriever)**：向量检索 + 图路径遍历，支持“先图后文”组合拳。
3. **Agentic 推理循环 (Orchestration)**：通过 ReAct 架构，智能体可自主调用 OCR、图扫描和向量检索引擎，实现多步推演、自我纠错。
4. **强一致性校验**：基于属性核验机器生成的文献引用，消除幻觉。

---

## ⏳ 未完成事项 (TODO)

| 状态 | 开发任务 | 细节说明 |
| :---: | :--- | :--- |
| ⏳ | **图谱构建器** | 从元数据与版式特征中构建知识实体并生成图谱引擎存储（Neo4j 等）。 |
| ⏳ | **Hybrid 检索内核** | 结合现有的 NumPy 搜索与图扫描，实现多模态多粒度权重的动态检索引擎。 |
| ⏳ | **Agentic 调度中心** | 替代粗暴的一把梭，新增基于规划的自反思智能体循环。 |
| ⏳ | **JSON-LD 标注** | 按知识表达规范生成古籍数字档案的标准字段格式（LD 联动）。 |
| ⏳ | **索引增量更新** | 避免每次全量重建向量，提高处理效率。 |
| ⏳ | **可溯源缓存机制** | 支持引用的可视化审查追踪 (Citation Trace UI)。 |
| ⏳ | **Celery 异步队列** | 图片批量 OCR/索引建立转移至异步任务以增强稳定性。 |
| ⏳ | **全球化多语言** | 国际化前端以及对 API 翻译通道的支持。 |

*(🙌 欢迎通过 Issue 或 PR 认领任务，参与共建！)*

---

## 🗂️ 项目结构

```text
font/
├── app/                 # Django 应用核心（Models、Views、API及页面）
├── config/              # Django 设置及路由总闸 (WSGI/ASGI)
├── ocr/                 # 古籍图片OCR识别子库（基于看典古籍API）
├── rag/                 # RAG 处理流
│   ├── naive/           # Naive RAG 实现（Embeddings, Retriever, Prompts）
│   └── graph/           # GraphRAG 实现（知识图谱构建与查询）
├── eval/                # GraphRAG 评估系统
│   └── scripts/         # 评估脚本（测试数据生成、性能评估、可视化）
├── scripts/             # 数据处理与图谱构建脚本
├── outputs/             # OCR 输出结果目录
├── media/               # 用户上传及生成的影像中间产物
├── tests/               # 存放测试用例与开发样例
├── CLAUDE.md            # 项目开发指南
├── README.md            # 项目自述文档
└── pyproject.toml       # 项目依赖与配置
```

---

## ❓ 常见问题

<details>
<summary><b>1. 首次运行报错 <code>OpenAI library is not installed</code>？</b></summary>
<br>
答：请重新执行 <code>pip install -r requirements.txt</code> 或 <code>uv sync</code>，并确认您已在激活的虚拟环境中。
</details>

<details>
<summary><b>2. 影像上传直接报 500 且提示 <code>analysis failed</code>？</b></summary>
<br>
答：请检查 <code>.env</code> 文件内的 <code>OPENAI_API_KEY</code> 及 <code>OPENAI_BASE_URL</code> 是否正确，大模型余额是否充足。必要时在 <code>app/views.py</code> 开启并检查日志。
</details>

<details>
<summary><b>3. Faiss 索引文件过大或内存溢出？</b></summary>
<br>
答：目前使用的是轻量 NumPy 方案，若需要切换大规模检索，可微调整 <code>scripts/build_index.py</code> 或外接如 Milvus 的专有向量数据库。
</details>

---

## 📄 许可证

基于 **Proprietary License** 许可。版权所有 © Jafekin, 大连理工大学 (Dalian University of Technology)。

> *发现 Bug、需要新特性，或者想交流思路？欢迎随时提 Issue / PR！*
