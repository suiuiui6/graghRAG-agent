# 2026-10-17 发布增量扫描独立复核

## 结论与范围

本轮对已完成的 detect-secrets 原始结果进行独立语境复核：2189 个文本输入（843 个候选文件中的 841 个 UTF-8 文本，以及 1348 个单独提取的历史审计 tar 成员），5579 条命中均已重构 exact scanner SHA1，未发现无法解释的命中。另 2 个非 UTF-8 候选不在原文本扫描范围；后续以 GB18030 严格解码且 JSON 解析成功，在只读转码副本补扫 exit 0、0 命中，原文件未改。此结论表示这些命中具有可核对的非凭据语境，**不等于全部内容安全、依赖无漏洞或全候选可公开发布**。原始扫描、候选及排除清单均未修改；本 reviewer 未联网验证任何 key，未修改生产代码、Git 或历史归档。

扫描输入：`.tmp/publish-retry-security-20261017/detect-secrets.json`，SHA256 `7f4e6f6bf1c35d48108c21e05430b10e26dfc276cb6590e49aa2d5d937f0a652`。

候选清单：同目录 `candidate-increment.json`，SHA256 `0d419de199020b1fdca7d9ece7f5cbcb3b36a697bac77612c6ce368aa7330664`。逐条复核结果保存在同目录 `triage-final.json`；复核脚本 `triage.py`、`triage-r2.py`、`triage-final.py`。脚本在隔离 `.tmp/backend-quality-venv-20261012/Scripts/python.exe -B` 下执行，最终均 exit 0。此前语境辅助脚本一次因 Windows 路径归一化 KeyError 退出 1，修正后 exit 0，未改扫描结果。

## 命中分类

| 分类 | 条数 | 已核对证据与限制 |
|---|---:|---|
| RECOMPUTED_FILE_SHA256 | 4811 | exact scanner SHA1 对应的值与实际文件字节 SHA256 一致；不据此断言被哈希内容无风险 |
| DECLARED_ARTIFACT_DIGEST | 658 | 结构化摘要字段；历史对象并非全部重新读取，不算内容安全证明 |
| DECLARED_HISTORICAL_FILE_DIGEST | 47 | 历史源码/日志文件名到摘要映射，当前对象可能不同或不可用 |
| DECLARED_NATIVE_BUILD_DIGEST | 4 | NumPy 原生构建身份/发行元数据摘要；不代表原生安全审计 |
| DECLARED_SNAPSHOT_FILE_DIGEST | 36 | 文件快照摘要字段；不代表已核验历史内容 |
| AST_LOCAL_ARTIFACT_PATH | 2 | Python AST 中本地证据路径字面量，不是凭据字段 |
| VERIFIED_RUNTIME_FILE_PATH | 5 | runtime 清单路径键，实际引用文件存在且 SHA256 匹配 |
| STRUCTURED_PUBLIC_GIT_REVISION | 3 | 发行元数据/RustSec receipt 中提交字段，未重新联网核验提交可达性 |
| SQLITE_OFFICIAL_SHA3_EXPECTATION | 1 | Python AST 中用于 SQLite 下载摘要校验的 SHA3 期望常量 |
| DECLARED_SQLITE_SHA3_DIGEST | 1 | 发行包 SHA3 字段；此分类本身不证明其内容安全 |
| IEEE754_TEST_RESULT_BITS | 8 | 数值类型回读结果的 8 字节 binary64 bits 字段 |
| PUBLIC_RUSTSEC_CRYPTO_TEST_VECTOR | 3 | 提取的 RustSec 公告 PoC/测试输出常量，非仓库凭据 |
| 未解释 | 0 | 不作绝对无秘密声明 |

额外实际重算 `derived-composition.json` 的两个完整 runtime 清单：base 3347/3347、derived 3347/3347 文件 SHA256 一致。该核验仅证明输入身份，不能代替全部原生组件漏洞分析。

非 UTF-8 补扫覆盖 `docs/testing/sqlite-r8-final-independent-20261017/differential-final/public.json` 及 `differential-history/diff-r4-20261017/public.json`；原文件/转码副本的摘要、命令结果见 `.tmp/publish-retry-security-20261017/triage-nonutf8-receipt.json`、`triage-nonutf8-scan.json`。实际命令 `.tmp/backend-quality-venv-20261012/Scripts/python.exe -B .tmp/publish-retry-security-20261017/triage-nonutf8.py`，内部 scanner 使用 `--all-files --no-verify`。首次默认沙盒运行因 multiprocessing Pool 权限失败，未获得 JSON；普通 escalation 重跑 exit 0，两份补扫 0 命中，不将第一次失败记为成功。

## 仍需发布者完成的检查

1. 扫描后候选内容漂移发现 `backend/tests/test_development_scope.py`、`backend/tests/test_development_structure.py`。旧扫描不得绑定新字节，最后提交快照需要增量补扫；新增文件也需要检查。
2. 排除清单中的环境文件、个人配置、未审研究结果及原始/二进制材料不得自动拷入公开快照。scanner 未命中不是隐私、来源权利或可公开性证明；未审私密材料保持排除。
3. 对发布树本身再检查无 `.env`、凭据及不允许的历史对象可达；现役 Chroma 漏洞、安全例外以及全量双覆盖率等独立门槛不由本复核豁免。
4. 本复核没有批准 git commit/push；发布者需将最终增量扫描、覆盖率及快照审查绑定到实际准备发布的文件字节。
