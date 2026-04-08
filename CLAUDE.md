# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Project Overview

Ancient Chinese script OCR and analysis system built with Django. Analyzes historical documents (oracle bones, Dunhuang manuscripts, stone rubbings, ancient books) and generates structured cataloging reports via a RAG pipeline.

**Current status**: NaiveRAG baseline + GraphRAG (Neo4j) both complete. Next: Agentic hybrid retrieval.

## Development Commands

### Setup

```bash
uv sync
uv run manage.py migrate
uv run manage.py runserver 0.0.0.0:8000
# http://localhost:8000  |  http://localhost:8000/admin
```

### Testing

```bash
python -m pytest tests/
python -m pytest tests/test_rag_pipeline.py -v
```

### Build NaiveRAG Index

```bash
python rag/naive/scripts/build_index.py \
  --data-dir rag/data \
  --index-path rag/naive/index \
  --image-weight 0.65 \
  --use-overlay
# Output: rag/naive/index/{embeddings.npy, ids.json, metadata.json, config.json}
```

### Build GraphRAG Knowledge Graph

```bash
# Start Neo4j
docker run -d --name neo4j -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/password neo4j:latest

# Build graph (add --entities for named entity extraction)
python -m rag.graph.scripts.build_graph \
  --data-dir rag/data \
  --entities \
  --embeddings rag/naive/index/embeddings.npy \
  --ids rag/naive/index/ids.json

# Stats only
python -m rag.graph.scripts.build_graph --stats-only
```

### OCR

```bash
python -m ocr.cli recognize data/example.jpg --save-all --output-dir rag/data
python -m ocr.cli batch images/*.jpg --output-dir rag/data
python -m ocr.cli status
```

### Data Processing

```bash
# OCR batch process the Shiji dataset into rag/data/
python rag/scripts/process_shiji_dataset.py \
  --data-dir "data/名录 史记2025-11-6" \
  --output-dir rag/data

# Analyze OCR results
python rag/scripts/analyze_results.py --data-dir rag/data

# Export to CSV/JSON/TXT
python rag/scripts/export_results.py --data-dir rag/data --output-dir rag/scripts/exports
```

### Django Management

```bash
python manage.py makemigrations && python manage.py migrate
python manage.py shell
python manage.py dumpdata app.ScriptAnalysis > backup.json
python manage.py collectstatic  # production
```

## Architecture

### Module Map

```
app/
  views.py        HTTP入口，编排RAG管道，持久化分析结果
  models.py       ScriptAnalysis 模型（含RAG元数据）
  urls.py         /  /api/analyze  /api/analyze-base64  /api/history

rag/
  naive/
    data_loader.py   NaiveDataLoader → PageData（统一元数据 schema）
    embeddings.py    Chinese-CLIP 惰性加载，512维向量
    retriever.py     TxtaiRetriever，NumPy 余弦相似度 Top-K
    prompt.py        get_prompt()，结构化 Markdown 报告模板
    pipeline.py      RAGPipeline.run()，analyze_with_llm()
    scripts/
      build_index.py 构建向量索引

  graph/
    models.py        Document/Edition/Collection/Page/Layout/Entity
    client.py        Neo4jClient（通用 merge_node/merge_relation）
    builder.py       GraphBuilder（NaiveDataLoader → Neo4j）
    retriever.py     GraphRetriever（全文/相似/版本推断/实体查询）
    scripts/
      build_graph.py CLI入口

  scripts/
    process_shiji_dataset.py  史记数据集批量OCR处理
    analyze_results.py        OCR结果统计分析
    export_results.py         CSV/JSON/TXT导出

ocr/
  client.py    KandiangujiOCRClient
  models.py    OCRResult / TextLine / WordInfo
  output.py    OCROutputManager（JSON、TXT、overlay图）
  cli.py       命令行工具
```

### Data Flow

```
rag/data/{页面目录}/           ← OCR 输出，每页一个目录
  {name}.json                  # OCR text_lines
  metadata.json                # 统计 + 图片路径
  extended_metadata.json       # 版本/机构元数据
  text/{name}.txt
  overlay/{name}_overlay.jpg

NaiveDataLoader.scan_pages()  →  List[PageData]
  ↓ build_index.py               ↓ GraphBuilder.build()
embeddings.npy + ids.json      Neo4j 图谱节点/关系

查询时：
  TxtaiRetriever.search_by_image()  →  Top-K 相似页 + text_info
  get_prompt(script_type, hint, context)  →  结构化 Prompt
  analyze_with_llm(image, prompt)  →  Markdown 报告
  ScriptAnalysis.save()  →  SQLite
```

### Key Patterns

**NaiveRAG pipeline**
```python
from rag.naive.pipeline import RAGPipeline

pipeline = RAGPipeline(index_path="rag/naive/index")
result = pipeline.run(
    image_path="media/uploads/example.png",
    script_type="汉文古籍",
    hint="宋刻本",
    k=3,
)
# result keys: analysis, retrieved_references, retrieval_scores,
#              retrieved_text_info, num_references, citations, pipeline_mode
```

**Direct LLM call**
```python
from rag.naive.pipeline import analyze_with_llm
from PIL import Image

result = analyze_with_llm(Image.open("test.jpg"), script_type="甲骨文", hint="商晚期")
```

**GraphRAG retrieval**
```python
from rag.graph import Neo4jClient, GraphRetriever

with Neo4jClient(password="password") as client:
    r = GraphRetriever(client)
    print(r.search_by_text("五帝本紀", limit=5))
    print(r.infer_edition("page_unknown_001"))
```

**Adding new metadata fields**
1. Add field to `EditionMetadata` in `rag/naive/data_loader.py`
2. Expose in `PageData.to_text_info()` and `to_metadata_dict()`
3. Rebuild index: `python rag/naive/scripts/build_index.py`
4. Update `rag/naive/prompt.py::_format_single_context()` if it should appear in context

## Environment Variables

`.env` (required):
```
SECRET_KEY=...
DEBUG=True
OPENAI_API_KEY=...
OPENAI_BASE_URL=https://aistudio.baidu.com/llm/lmapi/v3
ALLOWED_HOSTS=localhost,127.0.0.1
```

`.env` (optional):
```
KANDIANGUJI_TOKEN=...
KANDIANGUJI_EMAIL=...
RAG_FAKE_EMBEDDINGS=1   # skip model loading, return fake results (testing)
```

## Common Issues

**`OpenAI library is not installed`** → `uv sync`

**500 on upload** → check `OPENAI_API_KEY` / `OPENAI_BASE_URL` in `.env`

**Empty retrieval results** → confirm `rag/naive/index/embeddings.npy` exists; rebuild with `build_index.py`

**Image >1MB** → auto-compressed in `app/views.py::_compress_image_to_limit()`

## Code Style

- Chinese comments and docstrings throughout (domain convention).
- Logging over print statements.
- Lazy model initialization (Chinese-CLIP, OpenAI client).
- `pathlib.Path` for all file paths.
- Django ORM only; no raw SQL.
- File writes: max 300 lines / 12 000 chars per `Write` call — split large files across multiple calls.
