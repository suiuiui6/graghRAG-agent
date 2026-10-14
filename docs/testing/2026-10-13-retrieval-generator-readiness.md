# 检索与生成行为补证（2026-10-13）

本报告对应 `docs/plans/2026-10-13-quality-to-90.md` 的检索生成任务。维护流程使用 TDD 与 verification-before-completion；未启动 goal/Harness。仅交付未提交工作区，未调用真实模型、未读取 `.env`、未改用户 output 或历史研究冻结。其他任务修改保持原样。

## 实现与有效行为

- 新增 `backend/tests/test_retrieval_generation_readiness.py`：供应商超时/连接/HTTP错误的有界重试及结构化降级；查询缓存、预处理、嵌入与重排；真实临时 SQLite 缓存、NetworkX 图、BM25；受保护证据去重、场景/指标/页码/表格救助；引用核验、原始模型输出、答案补全、无证据拒答、储能反驳与救助失败追踪。替代供应商与模型边界，未 stub 被测检索/生成目标函数来制造覆盖。
- 已授权最小生产修复：生成补全文字乱码恢复为中文，工具清单正则中的 U+0008 恢复为词边界；检索/生成中的 W4S1 类型别名以 ASCII 标识符边界判断，允许相邻中文并拒绝 `xW4S1`、`W4S1x`、`W4S1_`；中文别名含义、最低/最高成本入口及输出恢复。未重构整体流水线。
- `test_answer_completeness.py` 末三项乱码夹具改为真实中文/英文问题和来源文本，保留工具用途、别名含义、数值与引用断言，并断言输出不含乱码。
- 最后补充证据边界：短锚点不足以证明支持、场景必须一致、无关/损坏/无值指标不得进入储能比较、显式模型词需文本依据、无来源工具不得被补全、救助检索异常须记录 failed。

生产修复的真实红测保留于 [首次红测](2026-10-13-retrieval-generator-red.log)（4 failed/59 passed）、[别名及极值红测](2026-10-13-retrieval-generator-alias-red.log)（4 failed/3 passed/109 deselected）。r5/r6 的单失败是新库存测试问句没有现有摘要指标入口要求的“产量/率/MWh”等提示，改为实际适用问句“摘要有哪些产量指标”，未修改生产入口或弱化断言。历史日志保留。

## 最终验证

独立候选 Python 3.12：`.tmp/backend-quality-venv-20261012/Scripts/python.exe`；coverage 7.6.12 从 `.tmp/coverage-runtime-py312-20261012` 注入。固定配置 `docs/testing/coverage-backend-2026-10-12.ini` 没有变化，仍包含完整 backend 生产范围及未导入生产文件，没有新增忽略或缩减分母。

| 运行 | 结果 | 范围/证据 |
|---|---|---|
| r7 | 149 passed/7.18s，exit 0 | readiness + answer_completeness，修正库存问句后 |
| r8 | 160 passed/8.05s，exit 0 | 两文件最终测试快照；[日志](2026-10-13-retrieval-generator-r8.log) |
| r9 | exit 1，超时 | 同下述15模块；Windows沙箱 `asyncio` 创建 `socketpair` 时阻塞在 accept，[原始栈](2026-10-13-retrieval-generator-r9.log)；未跳过测试或改变timeout |
| r10 | 387 passed/1 warning/14.28s，exit 0 | 同15模块，获准沙箱外仅允许本机回环通信；[日志](2026-10-13-retrieval-generator-r10.log)、[退出码](2026-10-13-retrieval-generator-r10-exit.txt) |
| r10 export | exit 0 | [coverage JSON](2026-10-13-retrieval-generator-r10.json)、[导出退出码](2026-10-13-retrieval-generator-r10-export-exit.txt) |

警告为 Starlette `anyio.abc.BlockingPortal` 弃用提示。导出另观察到既有 `agentic_rag_mvp.py` 文档字符串无效转义的 SyntaxWarning。均如实保留。

| 模块 | 行原始计数 | 行比例 | 分支原始计数 | 分支比例 | excluded |
|---|---:|---:|---:|---:|---:|
| generator.py | 863/873 | 98.8545% | 407/426 | 95.5399% | 0 |
| retrieval.py | 1457/1493 | 97.5887% | 614/650 | 94.4615% | 0 |

比例分别按行、分支原始计数计算，没有把 coverage 混合 `percent_covered` 当单独指标。检索分支尚未达到局部95%参考目标；两模块均超过90%。**此专项不替代后端全量、其他子项目覆盖率、安全扫描、真实供应商集成或整体提交门槛。** 仍有未覆盖分支，完整名单见机器报告。

