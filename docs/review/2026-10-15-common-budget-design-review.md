# 共同预算与分面裁决独立设计审查

2026-10-15。SCI统计报告专家，开发设计审查；已读留出协议v0.1、最新实际资源报告与主审方案。未读取新生成输出、Gold、密钥或联网。正式新contract/plan尚待主审提供，当前为 **PROVISIONAL / REPAIR**，不授权未冻结实现进入执行。

## 审查总结

两来源六题的三臂重复开发诊断合理，现有输入/输出/尝试额度相比旧profile有充分余量；不应故意制造困难或把三次重复当独立文档。需先关闭下列设计字段，再冻结54单元执行。

## 问题清单

### 🟠 High D1：范围指标必须分别定义“选择”与“访问”及无法映射状态

- 位置：拟议评价契约“范围selection/span P/R”。
- P0模型看见KG实体属性与邻边JSON；标签exact interval不证明属性/关系全文有相同源span。用标签字符面积作为所有输入覆盖会制造错误范围精度/召回。
- S故意全源扫描与每块范围判断是两个行为；不能直接把全源访问的低precision当范围选择失败，亦不能把访问全覆盖当语义范围判断正确。
- 建议逐臂定义selected_scope、visited_source_intervals、actual_model_input_intervals、final_out_of_scope_items；P0无可信属性源映射时span P/R为UNASSESSABLE/null，明确分母而非填0或1。若可验证标签投影只作独立“label projection”诊断。A解析selected scope可评，S范围判定以固定可审的map字段/最终claim归属评；不能事后从正确答案反推选对范围。
- Before：统一把所有访问source spans计算selection P/R。
- After：选择、访问及模型可见证据三张独立表，缺失映射显式缺失。

### 🟠 High D2：共同token cap为事后检查，不得包装成发前保证

- 位置：拟议预算契约与ledger schema。
- 实际usage只能响应后获得。超单次8192或累计65536输入、累计16384输出时，已发生费用必须保留，单元RESOURCE_CAP，禁止余下调用；不能输出“所有单元在共同额度内”却仅按JSONbytes拦截。
- 单次24000/累计192000 JSONbytes可发前限制，但不是token等价，统计时分列。usage缺失/传输未知成本应停整个profile，已知usage额度突破则只停止该单元，其他预登记单元可继续；这两类停机范围须明确。
- Before：“发前严格65536 token预算”。
- After：“预发送byte/attempt/output声明限制；响应后实际token核验，突破保留费用并标RESOURCE_CAP”。

### 🟡 Medium D3：177路径计划与432共同理论额度、5400总窗口必须一致

- 位置：拟议全局执行登记。
- 54×8=432为共同单元理论尝试总和；177为P054+A42+S81的实际路径上限，需当前共同structure/prompt下离线精确计划与原生P0重试上限证明。不能将旧S27直接当新S必然调用数。
- 5400秒小于54×120=6480秒允许上限和，作为额外全组限额合理，但耗尽未运行单元须NOT_RUN并保留全54分母；不能静默删单元或事后加时。开始总窗口、import/缓存清理/本地预处理是否含unit时间都应冻结。
- 声明输出177×2048=362496是保守包络，P0预处理300实际另列；说明非实际消耗/金额。不把缓存命中当免费，不在缺verified价格时给美元费用。

### 🟡 Medium D4：裁决细则与盲化权限未完全闭合

- 位置：拟议三面评分schema。
- 固定原子claim切分、同义重复/附加事实、item别名、严格tuple必需属性、可选属性主动错误、空claim分母null、拒答/部分回答/完整性承诺显式与隐含判据。unsupported与unassessable分开，不能混叫幻觉。
- 两名AI内容评分者分别独立上下文，内容结果锁定后才给独立输入审计角色看实际调用链。仲裁保留两份原判、分歧、来源及理由；不得看arm后择优改分。
- 匿名ID不能消除KG风格/引文泄漏；固定随机种子与揭盲映射由主审保管，记录评审猜测、可见资料、SINGLE_OPERATOR_UNBLINDED和AI_REVIEW_ONLY。可显示必要精确原文但避免路径/臂标签；不能修改证据内容追求盲化。
- 多阶段支持需原文实际输入→map输出→reduce输入→最终claim每跳核验；仅reduce看到map断言不足以支持。P0 KG属性有无源支持另报，不能把被序列化即视为真实。

## 统计分析计划（执行前）

```yaml
research_question: "相同模型配置与共同资源上限下，开发三臂的范围、完整性与输入证据支持分别如何表现？"
estimand: "固定两来源六题上的描述性配对表现及重复稳定性"
sample_unit: "question within source; repeat is technical rerun"
groups_or_exposures: [P0_NATIVE_SCOPED_KG, A_AUTO_READ, S_SCAN_ALL]
outcomes: [scope_selection, input_coverage, item_precision_recall, strict_tuple_recall, attribute_errors, claim_input_support, citation_entailment, completeness_commitment, strict_supported_complete_answer, run_status, actual_resources]
repeated_or_hierarchical_structure: "2 sources; 5+1 questions; 3 runs per arm-question; 54 run units"
missing_data_plan: "RESOURCE_CAP/ERROR/TIMEOUT/UNKNOWN/NOT_RUN retain registration denominator; semantic scores only where assessable, missing never coerced to0/1"
models_or_tests: []
effect_estimates: ["paired descriptive differences, question/source macro summaries, repeat distributions"]
uncertainty_intervals: []
multiplicity_control: "No significance testing or selected winning metric"
diagnostics: ["all54 registered units, Latin-order balance, per-unit usage/caps, cache state, assessor disagreement, evidence traceability"]
sensitivity_analyses: ["valid-answer-only metrics alongside full registered-unit strict success; source macro versus pooled item counts clearly separated"]
planned_software: "Existing locked local Python; no install; user-authorized generator route handled separately by orchestrator"
execution_status: NOT_EXECUTED
```

