# M3 证据核算与模块归因补充合同

> 版本：1.1；日期：2026-10-07  
> 状态：方法设计已审查；实验 `NOT_EXECUTED`。  
> 本文件补充 `paper-m3-method-contract.md`。以下均是拟实施的研究定义，不是已观察到的实验规律。旧结果与旧指标仍按原口径保留，不能用新定义重新命名旧数值。

## 1. 证据身份与等价映射

原始文本、KG 节点、表格行和最终上下文片段的粒度不同，不能直接对这些对象的 ID 做集合交集。

每个来源对象必须通过独立维护的 `evidence_registry` 映射到规范证据单元 `canonical_evidence_id`。规范单元记录文档哈希、原始 source item、实际可见 span、表格单元格或经核验的语义证据映射。KG 抽取结果仅在原文确实支持其表述时才能映射为同一证据；结构边和属性推断边本身不能成为支持事实的充分证据。

每题的标注结构为：

```yaml
question_id:
expected_behavior: answer | refuse | correct
gold_evidence_groups:
  - group_id:
    role: required_fact | correction_fact
    alternatives: []  # 任一个已核验的规范证据单元可满足该事实要求
sufficient_group_sets: []  # 每组列 group_id，表示一个已标注的充分证据组合
annotation_version:
```

`alternatives` 表示同一事实有多处等价来源；`sufficient_group_sets` 表示解题可以采用不同证据组合。不能要求系统同时命中所有替代出处，也不能根据哪个变体表现最好而事后选择 gold。

如果新结果发现原标注遗漏了有效证据，先由不知变体身份的标注者审核，记录版本变化，然后对所有变体统一重算。旧版本指标继续保留。

## 2. 四阶段的可观测定义

| 阶段 | 边界 | 必须记录 |
|---|---|---|
| S1 `path_hits` | 初始允许路径实际返回的候选；rescue 另记事件 | 完整来源、路径排名、规范证据映射、是否截断 |
| S2 `pre-rerank` | 所有已声明融合、rescue 和候选预算操作后，最终选择前 | 有序候选、融合分数、补入/删除及理由 |
| S3 `final-context` | 生成请求中实际序列化的上下文 | 文本与哈希、精确有序列表、可见 span、实际 token |
| S4 `answer claims` | 原始回答的原子 claim 与引用/支持映射 | claim 文本、引用集合、支持标签、人工裁决及原始回答哈希 |

S3 必须从生成边界取证，不能用响应 `sources` 列表推定；响应可能包含比 prompt 多或少的内容。截断后的上下文不得继承完整原块的命中结论，必须根据可见文本重新映射。

S4 分别保存 `cited_evidence` 与 `fully_supported_evidence`。部分支持单独存储，不进入严格支持集。所有 claim（包括无引用、无支持和矛盾 claim）都保留，不能只导出支持成功的 claim。

## 3. 证据召回、损失与补入

主检索指标使用事实组命中：一个 gold group 的任一有效 alternative 在该阶段实际可见，即算该组命中。主结果为命中组数除以固定 required group 数；同时报告是否至少满足一个预先标注的 `sufficient_group_set`。

对同一题、相同 gold groups，相邻阶段报告：

- `loss`：上一阶段已命中、本阶段未命中的组数 / required group 数；
- `addition`：上一阶段未命中、本阶段新增命中的组数 / required group 数；
- `recall_delta`：本阶段 recall 减上一阶段 recall。

这些定义须满足 `recall_delta = addition - loss`。证据可以经 rescue 补入，因此不假定每个阶段是前一阶段的子集。

拒答题如果没有 required evidence group，检索 recall/loss/addition 为 `not_applicable`，不记为 0，也不记为 1。错误前提题需要用于纠错的 gold evidence；不可定位或未裁决样本标记 `missing_annotation` 并单独报告。

S3→S4 的差异描述证据是否用于支持回答，不等同于检索模块丢失证据：模型可能使用不必要证据，也可能正确拒答。该差异必须结合 gold 行为与答案完整性解释。

## 4. claim 与引用的分母

以下主指标以变体盲法裁决后的原始回答为对象：

| 指标 | 分子 | 分母/缺失处理 |
|---|---|---|
| 严格 claim 支持率 | `fully_supported` 且需要证据的 claim 数 | 全部需要证据的 claim 数；无此类 claim 为 NA |
| 部分支持率 | `partially_supported` claim 数 | 同一分母；不赋予任意 0.5 权重 |
| 无支持/矛盾率 | 对应标签的 claim 数 | 同一分母；分栏报告 |
| claim 引用覆盖率 | 由其显式引用集合充分支持的 claim 数 | 全部需要引用的 claim 数；无引用 claim 仍进分母 |
| 引用支持精度 | 对其所连 claim 确有支持作用的 citation-claim link 数 | 所有 citation-claim links；无法解析或非法 ID 计失败 |
| gold 答案覆盖率 | 已正确表达且充分支持的 required answer units | 该题固定 gold answer units |