## 实际命令

工作目录仓库根；r10 通过 `require_escalated` 获准执行相同测试集合。r9 使用相同内容但 `r9` 数据文件/临时目录，在沙箱内因本机通信限制失败。

```powershell
$env:PYTHON_DOTENV_DISABLED='1'
$env:HF_HUB_OFFLINE='1'
$env:TRANSFORMERS_OFFLINE='1'
$env:PYTHONUTF8='1'
$env:PYTHONPATH='D:/graghRAG-agent/.tmp/coverage-runtime-py312-20261012'
$retrievalTests=@(
 'backend/tests/test_answer_completeness.py',
 'backend/tests/test_community_global_mode.py',
 'backend/tests/test_evidence_trace.py',
 'backend/tests/test_hybrid_retrieval_trimming.py',
 'backend/tests/test_kg_indexed_recall.py',
 'backend/tests/test_query_budgeting.py',
 'backend/tests/test_query_preprocess_guard.py',
 'backend/tests/test_retrieval_generation_readiness.py',
 'backend/tests/test_retrieval_precision_tuning.py',
 'backend/tests/test_retrieval_stage_metrics.py',
 'backend/tests/test_runtime_caching.py',
 'backend/tests/test_runtime_recovery.py',
 'backend/tests/test_source_control_integration.py',
 'backend/tests/test_source_control.py',
 'backend/tests/test_tail_latency_controls.py')
& .tmp/backend-quality-venv-20261012/Scripts/python.exe -X utf8 -m coverage run --rcfile=docs/testing/coverage-backend-2026-10-12.ini --data-file=docs/testing/2026-10-13-retrieval-generator-r10.coverage -m pytest @retrievalTests -q --tb=short -p no:cacheprovider --basetemp backend/tests/_sandbox_tmp/retrieval-r10 > docs/testing/2026-10-13-retrieval-generator-r10.log 2>&1
$testExit=$LASTEXITCODE
$testExit | Set-Content docs/testing/2026-10-13-retrieval-generator-r10-exit.txt
# 原始pytest退出码为0，单独保存，没有被导出成功覆盖。
& .tmp/backend-quality-venv-20261012/Scripts/python.exe -X utf8 -m coverage json --rcfile=docs/testing/coverage-backend-2026-10-12.ini --data-file=docs/testing/2026-10-13-retrieval-generator-r10.coverage -o docs/testing/2026-10-13-retrieval-generator-r10.json
$LASTEXITCODE | Set-Content docs/testing/2026-10-13-retrieval-generator-r10-export-exit.txt
git diff --check -- backend/generator.py backend/retrieval.py backend/tests/test_answer_completeness.py
```

上述 diff 检查 exit 0。r8 命令为同环境直接 `python -X utf8 -m pytest backend/tests/test_retrieval_generation_readiness.py backend/tests/test_answer_completeness.py -q --tb=short -p no:cacheprovider --basetemp backend/tests/_sandbox_tmp/retrieval-r8`；日志及原始退出码独立保存。无 Git commit/push/deploy。

## 冻结与交接

四归属文件在 r9 前到 r10 验证后 SHA256 相等： [前快照](2026-10-13-retrieval-generator-r9-inputs-before.json)、[后快照](2026-10-13-retrieval-generator-r10-inputs-after.json)，实际 Python 比较输出 `INPUT_HASH_MATCH True`。r9→r10 没有修改测试或生产代码。

| 路径 | SHA256 |
|---|---|
| backend/generator.py | CEC0DEB0165A6ED04D4F1C13547E77DBBC08A8E134C889985E1DCCFDE7FF1A3C |
| backend/retrieval.py | 2F0761DCB736F63BA6E688C9749057FB60EE419CE2F33541969E4E8CDE7BD0E1 |
| backend/tests/test_answer_completeness.py | 955DD4EED96F330468FEF9EA17F4C6C0F1E554DB23F316F05228C54888BB0E79 |
| backend/tests/test_retrieval_generation_readiness.py | 65B799915F5BA465929CEC2DDF6B0D7B4D13CCBBA4D22E5E160B45674A2B80E3 |

以上文件已通知协调者冻结，停止扩测试。协调者负责统一独立评审、受影响规范与 memory 回流，以及最终全量快照验证。旧的乱码 guard（例如生成异常识别、部分工具用途判定中的问号占位）仍可能需要有明确输入/契约的后续修复，本次未擅自扩大生产修改范围；不据局部覆盖率宣称全部功能问题已关闭。
