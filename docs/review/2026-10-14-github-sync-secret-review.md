# GitHub 同步候选密钥扫描独立审查

日期：2026-10-14。只读审查 `.tmp/github-sync-preflight-20261014/candidate-files.json`、candidate-tree 与 detect-secrets.json。1687个候选文件内容指纹全部与清单一致；16248个扫描命中全部逐项重构并对照扫描器 hashed_secret，匹配失败0。未输出命中值、未查询供应商、未读取真实环境配置、未改候选/扫描插件/过滤器/旧 baseline，也未提交或推送。

## 审查总结

当前候选命中在限定语义审查范围内全部有解释，未解释0，确认真实凭据0；这不是对所有文件内容或历史提交“绝无密钥”的证明。🔴 Critical 发布阻断1项：既有本地提交历史含已知凭据追踪事件，当前文件扫描不能授权发布该历史。另有2315项历史产物摘要仅按结构与用途解释，未全部重新取得旧输入计算其数值。

逐项无值记录：`.tmp/github-sync-secret-review-20261014/triage.json`，每项仅保存 path、line、type、classification、证据说明；不保存匹配明文或扫描器的匹配摘要。复核脚本 `triage.py` 只在内存匹配值，调用 KeywordDetector.analyze_string，不调用可能联网验证的 analyze_line/verify。扫描输入自身的内容绑定指纹存于该机器记录，不作为匹配明文输出。

## 当前候选分类

| 分类依据 | 数量 | 限制 |
|---|---:|---|
| 对候选内容重算的文件 SHA256 | 3131 | 文件指纹，不证明旧历史内容 |
| 重放数值 parser 后重新计算 IEEE754 bytes | 10101 | helper-oracle 的 binary64 位模式，不是凭据 |
| git cat-file 验证为本地 commit 对象 | 22 | 验证对象身份，不代表提交历史安全 |
| 结构化历史文件/冻结/请求摘要与恢复脚本预期摘要 | 2315 | 用途有解释；并非全部重算历史输入 |
| lock/registry 完整性校验与 checksum | 653 | 646个 Base64 integrity + 7个 hex checksum |
| registry dist.signatures.sig 公共签名 | 10 | 精确 finding匹配、字段用途与Base64解码长度核验；未联网验签 |
| registry gitHead / model cache snapshot revision | 6 | 公开版本标识字段，不是认证凭据 |
| 关键词：合成 sentinel / 默认值拒绝比较 / token_type标签 / 公告描述 | 10 | 逐项核 AST 或结构化来源，见下表 |
| 未解释 | 0 | 仅指本次16248个 finding；不覆盖所有潜在未检出秘密 |

Hex 15582、Base64 656、Secret Keyword 10总计16248。Base64全部逐项核验：646个 exact finding 对应 integrity 字段，算法前缀与解码长度一致；另外10个均为 registry 的 dist.signatures.sig。没有以高熵、路径名称或“provider detector零”单独判定误报。

## 关键词逐项核验

| path | line | type | 分类 |
|---|---:|---|---|
| docs/review/development-budget-20261013/verify_offline.py | 10 | Secret Keyword | 离线 unittest.mock.patch 验证脚本的显式 sentinel literal |
| docs/testing/2026-10-12-bandit.json | 1494 | Secret Keyword | B105报告引用 jwt_middleware 默认值拒绝比较；源码AST为比较条件，不是实际环境密钥 |
| docs/testing/2026-10-12-bandit.json | 3353 | Secret Keyword | B106报告引用 auth_service 的 token_type 枚举标签；不是 access/refresh token值 |
| docs/testing/2026-10-13-quality-final-bandit.json | 1494 | Secret Keyword | 同上，默认值拒绝比较 |
| docs/testing/2026-10-13-quality-final-bandit.json | 2572 | Secret Keyword | 同上，token_type 枚举标签 |
| docs/testing/2026-10-13-to90-final-bandit.json | 1494 | Secret Keyword | 同上，默认值拒绝比较 |
| docs/testing/2026-10-13-to90-final-bandit.json | 2572 | Secret Keyword | 同上，token_type 枚举标签 |
| docs/testing/2026-10-13-to90-wave3-bandit.json | 1494 | Secret Keyword | 同上，默认值拒绝比较 |
| docs/testing/2026-10-13-to90-wave3-bandit.json | 2572 | Secret Keyword | 同上，token_type 枚举标签 |
| docs/testing/2026-10-12-pip-audit-installed.json | 1 | Secret Keyword | 值仅位于 vulnerability advisory description，不在配置/credential对象 |

核验没有仅因“Bandit报告”而放行其内容；实际追到候选 `backend/middleware/jwt_middleware.py:95` 的拒绝比较及 `backend/services/auth_service.py:113,137,156` 的 token_type 参数。合成 sentinel 已核 literal、offline patch调用及使用方向，未将任意 provider形状字符串直接归类测试数据。

## 问题清单

### 🔴 Critical：禁止把含既往凭据的本地祖先历史直接推送

- 位置：本地 commit `5e331ab` 曾追踪 `backend/.env.backup`、`backend/.env_local_test`；commit `03f642e` 标题为“security: 停止跟踪仓库内真实凭据，强化 .gitignore”。本 reviewer 用 `git show --format=fuller --name-only` 亲核提交元信息与文件名，没有读取历史文件值或补丁。
- 根另核本地有80个尚不在任一 origin远端分支的提交。本 reviewer未独立穷尽该80历史；此次16248 finding是当前候选树扫描，不是历史扫描。
- 风险：后续停止追踪不会从 Git祖先删除原 blob；直接 push本地HEAD可能把已知凭据历史首次发布。凭据是否有效、已轮换或已过期没有在本次审查验证，不能用“当前扫描通过”降低发布风险。
- 建议：从已核远端干净 parent建立新 checkpoint分支，只加入已审当前候选快照，保留原本地分支，不重写/发布其旧祖先；提交前复核最终 tree和祖先可达范围。不得把凭据历史风险混入一般漏洞豁免。
- Before：直接推送当前本地 master及其未发布祖先。
- After：经过明确审查的干净 parent → 新 checkpoint提交 → 独立分支发布；原分支留在本地。该方式仍须满足用户授权、项目扫描/覆盖门槛及其他安全决策。

## 优先级与验证记录

1. 先排除旧凭据祖先可达性，再对最终checkpoint树与新增审查报告重跑扫描；本报告创建后未纳入先前1687文件树，需根纳入最终候选扫描。
2. Chroma公告安全门槛仍由项目规范约束；密钥finding解释不会豁免依赖漏洞、覆盖率或发布准入。
3. 保留历史摘要的解释与重算区别；若最终候选改变，重新绑定文件指纹和扫描结果。不要将本报告变成全局ignore baseline或弱化plugin/filter。

实际验证命令：`.tmp/backend-quality-venv-20261012/Scripts/python.exe .tmp/github-sync-secret-review-20261014/triage.py`，最终exit0，候选漂移0、finding重构失败0、未解释0。辅助安全上下文脚本只输出字段路径、AST标识符和分类特征；一次早期交互式命令语法失败已改用脚本，不作验收证据。只读本地 Git对象命令exit0；没有 fetch/push或供应商验证。
