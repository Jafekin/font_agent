
# TODO - 古文字识别分析智能体开发清单

> **项目阶段**：从 Naive RAG Baseline 向 Agentic GraphRAG 演进
> **更新时间**：2026-03-04
> **核心目标**：构建可规划、可追溯、可增量学习的古文字研究智能体

---

## 📊 当前进度概览

| 模块 | 完成度 | 状态 |
|------|--------|------|
| 基础设施（Django + API） | 100% | ✅ 已完成 |
| Naive RAG Pipeline | 100% | ✅ 已完成 |
| OCR/版式识别 | 100% | ✅ 已完成 |
| GraphRAG 图谱层 | 0% | 🔴 未开始 |
| Agentic 编排层 | 0% | 🔴 未开始 |
| 工程化优化 | 20% | 🟡 进行中 |

---

## ✅ 已完成功能（v1.0 Baseline）

### 核心能力
- [x] **Web 上传与分析入口**（`app/views.py`）
  上传图片触发分析，返回结构化 Markdown/JSON 报告

- [x] **分析历史留存**（`app/models.py`）
  自动记录分析结果，支持复盘与版本对比

- [x] **Naive RAG Pipeline**（`rag/pipeline.py`）
  Chinese-CLIP 嵌入 → NumPy 检索 → 结构化 Prompt → LLM 生成，默认带引用输出

- [x] **索引构建脚本**（`scripts/build_index.py`）
  批量生成 `embeddings.npy` / `metadata.json` / `ids.json` 索引文件

- [x] **OCR/版式识别模块**（`ocr/paddle_pipeline.py`）
  基于 PaddleOCR 的布局分析，输出列数、白口/黑口、边框、行高等版式指标

- [x] **RESTful API**（`app/urls.py`）
  提供 `/api/analyze`、`/api/analyze-base64`、`/api/history` 接口

---

## 🎯 待完成任务（v2.0 Agentic GraphRAG）

### 优先级说明
- 🔴 **P0 - 核心阻塞**：必须完成才能进入下一阶段
- 🟠 **P1 - 重要功能**：显著提升系统能力
- 🟡 **P2 - 优化增强**：改善用户体验或性能
- 🟢 **P3 - 可选扩展**：锦上添花的功能

---

## 📐 Phase 1: 图谱基础设施（GraphRAG 数据层）

### 🔴 P0 - 图存储选型与落地
**任务**：确定图数据库方案并实现基础 CRUD
**技术选项**：
- 轻量方案：SQLite + 自定义关系表 / NetworkX（适合原型验证）
- 生产方案：Neo4j / ArangoDB（适合复杂查询）
- 云原生：DuckDB + MotherDuck（适合分析场景）

**交付物**：
- [x] 完成技术选型文档（对比性能、查询能力、部署成本）
- [x] 实现图存储抽象层 `rag/graph/storage.py`（统一接口）
- [x] 编写单元测试覆盖节点/边的增删改查

**依赖**：无
**预估工作量**：3-5 天
**文件位置**：`rag/graph/storage.py`、`rag/graph/models.py`

---

### 🔴 P0 - 图谱构建器（Schema 设计 + ETL）
**任务**：将现有 `metadata.json` + 版式特征转换为知识图谱
**节点类型**：
- 文献（Document）：题名、作者、朝代、分类
- 卷次（Volume）：卷号、页数范围
- 页面（Page）：图片路径、OCR 文本、版式特征
- 版本（Edition）：刻本类型、出版者、年代
- 馆藏（Collection）：机构、编号、钤印
- 版式（Layout）：列数、行数、白口/黑口、边框类型

**关系类型**：
- HAS_VOLUME（文献→卷次）
- HAS_PAGE（卷次→页面）
- SIMILAR_TO（页面↔页面，带相似度权重）
- BELONGS_TO_EDITION（页面→版本）
- STORED_IN（文献→馆藏）
- CITES（页面→页面，引用关系）

**交付物**：
- [ ] 设计图谱 Schema 文档（Mermaid ER 图）
- [ ] 实现 ETL 脚本 `scripts/build_graph.py`（从现有索引构建图谱）
- [ ] 支持增量更新（检测新增/修改的 metadata）
- [ ] 可视化验证工具（导出 Cypher/GraphML 供 Neo4j Browser 查看）

