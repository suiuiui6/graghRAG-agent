# 2026-10-17 最终依赖复核与覆盖证据输入对账

本轮仅验证，不修改源码、测试、配置或锁文件，不运行 provider。新证据位于 `.tmp/publish-final-audit-20261017/`，包含完整命令、原始结果、退出码、锁/config 前后 hash、逐项制品比较、输入对账与 evidence-manifest。

## 当前锁审计

执行入口：

```powershell
.tmp/backend-quality-venv-20261012/Scripts/python.exe .tmp/publish-final-audit-20261017/run.py
```

四个真实子命令及结果分别保存在对应 `*-receipt.json`：

| 检查 | 完整范围 | 实际退出码 | 结果 |
|---|---|---:|---|
| backend pip-audit | 当前 uv.lock 全平台206个 registry 精确 name/version；208总条目含2个第一方非registry条目 | 1 | Chroma 1.5.9存在5条公告记录，按GHSA合并为4项；无跳过包 |
| rag_eval pip-audit | 当前 uv.lock 全平台23个 registry 精确 name/version | 0 | 无已知公告，无跳过包 |
| frontend pnpm audit | 当前锁依赖，官方 npm registry，报告345个依赖 | 0 | 五个严重程度计数均0 |
| backend uv lock --check | 当前 backend/pyproject.toml 与 uv.lock | 0 | Resolved 208 packages in 6ms |

pip-audit 用独立审计环境，参数为 `-r <全部锁包pins> --no-deps --disable-pip --strict --index-url https://pypi.org/simple --timeout 30 --progress-spinner off -f json -o <报告>`。这里 `--no-deps` 表示不重新解析已列全的锁包，并未缩小至当前平台或直接依赖；不修改业务环境。原始 warning（建议使用hash需求文件）保留，制品hash另行逐项对账；本轮未逐个下载994个制品，不把锁hash对比冒称下载验证或供应链签名验证。

Chroma四个唯一公告为 `GHSA-f4j7-r4q5-qw2c`、`GHSA-36p7-vc44-83pf`、`GHSA-xph7-9rjv-w5fr`、`GHSA-2wm9-hf6c-p5cr`。本次原始结果中 `PYSEC-2026-311` 出现两条同别名记录，因此原始记录数5与唯一GHSA数4分开报告。各记录 `fix_versions` 均为空。

**Chroma残留风险仍存在。本轮不是漏洞修复，也不构成生产准入。** SQLite隔离候选的通过不等于现役依赖已替换。包公告审计不覆盖完整CPython/SQLite/OpenBLAS/Windows CRT等原生安全面，也不证明所有公告可达或可利用。

## 锁内容及制品身份

基准为 `.tmp/publish-retry-declarations-20261017/before-uv.lock`，SHA256 `0b9618aede31fd0553ff10b845a2feb5a388d1e153c8e38549d769a3074dacf6`；当前 backend/uv.lock SHA256 `38ff460089d45739d2e2eb4fc91a04e93a7cba6085fd0e3628ecf3c5b7f00e4b`。

- **208个包名/版本全相同**。
- **994个包名/版本/制品文件名与对应hash全相同**；新增、删除及hash变化均0。
- registry从 `https://mirrors.aliyun.com/pypi/simple/` 迁至 `https://pypi.org/simple`，制品运输URL迁至pythonhosted；因此完整URL/source字典确有变化，不能声称它们未变。`lock-comparison.json` 保留严格URL比较的false；`content-comparison.json` 明确区分内容身份不变与运输地址变化。
- 本轮运行前后6个锁/配置文件hash相同，无审计引入的漂移；uv提示旧SSL_CERT_DIR无有效证书但检查退出0，日志保留。

## 历史完整覆盖输入复核

本轮重新枚举生产、测试与配置/锁的既定输入集合并计算hash，不以历史报告绑定变化后的代码：

- frontend对比 `.tmp/publish-retry-front-20261017/after.json`：**49/49相同**，新增/删除/变化均0。该历史全量命令退出0，29个生产文件范围一致，行927/957、分支853/913，分别高于90%。
- rag_eval对比 `.tmp/publish-other-20261017/after.json` 的自身子项目集合：**22/22相同**，新增/删除/变化均0。该历史全量命令退出0，12个生产文件范围一致，行1722/1742、分支415/440，分别高于90%。
- 审计结束后再算集合/hash仍相同。此次**没有重新执行前端或rag完整测试**，结论是已有同快照证据仍匹配这两个子项目；不据此代替后端最新全量验收。

## 日志边界

运行入口在所有四个子命令结束、summary与收据写盘后，控制台以GBK打印含NBSP的公告描述时触发 `UnicodeEncodeError`，包装脚本退出 **1**。这不是上述四项子命令的退出码；分别保留，不把包装退出1改记0。随后 `summarize.py` 用ASCII转义打印已有JSON、生成final-summary及证据manifest，退出0；未伪造/重写原始audit结果。

本轮未 commit、push、部署、迁移或改动现役依赖。提交与发布是否满足项目其他门槛，由根任务结合当前全量双覆盖率、凭据扫描和独立评审判断。
