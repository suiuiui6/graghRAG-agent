# 问答辅助模块行为补测与自修正边界修复

2026-10-12，专项范围：`query_optimizer.py`、`self_correction.py`、`evaluation.py`，补充旧版 `agentic_rag_mvp.py` 本地工具。输入：[整改计划](../plans/2026-10-12-quality-remediation.md)。未修改旧测试、冻结数据或覆盖配置；未运行全量，也不声明双覆盖率达标。

## 文件与行为

- `backend/tests/test_query_quality_behaviors.py`：49 项参数展开后的测试。查询词大小写、已有同义词去重、5/10 项注入上限、用户角色/语言/详略提示、原始及显式查询默认值、历史裁剪、代词原样/模型解析/启发式降级、HTTP 错误/JSON 错误/缺失响应字段降级。
- 自修正：真实临时 JSON 上下文、chunk 和嵌入 node 引用、重复无效引用、数字来源/小整数/重复数字、转折否定启发式、无需重生、错误提示传递、首次生成异常停止、持续错误预算上限、末轮成功和零轮预算正确/错误。
- 评测：检索 cutoff、重复召回、空 gold、空结果、排名 11 的 MRR；句子及引用标记指标；本地算法回调聚合、确定性耗时、中文 JSON 新目录落盘、空集与异常传播。`faithfulness` 仅验证当前引用标记计数语义，不把它当事实一致性评估。
- 旧 Agent：真实临时 nodes/edges JSON、真实 NetworkX 全图与 grounded 子图、类型与属性检索、结果限制、邻居 1/2 跳及默认关系、详情、全图统计、最终消息提取/2000 字截断、空响应与异常展示。启动时仅将两个明确的 KG 文件读路径重定向至临时文件，未打开真实 output。未新增实际 Agent 循环或停止策略测试，该演示仅有单次 `invoke` 展示函数。

## 红测与最小修复

修前 `SelfCorrection.correct` 仅在生成前校验；最后一次生成结束后直接失败返回。因此有来源的末轮正确答案仍被标 `final_passed=False` 并附警告，零轮预算的初始正确答案也直接失败。协调者明确授权后，仅修改该方法循环：初始答案及每次生成后校验，失败且预算耗尽时不再调用生成器。引用及数字算法、失败警告及异常返回轮数保持原行为。

真实红测日志摘要（修前，未改期望断言）：

```text
FAILED test_final_allowed_correction_is_validated_before_warning
    assert result.final_passed
E   assert False
E    CorrectedResult(answer_text='Budget 42 [c00001]\\n\\n[自修正警告: 经过 1 轮修正后仍存在未解决的问题，以下答案仅供参考]', correction_rounds=1, final_passed=False)
FAILED test_zero_correction_budget_still_validates_without_generator[Budget 42 [c00001]-True]
    assert result.final_passed is expected_passed
E   AssertionError: assert False is True
2 failed, 1 passed, 46 deselected, 1 warning in 1.61s
exit=1
```

上段为失败输出摘录，省略完整 dataclass 的 errors 列表，未作为原始机器报告。首次全部 39 项为 38 passed/1 failed，exit 1，1.61s；加入临时图谱后修前全部 47 项为 46 passed/1 failed，exit 1，57.32s。

## 实际命令与结果

仓库根 PowerShell，后端独立 `.venv` Python 3.12；每次设置：

```powershell
$env:PYTHON_DOTENV_DISABLED='1'
$env:HF_HUB_OFFLINE='1'
$env:TRANSFORMERS_OFFLINE='1'
$env:PYTHONIOENCODING='utf-8'
```

| 阶段 | 命令（均使用 backend/.venv/Scripts/python.exe） | 结果 |
|---|---|---|
| 末轮与零预算红测 | `-m pytest backend/tests/test_query_quality_behaviors.py -k 'final_allowed or zero_correction_budget' -q --tb=short -p no:cacheprovider --basetemp backend/tests/_sandbox_tmp/query-behaviors-20261012-red-zero` | 2 failed / 1 passed / 46 deselected，1.61s，exit 1 |
| 最终专项 | `-m pytest backend/tests/test_query_quality_behaviors.py -q --tb=short -p no:cacheprovider -o faulthandler_timeout=60 --basetemp backend/tests/_sandbox_tmp/query-behaviors-20261012-green` | **49 passed**，37.74s，exit 0 |

最终告警 9 条：pytest 配置 `timeout` 未识别 1 条（当前环境缺相应插件）；旧 Agent 模块 docstring 的 `\g` 无效转义在 8 次加载中各 1 条。未修改这些环境/历史模块问题，也不称无告警通过。

最终专项运行代码快照 SHA256：

- `backend/self_correction.py`：`BA6F77675FB9DAACEC78258120F57CDEFA4147ED59511AA5F979BA1A9940B976`
- `backend/tests/test_query_quality_behaviors.py`：`78F6406F87E9448B6F67E239441E674E16235526CA07DCBCC435F337C8AD636B`

## 验证边界与接续

测试使用本地真实临时文件、真实解析/计算/图算法。`requests.post`、`ChatOpenAI` 与 `create_agent` 仅在外部边界使用替身；requests Session 另设禁止外部 HTTP 的保护，环境模型 key 为测试占位文本。无 `.env` 读取、模型调用、真实 output 写入或研究 freeze 修改。这不是模型供应商、LangGraph 执行或端到端集成验收。

独立 reviewer 与全量固定范围覆盖验证由协调者后续执行；本专项不能代替 Git 提交门槛。未提交/推送。协调者负责规范及 memory 回流，避免并行覆盖共享文档。
