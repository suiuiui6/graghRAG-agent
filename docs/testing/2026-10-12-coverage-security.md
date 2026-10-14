# 双覆盖率与漏洞扫描结果（2026-10-12）

**结论：已完成后端测量与后端/前端依赖扫描，未满足提交门槛。** 后端行覆盖率65.49%、分支覆盖率54.09%；全量测试706通过/21失败。当前环境、锁文件与前端均检出漏洞，锁一致性检查失败。未修改产品代码、依赖清单或锁文件，未提交/推送。

## 双覆盖率

| 指标 | 原始计数 | 百分比 | ≥90% |
|---|---|---|---|
| 后端行 | 8670 / 13238 | 65.49327693004986% | 未达标 |
| 后端分支 | 2405 / 4446 | 54.09356725146199% | 未达标 |

使用整数交叉乘法判断门槛，不以显示值四舍五入。coverage自身的62.6272%是行/分支混合百分比，不能代替上面两个指标。在本次固定分母下，至少仍需覆盖3245个执行行和1597个分支才能分别达到90%；这不是以填数字代替行为断言。

范围为backend全部89个第一方生产Python文件，包括未导入research实现、CLI和scripts。仅排除测试、.venv、output/uploads等生成物；`research/test_deepseek_scope_pilot.py`为软件测试夹具，不计生产。开启namespace discovery，默认pragma行排除和部分分支豁免清空。实际JSON的89键与独立清单完全一致，missing=[]、unexpected=[]、excluded_lines=0；未导入文件以零覆盖进入分母。[独立范围复核](../review/2026-10-12-coverage-scope-review.md)通过。

| 优先补测模块 | 已覆盖行 / 总行 | 已覆盖分支 / 总分支 |
|---|---|---|
| doc_processor.py | 141 / 414 | 39 / 184 |
| worker.py | 372 / 574 | 113 / 174 |
| kg_builder.py | 8 / 205 | 0 / 142 |
| retrieval.py | 1313 / 1493 | 524 / 650 |
| generator.py | 709 / 873 | 293 / 426 |
| research/deepseek_scope_pilot.py | 0 / 265 | 0 / 110 |
| run_evaluation.py | 0 / 231 | 0 / 60 |
| pipeline.py | 0 / 182 | 0 / 30 |

前端没有既有测试/覆盖脚本，本次未建设其测试框架；langextract等独立子项目也未测量，不能称全项目双覆盖率通过。后端测试运行未收集全部子进程内部覆盖，未执行真实供应商全链；缺失执行仍体现为未覆盖，不用缩分母补偿。

## 漏洞与锁一致性

| 检查 | 范围 | 结果 | 退出码 |
|---|---|---|---|
| pip-audit 2.10.1，当前环境 | 161个公开发行包；1个本地langextract单列未作PyPI匹配 | 19个包、87条原始漏洞记录、59个唯一advisory ID | 1 |
| pip-audit 2.10.1，uv.lock | 205个固定registry依赖，含其他平台与dev依赖 | 4个包、9条原始记录、8个唯一advisory ID | 1 |
| npm audit，官方接口 | 现有frontend/package-lock.json，含prod/dev | 16个受影响依赖项：高危10、中危5、低危1、严重0 | 1 |
| Bandit 1.9.4，无nosec忽略/无规则豁免 | 后端90个Python文件（比生产清单多一个research测试），20,427行 | 中危4、低危176，高危0，解析错误0 | 1 |
| uv lock --check | 当前backend/pyproject.toml及uv.lock | Resolved 208 packages；锁文件需要更新，--check阻止写入 | 1 |

以上为扫描器原始记录。PyPI结果存在重复及别名，不把87条称为87个独立CVE；npm存在受依赖链影响的聚合条目，不把16项直接称为16个已确认可利用漏洞。扫描器结果用于待处理清单，实际可达性和修复方案仍需按代码/部署核验。本轮没有自动使用历史豁免抹掉告警。

当前环境与锁文件有99个同名包版本不同，详见 [差异清单](2026-10-12-environment-lock-drift.json)。这解释了两份扫描结果不同，也表明“已有uv.lock”不能证明当前运行环境复现该锁。离线锁检查曾因缺apscheduler缓存无法判定；随后联网只读检查已明确锁不一致，见 [最终锁检查日志](2026-10-12-uv-lock-check-online.log)。

锁文件的漏洞包：

| 包 | 锁定版本 | 原始记录数 | 扫描器给出的修复版本 |
|---|---|---|---|
| chromadb | 1.5.9 | 5 | 无 |
| multidict | 6.8.0 | 1 | 6.9.1 |
| oauthlib | 3.3.1 | 1 | 4.0.0 |
| pyjwt | 2.14.0 | 2 | 2.15.0 |

当前环境还检出aiohttp、anyio、cryptography、langchain、langgraph-sdk、langsmith、python-multipart、starlette、torch等包的问题，完整19包版本和修复版本在机器汇总与原始JSON，不以锁扫描结果覆盖运行环境风险。历史Chroma豁免见 `docs/governance/dependency-audit-2026-09-17.md`，本次保留全部发现，尚未重验其部署可达性。

