# M4 测试准备材料

项目：`graphrag-paper-001`；日期：2026-10-07。

## 1. 已执行的准备检查

工作树 HEAD：`46b202c3e400741fd569f024412c0745f224a538`，存在原有未提交修改和未跟踪文件；不是 paper freeze。

实际使用 `backend/.venv/Scripts/python.exe`，版本 3.12.8，PyYAML 可用。SCI capability detector 返回 PATH 中 python3 别名，该别名未用作执行解释器，不能据此替代实际解释器证据。

本轮真实命令：

```powershell
& backend/.venv/Scripts/python.exe -B .codex/skills/sci-skills/scripts/detect_local_capabilities.py
& backend/.venv/Scripts/python.exe -B iteration-2/eval-2-existing-components/rag_eval/test_run_inference_helpers.py
```

第二条退出码 0：`Ran 7 tests` / `OK`。只验证现有 helper，包括旧 ID 归一化行为；没有调用生产端点，不是 API 真实集成通过，也不是七变体实验。

历史 `ground_truth.json` 有 50 个 questions；历史 `raw_runs.jsonl` 有 50 条非空 JSON 记录、50 个唯一 qid。尚未在本轮验证每条答案或集合逐项对应，不能从计数相等推断结果正确。

| 输入 | SHA256（2026-10-07 字节快照） |
|---|---|
| `rag_eval/ground_truth.json` | `95f2fd33af49772c6e5369d8e7ad06b6000999bce0930628ed2891a686dc3867` |
| `rag_eval/raw_runs.jsonl` | `0a47a175ff6b15cd43e68b26b736add50fb7886e185511e1250e69f9b07b7aca` |
| `backend/uv.lock` | `31caa7407226490b13e1853875eb1ebbe8f895980da39f2b19f58c79f11c14a3` |

上表短路径中 rag_eval 为项目已有评测目录。哈希只证明观察到的字节，不补足原始生成命令、旧 commit 或许可。

## 2. P1 测试用例合同（已执行软件范围，详见 P1 验证记录）

| 测试 | 输入/条件 | 判定 |
|---|---|---|
| 默认兼容 | 不提供 enabled_sources | 维持旧默认路径与条件规则 |
| 空/未知列表 | 空数组或未知源 | 明确校验失败，无隐式默认补入 |
| 单源 | B01、B02 | 所有阶段仅允许指定来源；禁用路径不得调用 |
| 条件表格 | B05 的 metric 与非 metric | 记录 Table 的条件执行/跳过，不按结果好坏改题型 |
| 全部救援入口 | 触发 KG/text/table/storage rescue | 只允许 mask 内证据，含确定性答案证据 |
| global/multi-query | 禁 KG 或禁 vector，相关开关开启 | 拒绝/跳过规则符合合同，无跨源绕过 |
| 并发隔离 | 两个请求不同 mask | effective_config 不串请求，共享默认不变 |
| 主链失效 | 显式 mask + pipeline 初始化失败 | 不以 legacy fallback 冒充同一变体 |

## 3. P2/P3 测试用例合同（待新增和执行）

1. 同分候选、异步乱序、重复多源和缺 ID：稳定身份/排序，不随机，不覆盖 provenance。
2. `docA:n0010` 与 `docB:n0010`：必须为不同证据；legacy helper 的前缀剥离不可用于新 trace。
3. 中英混合文本、KG 格式化、超长 section、domain_hint 占满预算、边界截断：trace 与最终 messages 一致；不能把未见后半段 gold 计为到达。
4. 确定性纠错、拒答和模型 error_recovered：生成模式、决策证据、raw/final 答案分离；未调用模型时不伪造 raw。
5. 无引文 claim、部分支持、矛盾 claim、零 claim 拒答：分母正确；拒答支持率 NA，与 completeness/behavior 一并报告。
6. 运行目录冲突、计划 qid 缺失、响应重复、配置不一致、未知成本：显式记录且不能静默补 0 或覆盖旧文件。

测试中的合成边界夹具仅用于软件验证，标记 TEST_ONLY，不作为论文性能、样本或结果数据。

## 4. 集成测试与运行前提

生产端点测试按项目宪章放 `backend/tests/` 并使用真实依赖；纯 helper 测试不能替代它。测试前需确认隔离测试索引、已有本地权重和不联网的执行方式。不得使用真实生产库作写入/删除测试，也不为研究运行安装全局包。

P1 已执行 `test_query_budgeting.py`、`test_retrieval_stage_metrics.py`、`test_hybrid_retrieval_trimming.py` 等选定回归及新增来源控制测试，共 153 passed。真实端点集成限本地 BM25/SQLite/确定性链；模型链未执行。完整命令、警告和范围见 `paper-m4-p1-verification.md`。

原 `run_inference.py` 会加载凭据并调用远程生成服务；SCI-Skills 零 API 边界下不执行。若后续没有作者明确选择的现成本地模型，真实推理保留未执行，提供人工/本地执行交接后再验收。

## 5. 阶段评审

总体：**部分通过**。

- 实施步骤可执行：满足，见 P1–P3 的具体入口及用例。
- 资源需求明确：部分满足，解释器与文件已核实，本地模型/隔离索引仍待核实。
- 原型能支撑验证目标：部分满足，来源控制已通过软件验证，P2 追踪与 P3 冻结运行未实现。
- 风险有备选方案：满足，禁止远程替代、伪造 provenance 和冒充实验通过。
- 图件制作确认：不适用本轮；未制作图件，现有批准状态不变。

暂不进入 M5。P1 软件范围通过；剩余真实证据/答案链、独立冻结运行、预算锁定与模型完整集成验证。
