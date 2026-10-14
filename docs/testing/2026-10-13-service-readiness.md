# 服务行为补证

输入：[实施计划](../plans/2026-10-13-quality-to-90.md)。仅新增 `backend/tests/test_service_readiness.py`，并经协调者明确授权修复 `services/lifecycle.py::_clean_kg_versions`。

## 行为与边界

- KG：真实 JSON 合并及 ID 前缀隔离、grounded 子图、默认回退、坏产物降级。
- Catalog：真实 JSON/YAML/SQLite 统计、空与坏产物、分页搜索、质量/孤点/项目统计、指标读取失败。
- Exporter：真实 StreamingResponse 消费，CSV 行解析、ZIP 成员/manifest/JSON 对照，Cypher/RDF 内容、字典/反馈/会话导出与坏文件跳过。
- Conversation：真实文件保存/加载、稳定会话与自动会话 TTL 分流、20 轮截断、Markdown、保留清理、替换/临时文件清理 PermissionError、SQLite namespace/upsert/hash稳定性及指代缓存/失败回退。
- Bot：消息路由/文本与富文本提取/mention、配额、真实反馈文件与 Pydantic 错误评级拒绝、回答来源截断、模型及回复失败降级。
- Lifecycle：预览不删、反馈保留、时间/mtime/坏 JSON 清理、备份日/周保留、各清理类别独立失败汇总、文件删除失败、存储统计、KG版本根路径与越界拒绝。

Feishu HTTP、嵌入/索引/模型构造器及生成结果是明确的外部边界 double；真实供应商或真实模型未验收。其他服务使用临时工作目录与真实本地文件/数据库；禁止未替代 HTTP，不读取 `.env`，不触碰用户 output。故障注入只作用外部边界或文件操作；生命周期聚合独立失败场景替代类别清理函数以验证汇总隔离。越界路径测试按协调者要求替代 finder 输入，真实删除对象全部在临时目录。

## 红绿与修复

初始真实12版本目录：预览给出2个相对路径，清理返回0且目录仍存在；[红测](2026-10-13-service-readiness-red2.log)，exit1。根因是 `shutil.rmtree` 把 KG_ROOT 相对路径解释为 cwd 相对路径。

另构造临时 outside 目录输入，旧实现删除它并返回1；[越界红测](2026-10-13-service-readiness-containment-red.log)，exit1。修复先 resolve KG 根与删除目标，拒绝根本身及根外目标，再删除绝对路径，预览输出保持相对路径。专项同时断言仅删最旧2版本、最新10完整保留、outside sentinel完整保留。

初始红测的路径分隔符断言已修为 Path.as_posix；这是 Windows 测试表示适配，不是生产Bug。r2沙箱 asyncio 卡住后主动中止，r3开始申请沙箱外本机 socketpair。r3曾有新增测试错误放置尾部故障注入导致 NameError，修正后 r4 21通过；最终 r5 23通过。

## 最终实际验证

2026-10-13，Python3.12候选锁环境，r5 `23 passed in 5.34s`，pytest exit0；[日志](2026-10-13-service-readiness-r5.log)、[退出码](2026-10-13-service-readiness-r5-exit.txt)、[源码/配置快照](2026-10-13-service-readiness-snapshot.json)、[完整90文件JSON](2026-10-13-service-readiness-coverage.json)。coverage export exit0；没有 exclude/skip/ignore 或缩分母。

| 模块 | 行原始计数 | 分支原始计数 |
|---|---:|---:|
| conversation | 271/272 (99.63%) | 63/64 (98.44%) |
| services/catalog | 276/276 (100%) | 105/110 (95.45%) |
| services/kg_exporter | 205/205 (100%) | 80/80 (100%) |
| services/kg_service | 67/67 (100%) | 29/30 (96.67%) |
| services/lifecycle | 220/220 (100%) | 65/66 (98.48%) |
| services/bot_handler | 120/128 (93.75%) | 36/38 (94.74%) |

Bot 剩余8行/2分支为 `_handle_message` 包围 `_rag_query` 的异常处理，而 `_rag_query` 自身已捕获所有普通 Exception 并返回降级结果。未替代目标函数来制造可达覆盖。Conversation剩余为锁内二次ready检查，KG计数剩余为不存在默认nodes分支，lifecycle剩余为walk后文件瞬时消失分支。

专项结果不代替最终后端全量、前端或其他子项目覆盖，不代表研究准入/安全扫描通过；交由协调者合并全量。未commit/push。

另对新增服务测试、既有 `test_local_service_quality_behaviors.py` 及 `test_conversation_rewrite.py` 组合回归：57 passed，exit0，5.47s，1条Starlette/AnyIO既有弃用警告；[组合日志](2026-10-13-service-readiness-combined.log)与[退出码](2026-10-13-service-readiness-combined-exit.txt)。组合命令沿用下方离线环境，pytest输入改为上述三文件，basetemp改为`service-readiness-combined`；该次无coverage，不覆盖r5专项覆盖证据。

```powershell
$env:PYTHON_DOTENV_DISABLED='1'
$env:HF_HUB_OFFLINE='1'
$env:TRANSFORMERS_OFFLINE='1'
$env:PYTHONUTF8='1'
$env:PYTHONPATH='D:/graghRAG-agent/.tmp/coverage-runtime-py312-20261012'
& .tmp/backend-quality-venv-20261012/Scripts/python.exe -m coverage run --rcfile=docs/testing/coverage-backend-2026-10-12.ini --data-file=docs/testing/service-readiness.coverage -m pytest backend/tests/test_service_readiness.py -q --tb=short -p no:cacheprovider --basetemp backend/tests/_sandbox_tmp/service-readiness-5
# pytest退出码独立保存r5-exit.txt；日志r5.log。
& .tmp/backend-quality-venv-20261012/Scripts/python.exe -m coverage json --rcfile=docs/testing/coverage-backend-2026-10-12.ini --data-file=docs/testing/service-readiness.coverage -o docs/testing/2026-10-13-service-readiness-coverage.json
git diff --check -- backend/services/lifecycle.py backend/tests/test_service_readiness.py
```
