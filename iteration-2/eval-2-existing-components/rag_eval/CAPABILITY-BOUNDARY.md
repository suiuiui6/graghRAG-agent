# rag_eval 能力边界（Layer 0 摸底）

> 按 harness-engineering 维护期重新进入触发器"引入新核心组件"，从 Layer 0 开始，
> 作用范围仅限本子系统，不重做整个项目。

## ✅ 支持

- **检索质量评测（A1）**：Recall@k / NDCG@k / MRR，基于 ground truth 标注的相关文档 ID
- **忠实度评测（A2）**：答案与检索段落的事实一致性，基于 NLI 或 LLM-as-judge
- **鲁棒性评测（A3）**：在原始 query 上加扰动（拼写错误 / 同义词替换 / 语序调整），测量答案一致性
- **多跳推理评测（A4）**：基于多跳 QA 样本，测量答案精确匹配率与 F1
- **性能基准（A5）**：端到端延迟（p50 / p95 / p99）、吞吐量（QPS）
- **批量推理**：从 `ground_truth.json` 读题，批量调用本仓库 backend 的 `/api/query` 接口
- **离线指标计算**：所有 metrics 脚本只读 `raw_runs.jsonl`，可在无后端环境的机器上跑

## ❌ 不支持

- **在线监控**：不是 Prometheus / Grafana 替代品，不做实时告警
- **A/B 测试编排**：不做流量分桶、灰度发布
- **可视化大盘**：只产出 JSON + Markdown 报告，不提供 Web UI
- **跨模型对比**：当前每次评测固定一个模型；要对比多模型需在 `run_inference.py` 外层加 wrapper
- **数据集自动扩充**：`ground_truth.json` 需人工标注或外部来源，本子系统不做自动生成

## 与产品代码的关系

- **只读依赖**：评测脚本只调用 backend `/api/query` 接口与 Neo4j 只读查询
- **不修改 backend**：评测发现的问题应回流到 `integration/backend-api-architecture-v1.0.md` 而非本目录
- **数据隔离**：评测期间建议使用独立的 Neo4j database（如 `kg_eval`），避免污染生产 `kg_prod`
