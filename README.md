<div align="center">

# 📜 古文字识别分析智能体

### Agentic GraphRAG for Ancient Chinese Script Analysis

*把历史文献里的细小纹理交给机器看见，把识别到的故事交还给人*

<br>

[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-4.2+-092E20?style=for-the-badge&logo=django&logoColor=white)](https://www.djangoproject.com/)
[![Neo4j](https://img.shields.io/badge/Neo4j-5.0+-008CC1?style=for-the-badge&logo=neo4j&logoColor=white)](https://neo4j.com/)
[![License](https://img.shields.io/badge/License-Proprietary-red?style=for-the-badge)](#-许可证)

<br>

**基于 Agentic GraphRAG 的古文字研究工具链**，融合 Chinese-CLIP 嵌入、知识图谱推理与大模型分析，将甲骨文、敦煌文书、金石拓片转化为结构化的学术报告。

[快速开始](#-快速上手) · [功能特性](#-功能亮点) · [系统架构](#️-系统架构) · [API 文档](#-api-速览)

</div>

<br/>

## ✨ 功能亮点

<table>
<tr>
<td width="50%">

### 🖼️ 多模态识别
上传图片即刻触发大模型分析（ERNIE-4.5-Turbo-VL），返回结构化 Markdown/JSON 报告

### 💡 智能提示增强
支持年代、出处等自定义提示词，指导模型聚焦正确语境

### ⏳ 历史留痕
自动记录分析历史，方便专家复盘与比对

</td>
<td width="50%">

### 📐 版式指纹
PaddleOCR 驱动的布局分析，输出列数、白口/黑口等版式指标

### 🔍 GraphRAG 管线
Chinese-CLIP 向量 + 知识图谱推理，让大模型"带引用"地产出释读与版本判定

### 🧠 智能体推理
多步推演、自我纠错的 Agentic 架构（开发中）

</td>
</tr>
</table>

---

## 🎯 当前里程碑

```mermaid
graph LR
    A[✅ Naive RAG] --> B[✅ 索引构建]
    B --> C[✅ 版式识别]
    C --> D[⏳ GraphRAG]
    D --> E[⏳ Agentic 推理]

    style A fill:#90EE90
    style B fill:#90EE90
    style C fill:#90EE90
    style D fill:#FFD700
    style E fill:#FFD700
```

- ✅ **Naive RAG baseline**: `rag/pipeline.py` 串联嵌入、检索、Prompt 与 LLM
- ✅ **数据索引系统**: `scripts/build_index.py` 批量生成向量索引
- ✅ **版式识别实验场**: `ocr/` 目录独立调用，产出版式特征
- ⏳ **GraphRAG**: 版本、题名、馆藏等实体转成图谱节点（进行中）
- ⏳ **Agentic 架构**: 工具规划和回溯逻辑（规划中）

---

## 🏗️ 系统架构

<div align="center">
  <img src="doc/系统架构.jpg" alt="系统架构" width="85%">
</div>

<br>

<details>
<summary><b>核心模块说明</b></summary>

| 模块 | 功能 |
|------|------|
| 📂 `app/views.py` | HTTP 入口、文件解析、结果持久化 |
| 🧠 `rag/embeddings.py` | Chinese-CLIP 惰性加载，输出 512 维向量 |
| 🔎 `rag/retriever.py` | NumPy 索引的余弦相似度 Top-K 检索 |
| 📝 `rag/prompt.py` | 根据检索上下文构造结构化 Prompt |
| ⚙️ `rag/pipeline.py` | 检索 → Prompt → LLM 推理的流水线主干 |
| 🗺️ `rag/graph/` | GraphRAG 知识图谱构建与查询（开发中）|

</details>

---

## 📸 运行样例

<div align="center">
  <img src="doc/PixPin_2025-11-24_15-43-22.png" alt="运行样例" width="85%">
</div>

<details>
<summary><b>查看分析报告详情</b></summary>

<br>

**输入概览**
- 文献类型: 汉文古籍
- 用户提示: 未提供
- 检索上下文: 《史记一百三十卷》，宋建安黄善夫家塾刻本

**模型生成分析（摘要）**
- 文献信息: 汉文古籍（置信度 0.95），《史记》（置信度 0.98）
- 本页释文: 提取《三皇本纪》开篇部分，附现代白话文翻译
- 版本判定: 南宋建安黄善夫家塾刻本（置信度 0.92）
- 实体识别: 人名（裴骃、司马贞）、地名（雷泽、成纪）
- 馆藏信息: 国家图书馆
- 修复建议: 根据破损程度给出保护修复方案

</details>

---

## 🚀 快速上手

> **环境要求**: Python 3.10+，推荐使用 [uv](https://github.com/astral-sh/uv)

### 方式一：使用 uv（推荐）

```bash
# 克隆项目
git clone --recursive https://github.com/Jafekin/font.git && cd font
git submodule update --init
uv pip install -e . --no-build-isolation

# 创建环境并同步依赖
uv sync

# 初始化数据库
uv run manage.py migrate

# （可选）创建管理员账户
uv run manage.py createsuperuser

# 启动开发服务器
uv run manage.py runserver 0.0.0.0:8000
```

### 方式二：使用 venv

```bash
# 克隆项目
git clone --recursive https://github.com/Jafekin/font.git && cd font

# 创建并激活虚拟环境
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 安装依赖
pip install -e .

# 数据库初始化及启动
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
```

<div align="center">

**访问入口**

🌐 [前台界面](http://localhost:8000) · 🛡️ [管理后台](http://localhost:8000/admin)

</div>

---

## ⚙️ 环境变量

将 `.env.example` 复制为 `.env` 并配置以下字段：

<table>
<thead>
<tr>
<th width="25%">变量名</th>
<th width="35%">示例值</th>
<th width="40%">说明</th>
</tr>
</thead>
<tbody>
<tr>
<td><code>DEBUG</code></td>
<td><code>True</code></td>
<td>开发环境 <code>True</code>，生产环境 <code>False</code></td>
</tr>
<tr>
<td><code>SECRET_KEY</code></td>
<td><code>change-me</code></td>
<td>Django 密钥，生产环境请生成随机字符串</td>
</tr>
<tr>
<td><code>OPENAI_API_KEY</code></td>
<td><code>your-api-key</code></td>
<td>大模型 API Key（文心或类 OpenAI 接口）</td>
</tr>
<tr>
<td><code>OPENAI_BASE_URL</code></td>
<td><code>https://aistudio.baidu.com/llm/lmapi/v3</code></td>
<td>兼容 OpenAI 格式的模型 API 网关</td>
</tr>
<tr>
<td><code>ALLOWED_HOSTS</code></td>
<td><code>localhost,127.0.0.1</code></td>
<td>允许访问的域名，逗号分隔</td>
</tr>
<tr>
<td><code>KANDIANGUJI_TOKEN</code></td>
<td><code>your-ocr-token</code></td>
<td>看典古籍 OCR API 令牌（可选）</td>
</tr>
<tr>
<td><code>KANDIANGUJI_EMAIL</code></td>
<td><code>your-email</code></td>
<td>看典古籍 OCR API 邮箱（可选）</td>
</tr>
<tr>
<td><code>RAG_FAKE_EMBEDDINGS</code></td>
<td><code>1</code></td>
<td>使用假检索结果进行测试（可选）</td>
</tr>
</tbody>
</table>

---

## 🛠️ 运行与调试

### 测试与评估

```bash
# 运行单元测试
python -m pytest tests/

# GraphRAG 快速评估演示
python eval/scripts/quick_evaluation_demo.py

# 完整评估流程
python eval/scripts/evaluate_graphrag.py \
  --test-data tests/graphrag_test_data.json \
  --output-dir evaluation_results
```

### 知识图谱构建

```bash
# 从 outputs/ 目录构建知识图谱
python scripts/build_graph_from_outputs.py \
  --outputs-dir outputs \
  --extract-entities

# 添加相似度关系
python scripts/build_graph_from_outputs.py \
  --outputs-dir outputs \
  --extract-entities \
  --build-similarity \
  --embeddings-path rag/index/embeddings.npy \
  --similarity-threshold 0.85
```

### 批量处理

```bash
# 批量处理图片
python scripts/batch_process.py \
  --mode batch \
  --batch-size 50 \
  --delay 5.0

# 按版本类型处理
python scripts/batch_process.py --mode version --version A
```

<details>
<summary><b>常用 Django 管理命令</b></summary>

```bash
# 进入交互式终端
python manage.py shell

# 收集静态文件（生产部署）
python manage.py collectstatic

# 导出/备份分析记录
python manage.py dumpdata app.ScriptAnalysis > backup.json
```

</details>

---

## 🔌 API 速览

<table>
<thead>
<tr>
<th width="30%">Endpoint</th>
<th width="15%">方法</th>
<th width="55%">功能说明</th>
</tr>
</thead>
<tbody>
<tr>
<td><code>/</code></td>
<td><code>GET</code></td>
<td>渲染首页文件上传及 UI 界面</td>
</tr>
<tr>
<td><code>/api/analyze</code></td>
<td><code>POST</code></td>
<td>上传图片并触发分析，返回 Markdown 报告</td>
</tr>
<tr>
<td><code>/api/analyze-base64</code></td>
<td><code>POST</code></td>
<td>传入 Base64 编码的图片进行分析</td>
</tr>
<tr>
<td><code>/api/history</code></td>
<td><code>GET</code></td>
<td>获取最近 20 条系统分析记录</td>
</tr>
</tbody>
</table>

### API 调用示例

```python
import requests

with open("tests/image/22.jpg", "rb") as f:
    response = requests.post(
        "http://localhost:8000/api/analyze",
        files={"image": f},
        data={
            "script_type": "甲骨文",
            "hint": "商晚期 卜辞"
        }
    )
print(response.json())
```

---

## 🔍 OCR 与版式识别

独立的版式/形态识别模块（`ocr/` 目录），基于看典古籍 API，支持自动提取古籍影像特征。

### 命令行快速体验

```bash
# 识别单张图片
python ocr/cli.py recognize data/example.jpg

# 保存所有输出格式
python ocr/cli.py recognize data/example.jpg \
  --save-all \
  --output-dir ocr/outputs

# 批量识别
python ocr/cli.py batch images/*.jpg --output-dir outputs

# 检查 token 状态
python ocr/cli.py status
```

<details>
<summary><b>模块结构</b></summary>

| 文件 | 功能 |
|------|------|
| `ocr/client.py` | OCR API 客户端 |
| `ocr/models.py` | OCR 结果数据模型 |
| `ocr/output.py` | 输出格式化（JSON、TXT、标注图像）|
| `ocr/cli.py` | 命令行工具 |
| `ocr/config.py` | 配置管理 |

</details>

---

## 🌊 RAG 工作流

将"孤立的文献片段"放回其宏观上下文之中。

```mermaid
graph LR
    A[📷 图片输入] --> B[🧠 Chinese-CLIP<br/>向量嵌入]
    B --> C[🔎 NumPy<br/>余弦检索]
    C --> D[📝 Prompt<br/>拼装]
    D --> E[🤖 LLM<br/>生成]
    E --> F[📄 结构化报告]

    style A fill:#E3F2FD
    style B fill:#FFF9C4
    style C fill:#F3E5F5
    style D fill:#E8F5E9
    style E fill:#FFE0B2
    style F fill:#C8E6C9
```

### 使用示例

```python
from rag.pipeline import RAGPipeline

pipeline = RAGPipeline(index_path="rag/index")
result = pipeline.run(
    image_path="media/uploads/example.png",
    script_type="甲骨文",
    hint="王卜辞",
    k=3  # 检索 top-3 相似图片
)

print(result["analysis"])  # 生成报告
print(result["retrieved_references"])  # 引用文献
```

---

## 📊 GraphRAG 评估

完整的性能评估系统，支持检索质量和推理能力的量化测试。

### 快速开始

```bash
# 快速演示（无需测试数据）
python eval/scripts/quick_evaluation_demo.py

# 生成测试数据
python eval/scripts/generate_graphrag_test_data.py \
  --output tests/graphrag_test_data.json \
  --num-retrieval 20 \
  --num-edition 10

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

<table>
<tr>
<td width="50%">

**检索质量**
- Precision@K
- Recall@K
- F1@K
- MRR
- NDCG@K
- Hit Rate@K

</td>
<td width="50%">

**GraphRAG 特定**
- 版本推断准确率
- 实体关系准确率
- 多跳推理能力
- 端到端任务完成质量

</td>
</tr>
</table>

详细文档请参考 `eval/README.md`。

---

## 🗺️ Agentic GraphRAG 目标

系统将持续进化，最终目标是结合图谱的 Agentic GraphRAG 智能体：

<table>
<tr>
<td width="50%">

### 🏗️ 知识图谱构建
将版本、馆藏、批注提取为知识图谱（Neo4j / DuckDB）

### 🔄 混合检索
向量检索 + 图路径遍历，支持"先图后文"组合拳

</td>
<td width="50%">

### 🤖 Agentic 推理循环
通过 ReAct 架构，智能体自主调用 OCR、图扫描和向量检索

### ✅ 强一致性校验
基于属性核验机器生成的文献引用，消除幻觉

</td>
</tr>
</table>

---

## ⏳ 开发路线图

| 状态 | 任务 | 说明 |
|:---:|:---|:---|
| ⏳ | **图谱构建器** | 从元数据与版式特征中构建知识实体 |
| ⏳ | **Hybrid 检索内核** | 结合 NumPy 搜索与图扫描的动态检索引擎 |
| ⏳ | **Agentic 调度中心** | 基于规划的自反思智能体循环 |
| ⏳ | **JSON-LD 标注** | 按知识表达规范生成古籍数字档案 |
| ⏳ | **索引增量更新** | 避免每次全量重建向量 |
| ⏳ | **可溯源缓存机制** | 引用的可视化审查追踪 (Citation Trace UI) |
| ⏳ | **Celery 异步队列** | 图片批量 OCR/索引建立转移至异步任务 |
| ⏳ | **全球化多语言** | 国际化前端及 API 翻译通道 |

> 欢迎通过 Issue 或 PR 认领任务，参与共建！

---

## 🗂️ 项目结构

```
font/
├── app/                 # Django 应用核心（Models、Views、API）
├── config/              # Django 设置及路由（WSGI/ASGI）
├── ocr/                 # 古籍图片 OCR 识别子库
├── rag/                 # RAG 处理流
│   ├── naive/           # Naive RAG 实现
│   └── graph/           # GraphRAG 实现（知识图谱）
├── eval/                # GraphRAG 评估系统
│   └── scripts/         # 评估脚本
├── scripts/             # 数据处理与图谱构建脚本
├── outputs/             # OCR 输出结果目录
├── media/               # 用户上传及生成的影像
├── tests/               # 测试用例与开发样例
├── CLAUDE.md            # 项目开发指南
├── README.md            # 项目自述文档
└── pyproject.toml       # 项目依赖与配置
```

---

## ❓ 常见问题

<details>
<summary><b>首次运行报错 <code>OpenAI library is not installed</code>？</b></summary>

<br>

重新执行 `pip install -r requirements.txt` 或 `uv sync`，并确认在激活的虚拟环境中。

</details>

<details>
<summary><b>影像上传直接报 500 且提示 <code>analysis failed</code>？</b></summary>

<br>

检查 `.env` 文件内的 `OPENAI_API_KEY` 及 `OPENAI_BASE_URL` 是否正确，大模型余额是否充足。必要时在 `app/views.py` 开启日志。

</details>

<details>
<summary><b>索引文件过大或内存溢出？</b></summary>

<br>

目前使用轻量 NumPy 方案，若需要切换大规模检索，可微调 `scripts/build_index.py` 或外接 Milvus 等专有向量数据库。

</details>

<details>
<summary><b>如何贡献代码？</b></summary>

<br>

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

</details>

---

## 📄 许可证

基于 **Proprietary License** 许可。

版权所有 © Jafekin, 大连理工大学 (Dalian University of Technology)

---

<div align="center">

**发现 Bug、需要新特性，或者想交流思路？**

[提交 Issue](https://github.com/Jafekin/font/issues) · [发起 PR](https://github.com/Jafekin/font/pulls) · [查看文档](./CLAUDE.md)

<br>

Made with ❤️ by [Jafekin](https://github.com/Jafekin)

</div>
