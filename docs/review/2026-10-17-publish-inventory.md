# 2026-10-17 Git/GitHub 提交范围盘点

本报告仅盘点待审范围，不是安全扫描或提交门槛通过证明。用户已授权本地提交和 GitHub 推送；本 Agent 未 stage、checkout、commit 或 push。

盘点脚本实际执行 exit0，最终限制在显式发布根，得到 840 个待审增量文件、19,164,816 字节（这是本报告增加本段之前的盘点快照，文档最终字节仍须重算）。753 个文件位于 docs/testing，backend/research 新增14个、backend/tests 新增或修改9个。机器清单在 `.tmp/publish-inventory-20261017/candidate-increment.json`、排除记录 `excluded.json`、统计 `summary.json`。所有候选标为 pending-content-security-and-final-gates；尚未执行新增内容凭据扫描。首次全树枚举过慢，已改限定路径，最终命令约4.6秒。

## 已核身份与范围

实际 `git branch --show-current` 返回 `master`；`git rev-parse codex/safe-snapshot-20261014` 返回 `0ae36f25c63cb9f483899992534af41bebf32089`。沿用此前独立安全分支策略，不能推送含旧环境文件历史的 master。

实际 `git ls-tree` 核实安全基线的两个 gitlink 为 harness-engineering `833ef5894074d61f0a46d1c5cca189f41eba9a41`、langextract `6542a98a67c7ffb60c161c888286cafda590bbe0`。本次不得自动携带它们的 dirty 内容或新指针。

当前改动包括 backend 配置、检索、生成、会话、路由、worker 和相关测试，以及 14 个新增 research Python 模块、7 个新增测试。研究模块属于实际可执行代码，不能为了沿用历史双90证据而漏装或从分母排除。R8 适配器及消费者实现位于 docs/testing 的冻结候选，不应误称已经集成到生产。

## 可审查白名单构建方法

1. 在独立发布 checkout 中以已审安全分支为父提交，保留原工作区及历史；禁止 master 合并或 cherry-pick 旧历史。
2. 用明确路径清单复制当前安全生产代码、测试、依赖配置和经过内容审查的规范、记忆、冻结证据。逐文件记录相对路径、字节数、SHA256、基线 blob 和待审状态。缺失或变化必须显式处理，不能仅 `git add .`。
3. `.tmp/publish-inventory-20261017/inventory.py` 是候选增量生成脚本；生成结果仅表示待审范围，不能自动批准文件。最终报告须记录实际执行退出码及产物后才能引用其数量。
4. 排除真实 `.env`、个人配置、运行目录、子仓库 dirty 内容、研究 heldout/Gold/原始 PDF/论文材料和未经审查的大二进制。`.env.example` 必须逐值检查，不能仅凭文件名放行。研究规范和执行代码可审查纳入；研究结果、评分包及证据正文另行审查，防止私密材料泄漏。
5. 冻结证据按权威 manifest 验证每个字节；不得修改归档内旧路径、日志或 manifest 来美化发布。运行库二进制不随源快照复制。

## 扫描与提交前检查

对显式候选执行离线凭据扫描，保留命中指纹及路径，避免输出原始值；逐项解释命中，禁止用忽略 baseline 直接跳过。另核敏感路径、私密资料、二进制 schema/文本及文件尺寸。旧扫描不能替代新增文件扫描。

当前生产代码不同于 2026-10-14 已测快照，必须运行固定完整范围的 backend 行/分支双90，以及其他适用子项目的有效证据核验、规定测试与漏洞扫描。若任一门槛失败或证据不足，本轮不得 commit/push；保留可审查白名单与阻塞记录，不删去当前业务改动借旧证据放行。

最终还须审实际 staged bytes、父提交、安全分支可达对象及已知凭据 blob 不可达性；推送后核远端 ref 与本地 commit 相同。当前这些均未完成，不构成发布通过。

## 增量安全核对的实际状态

精确模式补扫840候选中的UTF8文本，实际 exit0、0命中：私钥头、GitHub token、provider key、AWS access key及URL内密码。报告 `.tmp/publish-inventory-20261017/regex-findings.json` 不含原始值。此有限模式检查不能替代完整凭据扫描。

RustSec `rustsec-db.tar` 逐字节SHA256与归档db-receipt一致：`0c3e3b16dc0bdf62a446b2b7808a567bfcaab9f52fad6336899c1306eecbef2c`；记录来源 `https://github.com/RustSec/advisory-db.git`、commit `edb58f5974b83eb8302332821cb6d389777aa351`。只读读取1348个UTF8普通成员，拒绝link、绝对路径及穿越，不执行成员；这核对的是既有来源收据和本地内容，不是本轮联网签名验证。

已启动与此前相同detect-secrets工具的 `--all-files --no-verify` 增量分批扫描，包含候选及tar文本。提交门槛失败后按root要求有界停止，会话64568实际退出码1（中断）；脚本只在最终汇总后落盘，未形成完整或可审计partial结果。因此状态 **NOT_COMPLETE**，不能报告扫描0命中，也未生成安全批准allowlist。扫描和regex脚本仅写本任务.tmp，未stage或改Git历史。

本轮可交付的是逐项指纹候选清单、排除范围及已完成的有限安全核对。root已通知backend timeout无覆盖报告、frontend启动未完成，提交继续BLOCKED。下一次须先恢复提交门槛，然后以最终候选字节重新执行可逐批落盘的完整安全扫描及独立审查。
