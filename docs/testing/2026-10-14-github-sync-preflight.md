# GitHub提交与同步预检

状态：LOCAL_CHECKPOINT_COMMITTED。用户在已明确说明四个未修公告及提交门槛后回复“先提交”，本次按该明确接续执行本地诊断提交例外。实际检查点 `aca3ba012c398440f86ff323b0b8f61642c50b9d`，1688项实际变更，正常git commit exit0；未推送、未部署，原安全问题和双90门槛不降低。其他本地文件和子仓库修改保留。

## 已完成准备

- 分支master，HEAD `46b202c3e400741fd569f024412c0745f224a538`。远端公开仓库 `suiuiui6/graghRAG-agent` 默认main；已用GitHub CLI及正常Git凭据助手只读核验，未输出令牌。初次Git连接重置，HTTP/1.1+gh凭据助手重试成功，fetch只更新远端引用。
- 本地HEAD相对origin/main为左33/右80，相对origin/master左17/右80；80个本地提交尚未在任一已核origin分支。历史曾跟踪backend/.env.backup及.env_local_test，后续移除不会清除祖先blob。见[独立密钥审查](../review/2026-10-14-github-sync-secret-review.md)。直接push本地HEAD历史为Critical阻断，不能以一般漏洞豁免放行。
- 候选清单 `.tmp/github-sync-preflight-20261014/candidate-files.json`：1687个源码/测试/文档/必要验证日志，53,586,831 bytes。临时目录、缓存、本地技能/配置/状态、未验证gitlink及二进制发布材料排除，未删除这些本地文件。四个项目Agent定义包含在候选内。langextract与harness-engineering自身脏改动未提交。
- detect-secrets1.5.0完整默认plugins离线扫描当前候选，exit0；这不等于无finding。16248项经独立逐项hashed身份匹配与用途审查，未解释0、确认真实凭据0；其中2315项历史摘要未全部重算旧输入，不作所有内容/历史绝无密钥的声明。原始扫描及无值triage保留各自.tmp独占目录；新增本预检、审查与memory尚须纳入最终tree复扫。

## 门槛核实

| 检查 | 实际结果 |
|---|---|
| 三子项目既有双90证据绑定 | summarize_to90.py exit0；backend/frontend/rag_eval current_input_drift均空；原全量被测范围/原始计数不变；本轮未重跑全部产品测试 |
| 后端185项runtime最新公告扫描 | pip_audit exit1，Chroma1.5.9五原始记录/四唯一GHSA，无fix_versions |
| 后端206项全锁最新公告扫描 | pip_audit exit1，同上；首次扫描网络超时诊断保留，不冒称通过 |
| 原始GHSA | GHSA-2wm9-hf6c-p5cr、GHSA-36p7-vc44-83pf、GHSA-f4j7-r4q5-qw2c、GHSA-xph7-9rjv-w5fr |
| 当前候选密钥扫描 | 限定语义审查有解释，不覆盖80祖先；新增文件及最终checkpoint tree待复扫 |
| Git提交/推送 | 本地checkpoint aca3ba012c398440f86ff323b0b8f61642c50b9d，commit exit0；push NOT_EXECUTED，无远端发布结论 |

实际命令：独立audit工具对 `docs/testing/2026-10-13-candidate-registry-pins.txt`、`2026-10-13-to90-final-lock-pins.txt` 执行 `pip_audit --no-deps --disable-pip --timeout 30 --progress-spinner off --cache-dir .tmp/pip-audit-cache -f json`，正规网络审批，只读公告，无ignore/升级。报告/日志/退出码保留 `.tmp/github-sync-preflight-20261014/pip-audit-{retry,lock}.*`。原测试报告/审计工具均未削弱。

## 必须的下一步决定与安全路线

用户“先提交”后，本地提交已获得授权，不重复询问。此例外只适用于记录已知失败的本地checkpoint，不能写成安全验收通过，也不授权发布上述旧凭据祖先。未来GitHub同步仍须以下clean-parent路线及最终内容复扫；本轮不执行远端写操作。

本地执行收尾：原1687候选无意外内容漂移，增量预检/审查/记忆四文件detect-secrets扫描exit0且命中0；白名单扩至1689路径，其中1688产生实际变更。正常git add/commit均exit0，未使用--no-verify。按AGENTS对暂存差异执行api_key/secret/token关键词自检，26285处仅作定位计数、不输出匹配内容，凭据判断以独立审查和增量扫描为准。空白检查exit2，679处尾空白和87处末尾空行属于原始文档/冻结材料格式，未篡改其内容来消除非功能性提示。提交后summarize_to90.py exit0，三子项目current_input_drift仍空；暂存区为空，仅未验证gitlink与排除的本地资料/环境仍在工作区。实际命令/日志/输入白名单保存.tmp/local-commit-20261014，收尾文档另作本地记录提交。

[测试规范README第51行](README.md:51)明确“Chroma公告仍阻塞安全验收……不因此允许提交”。用户若要求当前状态入库，需要明确仅诊断checkpoint的该项例外；双90和真实密钥保护仍保持，不能默认豁免。若不批准则继续不提交，先完成替换与安全整改。

若明确批准：从已核远端parent建立独立 `codex/` checkpoint分支，保留原本地分支和工作区；准备当前完整待发布tree，独立核祖先可达范围不含上述80旧提交/凭据blob，对最终内容及新增报告复扫，再正常commit/push并核远端SHA。不能直接在本地HEAD上提交后push该祖先链，也不能force-push/rewrite原分支。该路线尚未实施，不假称已准备完整checkpoint tree或已同步；本次候选清单供范围审阅，不替代最终tree检查。
