# 2026-10-17 测试隔离独立复核

范围：根 tests 遍历剪枝、development structure/scope 的 socket fixture、离线隔离回归和 auth readiness；只读生产及测试源码。使用 requesting-code-review / verification-before-completion 的独立检查方式。未修改产品、测试、锁或 pytest 配置，未 commit/push。

## 检查结论

所审隔离实现未发现阻断问题。`_sources()` 只将已在原函数结果范围外的 `BACKEND/tests` 提前剪枝，保留原过滤和 research 生产文件；`research/tests` 仍在范围。新增两个实际回归分别禁止对根 tests 调用 iterdir、确认未导入源码及 research/tests/helper.py 保留。没有清理测试树、改变 timeout 或覆盖范围。

两个 offline_network 是各自模块的 autouse 函数级 fixture，monkeypatch 在退出时恢复；导入模块本身不再改写全进程 socket。回归实际检查子进程导入前后 socket 方法身份及 Windows socketpair，并分别检查 create_connection/connect 确实拒网、上下文退出恢复；同进程 auth readiness 正常运行。测试级禁网仍针对原有两个入口，不声称新增了 connect_ex 等全网络边界。

## 实际执行证据

证据目录：`.tmp/publish-retry-test-review-20261017/`。使用既有 `.tmp/backend-quality-venv-20261012/Scripts/python.exe`，正常 require_escalated 权限，`PYTHON_DOTENV_DISABLED=1`、`PYTHONDONTWRITEBYTECODE=1`、HF/Transformers offline；不加载 .env。命令及原始退出码见 `commands.json`、`final-summary.json`，输出没有隐藏既知失败。

六文件命令（两个轮次使用相同选择，各自独立 basetemp）：

```text
python -m pytest backend/tests/test_error_handling_policy.py backend/tests/test_error_policy_source_walk.py backend/tests/test_development_structure.py backend/tests/test_development_scope.py backend/tests/test_offline_network_isolation.py backend/tests/test_auth_tenant_readiness.py -q --tb=short -p no:cacheprovider --basetemp <evidence>/temp-main|temp-final
```

- 初轮 `isolation-auth.log`：116 passed / 1 failed，14.33s，exit 1。唯一失败为 research 18 处 print，完整原断言正常报告，非源码遍历超时或 auth/socket 错误。
- 第二轮 `final.log`：117 passed，15.71s，exit 0；但 `final-before.json` / `final-after.json` 的 188 输入中策略文件被另一 Agent 并发修改，不把此轮声称为最终快照验证。其它 187 输入稳定。
- 第一组 `before.json` / `after.json` 检出策略文件及 pyproject 的并行修改，已明确通知主任务。print 政策修改由独立任务负责，本评审不将新 print 豁免作为隔离修复正确性的依据。
- 最终冻结复跑：`frozen/final.log` 为 117 passed，exit 0；`frozen/final-summary.json` 时间 2026-10-17T11:26:58.468872+00:00，`frozen/final-before.json` / `frozen/final-after.json` 全部 188 输入一致、drift=[]。该轮只将基于当前政策的执行结果与源码快照绑定，print 政策设计是否合理仍由其专属评审负责。

## LangExtract 失败的只读根因定位

不是必须经过测试收集或 sys.modules stub 才产生：相同环境中，全新 Python 子进程从仓库根直接 `import langextract`，得到 `__file__=None`、NamespaceLoader、`__path__=[D:/graghRAG-agent/langextract]`、`hasattr(extract)=False`（`root-import.log`，exit 0）；从 backend cwd 得到内层 `langextract/langextract/__init__.py`、SourceFileLoader、extract=True（`backend-import.log`，exit 0）。

安装的 `__editable___langextract_1_5_0_finder.py` 将真实包映射到内层目录，但通过 `sys.meta_path.append` 注册；默认 PathFinder 先发现根目录下外层同名目录并返回 namespace。因此 `bounded_langextract` 在 `backend/research/development_isolation.py:130` 读取 `lx.extract` 时失败。`test_pipeline_cli_behaviors.py:17` 的 fixture 和 worker quality 测试已有 prepend 内层路径及重新导入的处理，属于既有已知启动路径差异。

独立对照命令为 `python -m pytest <test_development_budget.py> <test_development_isolation.py> -q --tb=short -p no:cacheprovider --basetemp <独立目录>`：根 cwd 为 28 passed / 2 failed，5.29s，exit 1；backend cwd 为 30 passed，8.51s，exit 0。失败正是 budget:119 和 isolation:54。推荐主任务修正测试启动路径（明确 backend cwd 或包根路径优先），无需修改生产适配器或削弱断言。

## 追加：CLI stdout 政策八文件复核

主任务追加授权静态检查 `.tmp/publish-retry-cli-policy-20261017/source-manifest.json` 的八文件。manifest SHA256 为 `486e72429b81559f617e92eaf83be542f1b0dcda8d1407c6550e9392bae54819`；独立 `cli.py` 核全部八文件与清单一致、执行前后不变。`cli.log` / `cli-summary.json`：六个 `test_research_cli_output_policy.py` 行为回归 exit 0。检查覆盖 helper/nested function 拒绝、未注册 main 拒绝、ifmain else 拒绝、helper 默认静默、callback 事件、scope CLI golden stdout 与 packet 产物。

实际六个生产文件修改均为 keyword-only `progress=None`，回调发生在原 print 位置；CLI 在 main/ifmain 入口传相同 JSON 参数、ensure_ascii 与 flush 语义的 lambda。原工件写入和返回语义在当前改动范围内保留。注册表精确十个研究 CLI，没有整 research 文件夹放行；普通 helper 和嵌套函数的 print 仍被抓。

**P2，需修：main 函数签名的导入期输出被误放行。** 当前 `_library_print_lines` 将整个 `FunctionDef main` 作为允许根，默认参数与装饰器表达式也属于该根子树，但会在模块导入时执行，不属于 main body。独立探针 `list(_library_print_lines(ast.parse('def main(x=print(123)):\n    pass\n'), True))` 实际得到 `[]`，应报告第 1 行。当前八文件没有此种真实 print，但守卫的“仅入口体输出”契约存在缺口。建议仅将 `main.body` 作为允许根并补默认参数/装饰器回归；已将此 finding 交回主任务，未擅自修改其文件。

### P2 修订复验：已关闭

主任务修订允许根为 `main.body` 的语句，并排除其中直接定义的函数/异步函数/类；ifmain 的 body 同样处理。静态确认默认参数、装饰器与注解不再在允许根中，helper/nested function 仍被作用域边界拒绝，原 main/ifmain 内的 CLI callback 输出继续允许。

独立执行 `.tmp/publish-retry-test-review-20261017/r2.py`，使用正常提权 quality 环境、禁 dotenv，显式 PYTHONPATH 包根在先；完整命令、实际退出码及固定 16 文件前后 hash 均在 `r2/summary.json`。七个相关测试文件（原六文件加 `test_research_cli_output_policy.py`）共 126 passed，pytest exit 0，16 输入无漂移。新增三个有效回归逐项覆盖 default/decorator/annotation 的 import 期 print，旧 helper、nested、else 与未注册 main 断言保留。P2 在此输入快照关闭，未借其他 Agent 新增测试导致的全仓清单变化否定局部结论。

本报告不替代完整后端验收、双覆盖率或安全扫描，不据此允许提交。测试隔离及当前 CLI stdout 守卫修订在上述局部范围通过独立复核。
