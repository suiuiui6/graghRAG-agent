# 安全文件 GitHub 诊断快照独立审查

日期：2026-10-14。用户已授权“将安全的文件提交到Github”。本审查仅支持安全文件的独立诊断快照，不代表发布、部署或依赖漏洞修复完成。reviewer 不写发布工作区、不改源码/真实环境/历史、不提交或推送。

## 审查总结

1952个普通文件完整内容核验、16258个扫描命中逐项解释、16个覆盖率数据库文本补扫及三子项目被测输入核验均通过；当前文件范围无新增 Critical/High 阻断。**最终 staged tree 与根提交祖先/对象可达性待核**，当前不得将本报告当作最终提交已验收。已知4唯一 Chroma公告未修，双90有效也不等于 release准入。

目标：`C:/Users/14156/.codex/worktrees/safe-checkpoint-20261014/graghRAG-agent`，orphan分支 `codex/safe-snapshot-20261014`。来源为已锁定 `source-manifest.json`，1952普通文件，2个原远端 gitlink另外核。源HEAD `33adcc4` 只标来源身份，不作为新提交父节点，也不 cherry-pick旧提交。

## 已核文件范围与证据

- 独立按清单逐文件重算 target SHA256，1952项漂移0；同源工作区比对漂移0。`.gitattributes` 是发布侧新增的字节保留规则，不能误称其源路径已存在。
- 明确排除6项：`.claude/goal-state.json`、`.claude/settings.json`、`.lra/feature-list.json`、`.lra/init.sh`、`.lra/progress.txt`、`frontend/tsconfig.tsbuildinfo`。未将六份 `.l2-history` 数值 oracle当聊天删除；有效冻结完整性如下。
- 当前权威清单独立核：R5 284、R4b 110、R4 81、R3 61、R2 38，均缺失0/漂移0。R5内部两份复制历史 `freeze-manifest.json` 是旧原型清单，其相对旧根计算分别72缺失/6漂移、2缺失/15漂移；源目录同样如此，不能冒称它们是R5当前权威清单，也不是目标复制时新丢失。当前R5以r5-freeze-manifest为准，完整284已核。
- 2个 gitlink拟保持原远端基准：`harness-engineering` 对应833ef589…、`langextract` 对应6542a98a…。只保留既有指针，不携带实际子仓库内容或dirty更新；并不构成对子仓库历史的重新安全审计。

机器证据在 `.tmp/safe-github-publish-review-20261014/`：`tree-verification.json`、`inputs-verification.json`、`triage.json`、`coverage-text-scan.json`。全部独立脚本只写该目录。未执行发布快照中的历史archive/finalize脚本。

## 全候选扫描及新增命中

根完整扫描1952文件得到16258个 finding：Hex15587、Base64656、Keyword15。独立从目标原文件逐项重构每个 finding并匹配原扫描 hashed_secret，重构失败0、未解释0。没有仅复用旧1687文件结果，没有降低plugin阈值、修改filter或添加ignore baseline。

新10个命中全部位于 `.secrets.baseline`：136、145、154、163、172行各有 Hex/Keyword 两个类型。实际值位于 detect-secrets标准 `results.*.hashed_secret` 字段，是扫描器SHA1指纹，不是原始secret；此处仅解释baseline文件自身内容，不使用baseline跳过全树finding。

本轮分类数量：候选文件内容重算摘要4558、重放parser的IEEE754位模式10101、已核本地commit22、结构/用途可解释历史摘要888、lock/registry checksum653、registry公共签名10、registry/model revision6、合成sentinel及原代码标签/公告描述10、baseline fingerprint10。合计16258；历史摘要用途解释不等于全部重算旧输入，也不是所有未检出内容绝无secret的数学证明。

Base64全部逐项核：646个integrity字段有算法前缀及正确解码长度，另10个为registry `dist.signatures.sig`；未联网验签。Keyword原10项保持前次AST/来源解释，新增5项为baseline字段。无命中明文输出、无供应商凭据验证、无真实环境密钥读取。

