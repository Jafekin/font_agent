# 典型查询用例

本文档定义了古籍知识图谱的典型查询场景和 Cypher 查询语句。

---

## 1. 基础查询

### 1.1 查询文献的所有卷次

**场景**: 获取某部文献的完整卷次列表

**Cypher**:
```cypher
MATCH (d:Document {doc_id: 'doc_shiji'})-[:HAS_VOLUME]->(v:Volume)
RETURN v.volume_number, v.volume_title, v.page_count
ORDER BY v.volume_number
```

**返回示例**:
```json
[
  {"volume_number": 1, "volume_title": "五帝本紀第一", "page_count": 42},
  {"volume_number": 2, "volume_title": "夏本紀第二", "page_count": 38}
]
```

---

### 1.2 查询卷次的所有页面

**场景**: 获取某卷的所有页面信息

**Cypher**:
```cypher
MATCH (v:Volume {volume_id: 'vol_shiji_001'})-[:HAS_PAGE]->(p:Page)
RETURN p.page_id, p.page_number, p.image_path, p.ocr_confidence
ORDER BY p.page_number
```

---

### 1.3 全文搜索

**场景**: 在所有页面中搜索包含特定关键词的内容

**Cypher**:
```cypher
CALL db.index.fulltext.queryNodes('page_ocr_text_idx', '黃帝')
YIELD node, score
RETURN node.page_id, node.ocr_text, score
ORDER BY score DESC
LIMIT 10
```

---

## 2. 版本与版式查询

### 2.1 查询特定版本的所有页面

**场景**: 找出所有属于宋刻本的页面

**Cypher**:
```cypher
MATCH (p:Page)-[:BELONGS_TO_EDITION]->(e:Edition {edition_type: '刻本', edition_name: '宋刻本'})
RETURN p.page_id, p.image_path, p.page_number
ORDER BY p.page_number
```

---

### 2.2 查询特定版式的页面

**场景**: 找出所有双栏黑口的页面

**Cypher**:
```cypher
MATCH (p:Page)-[:HAS_LAYOUT]->(l:Layout)
WHERE l.column_count = 2 AND l.border_color = '黑口'
RETURN p.page_id, p.image_path, l.border_type, l.has_fish_tail
LIMIT 20
```

---

### 2.3 版式聚类分析

**场景**: 统计不同版式的页面数量

**Cypher**:
```cypher
MATCH (p:Page)-[:HAS_LAYOUT]->(l:Layout)
RETURN
  l.column_count,
  l.border_type,
  l.border_color,
  count(p) AS page_count
ORDER BY page_count DESC
```

---

## 3. 相似页面检索

### 3.1 查询相似页面

**场景**: 找出与某页面最相似的其他页面

**Cypher**:
```cypher
MATCH (p1:Page {page_id: 'page_shiji_001_001'})-[r:SIMILAR_TO]->(p2:Page)
RETURN p2.page_id, p2.image_path, r.similarity_score, r.similarity_type
ORDER BY r.similarity_score DESC
LIMIT 10
```

---

### 3.2 通过相似页面推断版本

**场景**: 基于相似页面的版本信息推断未知页面的版本

**Cypher**:
```cypher
MATCH (p1:Page {page_id: 'page_unknown_001'})-[r:SIMILAR_TO]->(p2:Page)-[:BELONGS_TO_EDITION]->(e:Edition)
WHERE r.similarity_score > 0.85
RETURN
  e.edition_id,
  e.edition_name,
  count(p2) AS similar_page_count,
  avg(r.similarity_score) AS avg_similarity
ORDER BY similar_page_count DESC, avg_similarity DESC
LIMIT 5
```

