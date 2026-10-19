# 开发隔离与P0/A资源测定计划

依据：用户明确选择的下一步及[适配契约](../contracts/2026-10-14-development-isolation-adapters.md)。普通格式兼容/配置修复，复用已评审留出协议，不启用goal/Harness，不设计新方法。

1. 根代理修改.env唯一model字段（已完成，其他bytes相等）；model_coder独占active默认模型解析与相关测试，红绿及旧专项验证，不触碰历史冻结/Ollama供应商路径。
2. debugger已只读复现范围格式根因、P0路由及入库边界；独立reviewer先审契约/本计划。阻断关闭后coder独占新development_structure/scope模块与tests，陌生文档红绿后实际无Gold六题路由验证。
3. 原生P0隔离runner与预算transport另由coder独占新research模块及tests：独占源码副本、原件桥接、真实LangExtract/grounding/KG/文档登记、真实scoped路由；所有副作用落新运行根。若能力不支持有界SDK/精确grounding，先报真实阻塞，不用夹具替代。
4. 根代理核前轮73产物hash、新模块/有效环境锁身份、权限路径与生产资产快照；独立代码复审后先离线准备，再按执行前预检修订的72次总上限实际索引/P0/A（索引40/P0最多18/A14）。每次未知成本或截断停止，不重新试参，索引与查询分账。旧64设计保留历史，首真实请求前核修订额度；实际SDK可能使用httpx2，必须按有效模块核拦截/本地MockTransport，不凭包名猜。
5. 根代理离线汇总和冻结新产物；独立统计专家核输入链/usage/上限/三臂身份边界，记录已完成与未测项、更新memory。禁止以开发单次运行/AI Gold推断语义失败稳定性或新方法必要性。

文件所有权：根代理docs/contracts、docs/plans、新docs/review/development-budget-20261014、memory及.env模型字段；model_coder active模型选择+专属测试；结构coder仅development_structure.py/development_scope.py及两测试；隔离coder仅新development_isolation.py/development_budget.py及专属测试；reviewer仅自己的review报告。各方保留其他任务改动，历史文件只读。执行代码放backend/research，docs只放计划、收据、统计及代码快照数据。