**依赖**：图存储选型完成
**预估工作量**：5-7 天
**文件位置**：`scripts/build_graph.py`、`rag/graph/schema.py`

---

### 🟠 P1 - GraphRAG 检索器
**任务**：实现基于图遍历的检索能力
**核心功能**：
- 关系路径检索（如：查询某文献的所有版本及其馆藏）
- 属性过滤（如：筛选宋刻本 + 白口 + 双边框的页面）
- 可解释证据路径（返回检索路径的节点序列与关系类型）
- 多跳推理（如：通过相似页面找到同版本的其他卷次）

**交付物**：
- [ ] 实现 `rag/graph/retriever.py`（封装 Cypher/Gremlin 查询）
- [ ] 支持自然语言查询转图查询（简单规则或 LLM 辅助）
- [ ] 返回结构化证据链（JSON 格式，包含节点 ID、关系类型、置信度）
- [ ] 性能基准测试（对比纯向量检索的召回率与精度）

**依赖**：图谱构建器完成
**预估工作量**：4-6 天
**文件位置**：`rag/graph/retriever.py`

---

## 🔄 Phase 2: 混合检索与一致性保障

### 🟠 P1 - Hybrid 检索内核
**任务**：融合向量检索与图检索，实现互补增强
**策略选项**：
- 串行模式：先图检索缩小候选集 → 再向量检索排序
- 并行模式：两路检索独立执行 → 结果混排（RRF/加权融合）
- 级联模式：向量检索 Top-K → 图扩展相关节点 → 重排序

**交付物**：
- [ ] 实现 `rag/hybrid_retriever.py`（支持多种融合策略）
- [ ] 可配置权重参数（向量 vs 图的比重）
- [ ] 支持动态过滤条件（如：仅检索特定朝代/版本）
- [ ] A/B 测试框架（对比不同策略的效果）

**依赖**：GraphRAG 检索器完成
**预估工作量**：3-5 天
**文件位置**：`rag/hybrid_retriever.py`

---

### 🟠 P1 - 引用一致性校验
**任务**：验证 LLM 生成的引用是否真实存在于知识库
**校验维度**：
- 存在性检查：引用的文献/页面 ID 是否在图谱中
- 内容一致性：引用的文本片段是否与原文匹配（模糊匹配）
- 关系合理性：引用的版本/馆藏关系是否正确

**失败处理**：
- 触发补检索（扩大搜索范围或调整查询策略）
- 降级提示（标注"引用未验证"或移除不可靠引用）
- 记录日志供人工审核

**交付物**：
- [ ] 实现 `rag/citation_validator.py`
- [ ] 集成到 `rag/pipeline.py` 的后处理阶段
- [ ] 输出校验报告（通过率、失败原因统计）

**依赖**：GraphRAG 检索器完成
**预估工作量**：2-3 天
**文件位置**：`rag/citation_validator.py`

---

### 🟡 P2 - 结果缓存与 Citation Trace
**任务**：优化重复查询性能，提供可视化证据链
**缓存策略**：
- 基于查询指纹（图片哈希 + 参数）的 Redis/SQLite 缓存
- TTL 设置（如 24 小时）与手动失效机制

**可视化功能**：
- 生成证据链路图（Mermaid/D3.js）
- 导出为 JSON/HTML 供专家审核
- 高亮关键节点与关系

**交付物**：
- [ ] 实现缓存层 `rag/cache.py`
- [ ] 实现证据链可视化 `rag/trace_visualizer.py`
- [ ] 在 Django Admin 中添加查看入口

**依赖**：引用一致性校验完成
**预估工作量**：2-4 天
**文件位置**：`rag/cache.py`、`rag/trace_visualizer.py`

---

## 🤖 Phase 3: Agentic 编排层

### 🔴 P0 - Agentic Orchestrator（核心调度器）
**任务**：实现智能体的规划、执行、反思循环
**架构参考**：ReAct / ReWOO / Graph Planner
**核心能力**：
- 任务分解（将复杂查询拆解为子任务）
- 工具调度（动态选择 OCR/图检索/向量检索/LLM）
- 自校验与回退（检测矛盾或低置信度结果，触发重试）
- 多轮对话（支持用户追问与上下文保持）

