# rag_eval 全生产范围验证（2026-10-13）

结论：本子项目固定全部 12 个第一方生产 Python 文件，最终 74 passed / 0 failed / 0 skipped，行 1722/1742 = **98.8518943743%**，分支 415/440 = **94.3181818182%**，分别超过 90%。锁定的 23 个公开依赖审计未发现已知漏洞，锁/实际安装版本漂移为 0。本结论仅为离线软件验证，不是科学评测、真实模型/供应商验收或全项目交付结论。未提交、推送或部署，Windows 仍为 `audit-only-windows`。

## 固定范围与快照

完整生产清单：`backend_validation.py`、`build_ground_truth.py`、`conversation_rewrite_metrics.py`、`conversation_validation.py`、`metrics_a1_retrieval.py`、`metrics_a2_faithfulness.py`、`metrics_a3_robustness.py`、`metrics_a4_multihop.py`、`metrics_a5_performance.py`、`release_gate.py`、`run_inference.py`、`run_inference_helpers.py`。初步沟通称 13 个，实际文件枚举与 coverage JSON 均为 **12** 个，此处更正计数，未排除任何生产入口。

`pyproject.toml` 固定 `source=["."]`、branch=true，omit 仅根 `test_*.py`、`tests/`、`.venv/`。包含全部 CLI、构建 Gold 工具与未导入文件；JSON 文件集合与生产清单完全相等，excluded_lines=0。pytest 收集全部 6 个既有根测试文件及 2 个新增 tests 文件。缓存、环境和历史输出不作为测试或生产代码。未添加 ignore/skip/nocover，未修改生产源文件、原 Gold、原 raw runs 或历史结果。

Git HEAD：`46b202c3e400741fd569f024412c0745f224a538`（工作区有其他任务的未提交变更）。最终测试输入 22 项：12 生产文件、8 测试文件、清单和锁。按相对路径排序的输入 SHA256 map，经 `json.dumps(map, sort_keys=True)` UTF-8 序列化后 SHA256 为 `f520bbee160dd7336cf24c60f19ec0670c89b50e5ddd6a5576ed5cc8c47eed6f`。最终运行前后 22 输入与 77 原有 JSON/JSONL/CSV/Markdown/log 文件均无漂移；清单保存在 [before](rag-eval-readiness-20261013/snapshot-before.json) / [after](rag-eval-readiness-20261013/snapshot-after.json)。该前后核对绑定最终运行，不冒称是任务启动时的历史快照。

## 环境、行为与边界

依据根 AGENTS 与本轮明确授权，建立本项目 `.venv`（CPython 3.12.8）、`pyproject.toml` 和 `uv.lock`，不复用 backend 环境。旧 CLAUDE 的“复用 backend/.venv”与当前规则冲突，本轮以根 AGENTS 和用户授权为准。覆盖生产实际 imports：FastAPI/TestClient、httpx、python-dotenv；开发依赖 pytest/coverage，传递依赖由 uv 锁定。`uv sync --frozen` 实装 23 包，最终与锁版本逐个一致。

新增 28 项（原有 46 项全部保留），验证如下行为：

- A1：集合去重、顺序 MRR、空相关集、空召回、缺 run、T1/T6 差异与真实 JSON 产出。
- A2：关键词标准化、拒答、合法/幻觉节点、禁词、空引用、缺 run、摘要截取、真实 JSON/Markdown 清单。
- A3：数字/页码过滤、拒答与误报、噪声/clean 对照、错误前提和缺 run fail-fast；所有输入是合成 TEST_ONLY。
- A4/A5：hop 分组、未知问题、工具 request/result 过滤、重复调用、空集合、Pearson、分位数、成本和临时报告输出。
- release_gate：真实临时指标文件、可选验证文件、有/无 raw hash、补充样本与非阻断弱点记录。
- inference：真实临时 JSONL 追加/resume、setup 会话、成功/异常持久化、duration/wall-clock 回退、参数/环境布尔、凭据缺失 guard 和实际 TestClient 装载。HTTP app 为测试自身 FastAPI app，未导入生产 server；凭据读取入口用替代 dotenv loader，未读取 `.env`。
- build_ground_truth：执行原文件 exact source/runpy，仅其 `pathlib` import 返回两个严格白名单重定向路径，500 合成节点/空边生成临时 50 题 JSON；验证分类计数、节点存在约束和错误节点断言。原 KG 与 Gold 均不读写。
- backend/conversation validation：真实摘要 JSON 输出及 exit-code 传播；替代 subprocess 边界，不宣称执行后端集成或验证后端全部通过。rewrite helpers 覆盖缺 qid/run、非法节点值及执行失败分类。

