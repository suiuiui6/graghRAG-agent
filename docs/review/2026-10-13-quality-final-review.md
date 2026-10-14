# 最后增量独立复审：隔离守卫与本地服务

## 审查总结

接受本轮有界增量：正式源码守卫恢复、反馈备注更新、逐条投递历史隔离、队列任务计数释放及恢复诊断字段符合有效契约，独立专项63例通过。新增问题统计：Critical 0 / High 0 / Medium 0 / Low 0；既有全量测试、双覆盖率和供应链交付阻塞不因此关闭。

本 reviewer 独立读取根 AGENTS、memory/index及2026-10-13记录、整改计划、上一轮quality-bug-review及local-service报告，再检查当前源码/测试和有效企业蓝图。按 requesting-code-review 组织独立审查，按 verification-before-completion 实际重跑后下结论。分支master、HEAD `46b202c3e400741fd569f024412c0745f224a538`；共享脏工作树未回退。本子任务唯一写入文件为本报告，memory由主协调者统一汇总。

## 修复审查与 before/after

| 定位 | Before | After及独立判断 |
|---|---|---|
| `backend/research/isolated_guard.py:151–169`；`backend/tests/test_isolated_guard_v2.py:9` | 正式源码v1不拦SQLite原生连接写入；v2测试引用临时目录文件，干净检出缺依赖 | 正式源码与可追溯`.tmp/isolated_guard_v2.py`字节哈希完全一致；v2测试固定引用正式源码。外部、`..`逃逸、file URI、空库名与整数参数被拒；内部真实SQLite写/读及`:memory:`成功，且外部文件未创建。未改历史冻结。 |
| `backend/services/feedback_store.py:80–86` | 更新忽略模型已有comment字段 | `comment is not None`才赋值并持久化；空串可清空，None保留，不隐式改变status。参数化用例重开真实store核对非空/空备注。 |
| `backend/services/webhook_manager.py:146–160` | 坏JSON中止整个倒序循环，丢失更旧有效记录 | 文件读取失败单独返回空；每条JSON/模型异常只跳过本条；limit按有效记录数，倒序保持。测试在两条真实记录间插坏JSON，明确两条均返回且顺序正确；正常limit=1另有断言。 |
| `backend/services/event_bus.py:74–85` | `_deliver`异常后未task_done，后续事件虽处理但join永远等待 | 成功get后才进入内层try/finally；成功、处理错误、处理中取消均恰好一次task_done。等待get时取消不进入finally，避免误扣/ValueError。取消继续由外层CancelledError结束worker，普通错误记录后继续；签名/重试逻辑未修改。 |
| `backend/models.py:318–322` | restore传入error被Pydantic忽略，调用端读取result.error可能AttributeError | 增加可选`error: str \| None = None`，成功响应兼容，失败原因保留；缺失/损坏/恶意归档路径实际进入失败分支。`routes/system.py:54–59`原有400诊断访问现在有字段承接。本专项未运行该HTTP端点，不把服务测试当API集成验收。 |

对应有效规范已回流企业蓝图：备注契约行344、恢复诊断行765、投递历史/队列取消行1374。models其余QueryOptions变更属于其他任务，不在本轮批准范围。

## 安全语义与测试质量

- 守卫是可信、有界、一次性子进程中的补充Python审计限制；它自身只校验manifest路径绑定，不验证外部防火墙、可执行文件hash或启动收据。保留源码的非原生沙箱声明，不把SQLite connect测试扩大为任意原生扩展或SQLite后续语句的完整隔离证明。
- 守卫两组使用新子进程、真实小SQLite文件和文件不存在断言；既有读密钥测试使用不存在的临时`.env`路径验证开文件前拒绝，未读取真实.env。系统DLL例外保持明确名称及绝对System32路径，不扩大为任意系统路径。
- 队列异常用例断言第二条被处理、两条顺序、join完成和worker结束；取消两分支断言join完成、task.done且task.exception为None，能抓住计数漏扣和get前误扣。处理中取消释放当前已领取任务不等价于排空/持久化所有排队事件，本轮未改变停机投递保证。
- HTTP边界requests/httpx全部显式替身或拒绝；真实HMAC针对实际请求字节校验，重试顺序及1/5/25秒退避通过记录参数核对；不调用供应商或模型。持久化、归档、Pydantic和asyncio队列本身为真实临时依赖。
- 恢复用例核对真实归档内容、恢复前快照及路径穿越/外链拒绝；未删除旧断言、跳过失败、改覆盖配置或修改冻结。新历史坏行测试直接验证JSON损坏；无效模型行由同一逐条try静态确认，未把此项描述成新增独立参数化实测。
- 所有新服务测试路径、singleton及当前目录由fixture重定向并恢复。未发现真实output写入路径；没有做全仓真实output前后hash，不声称完成完整目录无变化证明。

