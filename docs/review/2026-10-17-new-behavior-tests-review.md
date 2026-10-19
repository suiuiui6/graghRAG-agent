# 2026-10-17 新增研究行为测试独立评审

结论：所审两文件未发现阻断问题；没有发现通过削弱契约、跳过断言、篡改覆盖范围或替换待测算法来投机覆盖。只读评审，没有修改生产或测试代码。

- `test_research_report_behaviors.py`：使用合成且 hash 绑定的 wire/registration/评价输入，执行真实汇总算法；断言精确 token/attempt 数、UNKNOWN 成本、失败状态、map→reduce 连接、输入/输出 hash、额外事实仲裁与元陈述分离、未验证的科研边界。篡改用例同时检查拒绝及不生成成功报告。Supervisor 仅替换付费子进程边界，明确验证命令环境、脱敏和失败/超时/过期停止，不冒称真实付费端到端验证。
- `test_research_pilot_budget_behaviors.py`：真实登记/依赖身份/源码/索引 hash、预算守卫、HTML/PDF 结构桥接和实际 SDK 均保留；仅模型 transport 使用本地 MockTransport。检查预算中止前保留 KNOWN 费用、字节超限不发请求、UNRESOLVED 零成本、坏来源拒绝、坐标真实性及异常退出恢复。合成 PDF 仅用于文件身份和已给定 XML 的桥接，不冒称验证真实 PDF 解析器。完整离线 preflight 在全新进程激活复制的真实 worker/bridge/SDK，检查原生模块落在复制根且不写 docs_store/KG。
- 隔离：socket 补丁均由函数级 monkeypatch 管理；pilot 和 preflight 子进程覆盖 connect/connect_ex/create_connection，report 覆盖 connect/create_connection。Supervisor 的 dotenv 仅允许读取 tmp_path 下明确生成的假凭据文件；没有读取真实 .env 或历史研究/Gold。生成模块在 finally 从 sys.modules 删除，SDK entrypoint 异常恢复有有效断言。

## 独立执行

证据：`.tmp/new-behavior-tests-review-20261017/{run.py,tests.log,summary.json}`。正常 require_escalated，quality 环境，dotenv 禁用，包根优先 PYTHONPATH，HF/Transformers offline；独立 basetemp，不加载 coverage、不改根任务正在运行的覆盖率产物。

实际 pytest 选择：

```text
backend/tests/test_research_report_behaviors.py backend/tests/test_research_pilot_budget_behaviors.py -q --tb=short -p no:cacheprovider --basetemp .tmp/new-behavior-tests-review-20261017/temp
```

通过 Python 子进程的 pytest.main 执行，完整命令及 exact exit 保存在 summary：**81 passed，25.75s，exit 0**。额外断言整个 pytest 会话后 socket connect/connect_ex/create_connection 身份与会话前相同，日志 `SOCKET_GLOBALS_RESTORED`。110 个相关生产/测试/依赖配置输入前后 hash 无漂移。

两测试 SHA256：report `f63de4bdfeef241dcd7690d4aa8480e692ebb6b67b137ab0b61679c85b1844a5`；pilot `6a2e81ac07fcad66ea2a6401ae3c1d135dfcf63cfe0cf2ee5d791274e1e51f4b`。

这是两文件专项行为与隔离评审，不代表全量测试、双覆盖率、安全扫描或提交门槛通过；没有执行 commit/push。
