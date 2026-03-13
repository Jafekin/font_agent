# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an ancient Chinese script OCR and analysis system built with Django, featuring a Naive RAG (Retrieval-Augmented Generation) pipeline that uses Chinese-CLIP embeddings for semantic search. The system analyzes historical documents (oracle bones, Dunhuang manuscripts, stone rubbings, ancient books) and generates structured cataloging reports with citations.

**Current Status**: Naive RAG baseline complete. Next phase: evolving to Agentic GraphRAG with knowledge graph integration.

## Development Commands

### Environment Setup

```bash
# Using uv (recommended)
uv sync
uv run manage.py migrate
uv run manage.py createsuperuser  # optional

# Using venv
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
python manage.py migrate
```

### Running the Server

```bash
# Development server
uv run manage.py runserver 0.0.0.0:8000
# or
python manage.py runserver 0.0.0.0:8000

# Access points:
# - Frontend: http://localhost:8000
# - Admin: http://localhost:8000/admin
```

### Testing

```bash
# Run all tests
python -m pytest tests/

# Run specific test file
python -m pytest tests/test_rag_pipeline.py

# Run with verbose output
python -m pytest tests/ -v
```

### Building RAG Index

```bash
# Build/rebuild Chinese-CLIP vector index from images
python scripts/build_index.py --image-dir media/uploads --index-path rag/index --image-weight 0.65

# The script generates:
# - rag/index/embeddings.npy (normalized vectors)
# - rag/index/ids.json (document IDs)
# - rag/index/metadata.json (image paths, text_info, etc.)
# - rag/index/config.json (index configuration)
```

### Batch Processing

```bash
# Process images in batches
python scripts/batch_process.py --mode batch --batch-size 50 --delay 5.0

# Process by version type (A/B/C/D/E)
python scripts/batch_process.py --mode version --version A

# Process all versions separately
python scripts/batch_process.py --mode all-versions
```

### OCR Commands

```bash
# Recognize single image (layout analysis)
python ocr/cli.py recognize data/example.jpg

# Save all output formats
python ocr/cli.py recognize data/example.jpg --save-all --output-dir ocr/outputs

# Batch recognition
python ocr/cli.py batch images/*.jpg --output-dir outputs

# Check token status
python ocr/cli.py status
```

### Database Management

```bash
# Create migrations after model changes
python manage.py makemigrations

# Apply migrations
python manage.py migrate

# Django shell for testing
python manage.py shell

# Export analysis records
python manage.py dumpdata app.ScriptAnalysis > backup.json

# Collect static files (for production)
python manage.py collectstatic
```

## Architecture

### Core Components

**Django Application (`app/`)**
- `views.py`: HTTP endpoints for image upload, analysis, and history. Orchestrates RAG pipeline and persists results to database.
- `models.py`: `ScriptAnalysis` model stores analysis results with RAG metadata (references, scores, text_info).
- `urls.py`: Routes for `/`, `/api/analyze`, `/api/analyze-base64`, `/api/history`.

**RAG Pipeline (`rag/naive/`)**
- `embeddings.py`: Lazy-loads Chinese-CLIP model, generates 512-dim vectors for images/text.
- `retriever.py`: `TxtaiRetriever` loads numpy index, performs cosine similarity search.
- `prompt.py`: Constructs structured prompts with retrieved context for LLM.
- `pipeline.py`: `RAGPipeline.run()` orchestrates: retrieve → prompt → LLM → structured output. Also contains `analyze_with_llm()` for direct LLM calls.

**OCR Module (`ocr/`)**
- Independent layout analysis subsystem using third-party OCR API.
- `cli.py`: Command-line interface for recognition tasks.
- `client.py`: API client for Kandianguji OCR service.
- `config.py`: Configuration management (token, email, output paths).
- `models.py`: Data models for OCR results.
- `output.py`: Output formatting (JSON, TXT, annotated images).

**Scripts (`scripts/`)**
- `batch_process.py`: Batch processing with retry and checkpoint support.
- `process_shiji_dataset.py`: Dataset-specific processing logic.
- `example_usage.py`: Usage examples for the RAG pipeline.
- `export_results.py`: Export analysis results to various formats.

