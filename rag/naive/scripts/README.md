# rag/naive/scripts

## build_index.py

从 `rag/data/` 构建 Chinese-CLIP 向量索引。

```bash
python rag/naive/scripts/build_index.py \
  --data-dir rag/data \
  --index-path rag/naive/index \
  --image-weight 0.65 \
  --use-overlay
```

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `--data-dir` | `rag/data` | 页面数据目录 |
| `--index-path` | `rag/naive/index` | 索引输出目录 |
| `--image-weight` | `0.65` | 图像向量权重（0→纯文本，1→纯图像） |
| `--use-overlay` / `--no-overlay` | `--use-overlay` | 优先使用含 OCR 框的 overlay 图片 |

输出：`embeddings.npy`、`ids.json`、`metadata.json`、`config.json`。
