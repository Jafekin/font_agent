# GraphRAG Schema

## 节点

### Document（文献）

```cypher
CONSTRAINT doc_id IS UNIQUE
INDEX ON title
```

| 属性 | 类型 | 说明 |
| --- | --- | --- |
| doc_id | string | 唯一标识（来自 edition_dir） |
| title | string | 文献名称 |
| dynasty | string | 朝代/时期 |
| authors | string | 著者（顿号分隔） |
| annotators | string | 注释者（顿号分隔） |
| total_juan | int | 全书总卷数 |

### Edition（版本）

```cypher
CONSTRAINT edition_id IS UNIQUE
```

| 属性 | 类型 | 说明 |
| --- | --- | --- |
| edition_id | string | `edition_{version_type}_{edition_dir}` |
| version_type | string | A / B / C / D / E |
| annotation_system | string | 集解 / 三家注 等 |
| dynasty | string | 刻印朝代 |
| printer | string | 刻印者或书坊 |
| extant_juan | string | 现存卷数说明 |
| catalog_id | string | 编目号 |

### Collection（馆藏）

```cypher
CONSTRAINT collection_id IS UNIQUE
```

| 属性 | 类型 | 说明 |
| --- | --- | --- |
| collection_id | string | institution MD5 前10位 |
| institution | string | 收藏机构名称 |
| call_number | string | 索书号 |

### Page（页面）

```cypher
CONSTRAINT page_id IS UNIQUE
FULLTEXT INDEX ON ocr_text  →  page_ocr_idx
```

| 属性 | 类型 | 说明 |
| --- | --- | --- |
| page_id | string | 页面目录名 |
| image_path | string | overlay 或 source 图片路径 |
| ocr_text | string | OCR 纯文本（最多 2000 字符） |
| ocr_confidence | float | 平均置信度 |
| is_vertical | bool | 是否竖排 |
| width / height | int | 图片尺寸 |

### Layout（版式）

```cypher
CONSTRAINT layout_id IS UNIQUE
```

| 属性 | 类型 | 说明 |
| --- | --- | --- |
| layout_id | string | `layout_{line_count}_{has_annotation}` |
| line_count | int | OCR 识别行数 |
| has_annotation | bool | 是否存在双行小注 |

### Entity（命名实体）

```cypher
CONSTRAINT entity_id IS UNIQUE
INDEX ON entity_text
```

| 属性 | 类型 | 说明 |
| --- | --- | --- |
| entity_id | string | `{type}:{text}` MD5 前12位 |
| entity_text | string | 实体原文 |
| entity_type | string | PERSON / PLACE |

---

## 关系

| 关系 | 方向 | 说明 |
| --- | --- | --- |
| HAS_EDITION | Document → Edition | 文献包含某版本 |
| HAS_PAGE | Edition → Page | 版本包含某页面 |
| STORED_IN | Document → Collection | 文献藏于某机构 |
| HAS_LAYOUT | Page → Layout | 页面具有某版式 |
| MENTIONS | Page → Entity | 页面提及某实体 |
| SIMILAR_TO | Page → Page | 视觉相似（属性：score float） |
