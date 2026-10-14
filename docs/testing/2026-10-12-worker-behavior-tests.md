# Worker 本地行为测试与异常分类回归

验证时间：2026-10-12 19:30 +08:00。任务输入为根 AGENTS、memory 索引及当日记录、`docs/plans/2026-10-12-quality-remediation.md`。使用 test-driven-development、systematic-debugging、verification-before-completion 组织红测、根因和实测；using-superpowers 对明确分派子任务注明可跳过。未修改 worker、既有测试或覆盖配置，未提交。

## 文件与范围

- 新增 `backend/tests/test_worker_quality_behaviors.py`：67 个参数展开用例。
- 经协调者明确扩大所有权后，最小修改 `backend/errors.py` 的第三方异常识别与分类优先级；错误枚举和 wire 字段未变。
- 本记录由子任务维护；memory 汇总与独立代码评审交由主协调者执行。

真实执行：临时 PDF/MinerU JSON/Markdown、CSV/文本附件、DOCX 生成与解析、分块/去重、真实 LangExtract ExampleData/ModelConfig、BM25 构建、内存 DuckDB 表索引、溯源和空图构建、KG JSON 文件读写。验证节点/边去重及引用一致、任务专用目录、首个失败根因、分批部分成功与全部失败的差异、采样与 prompt 上限、标题/页码/字符偏移、CSV 批次和字段归一化、非法路径在供应商调用前拒绝，以及各必需阶段的错误包装与可选发布/审计的故障降级。

明确边界替身：MinerU submit/poll/download、OSS upload、Ollama requests.post、LangExtract extract、embedding 客户端及向量库、事件发布/审计入口。DOCX 流的 index setter 用替身捕获注册参数，防止默认注册触发真实 routes/runtime 产物；index builder 在正常分支保持真实，仅异常/不可用场景注入故障。真实 JSON 产物均在 pytest basetemp 内。PDF 模型结果为空，因此 PDF 落盘验证为空图；有实体/关系的 JSON 落盘由实际批量提取逻辑测试验证。

这些是本地组件和编排行为验证，不代表真实云供应商、模型或 Webhook 集成验收。任务 JSON store 位于 routes/ingest，而非 worker；本文件不导入 ingest 读取真实任务库，KG JSON 落盘不能冒称任务 store 恢复验证。

## 红测发现及最小修复

实际 `requests.Timeout` 继承 OSError，旧分类器在识别 HTTP 状态与解析异常之前处理通用 OSError，导致 TIMEOUT 误记 SERVER；requests.HTTPError 的 401/403/429/503 状态也被吞掉，requests.JSONDecodeError 同样误记 SERVER。httpx.PoolTimeout/WriteTimeout 未被原有具体类名列表识别。

红测命令：

```powershell
$env:PYTHON_DOTENV_DISABLED='1'
$env:HF_HUB_OFFLINE='1'
$env:TRANSFORMERS_OFFLINE='1'
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_worker_quality_behaviors.py -k 'classification or timeout_subclasses or business_error' -q --tb=line --show-capture=no -p no:cacheprovider --basetemp backend/tests/_sandbox_tmp/worker-quality-errors-red-20261012
```

结果：8 failed、3 passed、45 deselected，退出 1。失败为 requests.Timeout、HTTPError 四种状态、JSONDecodeError、httpx.PoolTimeout/WriteTimeout；requests.ReadTimeout/ConnectTimeout 原先已通过。更早 worker 首轮还复现了超时后部分成功/全部失败时 root_error 被错误归类的两条红测。

修复保持 stdlib-only：利用真实异常 MRO 的 requests/httpx 模块与基类名称识别超时；保留既有超时类名兼容；把具体解析异常和 HTTP 状态放在通用连接/OSError 分类之前；provider body_code 仍优先。新增用例明确验证已知 MinerU 业务码优先与未知 OSError 仍回退 SERVER。无新增枚举、豁免或测试跳过。

## 最终验证

```powershell
$env:PYTHON_DOTENV_DISABLED='1'
$env:HF_HUB_OFFLINE='1'
$env:TRANSFORMERS_OFFLINE='1'
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_worker_quality_behaviors.py backend/tests/test_errors.py -q --tb=short --show-capture=no -p no:cacheprovider --basetemp backend/tests/_sandbox_tmp/worker-quality-final4-20261012
```

结果：131 passed，2 warnings，19.15 秒，退出 0；新增 67 + 既有 errors 64。既有 warnings 为 pytest 不识别 timeout 配置和 jieba 依赖 pkg_resources 弃用，未静默屏蔽。

前次 DOCX 测试夹具使用六段近似文本，被真实去重合并为一块；已改成六段不同主题文字，未修改生产去重逻辑或放宽断言。LangExtract 组装测试从仓库根执行时遇到外层 `langextract/` namespace 覆盖 editable 包的根 API（无 extract），测试显式将 editable 项目目录加入 sys.path 并临时重新解析实际包，模拟 backend cwd 的包解析；测试退出后 monkeypatch 恢复原状态。此启动路径差异是环境限制，不作为生产 import 修复或额外验收结论。

`git diff --check -- backend/errors.py backend/tests/test_worker_quality_behaviors.py` 退出 0。验证后 SHA256：

| 文件 | SHA256 |
|---|---|
| backend/errors.py | 14dd69791988464970382a2b96ff432ed10d968e41e0acbbf79b621b319e4168 |
| backend/worker.py | fec90383cdc511abe6e9cba962e4c829799bcdcf254b191ca205eccf77e323ff |
| backend/tests/test_worker_quality_behaviors.py | 862a6166c60c2d4834cfd9ba9b87a19d94b0118e78425f3912b25b7e00cd920d |

未运行全量后端或重新测量覆盖率，不声称双覆盖达到 90%。未调用真实 API、读取 .env、下载模型或操作真实 backend/output。后续由主协调者完成独立审查及固定全量覆盖测量，保留既有全量失败和研究冻结边界。