## SQLite覆盖率数据补审

16个 `.coverage` 文件均只读以SQLite mode=ro打开。表集合限于coverage_schema、meta、file、context、line_bits、arc、tracer，未见应用业务表；数据库仍按覆盖率证据文件发布，不把它们冒称无内容二进制而跳过。

提取全部text列共1610行到reviewer私有 `coverage-text.jsonl`，对该文本用原工具27个plugin、`--no-verify --all-files`离线扫描exit0，finding0。原扫描与补扫plugin配置完全一致。内容解释包括coverage元数据、源码路径、context/tracer字段；未将数据库值输出到聊天，未执行数据库内内容。此补审针对逻辑schema/text值，不做数据库自由页取证或证明物理文件绝不曾含其他字节。

## 被测输入与双90有效性

| 子项目 | 被测输入核验 | 固定生产分母 | 行原始计数 | 分支原始计数 |
|---|---:|---:|---:|---:|
| backend | 171项漂移0 | 90 | 12698/13568 | 4154/4584 |
| frontend | 53项漂移0 | 29 | 927/957 | 853/913 |
| rag_eval | 22项漂移0 | 12 | 1722/1742 | 415/440 |

核验使用target中的最终被测输入清单并重新计算target代码/配置/测试文件指纹，原始两指标分别满足90%。本reviewer未重跑产品全量测试；验证的是已有证据对发布候选的有效性，不把root执行或历史执行改写成独立新跑。Chroma4唯一公告、安全原生边界、远程CI/分支保护与部署均不因快照上传关闭。

## 发布阻断与改进优先级

### 🔴 Critical：最终提交必须隔离所有旧凭据祖先与blob（待最终对象核验）

- 本地旧 `5e331ab` 曾追踪环境文件，`03f642e` 记录停止跟踪；远端origin/main本身也有历史环境文件blob。普通“远端干净parent”不能消除既有凭据历史，前次clean-parent建议已被新证据修正。
- Before：新提交继承本地或远端旧祖先，可能让既有凭据blob可达。
- After：orphan根提交，parents数0、rev-list count1，旧82提交及已知credential blobs均不可达；保留原master/远端历史不重写、不在此分支发布旧祖先。
- 最终须核实际staged/commit tree与上文1952文件清单、允许增量文档和2个既有gitlink一致。root准备提交身份后独立定点关闭；本reviewer绝不自行push。

### 🟠 High：最终文档增量与stage对象必须再扫描（待执行）

本报告及发布范围说明是在上述全树scan之后创建，不能声称已被16258结果覆盖。须纳入最终stage清单和增量扫描、再核没有生产输入变化；若最终tree其他内容改变则重跑适用检查。不得把文件审查当作对未审提交对象的自动放行。

优先级：先核最终tree/祖先并补扫新增文档，按用户既有授权发布独立快照；已知依赖/日志/适配器等问题继续保持原阻断状态，不将诊断快照宣传为安全发布完成。

## 实际命令与状态

```text
.tmp/backend-quality-venv-20261012/Scripts/python.exe .tmp/safe-github-publish-review-20261014/verify_tree.py
.tmp/backend-quality-venv-20261012/Scripts/python.exe .tmp/safe-github-publish-review-20261014/triage_publish.py
.tmp/backend-quality-venv-20261012/Scripts/python.exe -m detect_secrets scan --no-verify --all-files .tmp/safe-github-publish-review-20261014/coverage-text.jsonl
.tmp/backend-quality-venv-20261012/Scripts/python.exe .tmp/safe-github-publish-review-20261014/verify_inputs.py
```

最终各命令exit0。verify_tree首次因发布新增.gitattributes源路径不存在停止，已明确单列该规则后重新完整核验，未忽略其目标哈希。尚未独立核最终commit或远端推送状态；无提交/推送由reviewer执行。任务负责人归档文件证据并更新memory。
