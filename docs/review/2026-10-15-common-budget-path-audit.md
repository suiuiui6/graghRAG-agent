# 三臂共同预算：独立静态路径核验

2026-10-15。仅开发诊断，M2_OPEN。核查者只拥有本文件；未读 `.env`/密钥/Gold，未联网或模型调用，未修改执行器或历史快照。

## 当前结论

离线路径与调用算术成立：A每轮14，S每轮27，P0每轮至多18，共59×3=177 HTTP尝试。177×2048=362496是保守的声明输出上界，P0预处理实际请求上限300，不能把该上界当实际消耗。54×8=432是共同单元额度的理论总和，不是当前冻结路径允许发送432次。

本次仍为预执行审查；最终执行器、registration、依赖身份及guard测试尚待编排者交付后定点复核，不能据本文件单独放行API。当前执行器开发草稿SHA256 `5fba52f2f4953ef90247d96dc323470a24fd112058714d7d8d6c89932758ad64`；后续修改须复核受影响结论。

## 输入与路径证据

- 契约：`docs/contracts/2026-10-15-common-three-arm-evaluation.md`；计划：`docs/plans/2026-10-15-common-three-arm-evaluation.md`。
- A输入：`docs/review/development-budget-20261014/inputs.json`。六题map块数为1、1、1、1、1、3，每题一次reduce，因此14次。独立检查这些块精确按登记selected spans以8000 Unicode字符切分，不加载Gold。
- S输入：LinuxCNC规范文本18101字符，切为[0,8000)、[8000,16000)、[16000,18101)；NIST规范文本41704字符，切为五个完整8000字符块及[40000,41704)。各块源内连续无重叠，拼接逐字符等于规范全文。5个LinuxCNC题各3 map+1 reduce，NIST题6 map+1 reduce，合计27次。此证明仅为原文遍历，不证明抽取穷尽。
- 冻结实际P0：`.tmp/public-dev-budget-20261015-r2/backend/research/development_isolation.py:314`调用原生`/api/v1/rag/query`函数，带明确document_id、kg-only、evidence trace；不是BM25夹具，也不是JWT/HTTP端到端验证。
- `.tmp/public-dev-budget-20261015-r2/backend/routes/rag_query.py:220`的scoped路径禁session、强制KG、禁multi-query/cross-encoder，构造`RetrievalPipeline(None, None, kg_graph=...)`，未注入query_optimizer/domain_dict，故不走向量/embedding、共指、multi-query或旧agent退回。
- `.tmp/public-dev-budget-20261015-r2/backend/retrieval.py:279`预处理至多一次POST，无POST外循环，max_tokens300、temperature0；模型解析自环境默认flash并使用`non_thinking_options`。
- `.tmp/public-dev-budget-20261015-r2/backend/generator.py:45`默认max_tokens2048、max_retries1；282行重试函数为`max(0,int(config.max_retries))+1`，主generate仅一个generate_answer调用点。scoped路由不覆盖max_retries，因此至多2次回答尝试。引用提示/repair/complete/supplement没有新增LLM调用；确定性短路只降低调用数。
- `.tmp/public-dev-budget-20261015-r2/backend/config.py:18`对flash生成顶层`thinking={type:disabled}`。这是请求字段，不是已执行响应身份。temperature取请求，必须由最终guard锁为0；返回model/fingerprint须另记，不能把源码默认当运行身份或固定权重。
- scoped配置仍承接请求enable_global_mode；当前QueryOptions默认false。即使开启其KG社区召回也不增加生成请求，但本轮应保持登记默认false，避免改变证据访问行为。
- fresh rewrite-cache实际路径为冻结retrieval.py:41的`backend/output/rewrite-cache.sqlite3`；开发runner清理该路径及wal/shm/journal，必须每单元独立新进程执行并复核清理成功。供应商缓存仍可能命中，不能宣称禁缓存。

## 54单元顺序与执行边界

离线实际调用草稿`build_schedule`：54个唯一unit_id；每(question,arm)恰3次；三臂在每个三元组位置各6次，循环平衡成立。最终registration顺序及hash仍须核验，不由草稿结果替代。

当前草稿`CommonUnitGuard`静态具有共同temperature0、flash/thinking/非流式、P0 300或2048/A-S 2048声明、24000/192000请求字节、8192/65536/16384响应后token额度、每单元planned_calls路径限制。动态reduce必须经过相同实际transport guard，不能靠原文长度估计。字节上限不是发前精确token保证。120秒/5400秒是本地请求窗口，不证明供应商取消或最终结算；UNKNOWN请求必须停止全组并保留可能费用。