## 独立实际执行

2026-10-13（北京时间），在仓库根运行：

```powershell
$env:PYTHON_DOTENV_DISABLED='1'
$env:HF_HUB_OFFLINE='1'
$env:TRANSFORMERS_OFFLINE='1'
$env:PYTHONIOENCODING='utf-8'
backend/.venv/Scripts/python.exe -B -X utf8 -m pytest backend/tests/test_isolated_guard.py backend/tests/test_isolated_guard_v2.py backend/tests/test_local_service_quality_behaviors.py backend/tests/test_phase2.py::TestBackupManager backend/tests/test_phase3.py::TestWebhookManager -q --tb=short --show-capture=no -p no:cacheprovider --basetemp backend/tests/_sandbox_tmp/reviewer-quality-final-20261013
```

**exit0，63 passed、1 warning，5.76s**。其中guard25、新服务29、旧Backup/Webhook9。warning为旧环境pytest未知timeout配置，未声称插件约束生效。Windows asyncio本机socketpair沙箱阻塞已有根因证据，本次经require_escalated批准执行；外部HTTP仍被测试拒绝/替身隔离。原始独立输出保留于本reviewer工具记录。另对三service及models执行`git diff --check`，exit0，仅既有LF/CRLF提示。

本次使用原`backend/.venv`，未在候选新锁环境运行、未扫网络漏洞、未测全量/覆盖率、未构建镜像、未提交/推送。旧环境专项通过不能证明新锁环境兼容或全量门槛通过。

## 验证后源码快照

这是运行后文件SHA256，不声明运行前后整个工作区完全一致。

| 文件 | SHA256 |
|---|---|
| backend/research/isolated_guard.py（与.tmp/isolated_guard_v2.py相同） | 432717ba4c5193ded837af5bcd1863c37cafc18a896d2fe2255e74a943450637 |
| backend/tests/test_isolated_guard.py | a87819167c392f87aad4b0bb26fd758c58767c4157c7e192dafac61b4fc8d6d4 |
| backend/tests/test_isolated_guard_v2.py | 2785226b96dbd7d2c993da073207f411e08ab9509a99a831685f9e0258e6f23f |
| backend/services/feedback_store.py | 0ead47383879944400739da143b75d46c4537d6ccb2a65de266a8638a6994590 |
| backend/services/webhook_manager.py | 89487524ca880268ee8a9916141f25c775ea27a4827bc0a6d3baa7b78e4545a7 |
| backend/services/event_bus.py | 78c70fe9afb24f18406ec8751d9723b0da6fb65558a810ec501aef35ca843921 |
| backend/models.py | b8603e88ea3161de56a4a4bf3eb5c956bdc4bd15f7325be19acb197088d6d34c |
| backend/tests/test_local_service_quality_behaviors.py | 44ea8316aadc51688b08671e40fe7030c4830e9174770513cbefb53de924c33e |

## 问题清单与优化建议汇总

本轮新增问题为空，不编造before/after问题示例。既有供应链High和运行环境/全量验收限制沿用[上一轮独立评审](2026-10-12-quality-bug-review.md)，本次未重新扫描，不能独立更新其数量。

1. 主协调者优先核对候选锁环境实际版本并回归，保存扫描和失败退出码；镜像仍需真实可用Docker环境验证。
2. 最终源码稳定后重跑规定全量及固定生产分母双覆盖，研究冻结漂移保留失败证据；任何提交门槛缺失/未过继续禁止commit/push。
3. 由主协调者将63例独立结果、本轮源码hash及限制回流统一报告和memory；不得将重叠专项数相加为唯一全量数。

## 同日追加：新锁环境的测试契约修正

主协调者报告候选新锁环境首次全量为1048 passed、8 failed、8 errors；据此追加只读复审三测试文件的环境适配。该全量数字是协调者交接信息，本reviewer没有重新运行该次全量。本次独立运行下述三文件，接受本轮有界测试修正，新增Critical/High/Medium/Low均0。