边界替代仅为单元测试，不能证明真实模型、后端完整链或语义正确性。1 条 StarletteDeprecationWarning 原样保留：独立 Starlette 1.7.0 提示 TestClient 的 httpx 支持将迁移至 httpx2；当前真实 TestClient 场景通过，未隐瞒警告或为消警扩大迁移。

## 实际验证与证据

以下 cwd 为 `iteration-2/eval-2-existing-components/rag_eval`，路径相对仓库根另行说明。`UV_CACHE_DIR` 指向仓库 `.tmp/uv-audit-cache`；公开依赖安装及漏洞数据库查询经平台批准。初次默认 uv cache 拒绝访问后改仓库缓存；网络沙箱安装失败后获批安装。默认 pytest 系统 temp 权限失败后改 `--basetemp` 到仓库 `.tmp`；沙箱 TestClient socketpair 挂住后主动中断（exit1），最终获批在沙箱外离线复跑，不以初次失败结果冒称通过。

| 检查 | 实际命令 | 退出码、结果 |
| --- | --- | --- |
| 环境 | `uv venv .venv --python 3.12`（uv 实际为 `D:/Python/Scripts/uv.exe`） | 0，独立 Python 3.12.8 |
| 锁/安装 | `uv lock --index-url https://mirrors.aliyun.com/pypi/simple`；`uv sync --frozen` | 各 0，24 锁项含本项目 / 23 实装 |
| 最终全量 | `.venv/Scripts/python.exe -m coverage run -m pytest -q --basetemp=D:/graghRAG-agent/.tmp/rag-eval-tests-receipt --tb=short` | 0，74 passed / 1 warning / 2.72s |
| 导出 | `.venv/Scripts/python.exe -m coverage json -o D:/graghRAG-agent/docs/testing/rag-eval-readiness-20261013/coverage.json` | 0；1722/1742 行、415/440 分支 |
| 锁一致 | `uv lock --check --offline` | 0，24 packages |
| 清单导出 | `uv export --frozen --no-hashes --no-emit-project --format requirements-txt --output-file D:/graghRAG-agent/docs/testing/rag-eval-readiness-20261013/locked-requirements.txt` | 0，全 23 公开依赖 |
| 审计 | 仓库独立 `.tmp/audit-tools-20261012/Scripts/python.exe -m pip_audit -r docs/testing/rag-eval-readiness-20261013/locked-requirements.txt --no-deps --disable-pip --progress-spinner off --format json --output docs/testing/rag-eval-readiness-20261013/pip-audit.json --cache-dir .tmp/pip-audit-cache`（cwd 仓库根） | 0，23 项 vulns 全空，无忽略公告 |
| 输入核对 | `.venv/Scripts/python.exe D:/graghRAG-agent/.tmp/rag_eval_snapshot.py before/after` | 各 0，输入/生产/受保护数据 drift0；scope完全相等；实装锁漂移0 |
| 格式 | `git diff --check -- pyproject.toml uv.lock tests` | 0；新增文件的空白另由直接文本核对覆盖 |

原始 [pytest 日志](rag-eval-readiness-20261013/pytest.log)、[coverage JSON](rag-eval-readiness-20261013/coverage.json)、[逐文件覆盖](rag-eval-readiness-20261013/coverage.txt)、[审计 JSON](rag-eval-readiness-20261013/pip-audit.json)、锁导出与各 `.exit` 文件同目录保留。coverage 总综合 97.9377% 不是双门槛指标，本报告明确分别使用行与分支原始计数，不四舍五入越过门槛。

交接根协调者安排独立范围/测试质量审查并关联全项目门槛；本子任务不修改 memory、历史冻结、原科学规范/数值或其他任务文件。无生产缺陷修复、提交、推送、CI 部署或科学验收声明。
