# 古籍知识图谱 Schema 设计

## 概述

本文档定义了古籍文献知识图谱的核心实体、关系和属性约束，用于支持 GraphRAG 检索和推理。

---

## 核心实体（节点类型）

### 1. Document（文献）
**描述**: 古籍文献的顶层实体

**属性**:
- `doc_id` (string, 必需, 唯一): 文献唯一标识符
- `title` (string, 必需): 书名/题名
- `author` (string): 作者
- `dynasty` (string): 朝代（如：宋、明、清）
- `category` (string): 分类（如：经部、史部、子部、集部）
- `description` (text): 文献简介
- `created_at` (datetime): 创建时间
- `updated_at` (datetime): 更新时间

**索引**:
- PRIMARY KEY: `doc_id`
- INDEX: `title`, `author`, `dynasty`, `category`

**示例**:
```json
{
  "doc_id": "doc_shiji",
  "title": "史記",
  "author": "司馬遷",
  "dynasty": "漢",
  "category": "史部",
  "description": "中國第一部紀傳體通史"
}
```

---

### 2. Volume（卷次）
**描述**: 文献的卷次划分

**属性**:
- `volume_id` (string, 必需, 唯一): 卷次唯一标识符
- `volume_number` (integer, 必需): 卷号
- `volume_title` (string): 卷标题（如：五帝本紀第一）
- `page_count` (integer): 页数
- `description` (text): 卷次说明

**索引**:
- PRIMARY KEY: `volume_id`
- INDEX: `volume_number`

**示例**:
```json
{
  "volume_id": "vol_shiji_001",
  "volume_number": 1,
  "volume_title": "五帝本紀第一",
  "page_count": 42
}
```

---

### 3. Page（页面）
**描述**: 古籍的单页图像及其内容

**属性**:
- `page_id` (string, 必需, 唯一): 页面唯一标识符
- `page_number` (integer, 必需): 页码
- `image_path` (string, 必需): 图片文件路径
- `image_hash` (string): 图片哈希值（用于去重）
- `ocr_text` (text): OCR 识别的文本内容
- `ocr_confidence` (float): OCR 平均置信度
- `text_direction` (string): 文本方向（horizontal/vertical）
- `width` (integer): 图片宽度
- `height` (integer): 图片高度
- `created_at` (datetime): 创建时间

**索引**:
- PRIMARY KEY: `page_id`
- INDEX: `page_number`, `image_hash`
- FULLTEXT INDEX: `ocr_text`

**示例**:
```json
{
  "page_id": "page_shiji_001_001",
  "page_number": 1,
  "image_path": "media/uploads/shiji_vol1_p1.jpg",
  "image_hash": "a3f5e8d9c2b1...",
  "ocr_text": "五帝本紀第一\n史記一\n...",
  "ocr_confidence": 0.9712,
  "text_direction": "vertical",
  "width": 1920,
  "height": 3126
}
```

---

### 4. Edition（版本）
**描述**: 古籍的版本信息（刻本、抄本等）

**属性**:
- `edition_id` (string, 必需, 唯一): 版本唯一标识符
- `edition_type` (string, 必需): 版本类型（刻本、抄本、影印本等）
- `edition_name` (string): 版本名称（如：宋刻本、明嘉靖本）
- `publisher` (string): 出版者/刻印者
- `publish_year` (string): 出版/刻印年代
- `publish_place` (string): 出版/刻印地点
- `description` (text): 版本说明

**索引**:
- PRIMARY KEY: `edition_id`
- INDEX: `edition_type`, `publish_year`

**示例**:
```json
{
  "edition_id": "ed_shiji_song",
  "edition_type": "刻本",
  "edition_name": "宋刻本",
  "publisher": "建安書坊",
  "publish_year": "宋淳熙年間",
  "publish_place": "建安"
}
```

---

### 5. Collection（馆藏）
**描述**: 古籍的收藏机构和编号

**属性**:
- `collection_id` (string, 必需, 唯一): 馆藏唯一标识符
- `institution` (string, 必需): 收藏机构（如：国家图书馆、故宫博物院）
- `call_number` (string): 索书号/编号
- `location` (string): 存放位置
- `acquisition_date` (date): 入藏日期
- `condition` (string): 保存状况（完好、破损、修复等）
- `notes` (text): 备注

