# rag/scripts

史记数据集处理与结果分析工具。

## 脚本

### process_shiji_dataset.py

批量 OCR 处理史记图片数据集，支持断点续传与按版本筛选。

```bash
# 处理所有图片
python rag/scripts/process_shiji_dataset.py \
  --data-dir "data/名录 史记2025-11-6" \
  --output-dir rag/data

# 仅处理 A 版本
python rag/scripts/process_shiji_dataset.py \
  --data-dir "data/名录 史记2025-11-6" \
  --output-dir rag/data \
  --version A
```

输出结构（每页一个目录，与 NaiveDataLoader 兼容）：
```
rag/data/{页面名}/
├── {页面名}.json
├── metadata.json
├── extended_metadata.json
├── text/{页面名}.txt
└── overlay/{页面名}_overlay.jpg
```

### analyze_results.py

对 `rag/data/` 中的 OCR 结果进行统计分析。

```bash
python rag/scripts/analyze_results.py --data-dir rag/data
```

输出：置信度分布、按版本统计、文本方向分析，保存为 `analysis_report.json`。

### export_results.py

将 OCR 结果导出为 CSV / JSON / 纯文本 / Markdown 目录。

```bash
python rag/scripts/export_results.py \
  --data-dir rag/data \
  --output-dir rag/scripts/exports
```

## 推荐工作流

```
process_shiji_dataset.py   →   rag/data/
                                  ↓
rag/naive/scripts/build_index.py  →   rag/naive/index/   （NaiveRAG）
                                  ↓
rag/graph/scripts/build_graph.py  →   Neo4j             （GraphRAG）
                                  ↓
analyze_results.py / export_results.py  →  统计报告 / 导出文件
```