**交付物**：
- [ ] 实现 `rag/agent/orchestrator.py`（主控逻辑）
- [ ] 定义工具接口规范 `rag/agent/tools.py`
- [ ] 实现简单规划器（基于规则或 LLM Prompt）
- [ ] 集成到 `app/views.py`（替换现有 `rag/pipeline.py`）

**依赖**：Hybrid 检索内核完成
**预估工作量**：7-10 天
**文件位置**：`rag/agent/orchestrator.py`、`rag/agent/planner.py`

---

### 🟠 P1 - Skills 模块化封装
**任务**：将现有功能封装为可调度的工具（Skills）
**工具清单**：
- `OCRSkill`：调用 `ocr/paddle_pipeline.py`
- `LayoutAnalysisSkill`：提取版式特征
- `VectorSearchSkill`：调用 `rag/retriever.py`
- `GraphSearchSkill`：调用 `rag/graph/retriever.py`
- `RerankSkill`：对检索结果重排序
- `CitationValidateSkill`：调用引用校验器
- `ReportGenerateSkill`：调用 LLM 生成最终报告

**交付物**：
- [ ] 实现统一工具基类 `rag/agent/base_skill.py`
- [ ] 封装上述 7 个 Skill 类
- [ ] 编写工具注册表与自动发现机制
- [ ] 单元测试覆盖每个 Skill

**依赖**：Agentic Orchestrator 完成
**预估工作量**：4-6 天
**文件位置**：`rag/agent/skills/`

---

### 🟡 P2 - 可观测性（Tracing & Logging）
**任务**：记录智能体的决策过程，支持调试与优化
**记录内容**：
- 每轮工具调用（输入参数、输出结果、耗时）
- 检索参数（Top-K、过滤条件、融合权重）
- 证据路径（图遍历的节点序列）
- 置信度指标（每个结论的可信度评分）

**可视化**：
- 生成执行时间线（Gantt 图）
- 导出为 OpenTelemetry 格式（集成 Jaeger/Zipkin）

**交付物**：
- [ ] 实现 `rag/agent/tracer.py`
- [ ] 集成到 Orchestrator 的每个决策点
- [ ] 在 Django Admin 中添加查看入口
- [ ] 支持导出为 JSON/CSV

**依赖**：Skills 封装完成
**预估工作量**：3-4 天
**文件位置**：`rag/agent/tracer.py`

---

## 📤 Phase 4: 输出标准化与互操作性

### 🟡 P2 - JSON-LD 标注
**任务**：将分析结果转换为语义网标准格式
**Schema 参考**：Schema.org（Book、CreativeWork、ArchiveComponent）
**核心字段**：
- `@context`：定义命名空间
- `@type`：实体类型（如 Book、Manuscript）
- `identifier`：唯一标识符（馆藏编号）
- `author`、`datePublished`、`publisher` 等元数据
- `hasPart`：关联卷次与页面
- `isRelatedTo`：关联相似版本

**交付物**：
- [ ] 实现 `rag/output/jsonld_exporter.py`
- [ ] 定义本项目的 JSON-LD 模板
- [ ] 支持导出为 RDF/Turtle 格式
- [ ] 验证工具（检查 JSON-LD 合法性）

**依赖**：无（可独立开发）
**预估工作量**：2-3 天
**文件位置**：`rag/output/jsonld_exporter.py`

---

### 🟡 P2 - 输出模板收敛
**任务**：统一 Markdown/JSON 输出格式，便于评测与前端展示
**标准化内容**：
- 字段命名规范（驼峰 vs 下划线）
- 引用格式（统一为 `[文献ID:页码]` 或脚注形式）
- 置信度表示（0-1 浮点数 vs 百分比）
- 错误码与异常信息

**交付物**：
- [ ] 定义输出 Schema（JSON Schema 文件）
- [ ] 重构 `rag/prompt.py` 的模板
- [ ] 实现格式验证器 `rag/output/validator.py`
- [ ] 更新 API 文档

**依赖**：无（可独立开发）
**预估工作量**：2-3 天
**文件位置**：`rag/output/schema.json`、`rag/prompt.py`

---

## ⚙️ Phase 5: 工程化优化

### 🟠 P1 - 索引增量更新
**任务**：避免每次全量重建索引，支持增量更新
**实现方案**：
- 文件监听（watchdog）：检测 `media/uploads` 的新增/修改
- 差异计算：对比现有 `metadata.json` 与文件系统
- 增量嵌入：仅对新增/修改的图片生成向量
- 索引合并：更新 `embeddings.npy` 与 `ids.json`

