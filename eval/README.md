# GraphRAG 评估系统
> 完整的 RAG 评估工具集，支持检索质量评估、GraphRAG 特有能力测试、自动化测试数据生成和结果可视化。

[![Status](https://img.shields.io/badge/status-stable-green.svg)](.)
[![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)](.)
[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](.)

---

## 📋 目录

- [快速开始](#-快速开始)
- [评估指标](#-评估指标)
- [工具说明](#️-工具说明)
- [使用场景](#-使用场景)
- [性能基准](#-性能基准)
- [配置说明](#-配置说明)
- [常见问题](#-常见问题)
- [文件结构](#-文件结构)

---

## ⚡ 快速开始

### 30 秒快速体验

```bash
# 一键运行，无需准备
python eval/scripts/quick_evaluation_demo.py
```
### 3 分钟完整流程

```bash
# 1. 生成测试数据
python eval/scripts/generate_graphrag_test_data.py --output tests/test.json

# 2. 运行评估
python eval/scripts/evaluate_graphrag.py --test-data tests/test.json

# 3. 可视化结果
python eval/scripts/visualize_evaluation_results.py --metrics-file evaluation_results/*.json
```

### 查看所有示例

```bash
python eval/scripts/evaluation_examples.py
```

---

## 📊 评估指标

### 检索质量指标（6 项）

| 指标 | 说明 | 计算公式 | 优秀标准 |
|------|------|----------|
| **Precision@K** | 检索准确率 | 相关文档数 / K | ≥ 0.80 |
| **Recall@K** | 检索召回率 | 检索到的相关文档 / 全部相关文档 | ≥ 0.70 |
| **F1@K** | 综合指标 | 2 × P × R / (P + R) | ≥ 0.75 |
| **MRR** | 首个相关结果排名 | 1 / 首个相关结果位置 | ≥ 0.80 |
| **NDCG@K** | 考虑排名的质量 | DCG / IDCG | ≥ 0.85 |
| **Hit Rate@K** | 命中率 | 是否有相关结果 | ≥ 0.95 |

### GraphRAG 特有指标（4 项）

| 指标 | 说明 | 优秀标准 |
|------|------|----------|
| **版本推断准确率** | 通过相似页面推断版本的准确率 | ≥ 0.90 |
| **实体关系准确率** | 判断实体关系存在性的准确率 | ≥ 0.85 |
| **多跳推理准确率** | 多跳图遍历找到目标的准确率 | ≥ 0.75 |
| **平均路径长度** | 推理路径的平均长度 | 2-4 跳 |

---

## 🛠️ 工具说明

### 1. quick_evaluation_demo.py - 快速评估

**用途**: 无需准备测试数据，一键快速评估

```bash
python eval/scripts/quick_evaluation_demo.py
```

**功能**:
- ✓ 自动连接 Neo4j
- ✓ 检查图谱状态
- ✓ 运行简单检索测试
- ✓ 即时显示结果

**适用场景**: 日常开发、快速验证

---

### 2. generate_graphrag_test_data.py - 测试数据生成

**用途**: 从现有图谱自动生成标准测试数据集

```bash
python eval/scripts/generate_graphrag_test_data.py \
  --neo4j-uri bolt://localhost:7687 \
  --neo4j-user neo4j \
  --neo4j-password password \
  --output tests/graphrag_test_data.json \
  --num-retrieval 20 \
  --num-edition 10 \
  --num-entity 10 \
  --num-multi-hop 10
```

**参数说明**:
- `--output`: 输出文件路径
- `--num-retrieval`: 检索查询数量（默认 20）
- `--num-edition`: 版本推断用例数量（默认 10）
- `--num-entity`: 实体关系用例数量（默认 10）
- `--num-multi-hop`: 多跳推理用例数量（默认 10）

**生成内容**:
- 检索查询（文献标题、实体、版式、相似度）
- 版本推断用例
- 实体关系用例（正负样本）
- 多跳推理用例

**适用场景**: 建立标准测试集、持续评估

---

### 3. evaluate_graphrag.py - 完整评估

**用途**: 使用测试数据运行完整评估，计算所有指标

```bash
python eval/scripts/evaluate_graphrag.py \
  --neo4j-uri bolt://localhost:7687 \
  --neo4j-user neo4j \
  --neo4j-password password \
  --test-data tests/graphrag_test_data.json \
  --output-dir evaluation_results
```

**输出文件**:
- `evaluation_report_YYYYMMDD_HHMMSS.txt` - 文本格式报告
- `evaluation_metrics_YYYYMMDD_HHMMSS.json` - JSON 格式指标

**评估内容**:
- 检索质量指标（Precision, Recall, F1, MRR, NDCG, Hit Rate）
- 版本推断准确率
- 实体关系准确率
- 多跳推理准确率

**适用场景**: 正式评估、性能分析、发布验证

---

### 4. visualize_evaluation_results.py - 结果可视化

**用途**: 生成评估结果的可视化图表

```bash
python eval/scripts/visualize_evaluation_results.py \
  --metrics-file evaluation_results/evaluation_metrics_20260313_120000.json \
  --output-dir evaluation_results/plots
```

**生成图表**:
- `precision_recall_f1.png` - Precision/Recall/F1 曲线
- `ndcg_hit_rate.png` - NDCG 和 Hit Rate 对比
- `graphrag_radar.png` - GraphRAG 指标雷达图
- `metrics_summary.png` - 综合指标汇总
**图表特点**:
- 支持中文显示
- 高分辨率（300 DPI）
- 专业配色方案

**适用场景**: 结果展示、报告生成

---

### 5. evaluation_examples.py - 使用示例

**用途**: 查看所有使用示例和最佳实践

```bash
python eval/scripts/evaluation_examples.py
```

**包含示例**:
1. 快速评估演示
2. 生成测试数据
3. 运行完整评估
4. 可视化结果
5. 自定义测试数据
6. 持续评估流程
7. 常见问题排查
8. 最佳实践

**适用场景**: 学习参考、问题排查

---

## 💡 使用场景

### 场景 1: 日常开发调试

```bash
# 快速检查当前系统状态
python eval/scripts/quick_evaluation_demo.py
```

**输出示例**:
```
[1/5] 连接 Neo4j...
✓ Neo4j 连接成功

[2/5] 检查图谱状态...
  节点总数: 1250
  关系总数: 3840
✓ 图谱数据正常

评估结果
--------
MRR: 0.8333
Precision@5: 0.7200
Recall@5: 0.8100
F1@5: 0.7625
```

---

### 场景 2: 性能优化对比

```bash
# 1. 建立基线
python eval/scripts/generate_graphrag_test_data.py --output baseline_test.json
python eval/scripts/evaluate_graphrag.py --test-data baseline_test.json --output-dir baseline

# 2. 进行优化（例如调整相似度阈值）
python scripts/build_graph_from_outputs.py --similarity-threshold 0.90

# 3. 重新评估
python eval/scripts/evaluate_graphrag.py --test-data baseline_test.json --output-dir optimized

# 4. 对比结果
diff baseline/evaluation_report_*.txt optimized/evaluation_report_*.txt
```

---

### 场景 3: 发布前验证

```bash
# 完整评估流程
python eval/scripts/generate_graphrag_test_data.py \
  --output release_test.json \
  --num-retrieval 50 \
  --num-edition 20

python eval/scripts/evaluate_graphrag.py \
  --test-data release_test.json \
  --output-dir release_eval

python eval/scripts/visualize_evaluation_results.py \
  --metrics-file release_eval/evaluation_metrics_*.json \
  --output-dir release_plots
```

---

### 场景 4: 持续监控

```bash
# 定期运行评估（可配置 cron job）
#!/bin/bash
DATE=$(date +%Y%m%d)
python eval/scripts/evaluate_graphrag.py \
  --test-data tests/standard_test.json \
  --output-dir monitoring/$DATE
```

---

## 📈 性能基准

### 推荐目标值

| 指标 | 优秀 | 良好 | 及格 | 说明 |
|------|------|------|------|------|
| **Precision@5** | ≥ 0.80 | ≥ 0.60 | ≥ 0.40 | 前 5 个结果的准确率 |
| **Recall@5** | ≥ 0.70 | ≥ 0.50 | ≥ 0.30 | 前 5 个结果的召回率 |
| **F1@5** | ≥ 0.75 | ≥ 0.55 | ≥ 0.35 | 准确率和召回率的调和平均 |
| **MRR** | ≥ 0.80 | ≥ 0.60 | ≥ 0.40 | 首个相关结果的排名 |
| **NDCG@5** | ≥ 0.85 | ≥ 0.70 | ≥ 0.50 | 考虑排名的质量指标 |
| **版本推断** | ≥ 0.90 | ≥ 0.75 | ≥ 0.60 | 版本推断准确率 |
| **实体关系** | ≥ 0.85 | ≥ 0.70 | ≥ 0.55 | 实体关系判断准确率 |
| **多跳推理** | ≥ 0.75 | ≥ 0.60 | ≥ 0.45 | 多跳推理准确率 |

### 不同查询类型的基准

| 查询类型 | Precision@5 | Recall@5 | F1@5 | NDCG@5 |
|----------|-------------|----------|------|--------|
| **文献标题查询** | 0.85+ | 0.75+ | 0.80+ | 0.88+ |
| **实体查询** | 0.70+ | 0.65+ | 0.67+ | 0.75+ |
| **版式查询** | 0.80+ | 0.70+ | 0.75+ | 0.82+ |
| **相似度查询** | 0.90+ | 0.85+ | 0.87+ | 0.92+ |

---

## 🔧 配置说明

### Neo4j 连接配置

```bash
# 默认配置
--neo4j-uri bolt://localhost:7687
--neo4j-user neo4j
--neo4j-password password

# 自定义配置
--neo4j-uri bolt://your-host:7687
--neo4j-user your-username
--neo4j-password your-password
```

### 测试数据量配置

```bash
# 小规模测试（快速验证）
--num-retrieval 10 --num-edition 5 --num-entity 5

# 中等规模测试（日常评估）
--num-retrieval 20 --num-edition 10 --num-entity 10

# 大规模测试（正式评估）
--num-retrieval 50 --num-edition 20 --num-entity 20
```

### K 值配置

在代码中修改（`evaluate_graphrag.py`）:
```python
evaluator = GraphRAGEvaluator(client, k_values=[1, 3, 5, 10, 20])
```

---

## ❓ 常见问题

### Q1: 从哪里开始？

**A**: 运行快速评估演示：
```bash
python eval/scripts/quick_evaluation_demo.py
```

---

### Q2: 评估脚本报错 "无法连接到 Neo4j"

**A**: 检查以下几点：
1. Neo4j 是否正在运行：`docker ps | grep neo4j`
2. 端口是否正确：默认 7687
3. 用户名密码是否正确
4. 防火墙是否阻止连接

---

### Q3: 为什么所有指标都是 0？

**A**: 可能原因：
1. **图谱为空** - 需要先构建图谱
2. **测试数据的 ground_truth 不正确** - 检查测试数据格式
3. **查询类型不匹配** - 确认查询类型与图谱数据一致

---

### Q4: 如何解读评估结果？

**A**: 关注以下几点：
1. **MRR > 0.8** 说明相关结果排名靠前
2. **F1@5 > 0.7** 说明检索质量良好
3. **版本推断 > 0.9** 说明图谱质量高
4. 对比不同 K 值，了解检索深度的影响

---

### Q5: 评估结果不理想怎么办？

**A**: 优化方向：

**提高检索准确率**:
- 提高相似度阈值（`--similarity-threshold 0.90`）
- 优化全文索引
- 使用混合检索策略

**提高推理能力**:
- 增加实体提取（`--extract-entities`）
- 丰富图谱关系
- 优化路径查询

**提高整体性能**:
- 创建数据库索引
- 调整检索参数
- 使用更好的嵌入模型

---

### Q6: 如何提高评估速度？

**A**: 优化方法：
1. 减少测试用例数量
2. 限制检索的 K 值范围
3. 使用索引加速查询
4. 并行执行评估

---

### Q7: 可视化图表显示乱码

**A**: 安装中文字体：
```bash
# macOS
brew install font-noto-sans-cjk

# Ubuntu
sudo apt-get install fonts-noto-cjk

# 或在代码中指定字体
plt.rcParams['font.sans-serif'] = ['Arial Unicode MS']
```

---

### Q8: 如何建立持续评估？

**A**: 建议流程：
1. 生成标准测试集并版本控制
2. 每次重大更改后运行评估
3. 保存评估结果，建立趋势图
4. 定期审查和更新测试集

---

## 📦 文件结构

```
eval/
├── README.md               # 本文档
├── scripts/            # 评估脚本
│   ├── quick_evaluation_demo.py       # 快速评估
│   ├── evaluation_examples.py         # 使用示例
│   ├── generate_graphrag_test_data.py # 生成测试数据
│   ├── evaluate_graphrag.py        # 运行评估
│   └── visualize_evaluation_results.py # 可视化
├── tests/                     # 测试文件
│   └── test_graphrag_evaluation.py    # 单元测试
└── docs/                 # 详细文档（可选）
    ├── EVALUATION_DELIVERY.md         # 交付总结
    └── EVALUATION_SUMMARY.md          # 项目总结
```

---

## 🎓 学习路径

### 初级（1-2 小时）

1. ✅ 运行快速评估演示
   ```bash
   python eval/scripts/quick_evaluation_demo.py
   ```

2. ✅ 查看使用示例
   ```bash
   python eval/scripts/evaluation_examples.py
   ```

3. ✅ 理解基本指标（Precision, Recall, F1）

---

### 中级（半天）

1. ✅ 生成测试数据
   ```bash
   python eval/scripts/generate_graphrag_test_data.py --output tests/test.json
   ```

2. ✅ 运行完整评估
   ```bash
   python eval/scripts/evaluate_graphrag.py --test-data tests/test.json
   ```

3. ✅ 生成可视化图表
   ```bash
   python eval/scripts/visualize_evaluation_results.py --metrics-file results/*.json
   ```

4. ✅ 理解所有指标（包括 NDCG, MRR）

---

### 高级（1-2 天）

1. ✅ 创建自定义测试数据
2. ✅ 进行 A/B 测试
3. ✅ 优化系统性能
4. ✅ 建立持续评估流程

---

## 🚀 快速命令参考

```bash
# 快速评估
python eval/scripts/quick_evaluation_demo.py

# 生成测试数据
python eval/scripts/generate_graphrag_test_data.py --output tests/test.json

# 运行评估
python eval/scripts/evaluate_graphrag.py --test-data tests/test.json

# 可视化
python eval/scripts/visualize_evaluation_results.py --metrics-file results/*.json

# 查看示例
python eval/scripts/evaluation_examples.py

# 运行测试
pytest eval/tests/test_graphrag_evaluation.py -v
```

---

## 📊 统计数据

- **代码文件**: 6 个 (~2,100 行)
- **评估指标**: 10 项
- **查询类型**: 5 种
- **图表类型**: 4 类
- **使用示例**: 8 个

---

## 📞 获取帮助

1. **查看使用示例**: `python eval/scripts/evaluation_examples.py`
2. **查看代码注释**: 所有脚本都有详细文档字符串
3. **运行单元测试**: `pytest eval/tests/ -v`

---

## 📄 许可证

本项目遵循项目主许可证。

---

**版本**: 1.0.0
**最后更新**: 2026-03-13
**状态**: ✅ 完成并可用

**祝使用愉快！** 🚀