## 优化建议汇总

1. 将D1–D4及逐项精确prompt/index/ordering/budget/评分schema写入正式contract/plan后交独立复核。
2. 准备离线54单元调用计划、无Gold消费者检查、首次真实请求前快照冻结及预算边界行为测试。
3. 仅执行开发诊断；索引保持现有283节点固定产物、其temperature未知作为条件披露；H1/H2空、M2不推进、不触发新方法设计门禁。

唯一下一步：独立复核主审即将提交的正式共同预算与裁决契约。

## 正式契约定点复审

已读 `docs/contracts/2026-10-15-common-three-arm-evaluation.md` 与同日plan；本节更新上文初审状态，不抹除初审意见。**CONDITIONAL_DESIGN_PASS；EXECUTION_NOT_RELEASED**。

- D1关闭：正式契约明确S访问/选择分开、P0隐式KG范围span P/R不可评、标签投影独立诊断，A/S exact slices与多阶段输入区分。
- D2关闭（设计）：正式契约明确token响应后核验、已知费用超额RESOURCE_CAP、未知费用停全profile、byte与token非等价。还需实现验证单元120秒确实包含新进程启动与所有本地准备，而非guard创建后才起算。
- D3条件关闭：54单元全分母、5400秒耗尽NOT_RUN、177与432区别、声明输出包络已明确；当前chunks与原生retry路径的离线manifest及测试仍为执行硬门槛，尚未证明。
- D4部分关闭：内容两AI独立锁表→证据输入审计→第三AI仲裁、claim切分与unknown支持分列已规定。执行前评分schema仍须锁定item precision（正确范围内预测/唯一预测项）、无预测precision null及空集合政策；81为既有scoring_atoms，避免未经Gold核实笼统称每个均为属性。匿名包及可见资料权限应记录AI_REVIEW_ONLY/SINGLE_OPERATOR_UNBLINDED，不能仅因shuffle宣称盲评。

### 🟡 Medium D5：P0尝试路径说明归属反了

正式契约当前写“预处理2尝试+生成1”。本次静态读 `backend/retrieval.py` 的preprocess仅一次requests.post；`backend/generator.py:289` 是 `max_retries+1`，默认max_retries=1，主回答上限2尝试。应改“预处理1+主回答2=3”，总177及声明输出保守包络不变。Guard首失败关闭可能阻断第二实际尝试，但不可倒写原生调用图。Before/after如上；冻结路径证明前必须修正该描述。

### 完整性宣称的执行判据补充

新契约将UNSUPPORTED_COMPLETENESS简写为“范围覆盖不能推出语义穷尽”，需与继承协议§7.3完整表一起读：闭合Gold、所有必需内容正确、逐claim支持且有完整目标范围访问或已验证完备清单时，显式列全可SUPPORTED_COMPLETENESS；不能因不存在数学语义证书一概判无支持。范围访问本身不能替代内容/claim裁决。应在评分schema再次明确，而非交由评分者见答案后自行解释。

条件设计通过不释放真实执行：D5文字修正、当前离线177调用计划、最终prompt/index/代码/SHA登记和评分schema冻结经独立核实后，才可放行。唯一下一步为复核这些执行前冻结证据。

第二次定点复核：正式契约现已改“预处理1+主回答2=3”；新增item precision、空答案/null与unknown分母规则、机器内容/证据评分schema，并明确旧§7.3的SUPPORTED_COMPLETENESS条件与NONE状态。**D4/D5在本轮非空六题设计范围内关闭；D1–D5设计无未处理阻断，CONDITIONAL_DESIGN_PASS保持。** “81属性”建议后续报告准确称81 scoring_atoms/评分单元（内含条件、例子等），不改变冻结Gold分母。实际裁决包还需严格照schema而非自由文字。

唯一未释放的执行门槛：当前源码P0调用图与A/S切块产生177上界的离线manifest、最终54 schedule/输入/提示/索引及代码hash登记、预算边界与120秒从子进程启动前计时行为验证。设计通过不能替代这些证据，未见材料前不声称可执行。

最终执行门槛已核实：独立25专项通过；正式registration及全部源码/KG/契约计划/历史归档/依赖hash验证通过；六题A fresh resolver/assembly与登记一致，54balanced schedule及177当前路径计划闭合。runner SHA d5cbf52cb9dc5ff30bdd13fe7de9c050751cec6413f4e69f31f49f2abc998d9e，registration SHA0bc8fe290a67d3b3c047372e2685eb33cd5fed7c681ddd95da76df40233228ec。**PASS_FOR_AUTHORIZED_BOUNDED_DEVELOPMENT_EXECUTION**，仅授权开发生成准入，语义结果仍NOT_EXECUTED；细节见同日common-three-arm-code-review。