**证据路径**:
```
未知页面 --[SIMILAR_TO(0.92)]--> 相似页面1 --[BELONGS_TO_EDITION]--> 宋刻本
未知页面 --[SIMILAR_TO(0.89)]--> 相似页面2 --[BELONGS_TO_EDITION]--> 宋刻本
未知页面 --[SIMILAR_TO(0.87)]--> 相似页面3 --[BELONGS_TO_EDITION]--> 宋刻本
=> 推断: 未知页面可能属于宋刻本（置信度: 0.89）
```

---

## 4. 钤印与馆藏查询

### 4.1 查询包含特定钤印的页面

**场景**: 找出所有包含"天祿琳琅"印的页面

**Cypher**:
```cypher
MATCH (p:Page)-[:HAS_SEAL]->(s:Seal {seal_text: '天祿琳琅'})
RETURN p.page_id, p.image_path, s.seal_type, s.owner
ORDER BY p.page_id
```

---

### 4.2 查询文献的馆藏信息

**场景**: 查询某文献存储在哪些机构

**Cypher**:
```cypher
MATCH (d:Document {doc_id: 'doc_shiji'})-[r:STORED_IN]->(c:Collection)
RETURN
  c.institution,
  c.call_number,
  c.condition,
  r.completeness
```

---

### 4.3 钤印共现分析

**场景**: 找出经常与某印章一起出现的其他印章

**Cypher**:
```cypher
MATCH (p:Page)-[:HAS_SEAL]->(s1:Seal {seal_text: '天祿琳琅'})
MATCH (p)-[:HAS_SEAL]->(s2:Seal)
WHERE s1 <> s2
RETURN
  s2.seal_text,
  s2.owner,
  count(p) AS co_occurrence_count
ORDER BY co_occurrence_count DESC
LIMIT 10
```

---

## 5. 实体关系查询

### 5.1 查询提及特定人物的页面

**场景**: 找出所有提及"司馬遷"的页面

**Cypher**:
```cypher
MATCH (p:Page)-[r:MENTIONS]->(e:Entity {entity_text: '司馬遷', entity_type: 'PERSON'})
RETURN
  p.page_id,
  p.image_path,
  r.mention_count,
  r.context
ORDER BY r.mention_count DESC
```

---

### 5.2 实体共现分析

**场景**: 找出与"司馬遷"经常一起出现的其他人物

**Cypher**:
```cypher
MATCH (p:Page)-[:MENTIONS]->(e1:Entity {entity_text: '司馬遷'})
MATCH (p)-[:MENTIONS]->(e2:Entity)
WHERE e1 <> e2 AND e2.entity_type = 'PERSON'
RETURN
  e2.entity_text,
  e2.description,
  count(p) AS co_occurrence_count
ORDER BY co_occurrence_count DESC
LIMIT 10
```

---

### 5.3 实体关系路径查询

**场景**: 查询两个实体之间的关系路径

**Cypher**:
```cypher
MATCH path = (e1:Entity {entity_text: '司馬遷'})-[:RELATED_TO*1..3]-(e2:Entity {entity_text: '孔安國'})
RETURN path
LIMIT 5
```

---

## 6. 复杂路径查询

### 6.1 文献完整路径

**场景**: 从文献到页面的完整层级路径

**Cypher**:
```cypher
MATCH path = (d:Document {doc_id: 'doc_shiji'})-[:HAS_VOLUME]->(v:Volume)-[:HAS_PAGE]->(p:Page)
WHERE v.volume_number = 1 AND p.page_number = 1
RETURN path
```

**证据路径**:
```
Document(史記) --[HAS_VOLUME]--> Volume(卷1:五帝本紀第一) --[HAS_PAGE]--> Page(第1頁)
```

---

### 6.2 版本推断证据链

**场景**: 构建版本判定的完整证据链

