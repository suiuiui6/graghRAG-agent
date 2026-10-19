# 2026-10-17 Pilot 预算及隔离行为测试

本次仅新增 `backend/tests/test_research_pilot_budget_behaviors.py`，不修改生产代码、统计范围、阈值或既有断言。使用合成来源及有效 Python fixture，不读取真实用户数据或凭据，不向 provider 发请求。

## 实际验证

最终运行：

```powershell
.tmp/backend-quality-venv-20261012/Scripts/python.exe .tmp/publish-retry-pilot-tests-20261017/run.py
```

脚本执行 coverage 原有后端配置下的三个 pytest 模块：新增 pilot 测试、既有 `test_development_isolation.py`、`test_development_budget.py`。PYTHONPATH 包含本地 LangExtract、backend 及独立 coverage 支持目录；启用 `PYTHON_DOTENV_DISABLED=1`、`HF_HUB_OFFLINE=1`、`TRANSFORMERS_OFFLINE=1`。

- pytest 退出码 **0**：**75 passed in 25.40s**，其中新增 **45** 例。
- JSON 导出退出码 **0**；现有 `agentic_rag_mvp.py` 无效反斜线转义 SyntaxWarning 如实保留在 export.log。
- 三项输入运行前后 hash 相同。
- 新增测试 SHA256：`6a2e81ac07fcad66ea2a6401ae3c1d135dfcf63cfe0cf2ee5d791274e1e51f4b`。
- `new_document_pilot.py` SHA256：`10720e7eadd7620ddd7e15f8767ede8d76bb666b819d4f7bc9fd1b6cf2961385`。
- `development_isolation.py` SHA256：`8144ef633f3a7cb8e897e6c11115211a7d31b6d9c970ad88264c8386272e2410`。

机器记录、命令、前后 hash、日志和 coverage JSON 位于 `.tmp/publish-retry-pilot-tests-20261017/`，以 `receipt.json`、`final-tests.log`、`scoped-coverage.json` 为最终证据。本次仅三模块测试，**不能替代全量后端验收或证明整体双90达标**。

## 行为断言

- 正常登记及索引资产 hash 验证；登记、源码、canonical、快照、依赖、治理、KG、资产及索引费用账本分别漂移时明确停止。
- 未解析 A 单元写入零费用不可评分结果；非零计划在缺索引冻结收据时停止。真实调度保持三次轮换、唯一单元及各 arm 的路径上限。
- 真正 hash 登记的 prompt profile 下，来源数量、标识、manifest、PDF 后缀、hash、长度及问题失败均在 worker 启动前停止。
- index 单次输入字节超限不触达本地 transport；单次或累计 token 超限在保存实际已知费用后关闭。
- 原生 SDK 通过本地 MockTransport，检查实际输出 token、thinking、单 worker、零 SDK 重试及 ledger usage。
- 独占源码复制绑定当前 runner、保留冻结输入；拒绝重用及漂移。有效 Python 模块导入后再以 hash 检出源码漂移。
- 合成 PDF 身份/页映射经过真实 source loader 和 bridge；canonical LF/Unicode、PositionMap 与 offset 不变，Document 按既有 bridge 契约剥除段边空白。无效 grounded 区间不被误记为来源证据。
- fresh-process 真正复制 backend/LangExtract 后执行 activate→原生 worker/bridge/LangExtract SDK→本地预检；child 在导入前拒绝所有 socket，并核对恢复、无 provider key、预检不可覆盖、输入字节合计、有效模块路径均在副本中，未生成真实 KG/文档库。
- 对 bounded SDK factory 的异常路径验证全局入口恢复。禁网 monkeypatch 仅本测试模块 autouse fixture，测试后自动恢复。

fresh-process 预检是隔离行为证据，其副本代码不计入主进程生产覆盖统计。没有通过将副本路径纳入分母或跨运行拼接制造达标。

## 首轮诊断

1. sandbox 首次执行 WinError5（pytest 临时目录访问），退出 **1**，保留 `pytest-first.log`；正常提权执行后不再出现。
2. 首轮正常运行 **32 passed, 1 failed**，退出 **1**，保留 `pytest-second.log`。失败是测试预期错误：既有 bridge 对 Document 段边空白执行 strip；已对照生产实现修为明确文档文本以及原始 PositionMap/offset 同时断言，未修改生产。
3. 扩展后 **39 passed**，退出 **0**，保留 `pytest-third.log`；再补六种准入测试后得到上述最终75例组合通过。

本次为已有行为补回归测试，无生产修改，因此不声称新增实现的 TDD 红绿循环。未 commit/push；最终提交门槛由根任务全量验证。