**索引**:
- PRIMARY KEY: `collection_id`
- INDEX: `institution`, `call_number`

**示例**:
```json
{
  "collection_id": "coll_nlc_001",
  "institution": "中國國家圖書館",
  "call_number": "善本 001234",
  "location": "善本書庫",
  "condition": "完好"
}
```

---

### 6. Layout（版式）
**描述**: 页面的版式特征

**属性**:
- `layout_id` (string, 必需, 唯一): 版式唯一标识符
- `column_count` (integer): 列数
- `line_count` (integer): 行数
- `chars_per_line` (float): 行均字数
- `border_type` (string): 边框类型（单边、双边、四周双边等）
- `border_color` (string): 边框颜色（黑口、白口）
- `has_fish_tail` (boolean): 是否有鱼尾
- `has_annotation` (boolean): 是否有注释/小字
- `annotation_position` (string): 注释位置（双行、夹注等）

**索引**:
- PRIMARY KEY: `layout_id`
- INDEX: `column_count`, `border_type`

**示例**:
```json
{
  "layout_id": "layout_001",
  "column_count": 2,
  "line_count": 20,
  "chars_per_line": 18.5,
  "border_type": "四周雙邊",
  "border_color": "黑口",
  "has_fish_tail": true,
  "has_annotation": true,
  "annotation_position": "雙行小字"
}
```

---

### 7. Seal（钤印）
**描述**: 页面上的印章/钤印

**属性**:
- `seal_id` (string, 必需, 唯一): 钤印唯一标识符
- `seal_text` (string): 印章文字
- `seal_type` (string): 印章类型（藏书印、鉴赏印、校勘印等）
- `owner` (string): 印章所有者（收藏家/机构）
- `shape` (string): 形状（方形、圆形、椭圆等）
- `color` (string): 颜色（朱文、白文）
- `position` (string): 位置描述
- `image_embedding` (vector): 印章图像的向量表示

**索引**:
- PRIMARY KEY: `seal_id`
- INDEX: `seal_text`, `owner`, `seal_type`

**示例**:
```json
{
  "seal_id": "seal_001",
  "seal_text": "天祿琳琅",
  "seal_type": "藏書印",
  "owner": "清內府",
  "shape": "方形",
  "color": "朱文",
  "position": "卷首"
}
```

---

### 8. Entity（实体词条）
**描述**: 从文本中提取的命名实体（人名、地名、官职等）

**属性**:
- `entity_id` (string, 必需, 唯一): 实体唯一标识符
- `entity_text` (string, 必需): 实体文本
- `entity_type` (string, 必需): 实体类型（PERSON/LOCATION/ORGANIZATION/TITLE/EVENT）
- `normalized_name` (string): 规范化名称
- `description` (text): 实体描述
- `aliases` (list[string]): 别名列表
- `birth_year` (string): 出生年份（人物）
- `death_year` (string): 去世年份（人物）
- `dynasty` (string): 所属朝代

**索引**:
- PRIMARY KEY: `entity_id`
- INDEX: `entity_text`, `entity_type`, `normalized_name`
- FULLTEXT INDEX: `entity_text`, `description`

**示例**:
```json
{
  "entity_id": "ent_person_001",
  "entity_text": "司馬遷",
  "entity_type": "PERSON",
  "normalized_name": "司馬遷",
  "description": "西漢史學家，《史記》作者",
  "aliases": ["太史公", "子長"],
  "birth_year": "前145",
  "death_year": "前86",
  "dynasty": "漢"
}
```

---

## 核心关系（边类型）

### 1. HAS_VOLUME
**描述**: 文献包含卷次

**起点**: Document
**终点**: Volume
**方向**: 单向（Document → Volume）

**属性**:
- `sequence` (integer): 卷次顺序
- `created_at` (datetime): 创建时间

**约束**:
- 一个 Document 可以有多个 Volume
- 一个 Volume 只属于一个 Document

**Cypher 示例**:
```cypher
(d:Document)-[:HAS_VOLUME {sequence: 1}]->(v:Volume)
```

---

### 2. HAS_PAGE
**描述**: 卷次包含页面

**起点**: Volume
**终点**: Page
**方向**: 单向（Volume → Page）

**属性**:
- `sequence` (integer): 页面顺序
- `created_at` (datetime): 创建时间

