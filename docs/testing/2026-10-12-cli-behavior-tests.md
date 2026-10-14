# CLI 行为专项验证

本轮由质量整改协调者分配，使用 test-driven-development 和 verification-before-completion；不执行全量测试或 Git 提交。所有权为两份新增 CLI 测试及本报告；协调者在确认空评测集缺陷后，另行授权 `backend/run_evaluation.py` 的最小入口校验。

## 场景及边界

- `backend/tests/test_pipeline_cli_behaviors.py`：真实临时 MinerU Markdown/content_list，V1/V2 选择、中文字符定位、YAML 属性、CLI 参数错误和 cached/pdf/url 分流；实际 LangExtract 公共数据类型、真实 JSONL/图谱序列化和页码/bbox/属性；MinerU 提交/轮询/超时/失败，真实临时 ZIP 写入、解压及清理。
- `backend/tests/test_evaluation_cli_behaviors.py`：供应商 JSON/markdown JSON/异常降级，提示词截断；真实 prompt 构造及 citation 自动评分，生成失败恢复、平均指标、来源/意图统计、评分边界和建议阈值；临时图谱读取、索引构建/不可用/空返回降级，中文 JSON 报告往返。
- 模型调用、requests/curl 运输、存储与 Embedding 初始化为边界替代；ZIP 解压用本地 Python zipfile 替代系统 unzip。它们不是供应商、真实 Chroma/模型或生产 unzip 验收。
- 未读取 `.env`，未触发模型 API，未修改现有 output、研究冻结或覆盖配置。CLI 入口通过真实 `main()` 与 argparse 验证；未使用 subprocess 启动 CLI，因此 `if __name__ == '__main__'` 包装行未覆盖。

## 缺陷红绿证据

空 queries 原先进入 `avg()` 后 `sum(...)/n` 除零。先添加 `test_full_evaluation_rejects_empty_queries_with_clear_input_error`，实测 `1 failed`、退出 1，栈定位 `run_evaluation.py:277` 的 `ZeroDivisionError`。协调者明确授权最小校验，随后在 `run_full_eval` 开头增加：

```python
if not queries:
    raise ValueError("评测查询不能为空 (queries must not be empty)")
```

未改变非空数据评分公式、旧报告或冻结数值。完整专项绿测 45 passed、退出 0。该变更待协调者独立评审和全量回归。

## 执行命令

仓库根目录、现有 backend/.venv Python 3.12；每条 pytest 命令均设置 `PYTHON_DOTENV_DISABLED=1`、`HF_HUB_OFFLINE=1`、`TRANSFORMERS_OFFLINE=1`。环境已有 `Unknown config option: timeout` 警告，本轮未更改其配置。

红测命令：

```powershell
backend/.venv/Scripts/python.exe -B -X utf8 -m pytest backend/tests/test_evaluation_cli_behaviors.py::test_full_evaluation_rejects_empty_queries_with_clear_input_error -q --tb=short -p no:cacheprovider --basetemp backend/tests/_sandbox_tmp/cli-behaviors-red-20261012
```

绿测命令（45 passed、1 warning、2.65s、退出 0）：

```powershell
backend/.venv/Scripts/python.exe -B -X utf8 -m pytest backend/tests/test_pipeline_cli_behaviors.py backend/tests/test_evaluation_cli_behaviors.py -q --tb=short -p no:cacheprovider --basetemp backend/tests/_sandbox_tmp/cli-behaviors-green-20261012
```

独立覆盖命令（设置 `PYTHONPATH=.tmp/coverage-runtime-py312-20261012`，coverage 7.6.12）：

```powershell
backend/.venv/Scripts/python.exe -B -X utf8 -m coverage run --rcfile=docs/testing/coverage-backend-2026-10-12.ini --data-file=backend/tests/_sandbox_tmp/cli-behaviors-final-20261012.coverage -m pytest backend/tests/test_pipeline_cli_behaviors.py backend/tests/test_evaluation_cli_behaviors.py -q --tb=short -p no:cacheprovider --basetemp backend/tests/_sandbox_tmp/cli-behaviors-final-20261012
backend/.venv/Scripts/python.exe -m coverage json --rcfile=docs/testing/coverage-backend-2026-10-12.ini --data-file=backend/tests/_sandbox_tmp/cli-behaviors-final-20261012.coverage -o backend/tests/_sandbox_tmp/cli-behaviors-final-coverage-20261012.json
```

覆盖运行 pytest 输出 45 passed、1 warning、6.05s，整个 coverage run 最终退出 0。源码发现/保存阶段需额外时间；曾在结束前导出的临时 JSON 只有 20 个已导入文件，已作废。确认进程退出后重新导出成功、退出 0，最终报告 90 个生产文件、excluded_lines=0；本轮并发整改新增生产模块自动纳入，沿用原固定配置，未改分母定义或主报告。导出另有既有 agentic_rag_mvp.py 无效转义 SyntaxWarning。

最终目标文件计数为 pipeline 181/182=99.450549% 行、29/30=96.666667% 分支；run_evaluation 232/233=99.570815% 行、57/62=91.935484% 分支（coverage 显示的混合百分比不用作两项指标）。固定范围总计行1392/13365、分支195/4502，仅反映这批专项测试，不证明后端全量或项目双覆盖门槛通过。独立 data_file 与 JSON 均在上述 sandbox 路径，未覆盖主报告；最终原始命令输出留在本次工具执行记录。

## 快照与交接

验证后 SHA256：

| 文件 | SHA256 |
|---|---|
| backend/pipeline.py | 330B237F2CF31530DC17CD58CB4F603B3B7F070FF95F6E9961FFD5FF099DB045 |
| backend/run_evaluation.py | 9FE27B91F5FD9CE0EF44E583A29100A32845D96A6D3FA6234A3681277BB2B1E4 |
| backend/tests/test_pipeline_cli_behaviors.py | 9D574E7F6127CC472508AABFE9C6A75317D1DAC38B1F8DEC5BF0C3924ECD2183 |
| backend/tests/test_evaluation_cli_behaviors.py | F811B1961D03DE51A093DAAE252E4D025AC34CE1038ED7461AAE6493BD64AE66 |

未改既有测试/覆盖配置，未提交。其他任务共享工作区且继续修改生产，因此专项覆盖总体不是最终交付快照。协调者负责独立评审、固定全量验证、规范回流及统一 memory 更新；本子任务不竞争修改 memory。
