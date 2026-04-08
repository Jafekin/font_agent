# 古文字识别助手：关键流程示意

> 使用 Mermaid 流程图描述项目关键步骤，可在 VS Code / GitHub / mermaid.live 中预览，用于论文配图。

---

## 1. 古籍影像总体处理流程

```mermaid
flowchart LR
    A[古籍影像上传] --> B[文件接收与存储\nDjango: app/views.py]
    B --> C[OCR 识别\nocr/client.py]
    C --> D[结构化页面数据\nPageData schema]
    D --> E[Chinese-CLIP 向量编码\nrag/naive/embeddings.py]
    E --> F[向量索引\nembeddings.npy + metadata.json]
    F --> G[相似检索\nrag/naive/retriever.py]
    G --> H[RAG Prompt 组装\nrag/naive/prompt.py]
    H --> I[大模型分析\nrag/naive/pipeline.py]
    I --> J[结构化报告输出]
```

---

## 2. 版本指纹构建与相似版本检索

```mermaid
flowchart LR
    A[古籍页面图像] --> B[OCR 识别\n行数/列数/版心特征]
    B --> C[PageData 元数据\n版本/朝代/藏馆]
    C --> D[文本向量编码]
    A --> E[图像向量编码\nChinese-CLIP]
    D --> F[融合向量\n0.65×图像 + 0.35×文本]
    E --> F
    F --> G[向量索引写入\nrag/naive/index]
    G --> H[查询时余弦相似检索\nTop-K 候选]
    H --> I[版本判定与聚类]
```

---

## 3. GraphRAG 知识图谱构建与推理

```mermaid
flowchart LR
    A[PageData\nNaiveDataLoader] --> B[GraphBuilder\nrag/graph/builder.py]
    B --> C[Neo4j 图谱\nDocument/Edition/Page/Entity]
    C --> D[GraphRetriever\nrag/graph/retriever.py]
    D --> E{查询类型}
    E --> F[全文检索\nsearch_by_text]
    E --> G[相似页检索\nfind_similar]
    E --> H[版本推断\ninfer_edition]
    E --> I[实体查询\nfind_by_entity]
```

---

## 4. 著录识别与 RAG 语义增强流程

```mermaid
flowchart LR
    A[页面图像 + OCR 文本] --> B[标题/卷端/牌记定位]
    B --> C[初步字段抽取\n题名/卷次/著者线索]
    C --> D[向量检索相似页面\nrag/naive/retriever.py]
    D --> E[汇总上下文元数据\n题名/版本/藏地等]
    E --> F[构造 RAG Prompt\nrag/naive/prompt.py]
    F --> G[调用大模型\n生成结构化著录]
    G --> H[字段规范化与校验\n对照现有目录]
    H --> I[写入著录知识库]
```