**约束**:
- 一个 Volume 可以有多个 Page
- 一个 Page 只属于一个 Volume

**Cypher 示例**:
```cypher
(v:Volume)-[:HAS_PAGE {sequence: 1}]->(p:Page)
```

---

### 3. SIMILAR_TO
**描述**: 页面之间的相似关系（基于向量相似度）

**起点**: Page
**终点**: Page
**方向**: 双向（Page ↔ Page）

**属性**:
- `similarity_score` (float, 必需): 相似度分数（0-1）
- `similarity_type` (string): 相似类型（visual/layout/content）
- `computed_at` (datetime): 计算时间

**约束**:
- 相似度阈值 >= 0.8 才创建关系
- 每个 Page 最多保留 Top-10 相似页面

**Cypher 示例**:
```cypher
(p1:Page)-[:SIMILAR_TO {similarity_score: 0.92, similarity_type: "visual"}]->(p2:Page)
```

---

### 4. BELONGS_TO_EDITION
**描述**: 页面属于某个版本

**起点**: Page
**终点**: Edition
**方向**: 单向（Page → Edition）

**属性**:
- `confidence` (float): 版本判定置信度
- `identified_by` (string): 判定方式（manual/auto）
- `created_at` (datetime): 创建时间

**约束**:
- 一个 Page 可以属于一个或多个 Edition（存在多版本混合情况）
- 一个 Edition 可以包含多个 Page

**Cypher 示例**:
```cypher
(p:Page)-[:BELONGS_TO_EDITION {confidence: 0.95, identified_by: "auto"}]->(e:Edition)
```

---

### 5. STORED_IN
**描述**: 文献存储在某个馆藏

**起点**: Document
**终点**: Collection
**方向**: 单向（Document → Collection）

**属性**:
- `completeness` (string): 完整性（完整、残缺、仅存部分卷）
- `created_at` (datetime): 创建时间

**约束**:
- 一个 Document 可以存储在多个 Collection（多馆藏）
- 一个 Collection 可以包含多个 Document

**Cypher 示例**:
```cypher
(d:Document)-[:STORED_IN {completeness: "完整"}]->(c:Collection)
```

---

### 6. HAS_LAYOUT
**描述**: 页面具有某种版式

**起点**: Page
**终点**: Layout
**方向**: 单向（Page → Layout）

**属性**:
- `created_at` (datetime): 创建时间

**约束**:
- 一个 Page 对应一个 Layout
- 多个 Page 可以共享同一个 Layout（版式相同）

**Cypher 示例**:
```cypher
(p:Page)-[:HAS_LAYOUT]->(l:Layout)
```

---

### 7. HAS_SEAL
**描述**: 页面包含钤印

**起点**: Page
**终点**: Seal
**方向**: 单向（Page → Seal）

**属性**:
- `position_x` (integer): 印章 X 坐标
- `position_y` (integer): 印章 Y 坐标
- `confidence` (float): 识别置信度
- `created_at` (datetime): 创建时间

**约束**:
- 一个 Page 可以有多个 Seal
- 一个 Seal 可以出现在多个 Page（同一印章多次使用）

**Cypher 示例**:
```cypher
(p:Page)-[:HAS_SEAL {position_x: 100, position_y: 200, confidence: 0.88}]->(s:Seal)
```

---

### 8. MENTIONS
**描述**: 页面提及某个实体

**起点**: Page
**终点**: Entity
**方向**: 单向（Page → Entity）

**属性**:
- `mention_count` (integer): 提及次数
- `positions` (list[integer]): 提及位置（字符偏移）
- `context` (text): 上下文片段
- `created_at` (datetime): 创建时间

**约束**:
- 一个 Page 可以提及多个 Entity
- 一个 Entity 可以被多个 Page 提及

**Cypher 示例**:
```cypher
(p:Page)-[:MENTIONS {mention_count: 3, context: "黃帝者..."}]->(e:Entity)
```

---

### 9. RELATED_TO
**描述**: 实体之间的关联关系

**起点**: Entity
**终点**: Entity
**方向**: 双向（Entity ↔ Entity）

**属性**:
- `relation_type` (string): 关系类型（师生、父子、同僚、敌对等）
- `description` (text): 关系描述
- `source` (string): 关系来源（文献引用）
- `confidence` (float): 置信度
- `created_at` (datetime): 创建时间

