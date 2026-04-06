<!--
 * @Author        陈佳辉 1946847867@qq.com
 * @Date          2025-12-04 20:04:38
 * @LastEditTime  2025-12-10 18:50:26
 * @Description   
 * 
-->
# 脚本使用说明

## 功能
# Scripts 目录说明

`scripts/` 目录包含本项目日常数据处理、索引构建与资料抓取的三个主要脚本。下面按脚本逐一介绍其功能、依赖与典型用法

## process_shiji_images.py — 史记原始图片批处理

**用途**：批量清洗史记图像数据集，将分散的图片与目录信息整理成统一的文件命名与结构化 JSON 元数据，以便后续索引构建和标注。

**核心能力**

- 递归扫描给定数据目录，识别所有受支持的图片格式（JPG/PNG/WebP 等）。
- 根据目录命名约定解析版本类型、卷别、编号、作者、藏馆等信息。
- 依据模版 `史记_{版本类型}_{编号}_{序号}_{hash}.jpg` 重命名图片（可关闭）。
- 为每张图片生成与 `prompt.py` 一致的完整 JSON 描述，填充路径、题名、版本、收藏等字段。
- 将图片与 JSON 统一复制到输出目录，必要时在原目录创建备份。

**常用命令**

```powershell
python scripts/process_shiji_images.py `
  --data-dir "data/名录 史记2025-11-6" `
  --output-dir "data/processed_shiji"
```

| 选项 | 说明 |
| --- | --- |
| `--data-dir` | 待处理的原始数据目录（默认 `data/名录 史记2025-11-6`） |
| `--output-dir` | **必填**，处理后的图片与 JSON 将复制至该目录 |
| `--no-rename` | 保留原文件名，仅生成元数据 |
| `--no-backup` | 跳过对原文件的备份 |

处理完成后，`output-dir` 中会出现成对的图片与 JSON，方便后续索引构建或人工审核。

## build_index.py — 利用 Chinese-CLIP 构建向量索引

**用途**：读取整理后的图片（及其 JSON/TXT 描述），通过 Chinese-CLIP 生成图像与文本联合向量，落盘为 RAG 检索所需的 `embeddings.npy / ids.json / metadata.json / config.json`。

**核心能力**

- 自动为每张图片寻找同名 JSON/TXT 描述，必要时回退到默认描述。
- 调用 `rag/embeddings.py` 中封装的 Chinese-CLIP 接口分别计算图像、文本向量，并按权重融合。
- 将元数据压平存储，便于后续查询或调试。
- 输出包含模型信息、维度、文档数、失败数的 `config.json`，便于校验。

**常用命令**

```powershell
python scripts/build_index.py `
  --image-dir "data/processed_shiji" `
  --index-path "rag/index" `
  --image-weight 0.65
```

| 选项 | 说明 |
| --- | --- |
| `--image-dir` | 图片与 JSON 所在目录 |
| `--text-info-dir` | 如果文字描述单独存放，可指定另一个根目录 |
| `--index-path` | 索引输出目录（默认 `rag/index`） |
| `--model` | 自定义 Chinese-CLIP 模型名称 |
| `--image-weight` | 图像/文本融合权重，范围 0-1 |

执行成功后，可在 `rag/index/` 下看到生成的向量矩阵与配套元数据文件。

## search_details.py — 上海古籍联合目录详情抓取

**用途**：调用上海图书馆联合目录的检索接口，获取指定作品的书目信息，并进一步抓取实例的 JSON-LD 详情，格式化输出核心字段（责任者、分类、朝代、版式信息等）。

**工作流程**

1. 通过 `/es/api/gjmult/inst` 接口按题名与馆藏条件检索，取首条结果。
2. 使用返回的 `uri` 请求 `@graph` JSON-LD 数据，定位 `pmb:Instance` 节点。
3. 解析标题、分类、版本、册数、尺寸、版框、来源等字段，按固定模版打印。
4. 根据 `temporal` 字段的 authority URI 补充朝代信息（自动跟进 RDF 资源）。

**示例命令**

```powershell
python scripts/search_details.py
```

默认检索“祝氏集畧三十卷”，可在 `get_details()` 中更改 `search_txt`。运行时需要外网访问 `http://data.library.sh.cn/`，若处于无证书环境可继续使用脚本内置的 `verify=False`。

## 推荐的任务顺序

1. 使用 `process_shiji_images.py` 将原始图像整理为统一命名与 JSON 元数据。
2. 将输出目录作为 `build_index.py --image-dir` 输入，生成 RAG 检索所需的向量索引。
3. 在策展或数据核对阶段，利用 `search_details.py` 快速查询上海古籍联合目录的权威记录，校准元数据字段。

如需更多定制，可直接阅读对应脚本代码，每个函数均附带注释，方便扩展。*** End Patch
    "language": {"value": "汉文", "confidence": 1.0},

    "classification": {"value": "史部-紀傳類-通代之屬", "confidence": 1.0}