**Cypher**:
```cypher
MATCH (p:Page {page_id: 'page_target_001'})
OPTIONAL MATCH similar_path = (p)-[s:SIMILAR_TO]->(sp:Page)-[:BELONGS_TO_EDITION]->(e:Edition)
WHERE s.similarity_score > 0.85
OPTIONAL MATCH layout_path = (p)-[:HAS_LAYOUT]->(l:Layout)<-[:HAS_LAYOUT]-(lp:Page)-[:BELONGS_TO_EDITION]->(le:Edition)
OPTIONAL MATCH seal_path = (p)-[:HAS_SEAL]->(seal:Seal)<-[:HAS_SEAL]-(seap:Page)-[:BELONGS_TO_EDITION]->(se:Edition)
RETURN
  p.page_id,
  collect(DISTINCT e.edition_name) AS similar_editions,
  collect(DISTINCT le.edition_name) AS layout_editions,
  collect(DISTINCT se.edition_name) AS seal_editions
```

**证据路径示例**:
```
目标页面 --[SIMILAR_TO(0.92)]--> 相似页1 --[BELONGS_TO_EDITION]--> 宋刻本
目标页面 --[HAS_LAYOUT]--> 版式A <--[HAS_LAYOUT]-- 其他页 --[BELONGS_TO_EDITION]--> 宋刻本
目标页面 --[HAS_SEAL]--> 印章X <--[HAS_SEAL]-- 其他页 --[BELONGS_TO_EDITION]--> 宋刻本
=> 综合证据: 宋刻本（置信度: 0.95）
```

---

### 6.3 跨文献引用网络

**场景**: 查询文献之间的引用关系

**Cypher**:
```cypher
MATCH (d1:Document)-[:HAS_VOLUME]->(:Volume)-[:HAS_PAGE]->(p1:Page)
MATCH (p1)-[:CITES]->(p2:Page)<-[:HAS_PAGE]-(:Volume)<-[:HAS_VOLUME]-(d2:Document)
WHERE d1 <> d2
RETURN
  d1.title AS source_doc,
  d2.title AS cited_doc,
  count(p1) AS citation_count
ORDER BY citation_count DESC
```

---

## 7. 聚合统计查询

### 7.1 文献统计

**场景**: 统计每部文献的基本信息

**Cypher**:
```cypher
MATCH (d:Document)
OPTIONAL MATCH (d)-[:HAS_VOLUME]->(v:Volume)
OPTIONAL MATCH (v)-[:HAS_PAGE]->(p:Page)
RETURN
  d.title,
  d.author,
  d.dynasty,
  count(DISTINCT v) AS volume_count,
  count(DISTINCT p) AS page_count
ORDER BY page_count DESC
```

---

### 7.2 版本分布统计

**场景**: 统计不同版本类型的页面数量

**Cypher**:
```cypher
MATCH (p:Page)-[:BELONGS_TO_EDITION]->(e:Edition)
RETURN
  e.edition_type,
  e.edition_name,
  count(p) AS page_count,
  avg(p.ocr_confidence) AS avg_confidence
ORDER BY page_count DESC
```

---

### 7.3 实体类型分布

**场景**: 统计不同类型实体的数量

**Cypher**:
```cypher
MATCH (e:Entity)
RETURN
  e.entity_type,
  count(e) AS entity_count
ORDER BY entity_count DESC
```

---

## 8. 推荐查询

### 8.1 相关页面推荐

**场景**: 基于当前页面推荐相关页面

**Cypher**:
```cypher
MATCH (p:Page {page_id: 'page_current_001'})

// 相似页面
OPTIONAL MATCH (p)-[s:SIMILAR_TO]->(sp:Page)

// 同版本页面
OPTIONAL MATCH (p)-[:BELONGS_TO_EDITION]->(e:Edition)<-[:BELONGS_TO_EDITION]-(ep:Page)

// 提及相同实体的页面
OPTIONAL MATCH (p)-[:MENTIONS]->(entity:Entity)<-[:MENTIONS]-(mp:Page)

WITH p,
     collect(DISTINCT {page: sp, score: s.similarity_score, reason: 'similar'}) AS similar_pages,
     collect(DISTINCT {page: ep, score: 0.8, reason: 'same_edition'}) AS edition_pages,
     collect(DISTINCT {page: mp, score: 0.6, reason: 'shared_entity'}) AS entity_pages

UNWIND (similar_pages + edition_pages + entity_pages) AS recommendation
RETURN
  recommendation.page.page_id,
  recommendation.page.image_path,
  recommendation.score,
  recommendation.reason
ORDER BY recommendation.score DESC
LIMIT 10
```

