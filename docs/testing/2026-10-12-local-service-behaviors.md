# 本地持久化服务行为验证

本轮接续 `docs/plans/2026-10-12-quality-remediation.md`，子任务只补有行为断言的本地持久化测试；先复现缺陷，再按协调者授权最小修复。沿用 test-driven-development、systematic-debugging、verification-before-completion。无提交、冻结资料变更或覆盖配置修改。memory 汇总和有效规范回流由协调者负责。

## 范围及真实依赖

新增 `backend/tests/test_local_service_quality_behaviors.py`，当前29个参数展开用例。真实依赖是临时本地 JSON/JSONL 文件、tar.gz 归档、Pydantic 模型、内存 asyncio 队列与后台任务；这些服务本身没有 SQLite 持久化，未为增加工具数量引入无关数据库。

- 反馈：重开 store 后字段、状态、统计、最近10条负反馈、按状态过滤与排序、删除、事件和审计落盘，及可选观察者故障。
- Webhook：订阅 CRUD、软删除、禁用/通配/精确订阅、坏 JSON/模型隔离、投递计数与历史、真实 HMAC 对精确请求字节签名、ping 返回长度与异常边界。
- 事件：真实事件日志、订阅不可读与队列满时保留事件、实际重试编排/投递 JSONL/失败次数、后台处理异常后继续工作、queue.join 计数、等待 get 或正在处理时的取消关闭。
- 备份：活动 KG 版本归档、跳过缓存/日志、清单和哈希、恢复内容与恢复前快照、路径穿越/外部符号链接拒绝、缺失/损坏归档、坏版本元数据后的 staging 清理、daily/weekly 保留与 manual 保留、清理错误和定时备份。

唯一外部 HTTP 边界全部 double：requests.post 与 httpx.AsyncClient，未调用真实 URL。重试延迟由立即返回且记录秒数的 sleep 替身验证，实际顺序1/5/25，不进行长等待。所有服务路径和当前工作目录均隔离到 pytest basetemp；singleton 用 monkeypatch 恢复。事件/审计/订阅/备份协作本身保持真实临时文件，不冒称供应商集成测试。

## 红测与根因

初次沙箱执行在 Windows asyncio 新建事件循环时阻塞。`-o faulthandler_timeout=10` 的实际栈为 `asyncio.proactor_events._make_self_pipe → socket._fallback_socketpair → accept`；尚未进入业务协程。Ctrl+C 仅终止该子任务自己的 pytest。随后通过 require_escalated 正常运行同样本地测试；该权限用于 Windows 本机 socketpair，外部 HTTP 禁止仍由测试实现。

```powershell
$env:PYTHON_DOTENV_DISABLED='1'
$env:HF_HUB_OFFLINE='1'
$env:TRANSFORMERS_OFFLINE='1'
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_local_service_quality_behaviors.py -k 'update_comment or history_skips or worker_continues' -q --tb=short --show-capture=no -p no:cacheprovider --basetemp backend/tests/_sandbox_tmp/local-services-red-escalated-20261012
```

实际结果：3 failed、23 deselected、1既有 pytest timeout 配置 warning，0.71秒，退出1。

1. FeedbackUpdate 定义了 comment，但 store.update 只处理 status，备注修改持久化后仍为旧值。授权修复：仅在 comment is not None 时赋值，空串可清空，不传则保留。
2. Webhook get_deliveries 把整个倒序读取循环包在一次 try 中，坏 JSON 行使更旧有效记录丢失。授权修复：文件读取失败单独返回空结果，每行 JSON/模型失败仅跳过该行，继续历史读取。
3. EventBus._delivery_loop 在 _deliver 成功后才 task_done，异常虽捕获但队列 unfinished_tasks 未释放；后续事件正常处理，queue.join 仍超时。授权修复：仅成功 get 后进入内层 try/finally 释放一次任务计数，处理异常/处理中取消都释放；get 前取消不调用 task_done。

## 后续诊断缺陷及最终回归

三服务最小修复后，以下专项实跑29例：26 passed、3 failed，5.46秒，退出1。原3缺陷及新增空串/取消场景均已通过；失败全部集中于 backup.restore 的错误诊断模型。

```powershell
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_local_service_quality_behaviors.py -q --tb=short --show-capture=no -p no:cacheprovider --basetemp backend/tests/_sandbox_tmp/local-services-green-20261012
```

实际发现 `RestoreResult` 没有 error 字段，但 backup.restore 在缺失/损坏/恶意备份失败时传入 error；Pydantic 默认忽略额外参数，导致诊断丢失。测试的 failed 状态已通过，error 字段断言抛 AttributeError。`routes/system.py::restore_backup` 同样访问 result.error，缺字段也会妨碍其400响应。报告主协调者后获得明确授权，仅在 `backend/models.py::RestoreResult` 添加 `error: str | None = None`，与既有 BackupResult 一致；保留他人模型改动，未移除诊断断言。有效规范回流由协调者处理。

最终实跑时间2026-10-12 19:49 +08:00，使用相同三项离线环境变量及 require_escalated Windows 本机 socketpair 权限：

```powershell
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_local_service_quality_behaviors.py backend/tests/test_phase2.py::TestBackupManager backend/tests/test_phase3.py::TestWebhookManager -q --tb=short --show-capture=no -p no:cacheprovider --basetemp backend/tests/_sandbox_tmp/local-services-final-20261012
```

结果：38 passed、1既有 pytest timeout 配置 warning，4.59秒，退出0。其中新测试29，既有 BackupManager6、WebhookManager3；没有调用旧测试中的 API 用例。新测试确保两种反馈备注（非空/空串）、事件处理前/处理中的取消关闭均有明确断言。此前独立运行同样9条既有用例也9 passed、退出0。

验证后 SHA256：

| 文件 | SHA256 |
|---|---|
| backend/services/feedback_store.py | 0ead47383879944400739da143b75d46c4537d6ccb2a65de266a8638a6994590 |
| backend/services/webhook_manager.py | 89487524ca880268ee8a9916141f25c775ea27a4827bc0a6d3baa7b78e4545a7 |
| backend/services/event_bus.py | 78c70fe9afb24f18406ec8751d9723b0da6fb65558a810ec501aef35ca843921 |
| backend/models.py | b8603e88ea3161de56a4a4bf3eb5c956bdc4bd15f7325be19acb197088d6d34c |
| backend/tests/test_local_service_quality_behaviors.py | 44ea8316aadc51688b08671e40fe7030c4830e9174770513cbefb53de924c33e |

`git diff --check` 对三services和新测试通过。未测全量覆盖率，不能把本专项结果当90%证据。独立审查与固定全量验证由主协调者组织。