**Graph RAG (In Progress) (`rag/graph/`)**
- Future Agentic GraphRAG implementation with Neo4j integration.
- `models.py`: Graph entity models (Document, Version, Collection, etc.).
- `builder.py`: Knowledge graph construction from metadata.
- `retriever.py`: Hybrid retrieval (vector + graph traversal).
- `query_interface.py`: Natural language query interface.

### Data Flow

1. **Upload**: User uploads image via web UI or API → `app/views.py`
2. **Retrieval**: Image encoded with Chinese-CLIP → cosine search in `embeddings.npy` → top-K similar images with metadata
3. **Prompt**: Retrieved `text_info` fields assembled into structured prompt → `rag/prompt.py`
4. **Analysis**: Prompt + image sent to ERNIE-4.5-Turbo-VL → structured Markdown/JSON report
5. **Storage**: Result saved to `ScriptAnalysis` model with RAG metadata (references, scores)

### Key Files

- `config/settings.py`: Django settings, loads `.env` for secrets (OPENAI_API_KEY, OPENAI_BASE_URL).
- `rag/index/`: NumPy-based vector index (embeddings.npy, ids.json, metadata.json).
- `manage.py`: Django management entry point.
- `pyproject.toml`: Project dependencies and metadata.

## Important Patterns

### RAG Pipeline Usage

```python
from rag.pipeline import RAGPipeline

pipeline = RAGPipeline(index_path="rag/index")
result = pipeline.run(
    image_path="media/uploads/example.png",
    script_type="汉文古籍",
    hint="宋刻本",
    k=3  # retrieve top-3 similar images
)

# result contains:
# - analysis: LLM output (Markdown/JSON)
# - retrieved_references: list of doc IDs
# - retrieved_text_info: list of text snippets
# - num_references: count
# - retrieval_scores: similarity scores
# - citations: citation candidates
```

### Direct LLM Call (Fallback)

```python
from rag.pipeline import analyze_with_llm
from PIL import Image

image = Image.open("test.jpg")
result = analyze_with_llm(
    image=image,
    script_type="甲骨文",
    hint="商晚期",
    model="ernie-4.5-turbo-vl"
)
```

### Adding New Metadata Fields

When adding metadata to the index:
1. Update `scripts/build_index.py` to extract new fields
2. Ensure fields are serialized to `metadata.json`
3. Update `rag/retriever.py` if filtering logic is needed
4. Update `rag/prompt.py` to include new fields in context

### File Writing Guidelines

**CRITICAL**: When writing files, split into chunks of max 300 lines or 12000 characters per write operation. Use multiple Edit/Write calls for large files.

## Environment Variables

Required in `.env`:
- `SECRET_KEY`: Django secret (generate random string for production)
- `DEBUG`: Set to `False` in production
- `OPENAI_API_KEY`: API key for ERNIE/Baidu LLM
- `OPENAI_BASE_URL`: Default `https://aistudio.baidu.com/llm/lmapi/v3`
- `ALLOWED_HOSTS`: Comma-separated hostnames (e.g., `localhost,127.0.0.1,example.com`)

Optional:
- `RAG_FAKE_EMBEDDINGS=1`: Use fake retrieval results (for testing without model)
- `KANDIANGUJI_TOKEN`: OCR API token
- `KANDIANGUJI_EMAIL`: OCR API email

## Common Issues

**"OpenAI library is not installed"**: Run `pip install -r requirements.txt` or `uv sync`.

**500 error on upload**: Check `.env` has valid `OPENAI_API_KEY` and `OPENAI_BASE_URL`. Enable logging in `app/views.py`.

**Empty retrieval results**: Ensure `rag/index/` contains `embeddings.npy`, `ids.json`, `metadata.json`. Rebuild index with `scripts/build_index.py`.

**Image compression warnings**: Images >1MB are auto-compressed. Check `app/views.py::_compress_image_to_limit()` if quality issues occur.

## Code Style Notes

