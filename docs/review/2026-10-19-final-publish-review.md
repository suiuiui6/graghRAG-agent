# 2026-10-19 安全快照交付独立复核

结论：本次指定增量秘密扫描、候选内容身份、暂存 blob、安全父链及被测输入/生产覆盖范围核对均通过，未发现新增发布秘密或清单漂移。结论绑定加入本报告等收尾文档前的暂存树 `bfedae0874c1881f89813e037efce88dfe2d31d8`；收尾文档须由主任务补扫并核对暂存字节后提交。本评审没有执行 commit/push/deploy，也不表示生产安全准入通过；后端依赖审计 exit 1、现役 Chroma 已知公告仍未修复。

## 范围与执行

独立上下文，只读项目源与隔离工作树 `C:/Users/14156/.codex/worktrees/safe-checkpoint-20261014/graghRAG-agent`，仅在自己的 `.tmp/final-publish-review-20261019` 和本报告写入。未改变源代码、测试、锁、覆盖配置或父任务清单。按 AGENTS 与实际 requesting-code-review/verification-before-completion 技能核查。全量测试由主任务执行，本评审独立读取原报告/日志并复算范围、计数与内容身份，没有声称独立重跑全量。

实际命令（工作目录仓库根）：

```text
.tmp/backend-quality-venv-20261012/Scripts/python.exe .tmp/final-publish-review-20261019/triage_delta.py
.tmp/backend-quality-venv-20261012/Scripts/python.exe .tmp/final-publish-review-20261019/verify_publish.py
.tmp/backend-quality-venv-20261012/Scripts/python.exe .tmp/final-publish-review-20261019/keyword_review.py
```

最终三个命令均 exit 0。Git 隔离工作树访问使用正常 require_escalated。verify_publish 内实际使用 `git ls-files --stage -z`、`git cat-file --batch`、`git ls-tree -rz`、`git rev-parse HEAD`、`git rev-list --count HEAD`、`git branch --show-current` 与 `git merge-base --is-ancestor`，无 Git 修改操作。此前评审脚本因未排除源码目录内测试文件两次断言失败，又因重建旧转码未采用 Windows CRLF 一次失败；均为独立验证器假设修正，未修改待发布文件或报告来让其通过。最终脚本按已生效的 Vitest/coverage 测试排除配置和旧转码实际文本写入语义完整重跑。

## 秘密扫描与内容身份

- 新清单 903 文件，旧已审清单 843 文件；其中 **833** 项 path/SHA256 完全一致，**70** 项新增或变化，差集精确等于 delta.json。903 项当前源字节与清单及实际暂存 blob SHA256 均匹配。旧 5579 条已审结果沿用其已核身份，本轮没有机械重扫旧结果或拿历史摘要覆盖变化文件。
- 新 delta-scan.json 的 **1165** 条命中逐一重构原扫描器匹配串并核对 hashed_secret 的 SHA1，重构失败 0。**676** 条与实际文件 SHA256 相符；其余 **489** 条逐一核对引用文件、锁定旧 manifest、safe-parent baseline_blob 或原扫描/转码收据。未解释项 **0**。尤其旧清单中的 baseline_blob 已与真实安全基线 ls-tree 的相应 blob ID 核对，不因“像摘要”就忽略。摘要分类只说明命中内容身份，不等于被摘要内容已经安全审计。
- 2 个非 UTF8 public.json 与旧 source_sha256、当前暂存字节相等；严格 gb18030 解码及 JSON 解析成功，按 Windows CRLF 重建转码后 SHA256 与旧零命中扫描收据及转码文件相等。
- RustSec tar 原字节匹配 db-receipt archive_sha256、旧候选与暂存字节；来源登记为官方 advisory-db Git 仓库、commit `edb58f5974b83eb8302332821cb6d389777aa351`。**1348** 个普通成员逐一与旧已扫 tar-members 内容 SHA256 对照一致，均严格 UTF8；无软/硬链接、绝对路径或 `..` 路径穿越。这里核对本地来源收据和字节，没有声称重新联网验证上游。
- AGENTS 关键词自检实际捕获 2716 行，文件 SHA256 `54d2ddd9e290d94d09e5b037232ca05f75e0d8e7c88b06facba9d4f9f0763be2`。独立对捕获运行 KeywordDetector 得 8 个实际匹配：7 个明确合成/占位/拒绝默认值，另 1 个对照生产预算测试 AST 与 bounded_langextract/SDK MockTransport，确认仅离线测试夹具。无未解释项；不把业务 token 词当凭据，也不将关键词自检冒称完整秘密扫描。评审输出不包含疑似凭据原值。