**交付物**：
- [ ] 重构 `scripts/build_index.py` 支持 `--incremental` 参数
- [ ] 实现文件变更检测逻辑
- [ ] 支持 CI/CD 集成（GitHub Actions 自动触发）
- [ ] 性能测试（对比全量 vs 增量的耗时）

**依赖**：无（可独立开发）
**预估工作量**：3-4 天
**文件位置**：`scripts/build_index.py`

---

### 🟡 P2 - Celery 异步流水线
**任务**：将耗时任务异步化，提升 Web 响应速度
**异步任务**：
- 批量图片识别（OCR + 版式分析）
- 索引构建（嵌入生成）
- 图谱计算（相似度矩阵、社区发现）

**技术栈**：Celery + Redis/RabbitMQ
**交付物**：
- [ ] 配置 Celery（`config/celery.py`）
- [ ] 封装异步任务 `app/tasks.py`
- [ ] 修改 `app/views.py` 返回任务 ID
- [ ] 实现任务状态查询接口 `/api/task/<task_id>`
- [ ] 添加任务监控面板（Flower）

**依赖**：无（可独立开发）
**预估工作量**：4-5 天
**文件位置**：`config/celery.py`、`app/tasks.py`

---

### 🟢 P3 - 多语言界面与 API 翻译
**任务**：支持中英文切换，扩大用户群体
**国际化方案**：Django i18n + 前端 i18next
**翻译内容**：
- 前端界面文案
- API 错误信息
- 分析报告模板（可选：调用翻译 API）

**交付物**：
- [ ] 配置 Django i18n（`config/settings.py`）
- [ ] 提取翻译字符串（`django-admin makemessages`）
- [ ] 翻译 `.po` 文件（中文/英文）
- [ ] 前端添加语言切换按钮
- [ ] 测试多语言环境

**依赖**：无（可独立开发）
**预估工作量**：3-4 天
**文件位置**：`locale/`、`app/templates/`

---

## 🚀 实施建议

### 推荐开发顺序（按依赖关系）
1. **Phase 1（图谱基础）** → 2. **Phase 2（混合检索）** → 3. **Phase 3（Agentic 编排）**
4. **Phase 4 & 5（并行开发）**：输出标准化与工程化优化可同步进行

### 里程碑划分
- **M1（图谱验证）**：完成 Phase 1，验证图谱构建与基础检索（预计 2-3 周）
- **M2（混合检索）**：完成 Phase 2，对比 Hybrid 检索效果（预计 1-2 周）
- **M3（智能体原型）**：完成 Phase 3 核心功能，实现端到端 Agentic 流程（预计 3-4 周）
- **M4（生产就绪）**：完成 Phase 4 & 5，优化性能与用户体验（预计 2-3 周）

### 风险与应对
| 风险 | 影响 | 应对措施 |
|------|------|----------|
| 图数据库性能不足 | 查询延迟高 | 提前做性能基准测试，必要时降级为 SQLite |
| LLM 幻觉导致引用错误 | 结果可信度低 | 强化引用校验，增加人工审核环节 |
| 异步任务队列故障 | 任务丢失 | 使用持久化消息队列（RabbitMQ），添加重试机制 |
| 多语言翻译质量差 | 用户体验差 | 优先保证中文质量，英文可先用机器翻译 + 人工校对 |

---

## 📝 附录

### 相关文档
- 系统架构：`doc/architecture_flows.md`
- API 文档：`README.md` § API 速览
- 数据格式：`rag/index/metadata.json`（示例）

### 技术栈参考
- 图数据库：[Neo4j](https://neo4j.com/) / [NetworkX](https://networkx.org/)
- 智能体框架：[LangGraph](https://github.com/langchain-ai/langgraph) / [AutoGen](https://github.com/microsoft/autogen)
- 异步任务：[Celery](https://docs.celeryq.dev/)
- 可观测性：[OpenTelemetry](https://opentelemetry.io/)

### 贡献指南
欢迎通过 Issue/PR 认领任务或提出改进建议。开发前请：
1. 在 Issue 中声明认领任务
2. 创建功能分支（如 `feature/graph-storage`）
3. 提交 PR 前确保通过单元测试与代码规范检查