---

### 8.2 相关文献推荐

**场景**: 基于当前文献推荐相关文献

**Cypher**:
```cypher
MATCH (d:Document {doc_id: 'doc_current_001'})

// 同作者文献
OPTIONAL MATCH (d2:Document)
WHERE d2.author = d.author AND d2 <> d

// 同朝代同类别文献
OPTIONAL MATCH (d3:Document)
WHERE d3.dynasty = d.dynasty AND d3.category = d.category AND d3 <> d

// 引用关系文献
OPTIONAL MATCH (d)-[:HAS_VOLUME]->(:Volume)-[:HAS_PAGE]->(:Page)-[:CITES]->(:Page)<-[:HAS_PAGE]-(:Volume)<-[:HAS_VOLUME]-(d4:Document)

RETURN
  DISTINCT d2.doc_id AS doc_id,
  d2.title,
  d2.author,
  'same_author' AS reason
UNION
RETURN
  DISTINCT d3.doc_id AS doc_id,
  d3.title,
  d3.author,
  'same_category' AS reason
UNION
RETURN
  DISTINCT d4.doc_id AS doc_id,
  d4.title,
  d4.author,
  'citation' AS reason
LIMIT 10
```

---

## 9. 性能优化查询

### 9.1 使用索引的查询

**场景**: 利用索引加速查询

**Cypher**:
```cypher
// 使用属性索引
MATCH (d:Document)
WHERE d.dynasty = '宋' AND d.category = '史部'
RETURN d.title, d.author

// 使用全文索引
CALL db.index.fulltext.queryNodes('page_ocr_text_idx', '黃帝 AND 軒轅')
YIELD node, score
RETURN node.page_id, score
LIMIT 10
```

---

### 9.2 分页查询

**场景**: 大结果集分页

**Cypher**:
```cypher
MATCH (p:Page)
RETURN p.page_id, p.image_path, p.page_number
ORDER BY p.page_number
SKIP 100
LIMIT 20
```

---

## 10. 图谱维护查询

### 10.1 查找孤立节点

**场景**: 找出没有任何关系的节点

**Cypher**:
```cypher
MATCH (n)
WHERE NOT (n)--()
RETURN labels(n) AS node_type, count(n) AS count
```

---

### 10.2 查找重复节点

**场景**: 检测可能重复的页面（基于哈希）

**Cypher**:
```cypher
MATCH (p:Page)
WHERE p.image_hash IS NOT NULL
WITH p.image_hash, collect(p) AS pages
WHERE size(pages) > 1
RETURN p.image_hash, [page IN pages | page.page_id] AS duplicate_pages
```

---

### 10.3 删除低质量关系

**场景**: 删除相似度过低的 SIMILAR_TO 关系

**Cypher**:
```cypher
MATCH ()-[r:SIMILAR_TO]->()
WHERE r.similarity_score < 0.7
DELETE r
```

---

## 查询性能建议

1. **使用索引**: 确保在常用查询字段上创建索引
2. **限制结果集**: 使用 LIMIT 限制返回数量
3. **避免笛卡尔积**: 使用 OPTIONAL MATCH 而非多个 MATCH
4. **使用 PROFILE**: 分析查询性能
   ```cypher
   PROFILE MATCH (d:Document) RETURN d LIMIT 10
   ```
5. **批量操作**: 使用 UNWIND 进行批量插入
   ```cypher
   UNWIND $batch AS item
   CREATE (p:Page {page_id: item.page_id, ...})
   ```

---

**版本**: v1.0 (2026-03-04)
