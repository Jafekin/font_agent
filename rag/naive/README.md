# RAG 使用示例

## 快速开始

### 0. 环境准备

1. 安装第三方 Chinese-CLIP 依赖：
    ```bash
    pip install -e thirdparty/Chinese-CLIP
    ```
2. （可选）设置 `HUGGINGFACE_HUB_TOKEN` 以提升模型下载速度。
3. 确认 `scripts/build_index.py` 和 `rag/embeddings.py` 使用相同的模型名，默认是 `OFA-Sys/chinese-clip-vit-base-patch16`（脚本会自动映射到 `ViT-B-16` 权重）。

### 1. 准备原始数据

为每张图片放置一个同名的文字描述文件（JSON / TXT / MD），目录结构示例：

```
media/uploads/
├── image1.jpg
├── image1.json          # JSON 描述
├── image2.png
└── image2.txt           # 纯文本描述
```

`image1.json` 示例：

```json
{
   "title": "史记一百三十卷",
   "author": "（汉）司马迁",
   "edition": "北宋刻本",
   "description": "这是一张史记古籍图片......"
}
```

`image2.txt` 示例：

```
这是一张甲骨文图片，记录了商代晚期的卜辞内容。
主要内容包括：祭祀、田猎、征伐等。
```

### 2. 构建本地向量索引

运行脚本即可自动：扫描图片 → 提取/兜底文字 → 使用 Chinese-CLIP 生成图文向量 → 保存为 numpy 索引：

```bash
python scripts/build_index.py \
      --image-dir media/uploads \
      --index-path rag/index \
      --image-weight 0.65
```

输出目录包含：

```
rag/index/
├── embeddings.npy   # N×D 浮点矩阵
├── ids.json         # 每行对应的文档 ID
├── metadata.json    # 展平后的元数据 + text_info
└── config.json      # 模型名、向量维度、统计信息
```

若构建过程中提示模型未找到，请确认已经安装 `huggingface_hub`，必要时设置代理或提前拉取权重。

### 2. 使用RAG管道分析图片

```python
from rag.pipeline import RAGPipeline

# 初始化管道
pipeline = RAGPipeline(index_path="rag/index")

# 用户上传图片后，进行分析
result = pipeline.run(
    image_path="/Users/jafekin/Desktop/古籍/名录 史记2025-11-6/C史记 集解、索隐、正义三家注本 4明嘉靖四年（1525）汪谅刻本/【2】03476 （二）03215 史记一百三十卷 （汉）司马迁撰 （南朝宋）裴骃集解 （唐）司马贞索隐 （唐）张守节正义 明嘉靖四年（1525）汪谅刻本 山东省图书馆/IMG_4549.jpg",
    script_type="汉文古籍",
    hint="用户提供的提示信息（可选）",
    k=5  # 检索top-5个相似图片
)

# 检查结果
if result['success']:
    # LLM的分析结果
    analysis = result['analysis']
    print("分析结果:", analysis)
    
    # 检索到的文字信息（这些信息会被输入给LLM）
    text_info = result['retrieved_text_info']
    print("\n检索到的文字信息:")
    for i, info in enumerate(text_info, 1):
        print(f"{i}. {info[:100]}...")  # 显示前100个字符
    
    # 参考来源
    references = result['retrieved_references']
    print(f"\n参考来源: {references}")
    
    # 相似度分数
    scores = result['retrieval_scores']
    print(f"相似度分数: {scores}")
else:
    print(f"错误: {result['error']}")
```

### 3. 仅检索相似图片（不调用LLM）

```python
from rag.pipeline import RAGPipeline

pipeline = RAGPipeline(index_path="rag/index")

# 搜索相似图片
similar_images = pipeline.search_similar(
    query_image_path="/Users/jafekin/Desktop/古籍/名录 史记2025-11-6/C史记 集解、索隐、正义三家注本 4明嘉靖四年（1525）汪谅刻本/【2】03476 （二）03215 史记一百三十卷 （汉）司马迁撰 （南朝宋）裴骃集解 （唐）司马贞索隐 （唐）张守节正义 明嘉靖四年（1525）汪谅刻本 山东省图书馆/IMG_4549.jpg",
    k=5
)

for item in similar_images:
    print(f"图片ID: {item['id']}")
    print(f"图片路径: {item['image_path']}")
    print(f"文字信息: {item['text_info']}")
    print(f"相似度: {item['score']:.3f}")
    print("---")
```

### 4. 获取图片对应的文字信息

```python
from rag.pipeline import RAGPipeline

pipeline = RAGPipeline(index_path="rag/index")

# 直接获取图片对应的文字信息
text_info_list = pipeline.get_text_info_for_image("image.jpg", k=1)

if text_info_list:
    print(f"文字信息: {text_info_list[0]}")
else:
    print("未找到对应的文字信息")
```

## 工作流程说明

1. **构建知识库**：
   - 将图片和对应的文字信息组织好
   - 运行`build_index.py`构建索引
   - 索引会保存图片的向量表示和对应的文字信息

2. **用户上传图片**：
   - 用户通过前端上传图片

3. **检索相似图片**：
   - 管道直接加载 `embeddings.npy + ids.json` 完成向量检索
   - 返回相似图片及其对应的文字信息

4. **构建增强提示词**：
   - 将检索到的文字信息作为上下文
   - 与用户提示一起构建增强的提示词

5. **LLM分析**：
   - 将增强提示与用户图片传入 LLM
   - 基于检索上下文得到最终回答

6. **返回结果**：
   - 返回LLM的分析结果
   - 同时返回检索到的文字信息和参考来源

## 注意事项

1. **文字信息文件命名**：
   - 图片文件：`image.jpg`
   - 对应的文字信息文件：`image.json` 或 `image.txt`
   - 文件名（不含扩展名）必须相同

2. **文字信息格式**：
   - JSON格式：脚本会自动提取`description`、`text`、`content`等字段
   - 文本格式：直接读取文件内容
   - 如果找不到文字信息文件，会使用图片文件名作为默认信息

3. **索引更新**：
   - 添加新图片后，需要重新运行`build_index.py`更新索引
   - 或者实现增量索引功能（未来扩展）

4. **性能优化**：
   - 设置 `RAG_DEVICE=cuda` 以启用 GPU 编码
   - `RAG_FAKE_EMBEDDINGS=1` 可用于无 GPU 环境的快速冒烟测试
   - 减少图片尺寸或分批构建以控制显存与内存占用

