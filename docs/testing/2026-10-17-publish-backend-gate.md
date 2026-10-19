# 2026-10-17 当前后端提交门槛复验

结论：**BLOCKED，禁止 commit/push**。当前工作区后端完整测试未通过且无有效双覆盖率报告；不能复用10月13日90文件证据替代当前104生产文件。执行模式 audit-only-windows。

本轮不修改产品、测试或阈值，保留其他任务修改。固定配置 `docs/testing/coverage-backend-2026-10-12.ini` 的 `source=backend`、全部原omit及空exclude/partial保持不变；新增14 research生产文件自然属于范围。186源码/测试/依赖锁/配置输入前后hash相同。

## 实际命令与退出码

证据目录 `.tmp/publish-backend-20261017/`：`run.py`、`commands.json`、`before.json`、`after.json`、`tests.log`、`export.log`。正常 require_escalated 调用，禁dotenv、模型网络；使用既有隔离backend-quality环境及独立coverage-runtime。

```text
.tmp/backend-quality-venv-20261012/Scripts/python.exe -m coverage run --rcfile=docs/testing/coverage-backend-2026-10-12.ini --data-file=.tmp/publish-backend-20261017/backend.coverage -m pytest backend/tests backend/research/test_deepseek_scope_pilot.py -q --tb=short -p no:cacheprovider --basetemp .tmp/publish-backend-20261017/test-temp
exit 1
.tmp/backend-quality-venv-20261012/Scripts/python.exe -m coverage json --rcfile=docs/testing/coverage-backend-2026-10-12.ini --data-file=.tmp/publish-backend-20261017/backend.coverage -o .tmp/publish-backend-20261017/coverage.json
exit 1: No data to report
```

全量约13%之后在 `test_error_handling_policy.py:38` 的 `_sources()` 遍历目录时被既有pytest-timeout硬退出。没有最终测试通过/失败计数，没有行/分支原始计数，不能称0%或达标。未跳过该测试、未提高/关闭timeout或调整范围。全量前已有失败，独立首失败探针20pass/1fail（exit1）：`test_local_login_refresh_and_disable`收到HTTP500，JSON解析失败，附Proactor selfpipe警告；根因未确定，不能直接归因产品。独立正常提权 `socket.socketpair()`＋`asyncio.ProactorEventLoop()` probe exit0，不能笼统称平台禁止socket。

首runner因旧测试产物遍历过慢、尚未执行pytest即中断；快照改为按conftest已有生成目录规则剪枝后重启，未排除生产源码。`run.py`最终汇总因coverage缺失抛FileNotFoundError，原始测试/export退出码已独立保存，无吞失败。

## 当前完整锁漏洞扫描

`audit.py`读取backend/uv.lock全部registry精确pin（206，不按平台或extra过滤），独立审计环境执行pip-audit `--no-deps --disable-pip --strict --index-url https://pypi.org/simple --timeout 30 --progress-spinner off -f json`，exit1。no-deps依据为完整精确导出，非缩范围。锁SHA256 `0b9618aede31fd0553ff10b845a2feb5a388d1e153c8e38549d769a3074dacf6`。

原始 `audit.json` 有5记录，均chromadb1.5.9，4唯一GHSA；PYSEC-2026-311重复两条，其他PYSEC-2026-3813/3814/3815，全部fix_versions为空。未ignore公告，未把隔离SQLite候选75包audit0替代现役完整锁审计；本扫描不覆盖原生组件完整SBOM。

下一步：只重开当前测试环境/目录遍历与500根因定位，保留完整scope和行为断言；修复或取得有效环境后重跑完整测试及双指标。此前不得本地提交或推送。