**约束**:
- 实体之间可以有多种关系类型

**Cypher 示例**:
```cypher
(e1:Entity)-[:RELATED_TO {relation_type: "師生", description: "司馬遷師從孔安國"}]->(e2:Entity)
```

---

### 10. CITES
**描述**: 页面引用另一页面（交叉引用）

**起点**: Page
**终点**: Page
**方向**: 单向（Page → Page）

**属性**:
- `citation_type` (string): 引用类型（直接引用、参见、对比等）
- `citation_text` (text): 引用文本
- `created_at` (datetime): 创建时间

**约束**:
- 用于构建文献内部的引用网络

**Cypher 示例**:
```cypher
(p1:Page)-[:CITES {citation_type: "參見", citation_text: "詳見卷三"}]->(p2:Page)
```

---

## 图谱约束和索引

### 唯一性约束
```cypher
CREATE CONSTRAINT doc_id_unique IF NOT EXISTS FOR (d:Document) REQUIRE d.doc_id IS UNIQUE;
CREATE CONSTRAINT volume_id_unique IF NOT EXISTS FOR (v:Volume) REQUIRE v.volume_id IS UNIQUE;
CREATE CONSTRAINT page_id_unique IF NOT EXISTS FOR (p:Page) REQUIRE p.page_id IS UNIQUE;
CREATE CONSTRAINT edition_id_unique IF NOT EXISTS FOR (e:Edition) REQUIRE e.edition_id IS UNIQUE;
CREATE CONSTRAINT collection_id_unique IF NOT EXISTS FOR (c:Collection) REQUIRE c.collection_id IS UNIQUE;
CREATE CONSTRAINT layout_id_unique IF NOT EXISTS FOR (l:Layout) REQUIRE l.layout_id IS UNIQUE;
CREATE CONSTRAINT seal_id_unique IF NOT EXISTS FOR (s:Seal) REQUIRE s.seal_id IS UNIQUE;
CREATE CONSTRAINT entity_id_unique IF NOT EXISTS FOR (e:Entity) REQUIRE e.entity_id IS UNIQUE;
```

### 属性索引
```cypher
CREATE INDEX doc_title_idx IF NOT EXISTS FOR (d:Document) ON (d.title);
CREATE INDEX doc_author_idx IF NOT EXISTS FOR (d:Document) ON (d.author);
CREATE INDEX doc_dynasty_idx IF NOT EXISTS FOR (d:Document) ON (d.dynasty);
CREATE INDEX page_number_idx IF NOT EXISTS FOR (p:Page) ON (p.page_number);
CREATE INDEX page_hash_idx IF NOT EXISTS FOR (p:Page) ON (p.image_hash);
CREATE INDEX entity_type_idx IF NOT EXISTS FOR (e:Entity) ON (e.entity_type);
CREATE INDEX entity_text_idx IF NOT EXISTS FOR (e:Entity) ON (e.entity_text);
CREATE INDEX layout_column_idx IF NOT EXISTS FOR (l:Layout) ON (l.column_count);
```

### 全文索引
```cypher
CREATE FULLTEXT INDEX page_ocr_text_idx IF NOT EXISTS FOR (p:Page) ON EACH [p.ocr_text];
CREATE FULLTEXT INDEX entity_description_idx IF NOT EXISTS FOR (e:Entity) ON EACH [e.entity_text, e.description];
```

---

## 图谱统计信息

### 预期规模
- **Document**: ~100-1000 个文献
- **Volume**: ~1000-10000 个卷次
- **Page**: ~10000-100000 个页面
- **Edition**: ~100-500 个版本
- **Collection**: ~10-50 个馆藏机构
- **Layout**: ~50-200 种版式
- **Seal**: ~500-2000 个钤印
- **Entity**: ~5000-50000 个实体

### 关系密度
- **HAS_VOLUME**: 1:N（平均 10 卷/文献）
- **HAS_PAGE**: 1:N（平均 20 页/卷）
- **SIMILAR_TO**: N:N（每页 Top-10 相似）
- **MENTIONS**: N:N（每页 5-20 个实体）
- **HAS_SEAL**: N:N（每页 0-5 个印章）

---

## 版本历史

- **v1.0** (2026-03-04): 初始 Schema 设计