Bandit四项均为`backend/table_index.py`的B608 SQL字符串构建：148、175、237、247行，其中237行为中置信度，其余低置信度；均为中严重度。历史CI接受的B608豁免没有自动应用。低危176项包括宽捕获、assert、子进程调用和开发密钥等；工具告警不自动等于实际漏洞，不能不经分析就机械删除代码或吞掉发现。

前端受影响直接依赖包含postcss、react-router-dom、tailwindcss、vite。部分修复涉及Tailwind主要版本迁移，不能直接运行`audit fix --force`替代兼容设计与验证。原npmmirror漏洞接口ECONNRESET，已保留首次失败日志，改用npm官方接口重试成功；没有修改registry配置或锁文件。

## 证据、命令与工具隔离

基线HEAD `46b202c3e400741fd569f024412c0745f224a538`。执行前后生产代码、覆盖配置、后端清单/锁及前端清单/锁SHA256全部一致，见 [输入快照](2026-10-12-audit-inputs.json)。时间见输入与 [机器汇总](2026-10-12-coverage-security-summary.json)。独立临时工具环境`.tmp/audit-tools-20261012`，固定coverage7.6.12、pip-audit2.10.1、bandit1.9.4；[工具完整版本](2026-10-12-audit-tool-versions.txt)。后端venv未安装或升级产品/测试依赖；coverage通过仅含该包的专用Python3.12目录加载。

在仓库根，后端覆盖运行设置：`PYTHONPATH=D:/graghRAG-agent/.tmp/coverage-runtime-py312-20261012`、`PYTHON_DOTENV_DISABLED=1`、`HF_HUB_OFFLINE=1`、`TRANSFORMERS_OFFLINE=1`。

```powershell
& backend/.venv/Scripts/python.exe -m coverage run --rcfile=docs/testing/coverage-backend-2026-10-12.ini -m pytest backend/tests -q --tb=short -p no:cacheprovider --basetemp backend/tests/_sandbox_tmp/coverage-20261012
# 706 passed, 21 failed, 5 warnings, 90.37s; exit 1
& backend/.venv/Scripts/python.exe -m coverage json --rcfile=docs/testing/coverage-backend-2026-10-12.ini
# export exit 0，测试失败仍保留原始覆盖报告，不改变测试退出码

& .tmp/audit-tools-20261012/Scripts/python.exe -m pip_audit -r docs/testing/2026-10-12-audit-installed.txt --no-deps --disable-pip --progress-spinner off --timeout 15 --cache-dir .tmp/pip-audit-cache -f json -o docs/testing/2026-10-12-pip-audit-installed.json
& .tmp/audit-tools-20261012/Scripts/python.exe -m pip_audit -r docs/testing/2026-10-12-audit-locked.txt --no-deps --disable-pip --progress-spinner off --timeout 15 --cache-dir .tmp/pip-audit-cache -f json -o docs/testing/2026-10-12-pip-audit-locked.json
& .tmp/audit-tools-20261012/Scripts/python.exe -m bandit -r backend --exclude backend/.venv,backend/tests,backend/output,backend/uploads,backend/__pycache__ -f json -o docs/testing/2026-10-12-bandit.json --ignore-nosec
# 三条扫描均exit 1：有发现，不是扫描失败

# 在frontend中
npm audit --package-lock-only --ignore-scripts --json --registry=https://registry.npmjs.org --fetch-retries=1 --fetch-timeout=20000 --cache ../.tmp/npm-audit-cache
# exit 1：有发现

# 仓库根，UV_DEFAULT_INDEX=https://mirrors.aliyun.com/pypi/simple/
uv lock --check --project backend --cache-dir .tmp/uv-audit-cache
# exit 1：lock needs update
```

原始证据：[coverage JSON](2026-10-12-backend-coverage.json)、[测试日志](2026-10-12-backend-coverage-tests.log)、[已安装依赖JSON](2026-10-12-pip-audit-installed.json)、[锁定依赖JSON](2026-10-12-pip-audit-locked.json)、[npm JSON](2026-10-12-npm-audit-official.json)、[Bandit JSON](2026-10-12-bandit.json)。完整日志及独立退出码文件均在本目录，未编辑扫描器原始报告。

全量21个失败为研究隔离模块缺失18、研究CLI print规范1、冻结完整性1、研究测试pytest导入策略1。与此前22失败相比，本次产物计数用例通过，反映其对现有产物状态的依赖，不能算本轮修复了该用例；本轮未修改生产代码或测试。冻结失配不能通过更新期望值或忽略研究业务代码绕过。

## 后续优先级

1. 先明确目标依赖版本，更新并审查过期锁，在独立环境复现；以PyJWT、Web/上传依赖及前端高危发现为优先，核实Chroma历史豁免；修复前后重跑审计和P0回归。禁止用扫描器无差别强制升级。
2. 收敛全量21失败，特别是研究隔离模块与冻结契约；保留本轮固定生产范围。为doc_processor、worker、kg_builder和未执行入口补真实行为/异常测试，再测两指标。
3. 前端及其他独立可执行子项目补固定范围与测试策略，再建设可信CI双指标和扫描门禁。当前Windows仍为audit-only-windows。

本次完成的是测量与扫描，不是修复全部漏洞、覆盖率达标或上线验收。无commit/push、自动升级或部署。