- Chinese comments and docstrings are used throughout (project is for Chinese historical documents).
- Logging is preferred over print statements.
- RAG pipeline uses lazy initialization for models (Chinese-CLIP, OpenAI client).
- All file paths should use `pathlib.Path` for cross-platform compatibility.
- Database queries use Django ORM; avoid raw SQL.

## GraphRAG Module (Enhanced)

The project now includes an enhanced GraphRAG module that builds knowledge graphs from the `outputs/` directory:

### Building Knowledge Graph from outputs/

```bash
# View dataset statistics
python scripts/build_graph_from_outputs.py --outputs-dir outputs --stats-only

# Build basic graph (no entity extraction)
python scripts/build_graph_from_outputs.py --outputs-dir outputs

# Build full graph with entity extraction
python scripts/build_graph_from_outputs.py --outputs-dir outputs --extract-entities

# Add similarity relations from embeddings
python scripts/build_graph_from_outputs.py \
  --outputs-dir outputs \
  --extract-entities \
  --build-similarity \
  --embeddings-path rag/index/embeddings.npy \
  --ids-path rag/index/ids.json \
  --similarity-threshold 0.85
```

### Evaluating GraphRAG Performance

The project includes a comprehensive evaluation system for testing GraphRAG performance:

```bash
# Quick evaluation demo (no test data needed)
python eval/scripts/quick_evaluation_demo.py

# Generate test data from existing graph
python eval/scripts/generate_graphrag_test_data.py \
  --output tests/graphrag_test_data.json \
  --num-retrieval 20 \
  --num-edition 10

# Run full evaluation
python eval/scripts/evaluate_graphrag.py \
  --test-data tests/graphrag_test_data.json \
  --output-dir evaluation_results

# Visualize results
python eval/scripts/visualize_evaluation_results.py \
  --metrics-file evaluation_results/evaluation_metrics_*.json \
  --output-dir evaluation_results/plots
```

**Evaluation Metrics**:
- Retrieval quality: Precision@K, Recall@K, F1@K, MRR, NDCG@K, Hit Rate@K
- GraphRAG specific: Edition inference accuracy, entity relation accuracy, multi-hop reasoning
- See `eval/README.md` for detailed documentation

### Key Components

- **OutputsDataLoader** (`rag/graph/data_loader.py`): Loads OCR results and metadata from `outputs/` directory structure
- **EnhancedGraphBuilder** (`rag/graph/enhanced_builder.py`): Builds Neo4j graph from outputs data with entity extraction
- **GraphBuilder** (`rag/graph/builder.py`): Original builder for `rag/index/metadata.json` format
- **Neo4jClient** (`rag/graph/neo4j_client.py`): Neo4j database client with CRUD operations
- **GraphQueryInterface** (`rag/graph/query_interface.py`): Query interface for graph traversal and inference

### outputs/ Directory Structure

Each page in `outputs/` contains:
- `{name}.json`: Structured OCR results with text lines and word positions
- `metadata.json`: Statistics (line count, confidence, image size)
- `extended_metadata.json`: Parsed version, edition, collection info (optional)
- `raw/{name}_raw.json`: Raw API response
- `text/{name}.txt`: Plain text output
- `overlay/{name}_overlay.jpg`: Annotated image

### Graph Schema

- **Nodes**: Document, Volume, Page, Edition, Collection, Layout, Seal, Entity
- **Relationships**: HAS_VOLUME, HAS_PAGE, SIMILAR_TO, BELONGS_TO_EDITION, STORED_IN, HAS_LAYOUT, HAS_SEAL, MENTIONS

See `rag/graph/USAGE.md` for detailed usage examples and `rag/graph/SCHEMA.md` for complete schema documentation.

## Future Work (Agentic GraphRAG)

Next steps for full Agentic GraphRAG:
1. **Hybrid Retrieval**: Combine vector search with graph traversal and attribute filtering
2. **Agent Orchestration**: Multi-step reasoning with tool calls (OCR, graph query, vector search)
3. **Citation Validation**: Use graph IDs to verify LLM-generated citations
4. **Query Planning**: Natural language to Cypher query translation
