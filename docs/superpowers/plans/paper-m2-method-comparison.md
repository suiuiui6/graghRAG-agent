# GraphRAG 论文 M2 方法与竞品对比

> 最新裁决（2026-10-07）：本对比与工程合同保留为历史/暂定资产；新颖性与推进建议以 `paper-recent-journal-limitations-review.md`、`paper-conflict-calibration-competitor-review.md` 和控制台第11节为准。宽泛冲突校准贡献已否决，M2仍部分通过，P1软件资产不撤销。

> 状态：M2 验收稿  
> 基线代码：`46b202c`（2026-09-18）  
> 文献台账：`paper-m2-literature-ledger.md`

## 1. M2 结论

推荐主线 A 可以保留，但论文身份需要进一步收窄：

> 面向中文复杂长文档的生产一致性 GraphRAG 证据治理与评测框架，研究从检索路径、最终上下文到答案 claim 的证据损耗，并在相同预算下评价正确性、引用支持、拒答/纠错与成本。

这更接近**系统与评价方法论文**，而不是基础 GraphRAG 算法论文。以下内容已经有直接竞品，不能作为单独创新点：图检索、社区摘要、层次索引、source-chunk 关联、引用生成、拒答评测、自适应路由、模块化消融和质量—成本分析。

## 2. 现有方法对比表

| 方法族 | 代表工作 | 已解决问题 | 仍留给本项目验证的具体不足 |
|---|---|---|---|
| 平面稀疏/稠密 RAG | BM25、dense、hybrid + reranker | 局部事实检索与简单融合 | 不能天然表达跨块关系；但必须作为公平基础线，不能只和 naive RAG 比 |
| 社区摘要 GraphRAG | Edge et al. GraphRAG | 全局 sensemaking、社区级汇总 | 生成式摘要可能与原始证据脱节，且非 claim/坐标级溯源 |
| 图遍历与 KG 引导 | HippoRAG、KG²RAG、GraphReader | 关系扩展、多跳召回、source chunk 关联 | 图抽取错误、方向/多关系和最终 claim 支持尚未统一审计 |
| 长文档层次/回源 | LongRAG、LongBench、full-context LLM | 长上下文压缩、跨块恢复、多粒度评价 | 非 graph；通常不覆盖页码/bbox、引用精度和生产调用一致性 |
| 引用与忠实性 | ALCE、RAGTruth | citation recall/precision、span 级幻觉 | 多从既有 passage 开始，未审计“原文→派生图→最终引用”损耗 |
| 不可回答与拒答 | UAEval4RAG、RefusalBench | 缺失、矛盾、错误前提、过拒答等行为评价 | 需中文化，并与真实知识库和纠错行为结合 |
| 自适应与成本路由 | Adaptive-RAG、SELF-ROUTE | 按问题复杂度选择检索/全文策略 | 通常未把 claim 支持、图构建成本和生产 SLO 放入同一评价面 |
| RAG 诊断框架 | ARES、RAGChecker | 分离检索、上下文、回答维度并支持诊断 | 不验证评测程序是否经过生产 API 和同一 source assembly |
| 当前仓库 | Vector + KG + BM25；条件 Table；自适应 Cross-Encoder | 已有多路召回、RRF、预算、拒答/纠错和结构化 sources | 缺 source mask、claim entailment、稳定 provenance、held-out 数据与统一 frozen rerun |

## 3. 当前生产链的真实边界

主接口是 `POST /api/v1/rag/query`。默认配置为 `max_total_candidates=5`、`max_context_tokens=4000`、Cross-Encoder 开启、Multi-Query 与 Global 关闭；source caps 为 vector 2、KG 2、BM25 1、table 1、multi-query 1。

默认链路不是“五路全开”：

1. 查询指代改写、领域词扩展和 LLM/启发式查询预处理；
2. 默认运行 Vector + KG + BM25，只有 metric 意图才增加 Table；
3. RRF 后仍可能执行 KG/BM25/Table rescue；
4. Cross-Encoder 只在候选数、时延预算、工作量和题型规则允许时执行；
5. 冲突降权、去重、token 截断与 source cap 共同形成 `final-context`；
6. 当前 citation verification 只检查引用 ID 是否出现在上下文，不能证明 claim 得到证据支持。

关键代码定位：

- 主路由：`backend/routes/rag_query.py:218`
- 请求级预算：`backend/routes/rag_query.py:97`、`backend/models.py:40`
- 默认配置：`backend/config.py:59`、`backend/config.py:79`
- 检索调度与融合：`backend/retrieval.py:465`、`backend/retrieval.py:1766`
- rescue 与 Cross-Encoder 决策：`backend/retrieval.py:2658`、`backend/retrieval.py:2716`
- 引用 ID 检查：`backend/generator.py:1215`

## 4. 现有代码可跑与不可跑的对照

| 对照 | 当前请求级可执行 | 准确解释 |
|---|---:|---|
| Full production default | 是 | 默认 local hybrid + adaptive shortlist + 可选 Cross-Encoder |
| `enable_cross_encoder=false` | 是 | 只能称 `no-cross-encoder`，不能称 `no-rerank` |
| Multi-Query off/on | 是 | 仅在预处理实际改写查询时触发，并引入额外 LLM 调用 |
| Global off/on | 是 | 只适用于全局类问题，不能在全题集当通用 baseline |
| candidate/context/source-cap 扫描 | 是 | source cap 只能设正整数，不能关闭来源 |
| BM25-only / Vector-only / KG-only | 否 | 请求没有 `enabled_sources`，且 post-RRF rescue 仍会恢复其他来源 |
| Vector+BM25 / Vector+KG | 否 | 同上，省略某项仍会合并默认 caps |
| no-KG / no-table / no-budget | 否 | 缺统一 ablation mask；`max_tool_calls` 不参与主链 |
| 真正 no-rerank/final-context selection | 否 | 关闭 Cross-Encoder 后仍有 shortlist、threshold、trim、dedup |
| no-citation-verification / no-refusal-policy | 否 | 相关开关未暴露到生产请求 |

