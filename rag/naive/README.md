# NaiveRAG 模块

基于 Chinese-CLIP 的图像+文本向量检索管道，为 LLM 提供结构化古籍上下文。

## 架构

```
rag/data/{页面目录}/          ← 数据源（每页一个目录）
        ├── {name}.json       # OCR text_lines
        ├── metadata.json     # OCR 统计 + 图片路径
        ├── extended_metadata.json  # 版本/机构元数据
        ├── text/{name}.txt   # 清洗后纯文本
        └── overlay/{name}_overlay.jpg

data_loader.py  → NaiveDataLoader  → PageData（统一 schema）
scripts/build_index.py  → embeddings.npy + ids.json + metadata.json
retriever.py  → TxtaiRetriever（cosine 相似度搜索）
pipeline.py  → RAGPipeline（检索 → 提示 → LLM）
prompt.py  → get_prompt()（结构化 Markdown 报告模板）
```

## 快速上手

### 1. 构建向量索引

```bash
python rag/naive/scripts/build_index.py \
  --data-dir rag/data \
  --index-path rag/naive/index \
  --image-weight 0.65 \
  --use-overlay
```

生成文件：
```
rag/naive/index/
├── embeddings.npy   # N×512 float32 向量矩阵
├── ids.json         # 页面 ID 列表
├── metadata.json    # 每页元数据 + text_info
└── config.json      # 模型名、维度、统计
```

### 2. 调用 RAG 管道

```python
from rag.naive.pipeline import RAGPipeline

pipeline = RAGPipeline(index_path="rag/naive/index")
result = pipeline.run(
    image_path="path/to/query.jpg",
    script_type="汉文古籍",
    hint="宋刻本",   # 可选
    k=3,
)

print(result["analysis"])        # LLM 结构化报告
print(result["retrieved_references"])  # 检索到的页面 ID
print(result["retrieval_scores"])      # 相似度分数
```

### 3. CLI 检索查询

```bash
# 文本向量检索
python -m rag.naive.scripts.query text "五帝本紀" --limit 5

# 图片向量检索
python -m rag.naive.scripts.query image path/to/image.jpg --limit 3

# 元数据过滤
python -m rag.naive.scripts.query text "司马迁" --filter type=image

# JSON 输出
python -m rag.naive.scripts.query image img.jpg --json
```

### 4. 仅检索（不调用 LLM）

```python
results = pipeline.search_similar(query_image_path="query.jpg", k=5)
for r in results:
    print(r["id"], r["score"], r["text_info"][:80])
```

## 数据 Schema（PageData）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `page_id` | str | 目录名（唯一 ID） |
| `full_text` | str | 清洗后 OCR 纯文本 |
| `edition.version_type` | str | 版本类型（A/B/C/D/E） |
| `edition.annotation_system` | str | 集解 / 三家注 等 |
| `edition.printing_info.dynasty_period` | str | 朝代/时期 |
| `edition.printing_info.printer` | str | 刻印者或书坊 |
| `edition.holding_institution` | str | 收藏机构 |
| `edition.authors` | list[str] | 著者 |
| `edition.annotators` | list[str] | 注释者 |
| `edition.total_juan` | int | 全书总卷数 |

## 关键参数

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `--image-weight` | 0.65 | 图像向量权重（0→纯文本，1→纯图像） |
| `--use-overlay` | True | 优先用含 OCR 框的 overlay 图片 |
| `k` | 3 | 检索返回的相似页面数 |
| `RAG_FAKE_EMBEDDINGS=1` | — | 跳过模型加载，返回假结果（测试用） |
