# rag_eval — RAG 评测子系统

> 触发重新进入 harness-engineering Layer 0 的产物（2026-05-29）。
> 作用范围：仅此目录内的评测脚本与指标，不影响产品代码。

## 用途

对现有 GraphRAG 系统做五类评测：
- **A1 检索质量**：召回率 / NDCG / MRR（`metrics_a1_retrieval.py`）
- **A2 忠实度**：答案与检索内容的一致性（`metrics_a2_faithfulness.py`）
- **A3 鲁棒性**：扰动输入下的答案稳定性（`metrics_a3_robustness.py`）
- **A4 多跳推理**：跨段落 / 跨实体的多跳问题准确率（`metrics_a4_multihop.py`）
- **A5 性能**：延迟 / 吞吐量基准（`metrics_a5_performance.py`）

## 运行环境

复用 `backend/.venv`（评测脚本依赖与后端一致），不新建独立环境。
若未来评测需要不同依赖版本，再独立 `uv venv .venv --python 3.12`。

激活：
```bash
# macOS/Linux
cd D:/graghRAG-agent/backend && source .venv/bin/activate

# Windows
cd D:/graghRAG-agent/backend && .venv\Scripts\activate
```

## 评测流程（三步）

```bash
# 1. 构建 ground truth
python build_ground_truth.py   # → ground_truth.json

# 2. 跑推理
python run_inference.py        # → raw_runs.jsonl + run.log

# 3. 算指标（可分别运行）
python metrics_a1_retrieval.py   # → metrics_a1_retrieval.json + report_a1_retrieval.md
python metrics_a2_faithfulness.py
python metrics_a3_robustness.py
python metrics_a4_multihop.py
python metrics_a5_performance.py
```

## 规范文档

- 能力边界（什么能评 / 什么不能评）：`CAPABILITY-BOUNDARY.md`
- 输入输出 schema 与指标定义：`RAG-EVAL-SPECIFICATION.md`

## 数据约束

- `ground_truth.json` 是评测真值，**禁止**被推理脚本写入
- `raw_runs.jsonl` 每行一条推理记录，禁止合并为单 JSON 数组（流式追加）
- `run.log` 不进 git（已在 `.gitignore`）
- 评测结果 `metrics_*.json` 进 git，作为基线供后续回归对比
- 历史报告 `report_*.md` 进 git，可纵向对比多轮评测结果