不能用旧 `/api/v1/query` 伪装 KG-only baseline：它是另一套 LangGraph Agent，具有不同 prompt、工具上限和生成行为。`backend/agentic_rag_mvp.py` 已废弃，也不能充当现代对照。当前仓库没有 `rag_eval/baselines/`，既有组件测试不是 baseline 结果。

## 5. M3/M5 所需最小 baseline 阶梯

在增加统一、可记录的 `enabled_sources`/`ablation_flags` 后，主表至少需要：

1. BM25-only；
2. Vector-only；
3. Vector + BM25 + RRF，Cross-Encoder off；
4. Vector + BM25 + KG + conditional Table + RRF，Cross-Encoder off；
5. Full production adaptive：与第 4 行相同来源，启用自适应 Cross-Encoder 与预算保护。

KG-only 放诊断表或附录；Multi-Query 和 Global 是专项消融，不混入最小主表。若资源允许，再增加 full-context LLM 或 SELF-ROUTE 风格基线，以回应长上下文直接读取的强竞品。

## 6. 公平预算合同

- 同一 frozen commit、文档/索引快照和 SHA-256。
- 同一问题集、同一 `final-context` 指标面和独立 raw run 文件。
- 查询预处理结果冻结并重放，避免外部 LLM rewrite 漂移。
- 基础检索器统一关闭 Cross-Encoder；Cross-Encoder 只在独立增量行比较。
- `K_final=5`、`context_tokens=4000`、pre-rerank cap 统一为 7。
- 还需统一 raw recall 总预算，不能只统一 final top-k。
- 相同生成模型精确版本、prompt hash、temperature 0、最大输出 2048、stop/retry policy。
- 同时报 `final-context` 检索、claim/citation 支持、拒答/纠错、P50/P95 延迟和 paired delta。
- Cross-Encoder 行报告实际执行率及 `rerank_skipped` 原因，而不是只按配置开关归组。
- token/cost 包含查询预处理、Multi-Query、检索与最终生成；当前只统计最终生成的口径不够。
- 只接受 `metadata.mode == "rag_pipeline"`；降级到 legacy KG Agent 的题目或轮次作废。

## 7. 投稿前必须消除的公平性风险

1. 多路召回使用 `as_completed`，重复候选最终 source 归属可能随线程完成顺序变化，继而影响 source cap；需稳定 provenance 合并规则。
2. 生成器含针对当前题型的确定性 rescue/repair，同一 50 题已存在调参风险；至少增加 held-out 问题或跨文档测试。
3. citation verification 只做 ID 存在检查，不能命名为事实一致性验证。
4. 当前 runner 尚不能选择 baseline variant；不同 variant 必须产生不可覆盖的独立结果和 manifest。
5. grounding 的字符区间、未知文档回退和跨 segment 映射风险未解决前，不能把 page/bbox traceability 作为 headline 结果。

## 8. 改进方向与预期贡献

### 8.1 必须实现的研究方法

1. **生产一致的消融契约**：同一 `/rag/query` 路由支持 source mask、模块开关和完整 metadata，正常召回与 rescue 共同遵守。
2. **四层证据面**：明确区分 `path_hits`、`pre-rerank`、`final-context` 与 answer claims，计算每层的证据保留/损耗。
3. **claim 级支持与行为标注**：把 node-ID validity 降级为格式合法性，新增 claim support、citation precision/recall、拒答适当性和错误前提纠正。
4. **稳定谱系**：为图事实与最终 sources 保存 document hash、source span、page/bbox、构建版本及确定性 provenance 合并。
5. **预算匹配评价**：把索引、预处理、检索、重排和生成成本纳入统一口径，给出 paired interval 或置信区间。
6. **外部有效性切片**：除现有 50 题外增加 held-out 或跨文档小规模集合，并按正文/表格/列表/数值/多证据/不可回答分层。

### 8.2 可检验的贡献假设

- H1：生产一致的证据面核算会揭示 `path_hits` 指标对最终可用证据的系统性高估。
- H2：在相同召回与上下文预算下，KG/conditional Table 对特定复杂题型带来增量，但不会在所有题型上稳定优于简单 hybrid。
- H3：claim 级支持与引用精度会显著低于引用 ID 合法率，从而改变对“忠实性”的结论。
- H4：自适应 Cross-Encoder/预算保护存在可测的质量—延迟权衡，且配置开启率不等于实际执行率。
- H5：基于语义行为的拒答评价会暴露关键词式 T5 指标的误判。

这些均是待实验假设，不是当前结果。

## 9. M2 正式评审

| 验收项 | 状态 | 依据 |
|---|---|---|
| 明确相对谁改进 | 通过 | 已覆盖平面检索、GraphRAG、长文档、引用、拒答、自适应与评测框架 |
| 不足具体可核验 | 通过 | 已映射到 claim/坐标谱系、生产一致性、预算与代码开关缺口 |
| 改进方向与后续对齐 | 通过 | 已形成 source mask、证据面、claim 支持、稳定谱系、预算和外部有效性六项输入 |
| 文献身份与证据等级可靠 | 通过 | 15 篇核心文献均核验官方全文，空白均标注 `AI_INFERENCE` |

**M2 结论：PASS。**

M3 不应直接发明新模型；应先把上述贡献假设收束成一个最小方法合同，决定论文究竟以“证据损耗评测框架”为主，还是额外实现可归因的证据治理模块。