完整原生代码与资产漂移校验、真实requests/SDKtransport覆盖、超额继续其他单元与UNKNOWN整组停止等行为需最终专项测试支持。本文件没有将静态guard存在当作行为测试通过。

## 实际离线验证

命令：PowerShell here-string传入 `backend/.venv/Scripts/python.exe -B -`，仅载入执行器标准库顶层及调用`prove_p0_path`、`scan_chunks`、`build_schedule`；独立重算A/S块和schedule断言。exit0。完整命令与输出在本次工具记录中。

结果：指定冻结generator/retrieval/config/scoped-route/isolation五文件SHA与snapshot匹配；P0单题≤3；A14/S27；177上界；54唯一单元；9个(arm,position)组合均6次；核查前后草稿hash不变。未执行remote、未导入生产服务、未运行语义评分。

```yaml
contract_version: "1.0"
expert_skill: sci-skills-statistical-reporting
project_id: graphrag-paper-001
paper_family: M
stage_id: M2
task_id: null
task_status: PROVISIONAL
inputs_reviewed:
  - docs/contracts/2026-10-15-common-three-arm-evaluation.md
  - docs/plans/2026-10-15-common-three-arm-evaluation.md
  - docs/review/development-budget-20261014/inputs.json
  - .tmp/public-dev-budget-20261015-r2/snapshot.json
  - .tmp/public-dev-budget-20261015-r2/backend/generator.py
  - .tmp/public-dev-budget-20261015-r2/backend/retrieval.py
  - .tmp/public-dev-budget-20261015-r2/backend/config.py
  - .tmp/public-dev-budget-20261015-r2/backend/routes/rag_query.py
  - .tmp/public-dev-budget-20261015-r2/backend/research/development_isolation.py
  - .tmp/public-dev-budget-20261015-r2/backend/research/development_budget.py
  - backend/research/common_three_arm.py (development draft, SHA recorded above)
outputs:
  - docs/review/2026-10-15-common-budget-path-audit.md
evidence_status:
  - "EXECUTED_LOCAL: read-only offline call-graph, exact partition, snapshot subset and schedule assertions; exit0."
  - "VERIFIED_USER_MATERIAL: frozen native config and old public input spans."
  - "AI_INFERENCE: bounded scoped path gives at most 18 P0 attempts per round."
  - "NOT_EXECUTED: no network/key/Gold access, model inference, semantic scoring or scientific stage change."
  - "PENDING_VERIFICATION: final runner/registration/test evidence and actual wire receipts."
assumptions:
  - "Only the explicit scoped KG production path is P0 for this experiment."
  - "Two public source units, six correlated questions and three repeats are not independent document samples."
  - "Known token overage retains usage and stops the unit; unknown remote cost stops the whole profile."
author_input_needed: []
manual_actions: []
quality_checks:
  - "PASS_STATIC: A14/S27/P0max18 -> 177 attempts across three repeats."
  - "PASS_OFFLINE: A selected-span partitions and S full-source partitions are exact."
  - "PASS_OFFLINE: draft schedule is 54 unique units, three per question-arm, balanced positions."
  - "PASS_STATIC: scoped KG excludes optional model branches; model/temp/thinking/output limits are identified."
  - "PENDING: independently verified final registration, code hash and guard behavior."
conflicts: []
conflict_resolution_status: NOT_REQUIRED
merge_permission: orchestrator_only
recommended_next_action: "Root supplies final runner, registration and offline guard-test evidence for bounded independent re-review before API execution."
stage_acceptance_recommendation: NOT_ASSESSED
```

下一步：编排者交付最终执行器、registration及guard行为测试证据后，进行定点独立复核。

## 最终登记定点复核（取代上方草稿的待登记结论）

结论：**本专项PASS，未发现路径/manifest/资产身份阻断**。放行范围限本次独立预算路径核验；guard专项测试及代码安全审查仍由对应负责人确认，不由本文件代签。M2保持开放，未执行网络、未读key或Gold。

