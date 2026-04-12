<!--
 * @Author        Jiahui Chen 1946847867@qq.com
 * @Date          2026-04-12 21:03:13
 * @LastEditTime  2026-04-12 21:04:58
 * @Description   
 * 
-->
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

## query.py

对已构建的向量索引执行文本或图片检索，输出每条结果的完整 metadata。

```bash
# 文本向量检索
python -m rag.naive.scripts.query text "五帝本紀" --limit 5

# 图片向量检索
python -m rag.naive.scripts.query image ocr/tests/test.jpg --limit 3

# 元数据过滤
python -m rag.naive.scripts.query text "司马迁" --filter type=image

# JSON 格式输出
python -m rag.naive.scripts.query image img.jpg --json

# 指定索引目录
python -m rag.naive.scripts.query --index rag/naive/index text "本紀"
```

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `--index` | `rag/naive/index` | 索引目录 |
| `--limit` | `5` | 返回结果数 |
| `--filter` | — | 元数据过滤，格式 `key=value`，可多个 |
| `--json` | False | JSON 格式输出 |
| `-v` | False | 显示详细日志 |

每条结果输出字段：`id`、`score`、`text_info`、`image_path` 及 metadata 中所有非空字段。
