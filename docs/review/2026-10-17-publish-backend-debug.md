# 提交重试：后端登录 500 根因定位（2026-10-17）

## 故障摘要
- 旧全量测试首败是登录 GET 返回 500，随后 JSONDecodeError；正常提权并不能消除该失败。
- 单独运行 `test_local_login_refresh_and_disable` 为 1 passed / exit 0；全量收集后 fail-fast 为 20 passed / 1 failed / exit 1。私有插件强制 `TestClient.raise_server_exceptions=True`，没有修改产品或测试断言。
- 影响全量收集后的 Windows ASGI/asyncio 测试；不是已确认的产品登录逻辑错误。

## 根因分析
- 第一次偏离预期：`backend/tests/test_development_structure.py:14-15` 在导入期永久修改 `socket.socket.connect` 和 `socket.create_connection`。
- 数据流：pytest 全量收集导入该测试 → 全局 socket 被替换为 `deny_network` → auth TestClient 启动 AnyIO portal → CPython Windows ProactorEventLoop 创建 self-pipe → `socket.socketpair()` 在 `socket.py:623` 连接 `127.0.0.1` → 此测试模块的 `deny_network` 抛出 AssertionError。
- 测试设置 `raise_server_exceptions=False` 把该异常转换成 500；随后响应 JSON 解析失败掩盖了首次错误。析构 `_ssock` 缺失也是初始化中断的后果。
- 单独 socketpair 探针不覆盖 pytest 收集后的污染状态，因此不能用此前探针通过排除这一故障。

## 可执行修复方案（交由 coder）
- 移除模块顶层两条 socket 赋值；新增本文件 `@pytest.fixture(autouse=True)`，由 `monkeypatch.setattr(socket.socket, 'connect', deny_network)` 及 `monkeypatch.setattr(socket, 'create_connection', deny_network)` 在测试范围内安装禁网策略。
- 不删禁网断言，不改变产品登录代码，不改 FastAPI 返回值。
- 回归先同进程收集/执行 auth 与 development_structure 两模块，验证 auth 正常且结构测试仍禁网；然后用原全量覆盖命令重跑。
- 同类扫描另发现 `backend/tests/test_development_scope.py:7-8` 同样顶层覆写，须一起改为本文件 fixture。`backend/research/development_isolation.py:238` 是隔离执行机制的一部分，不能据此直接移除。本报告不把单点根因解释为所有剩余失败已修复。

## 环境核查及证据
- 正常提权 `uv pip check --python .tmp/backend-quality-venv-20261012/Scripts/python.exe`：exit 0，186 packages compatible。
- 安装 registry 包与 `backend/uv.lock` 对应版本没有差异；lock 跨平台包不全安装不构成污染，本地 editable langextract 不应计为额外 registry 包。简单名称规范化脚本中 boolean.py 与 boolean-py 差异需按 PEP 503 判读。
- 当前该环境实际 CPython 3.12.8 / SQLite 3.45.3；没有擅自替换为 R7 派生 profile。
- 私有证据：`.tmp/publish-retry-backend-20261017/raise.log`、`receipt.json`、`prefix.log`、`prefix-receipt.json`、`environment.json`；实际命令记录于 receipt。正常提权运行私有 `run_debug.py` 和 `run_prefix.py`，wrapper 均正常返回，内部 pytest 退出码分别 0 与 1。
- 调试使用 systematic-debugging 技能；只读产品，未提交或推送。

## 规范文档检查
建议在测试规范补充：禁止测试导入期永久覆写共享运行库；禁网策略通过 fixture 限定生命周期，不能误封 Windows asyncio 所需的本地 socketpair。此项应由修改者回流测试规范。