这些是本项目拟定操作定义；正文引用已有 citation precision/recall 工作时，需列出实现与其定义的具体对应和差异。

只报告 claim 支持率会奖励少说或拒答。主表必须同时报告答案正确性、gold 答案覆盖率、引用覆盖率和回答行为；不能把“无 claim 的纯拒答”算成 100% 支持。

同一 claim 的多个引用先整体判定是否充分支持，再逐条标注每个 citation link 的作用。需保留“单条不足、组合充分”的情况。正确但无引用的 claim 仍算引用覆盖失败；其事实正确性另记。

人工标注与 runtime 自检分栏。标注者看到原始回答、问题、final-context 和原文依据，但不看到变体名称。初标、复核、分歧与仲裁记录均保留；具体样本量、复核比例和一致性指标留给 M5 锁定。

## 5. 行为评价与无效运行

gold 行为允许 `answer/refuse/correct`。观测行为额外允许 `clarify`、`mixed`，避免把澄清或“先拒答后编答案”强塞进三类。纯空白与系统错误记执行失败。

分别报告：可回答题的正确回答率及过拒答率、不可回答题的适当拒答率、错误前提题的有证据纠错率，以及完整行为混淆矩阵。关键词出现只用于诊断；语义裁决决定是否适当。

每题保存 `run_status`、`invalid_reason` 和失败阶段。汇总至少报告 scheduled、attempted、valid、invalid、failed 数量。成对分析使用共同有效题并公布覆盖比例；因超时或初始化失败的题不能被静默删除，另报全请求成功率与保守敏感性分析。具体敏感性分析规则在 M5 预先冻结。

legacy fallback、mask 泄漏、trace 无法与真实 prompt 对齐属于运行有效性失败；答案错误、合理预算下未命中证据属于科学结果，不能以 `invalid_run` 排除。

## 6. 可归因的 baseline 与消融

M2 五行最低阶梯继续保留，但第 3→4 行同时增加 KG 与 Table，只能说明组合增量。新增如下主/诊断变体以分别归因：

| 变体 | 来源 | Cross-Encoder | 作用 |
|---|---|---|---|
| B01 | BM25 | off | 稀疏基础线 |
| B02 | Vector | off | 稠密基础线 |
| B03 | Vector + BM25 | off | 简单 hybrid |
| B04 | Vector + BM25 + KG | off | KG 的单模块增量 |
| B05 | Vector + BM25 + conditional Table | off | Table 的单模块增量 |
| B06 | Vector + BM25 + KG + conditional Table | off | 两模块组合 |
| B07 | 同 B06 | adaptive | 自适应 Cross-Encoder 增量 |

比较 B04/B03、B05/B03，并用 B06 检查交互；只比较 B06/B03 时禁止写“证明 KG 或 Table 单独贡献”。B07/B06 固定其他预算和选择逻辑，只解释 Cross-Encoder 策略的整体增量。预算控制贡献通过预先声明的 candidate/context 扫描另检验，不用一次开关同时关闭多个机制。

Table 在 metric 子集执行：分别报告全题集 intention-to-treat 对比、预先定义的 metric 子集以及实际执行率。Multi-Query、Global、生成侧策略和 full-context 基线另列专项试验。

全变体固定同一 RRF 常数策略及最终选择器；当前实现对 Vector 和 Multi-Query 使用较大的 RRF 常数，需在 frozen config 明示，不能称各来源等权。公平比较需分别锁定总 raw 召回预算、候选预算、final k 与 context token；各路径的 raw 配额在开发题上确定后冻结。

## 7. 状态与实施任务

当前仅完成设计与代码落点复核。以下任务在 M4 实施，均为 `NOT_EXECUTED`：

1. 请求级来源 mask 与有效配置回传，同时约束正常召回、global、检索 rescue 和生成补证。
2. 合并完整多来源 provenance，稳定身份和排序；去除实验结果中的随机 ID 回退。
3. 在生成边界保存真实 prompt 上下文与其哈希，记录截断后的实际证据映射。
4. 独立保存原始回答、claims、引用与行为；离线裁决先采用文件协议。
5. runner 读入冻结变体配置，输出不可覆盖目录、manifest、失败清单和分阶段成本。
6. 将新字段回流到现有后端 API 与 RAG 评测规范，再执行真实依赖集成验证。

最小原型可先支持固定生成链与离线人工裁决；在线自动 entailment、自动答案改写与新模型训练均不构成本合同的验收前提。