## 暂存区、父链与验证范围

实际读取全部 **2832** 个普通暂存 blob，按 Git blob header+bytes 重算 SHA1 并逐一取 SHA256；差异路径集合精确等于 903 候选。普通文件模式合法，无 `.env` 或非 example 环境文件。两个 gitlink 保留安全基线值：harness-engineering `833ef5894074d61f0a46d1c5cca189f41eba9a41`，langextract `6542a98a67c7ffb60c161c888286cafda590bbe0`。

分支为 `codex/safe-snapshot-20261019`，HEAD 为安全父 `0ae36f25c63cb9f483899992534af41bebf32089`，可达提交计数 1；`merge-base --is-ancestor 33adcc4cbd26bb6cd6b519c038fe2cad68baea59 0ae36f25c63cb9f483899992534af41bebf32089` 实际 exit 1，master 不在安全父链祖先中。

独立从完整暂存路径枚举生产文件，按现有配置排除测试、依赖和产物，和原 coverage JSON keys 精确集合相等；没有只按已导入文件或候选变更文件取分母。前端 src 内 `*.test.ts` 和 rag_eval 根目录 `test_*.py` 按已有配置排除，非新增排除。

| 子项目 | 生产文件 | 被测输入逐个与源/暂存核对 | 行原始计数 | 分支原始计数 |
|---|---:|---:|---:|---:|
| backend | 104 | 195 | 14424/15499 | 4744/5222 |
| frontend | 29 | 49 | 927/957 | 853/913 |
| rag_eval | 12 | 22 | 1722/1742 | 415/440 |

各两项按整数 `10*covered >= 9*total` 独立复算达标，backend/rag excluded_lines=0。原日志 backend 1803 passed、frontend 122 passed、rag_eval 74 passed，原测试/导出退出码与源前后收据见永久 publish-gate 证据；本轮只证明这些执行与当前暂存内容绑定，不额外声称所有 API 已逐个真实供应商验收。Windows 仍为 audit-only-windows，未验证远程 CI/保护分支机械门禁。

## 机器证据及后续

- `.tmp/final-publish-review-20261019/verification.json`，SHA256 `39182d4bbaf163806614fd568997b14df4ddbd2b4a97efe085eb16b11f37a0fd`：候选/暂存/父链/范围/计数/非 UTF8/tar 汇总。
- `.tmp/final-publish-review-20261019/triage-verified.json`，SHA256 `b2f9e3e12a4aaa52c43cb8acbfb385a31e659319608e70cc9d56474f16f20790`：1165 条路径、行号、精确扫描指纹和逐项来源分类；无匹配原值。
- `.tmp/final-publish-review-20261019/keyword-review.json`，SHA256 `98a771d671bf91b4e18dc57a523ca30af309375f13476c0cce86e86078d9d303`：关键词上下文分类和匹配指纹；无匹配原值。

主任务可将汇总复制到永久证据，并对本报告及新增归档/交付元数据做最后补扫和暂存身份核对；若被测源/测试/配置变化，须重新执行适用验证。当前评审未修改 memory，交接由主任务统一回流，避免并发覆盖。本报告只批准所核安全快照内容和证据一致性，不撤销已知依赖漏洞、不授权生产部署。
