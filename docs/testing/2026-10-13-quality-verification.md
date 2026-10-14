# 双覆盖率与漏洞整改：最终阶段证据

**结论：部分修复，整体提交门槛BLOCKED。无commit/push/deploy。** 本轮承接历史评估五项P0及用户授权的双覆盖率/漏洞整改；不修改历史研究冻结。最新结果取代[执行中记录](2026-10-12-quality-remediation.md)中的待测状态。

## 当前快照与验证

基线46b202c3e400741fd569f024412c0745f224a538；未提交输入快照`118c5c607d512f4d3c3387e3f98a1d7a6ec6b2b0a87f314fe9df8f05642da914`。158项源码/测试/锁/配置前后hash一致，固定生产清单90文件与coverage JSON完全一致，excluded_lines=0。覆盖配置未改；原89文件自然增加正式恢复的隔离守卫，不排除未导入生产文件。

新锁候选环境Python3.12.8/pytest9.1.1/coverage7.6.12，全量实际 **1065 passed、1 failed、14 warnings，57.83s，pytest exit1**；覆盖导出exit0，不覆盖测试失败状态。

| 指标 | 原始计数 | 百分比 | 状态 |
|---|---|---|---|
| 后端生产行 | 10985/13387 | 82.05721969074476% | 未修复（未达90%门槛） |
| 后端生产分支 | 3306/4514 | 73.23881258307487% | 未修复（未达90%门槛） |
| 前端/其他相关子项目双指标 | 未测 | — | 待验证 |

首次为89文件行65.49%/分支54.09%，当前生产快照及分母已随真实修复/恢复变化；上述是当前原始计数，不用混合行/分支总分代替。保持当前分母，至少另覆盖1064行和757分支才分别到90%；新代码变化后须重新计算。

唯一失败是`test_b0_preparation_is_not_execution`的真实冻结一致性检查。15个冻结条目中rag_query.py、models.py、doc_processor.py、uv.lock四项漂移；元数据仅证明磁盘hash，未证明加载运行身份。未改冻结/旧实验/断言，也不宣称新代码可复用历史实验结论。

## 分项修复状态

| 项目 | 状态 | 证据及边界 |
|---|---|---|
| 正式隔离守卫缺文件、SQLite路径边界 | 已修复 | 可追溯v2原样恢复；两组25passed，独立63专项包含此范围。仍是Python附加审计护栏，不代替OS隔离 |
| CLI规范、研究临时源码覆盖导出、测试角色分类 | 已修复 | JSON/退出语义保留，临时源码迁tests；最终JSON有效且全90文件纳入 |
| 本地行为缺陷 | 已修复 | mapping非对象、空评测、异常继承分类、自纠正末轮、词典大小写、空图端点、原文offset、空反馈备注、坏投递行、事件取消task_done、恢复error字段均有红绿及独立复核；不替代真实云供应商验收 |
| 新锁环境版本一致性 | 已修复 | uv sync exit0，实际186包/185 registry与锁版本漂移0；旧backend/.venv保留，新环境全量仅研究冻结失败 |
| 后端依赖漏洞 | 部分修复 | PyJWT/multidict/oauthlib升级；锁检查exit0。全锁206 registry与实际安装185 registry分别审计均仅Chroma1.5.9，5原始记录/4唯一公告，exit1，未ignore |
| 前端依赖漏洞 | 部分修复 | pnpm唯一有效锁、Node22.23.3冻结安装/构建exit0；剩高1/中3共4公告，未force Router7/Tailwind4迁移 |
| 安装/发布入口锁一致性 | 部分修复 | Docker/CI消费uv.lock/pnpm-lock，CI发布依赖四检查job，静态独立复核通过；Docker daemon缺失，镜像/远程CI待验证 |
| Bandit中危 | 未修复 | 90生产文件扫描141发现：中4/低137/高0，errors=[]，nosec=0，skipped_tests=0，exit1；四中危均table_index.py B608 |
| 研究冻结及运行身份 | 待验证 | 四条真实漂移未闭合，需新的研究版本/冻结/验证协议，禁止直接更新旧hash |
| 全子项目提交门槛 | 未修复 | 后端两指标不足、冻结失败，前端及其他覆盖证据缺失；Windows仅audit-only-windows |

无本轮项目被判“已不适用”；不为了凑分类将真实风险作废。原评估62项的其余范围未在本轮重新验收，不据此全数改状态。

## 剩余优先级

1. **P0，提交/发布阻断**：Chroma公告及compose独立服务的可达性/去留、前端高危及无同主版本补丁项需要明确升级迁移或有证据的风险处置；真实镜像扫描仍缺。不得套用旧Chroma例外或隐藏非零退出。
2. **P0，研究复用阻断**：为当前源码建立独立研究版本与运行身份决策，历史冻结不回写；当前研究验证失败保留。
3. **P1，双覆盖率**：下一批先retrieval（缺180行/126分支）、generator（164/133），再bot_handler（114/38）、conversation（88/38）、isolated_guard（87/43）及catalog/doc_processor。补有效成功/异常/恢复行为断言，不围绕数字写镜像测试；前端/其他子项目须先固定完整生产范围与覆盖工具链。
4. **P1，安全与交付**：逐处验证table_index.py:148/175/237/247的B608动态SQL风险，补输入/标识符边界后最小修复；真实Docker/CI运行、可信双指标门禁与保护分支另待建设。

## 可复核证据

- [机器汇总](2026-10-13-quality-verified-r2-summary.json)、[全量日志](2026-10-13-quality-verified-r2-backend.log)、[pytest退出码](2026-10-13-quality-verified-r2-backend-exit.txt)、[覆盖JSON](2026-10-13-quality-verified-r2-backend-coverage.json)、[导出退出码](2026-10-13-quality-verified-r2-coverage-export-exit.txt)。
- [输入前快照](2026-10-13-quality-verified-r2-inputs-before.json)、[输入后快照](2026-10-13-quality-verified-r2-inputs-after.json)、[命令/工具/扫描范围说明](2026-10-13-quality-verification-commands.md)、[实际安装元数据](2026-10-13-candidate-dependency-metadata.json)、[当前冻结漂移](2026-10-13-research-production-integrity.json)。
- [实际安装漏洞JSON](2026-10-13-candidate-pip-audit.json)、[退出码](2026-10-13-candidate-pip-audit-exit.txt)、[Bandit JSON](2026-10-13-quality-final-bandit.json)、[退出码](2026-10-13-quality-final-bandit-exit.txt)、[前端审计](2026-10-12-remediated-pnpm-audit.json)。Bandit首次180包含研究测试，当前141按生产角色排除该测试并增加正式守卫，不能宣称39个生产漏洞已修复。
- [独立最终复审](../review/2026-10-13-quality-final-review.md)：原增量独立63passed；候选测试适配独立75passed；工具顺序污染最后四行经静态复核，61组合结果明确由协调者执行。专项重叠不相加为全量数。

规范已回流backend/CLAUDE.md、企业/工程蓝图、bridge规范与LOCAL_SCOPE_V2说明；本报告不是供应商在线验收、镜像认证或研究实验结果。
