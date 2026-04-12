<!--
 * @Author        Jiahui Chen 1946847867@qq.com
 * @Date          2026-04-08 20:55:12
 * @LastEditTime  2026-04-09 20:40:34
 * @Description   
 * 
-->
# 开发进度

## 已完成

- [x] 第 1 周：开题准备与需求分析（输入输出定义、验收指标、数据来源）
- [x] 第 2 周：数据与元数据规范化（PageData schema、extended_metadata 字段规范）
- [x] 第 3 周：图谱建模设计（Document/Edition/Collection/Page/Layout/Entity schema）
- [x] 第 4 周：GraphRAG 索引构建（`rag/graph/builder.py`，Neo4j 节点/边入库）
- [x] 第 5 周：GraphRAG 查询接口（`rag/graph/retriever.py`，相似检索、版本推断、实体查询）
- [x] 第 6 周：向量检索模块（`rag/naive/`，Chinese-CLIP + NumPy 索引，统一 PageData schema）

## 进行中

- [ ] 第 7 周：混合检索策略（图约束候选集 + 向量排序融合）
- [ ] 第 8 周：结构化 Prompt 与报告模板优化（置信度字段、引用清单格式规范）
- [ ] 第 9 周：引用一致性校验（生成引用与图谱节点 ID 的存在性核验）
- [ ] 第 10 周：回退/补检索机制（证据不足时追加检索与降级策略）

## 待开始

- [ ] 第 11 周：Agentic 架构设计（OCR/图检索/向量检索/报告汇总封装为 skills）
- [ ] 第 12 周：智能体执行流程（端到端闭环，接入 Web/API 演示入口）
- [ ] 第 13 周：可观测性与日志（工具调用日志、中间结果导出）
- [ ] 第 14 周：评测数据集（检索命中率、引用通过率、端到端成功率）
- [ ] 第 15 周：对比实验（NaiveRAG vs GraphRAG vs 混合检索，有无引用校验）
- [ ] 第 16 周：系统优化与工程收敛（异常处理、配置管理、可复现脚本）
- [ ] 第 17 周：论文撰写（方法、实验与案例分析、相关工作、图表）
- [ ] 第 18 周：论文定稿与答辩准备

