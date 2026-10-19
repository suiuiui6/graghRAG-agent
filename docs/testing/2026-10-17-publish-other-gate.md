# Git/GitHub提交前其他子项目门槛（2026-10-17）

结论：**BLOCKED**。rag_eval完整全生产范围双指标通过；frontend完整测试执行环境受阻，不能以历史报告放行。本任务只验证，未修改产品、测试、覆盖配置、依赖锁；未提交、推送或部署，Windows为audit-only-windows。

实际证据在 `.tmp/publish-other-20261017/`，输入清单 `before.json`、`after.json`、`retry-inputs.json` 及最终 `summary.json`：输入前后无漂移。脚本 `run.py`、`retry.py`、`analyze.py` 保留命令及检查实现。测试禁用dotenv读取，未读供应商凭据或生产数据。

| 范围 | 实际执行 | 退出/结果 |
|---|---|---|
| rag_eval | 项目独立 `.venv/Scripts/python.exe -m coverage run --data-file=D:/graghRAG-agent/.tmp/publish-other-20261017/rag.coverage -m pytest -q --tb=short -p no:cacheprovider --basetemp=D:/graghRAG-agent/.tmp/publish-other-20261017/rag-temp`，cwd项目目录 | exit0，74passed，1原有Starlette警告，0failed；约9.47秒测试 |
| rag_eval导出 | 同一Python `-m coverage json --data-file=…/rag.coverage -o …/rag-coverage.json` | exit0；行1722/1742=98.8518943743%，分支415/440=94.3181818182% |
| frontend第一次 | `pnpm test:coverage --coverage.reportsDirectory=…/frontend-coverage` | exit1；PATH Node18.20.8缺失node:inspector/promises，不能验证 |
| frontend第二次 | PATH指定现有隔离Node22.23.3、同命令，reportsDirectory改为frontend-coverage-final | exit1；9个fork worker handshake timeout；0测试执行，生成行0/957、分支0/913仅诊断，不是有效业务覆盖证据 |
| frontend第三次 | 隔离Node22直接运行 `frontend/node_modules/vitest/vitest.mjs run --root frontend --coverage --pool=threads --maxWorkers=1 --coverage.reportsDirectory=…/frontend-coverage-threads` | 未完成。约3分钟无测试进度，核对PID9880的专属命令后终止；原生exit -1，无有效覆盖报告 |
| frontend锁依赖审计 | `pnpm audit --json --registry=https://registry.npmjs.org`，cwd frontend | exit0，完整345依赖，info/low/moderate/high/critical全部0 |

rag_eval生产清单由实际根目录全部非test Python枚举，共12文件，与coverage JSON文件集合完全一致，包含CLI/build_ground_truth及未导入文件，excluded0。配置保持source=["."]，omit仅测试/环境；没有通过缩范围或忽略分支取得指标。

frontend配置原样覆盖src全部ts/tsx及public全部js，双门槛各90。改变池类型/worker数量仅为Windows执行适配，未删测试或改断言。线程挂起的外层PowerShell退出0仅是写入exit文件成功，原生Node退出-1明确保存在frontend-threads.exit；不得将外层0称为测试通过。

原始日志与receipt：`rag-test.log`、`rag-test.receipt.json`、`rag-export.receipt.json`、`rag-coverage.json`、`frontend-audit.log`及receipt、`frontend-test.log`及receipt、`frontend-test-node22.log`及receipt、`frontend-threads.log`、`frontend-threads.exit`、`frontend-threads-termination.txt`。原始安全审计覆盖公开包公告，不证明浏览器行为或全原生供应链安全。

下一步：修复/确认前端Vitest worker运行环境，再使用完整固定范围重跑；协调者同时处理backend全量验证阻塞。双指标及规定测试证据齐备前禁止commit/push。本轮没有运行前端build、真实Chromium功能验证或rag_eval新的锁依赖audit，均不声称已完成。