| 定位 | Before / 根因 | After / 独立判断 |
|---|---|---|
| `backend/tests/test_pipeline_cli_behaviors.py:16–22,193` | 仓库外层langextract namespace与实际editable包导出混淆；Windows默认文本编码未显式契约 | autouse fixture把本地editable包根放到sys.path前端，重新解析真实`langextract`并临时赋给pipeline.lx；没有伪造库API。数据类型仍来自真实公共模块，模型边界仍显式替身。中文产物读取显式UTF-8，不删除原内容断言。monkeypatch负责恢复路径、模块键及pipeline引用。 |
| `backend/tests/test_query_quality_behaviors.py:300–304,338` | 父包延迟导出对象不保证等于demo实际from-import使用的子模块，替身可能未落到调用处 | `importlib.import_module('langchain.agents')`拿到具体子模块对象后patch create_agent。真实图/工具查询、grounded过滤及断言保持；仍只验证旧demo本地行为，不冒称实际Agent循环。 |
| `backend/tests/test_supply_chain.py:64–66,137–143,175–225` | jieba在全局未解析豁免中，缺包新环境会令其load-bearing校验失败；同时全局豁免可遮蔽以后其他调用点 | 移出jieba全局豁免；新增AST遍历要求整个既有生产扫描范围仅有一个jieba导入，必须是index_registry._tokenize_for_bm25内带ImportError处理的try顶层单一import，且函数末尾调用既有fallback。声明校验仅跳过这个核实过的路径。新增缺包、正常tokens及空tokens行为断言，fallback是实际生产实现；langchain_core全局豁免的严格load-bearing逻辑未改。相比旧规则缩小jieba放行范围，没有把缺包加入通用豁免。 |

核对`backend/index_registry.py:213–231`的既有docstring和`backend/pyproject.toml`的明确可选依赖说明，jieba缺失时bigram回退是原契约。本轮没有修改生产分词逻辑、依赖清单、锁或覆盖配置；生产扫描范围沿用之前已经审查的分类，不新增排除。`test_optional_jieba_is_guarded_and_falls_back_when_absent`只在导入jieba时注入ModuleNotFoundError，其他imports调用原函数；tokens用sys.modules临时替身验证提供者结果过滤，退回路径为真实实现。AST并非通用程序证明，其约束与两项行为测试共同验证当前唯一可选点；未宣称供应链扫描器已能检测所有未安装第三方包。

独立实跑使用**候选新锁环境**（本追加不再使用旧backend/.venv），2026-10-13北京时间、同前三项离线环境变量及UTF-8输出设置，普通沙箱无需提升权限：

```powershell
.tmp/backend-quality-venv-20261012/Scripts/python.exe -B -X utf8 -m pytest backend/tests/test_pipeline_cli_behaviors.py backend/tests/test_query_quality_behaviors.py backend/tests/test_supply_chain.py -q --tb=short --show-capture=no -p no:cacheprovider --basetemp backend/tests/_sandbox_tmp/reviewer-candidate-contract-20261013
```

**exit0，75 passed、12 warnings，16.81s。** 告警均为既有agentic_rag_mvp docstring无效转义（实际导入或AST解析），没有timeout配置未知告警。原始结果在reviewer工具记录。本追加验证只证明三文件在候选环境通过，不关闭全量/双覆盖率/剩余漏洞，亦未独立核对候选所有已安装版本等于锁；由协调者继续统一验证。

运行后输入SHA256（取代首轮相关测试快照，原历史结果保留）：

| 文件 | SHA256 |
|---|---|
| backend/tests/test_pipeline_cli_behaviors.py | 6e20b6456b3a8f94c0fe28bc8ccafc003132480f98bfb327ce7d8e57e502bd81 |
| backend/tests/test_query_quality_behaviors.py | 2774ffb90a4974f89d1b5fc62db054d929b283f44bd8fdffac901a3f6947321a |
| backend/tests/test_supply_chain.py | 307cc047fd98aeadf6ed3cd8c8e904409a63c6b2e31b2f2a2db52d874395f32d |

本次仅追加本报告；未编辑三测试、生产、冻结或memory，无commit/push。

### 同日最终追加：收集期tool替身污染

再次只读确认`test_query_quality_behaviors.py:306–309`新增四行：从真实`langchain_core.tools`导入tool，在legacy_kg fixture内以monkeypatch暂时替换`langchain.tools.tool`，退出时恢复先前对象。根因在旧`test_kg_indexed_recall.py:51–62`收集期安装的全局ToolWrapper只具invoke、不具name；局部选择真实装饰器让当前demo的工具元数据/实际invoke保持真实语义。原KG测试、生产代码与业务断言均未修改，不扩大全局豁免，也不把临时替身永久替换到测试进程。

接受该最小测试隔离修正，未发现新增阻断。本reviewer按协调者指示不重复大测试；独立读取[组合原始日志](../testing/2026-10-13-candidate-order.log)及[退出码](../testing/2026-10-13-candidate-order-exit.txt)，确认报告为61 passed、exit0。该组合由协调者实际执行，不冒称reviewer自身重跑。先前75例独立结果对应旧query快照，不能作为这四行之后的新独立运行证据；最终全量仍由协调者另跑。

最终只读SHA256：`backend/tests/test_query_quality_behaviors.py` = `b5657e61b445627e60c16cb3cac2cd2fcadf241afbc4a90def6c81c627701352`，取代本报告上表query当前快照，保留上表作为75例运行的历史输入记录。
