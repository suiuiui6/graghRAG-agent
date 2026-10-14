# 2026-10-12 后端覆盖率测量范围独立审查

## 审查总结

本次后端统计范围通过独立复核：配置及最终 JSON 包含全部 89 个已盘点第一方生产 Python 文件，包含未导入的 research 实现与 scripts；未发现通过排除业务文件或 pragma 缩减分母。测量结果未满足提交门槛，不能声称后端测试通过或全项目覆盖率已验证。

问题统计：范围配置 Critical 0、High 0、Medium 0、Low 0；提交阻塞 2 项（双指标不足、全量测试失败）。本报告是测量范围审查，不是生产代码全面安全审查或漏洞扫描结果。

## 输入与边界

- 根 AGENTS.md、memory/index.md、memory/2026-10-12.md、docs/testing/README.md；该任务为聚焦测量范围审查，不触发 /goal。
- 配置：`docs/testing/coverage-backend-2026-10-12.ini`，SHA256 `4d9cc425396c80c16fe2e65efb4786e38f99b305d24f9f7a713fa8fa82922a70`。
- 固定输入清单：`docs/testing/2026-10-12-audit-inputs.json` 中 `production_files`。
- 最终 JSON：`docs/testing/2026-10-12-backend-coverage.json`，coverage 7.6.12，报告时间 `2026-10-12T18:21:41.456694`；测试日志：`docs/testing/2026-10-12-backend-coverage-tests.log`。
- 分支 master，基线 `46b202c`；工作区已有大量其他任务变更。审查者只写本报告，没有修改配置、源码、依赖或测试，也没有运行 pytest、模型或供应商 API。
- 读取 using-superpowers 后按其 SUBAGENT-STOP 条款跳过启动编排；读取 requesting-code-review 作为独立评审组织方式参考，当前审查已处于主任务派发的独立上下文，不再次派发评审。

## 范围与防规避核验

独立 `os.walk` 清单按目录分量剪枝 `.venv`、`tests`、`output`、`uploads`、`__pycache__`、`node_modules`，另排 `backend/research/test_*.py`。现存唯一该匹配文件 `test_deepseek_scope_pilot.py` 明确为 pytest 软件夹具，因此属于测试本身。生产 research 实现 6 个、scripts 2 个全部保留，不能因测试困难排除。

配置第 3 行 `source = backend` 只有与第 15 行 `include_namespace_packages = True` 配合才满足当前无 `__init__.py` 的 research/scripts 未导入文件发现需求。本地已安装 coverage 7.6.12 的 `coverage/files.py:516–540` 和 `coverage/inorout.py:547–559` 直接确认该机制；实际加载的配置为：

```text
source=['backend']; branch=True; include_namespace_packages=True
exclude_list=[]; partial_list=[]
```

空 `exclude_lines` / `partial_branches` 已实际覆盖默认列表，未采用默认 pragma 排除或部分分支豁免。最终机器报告核验：

```text
独立清单 = 固定输入清单 = JSON 文件数 = 89
missing=[]; unexpected=[]; excluded_line_count=0
固定清单中全部生产文件 SHA256 复核：hash_mismatch=[]
```

未被执行的文件确实进入分母，例如：

| 文件 | 行已覆盖/总数 | 分支已覆盖/总数 |
|---|---:|---:|
| backend/research/deepseek_scope_pilot.py | 0/265 | 0/110 |
| backend/scripts/check_imports.py | 0/19 | 0/6 |
| backend/scripts/purge_log_secrets.py | 0/41 | 0/16 |

后续每次测量应继续将最终 JSON 文件集合与预先固定清单做相等校验，报告缺文件或额外文件均须核实原因，不能只看 `source` 配置文字。本次未发现范围问题，因此无需要修改的 before/after 示例；无需以缩范围修正较低覆盖率。

## 提交阻塞及建议

### 🟠 High：双覆盖率未达到 90%

最终 JSON 原始计数：行 `8670/13238 = 65.49327693004986%`；分支 `2405/4446 = 54.09356725146199%`。两项均未达标。JSON 的 `percent_covered=62.62723365754354` 是合并指标，不可用作单独行或分支指标。

建议优先补充生产关键异常与授权边界的有效行为测试，再按相同 89 文件范围重测。不得删代码、弱化断言、增加排除或更新冻结数值来制造通过。

```python
# before：不能凭合并指标判断两个门槛
passed = totals['percent_covered'] >= 90
# after：分别按原始整数计数判断，且须先验证指标存在及分母非零
passed = (totals['covered_lines'] * 10 >= totals['num_statements'] * 9
          and totals['covered_branches'] * 10 >= totals['num_branches'] * 9)
```

### 🟠 High：全量测试未通过

最终日志为 `21 failed, 706 passed, 5 warnings in 90.37s`，不能将成功生成 JSON 等同于测试通过。建议主任务保留 pytest 的实际退出码与失败清单，先定位失败根因，再执行全量回归；本审查未独立重跑这些测试或裁定失败是否由本轮产品修复引起。

## 适用子项目范围与改进顺序

1. 保留当前固定生产范围和零 pragma 排除，修复失败并补有效测试；重测后再次核对文件集合、源码/测试/配置快照和两项原始计数。
2. 最终交付同时保留完整命令、实际退出码、日志与报告，不把本次独立静态复核表述为审查者执行了完整测试。
3. 前端 package.json 当前只有 dev/build/preview，没有 test/coverage 脚本；后端 89 文件结果不能代表前端或全项目覆盖率。其他可执行子项目的固定范围尚未全面确认，不能据此通过纯文档或全项目提交门槛。
4. Windows 仍为 `audit-only-windows`；本次未启用可信 CI 或机械提交阻断。漏洞扫描结论由主任务单独保留证据，本报告不冒充扫描通过。

## 实际审查操作

只读 PowerShell 读取上述规范、配置、清单及日志；`git status --short`、`git branch --show-current`；`rg` 定位本地安装 coverage 实现；使用 `backend/.venv/Scripts/python.exe -B -X utf8 -` 运行独立目录盘点、SHA256 对照、配置加载及 JSON 集合/计数核验（退出码均 0）。coverage 从 `.tmp/coverage-runtime-py312-20261012` 加载，未安装到或改变 backend 虚拟环境。最终 JSON 核验时间为本地 2026-10-12 18:22 左右。主任务负责合并本报告到 memory 接续记录，避免并发覆盖共享记录。