- 最终runner SHA256：`d5cbf52cb9dc5ff30bdd13fe7de9c050751cec6413f4e69f31f49f2abc998d9e`，工作区与正式隔离runtime副本一致。
- `.tmp/common-three-arm-final-20261015/registration.json` SHA256：`0bc8fe290a67d3b3c047372e2685eb33cd5fed7c681ddd95da76df40233228ec`，登记hash收据一致。
- 正式锁环境 `D:/graghRAG-agent/.tmp/backend-quality-venv-20261012/Scripts/python.exe -B -` 执行只读审查，exit0。最初误用backend/.venv核依赖exit1（缺httpx2），保留为审计环境不匹配记录；已改用正式环境复核，不安装依赖、不修改任何环境。
- 实际调用最终`verify_registration`前后均通过：146源码文件、5个KG/store文件、全部登记原文、runtime snapshot、契约/计划hash、4份历史KG归档hash及7项依赖版本精确匹配。正式runtime4个KG JSON逐个等于永久`executed-isolation/kg`归档，不从生产索引读取。
- 在正式runtime研究模块路径下，离线逐题实际调用`resolve_a_work`六次，独立重算resolution与assembly后8000字符chunks，全部与机器登记相等；每次A执行前也由`map_reduce`调用该函数，并在任何不一致时停止。该事实没有评价选择是否科学正确。
- 重新逐字符拼接S块，等于规范全文；A14/S27/P0最多18，每轮59，三轮177；54个登记单元的题/臂/重复/顺序及每单元路径额度与实际`build_schedule`逐字段一致，三臂各位置均6次。
- 登记model_config逐字段满足flash、temperature0、thinking disabled、非流式、生成2048/预处理300、P0 global-mode false；common_budget逐字段满足8次、24000/192000字节、120秒、8192/65536/16384实际tokens、全局5400秒/177次。最终guard另实施global剩余尝试发前检查，父进程deadline传入worker；不能将这些静态核查等同所有故障分支行为测试。
- 正式登记保留来源/代码/治理/历史KG身份与预算；运行中仍须核实际wire model、usage、缓存与未知费用。字节限制不是发前精确token保证，模型名及fingerprint不是固定权重证明。

```yaml
contract_version: "1.0"
expert_skill: sci-skills-statistical-reporting
project_id: graphrag-paper-001
paper_family: M
stage_id: M2
task_id: null
task_status: COMPLETE
inputs_reviewed:
  - docs/contracts/2026-10-15-common-three-arm-evaluation.md
  - docs/plans/2026-10-15-common-three-arm-evaluation.md
  - docs/review/development-budget-20261014/inputs.json
  - backend/research/common_three_arm.py (final d5cbf52cb9dc5ff30bdd13fe7de9c050751cec6413f4e69f31f49f2abc998d9e)
  - .tmp/common-three-arm-final-20261015/registration.json
  - .tmp/common-three-arm-final-20261015/registration.sha256.json
  - .tmp/common-three-arm-final-20261015/runtime/snapshot.json
  - ".tmp/common-three-arm-final-20261015/runtime: all registered 146 code files, five KG/store files, source files and resolver modules."
  - "docs/review/development-budget-20261014/executed-isolation/kg: four permanent KG JSON files."
outputs:
  - docs/review/2026-10-15-common-budget-path-audit.md
evidence_status:
  - "EXECUTED_LOCAL: final locked interpreter read-only verification exit0; command/output retained in task tool transcript."
  - "VERIFIED_USER_MATERIAL: registration/code/source/governance/KG/dependency identities match final frozen assets."
  - "EXECUTED_LOCAL: all six final A resolver/assembly outputs match registration; S canonical slices and 54-unit schedule independently checked."
  - "NOT_EXECUTED: no remote inference, key/.env/Gold access, semantic scoring or scientific stage change."
  - "PENDING_VERIFICATION: actual runtime receipts and separate guard fault-behavior review."
assumptions:
  - "Result certifies this scoped KG path and registered A/S execution plan only."
  - "177 is a path attempts ceiling and 362496 a conservative declared output bound, not actual token consumption."
  - "Two source units, six questions and three repeats do not support independent-document statistical inference."
author_input_needed: []
manual_actions: []
quality_checks:
  - "PASS: final runner and registration SHA identities."
  - "PASS: all registered code/source/KG/store/snapshot/governance hashes and seven dependency versions."
  - "PASS: four runtime KG JSONs equal permanent archive JSONs."
  - "PASS: six actual automatic resolver reruns and exact A/S chunks."
  - "PASS: A14/S27/P0max18 and global177, 54 balanced schedule and unit path limits."
  - "PASS: model configuration/common caps match contract fields."
  - "BOUNDARY: no claim that this audit replaces independent guard tests, semantic evaluation or overall acceptance."
conflicts: []
conflict_resolution_status: NOT_REQUIRED
merge_permission: orchestrator_only
recommended_next_action: "Root combines this passing path/manifest audit with the separate final guard/code review, then executes only the already authorized frozen development registration if all gates are clear."
stage_acceptance_recommendation: PASS_CANDIDATE
```

下一步：编排者汇合本专项与最终guard/代码审查证据，全部无阻断时按已授权冻结登记执行。
