# 本轮 Phase 2 验证记录

日期：2026-10-12（Asia/Shanghai）。在 `backend/` 使用项目 `.venv/Scripts/python.exe` 执行：

```powershell
$env:PYTHON_DOTENV_DISABLED='1'
$env:HF_HUB_OFFLINE='1'
$env:TRANSFORMERS_OFFLINE='1'
$env:PYTHONDONTWRITEBYTECODE='1'
& .venv/Scripts/python.exe -m pytest tests/test_phase2.py -k 'not Endpoints' -q --disable-warnings --tb=short
```

实际结果：**5 failed, 28 passed, 6 deselected, 1 warning in 8.01s**，退出码 1。

| 失败用例 | 实际断言 |
|---|---|
| TestCatalog.test_build_catalog | total_entities 为 0，预期 >= 3 |
| TestCatalog.test_search_entities | 未检出预期预算实体 |
| TestCatalog.test_list_entities_by_type | total 为 0，预期 >= 1 |
| TestKgExporter.test_export_kg_json | nodes 为 0，预期 >= 3 |
| TestQualityMonitor.test_compute_quality | grounding_rate 为 0.0，预期 > 0 |

这组测试使用本地临时文件，不调用外部模型或 MinerU。排除的 6 个 Endpoints 用例没有运行。

判读限制：`test_phase2.py:91` 前后通过 chdir 切换临时目录；部分服务使用模块级路径。当前未对路径绑定和版本产物夹具做独立根因复现。上述结果说明本轮测试未全绿，不能单独推出生产数据损坏、备份不可用或目录功能必然失效。已通过的用例也不能替代真实服务部署和灾备演练。
