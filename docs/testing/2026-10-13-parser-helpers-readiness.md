# 解析、索引与运行辅助行为覆盖

2026-10-13，分支 master。本任务仅新增 `backend/tests/test_parser_index_readiness.py`、`backend/tests/test_runtime_helpers_readiness.py` 及本记录，保留其他任务修改；未改生产、旧研究冻结、覆盖配置、忽略规则或依赖，没有 commit/push/deploy。

## 行为地图与隔离

- 解析：真实 DOCX 自定义 Heading/空表/XML 查询、XLSX 前置空行与自动列名、MinerU JSON→真实 bridge 位置映射、最新缓存选择/坏 JSON/无页映射/空文档；长语义切块、内部空白固定切块、项目来源、去重、JSONL 缺元数据往返。
- 索引：真实 rank_bm25 与 DuckDB，原子 JSON 写入、旧字符串 chunk 恢复、坏类型与坏 chunk 独立降级、缺依赖、磁盘路径为目录时持久化失败但保留内存索引、旧 query 参数签名。可选 jieba 用协议边界替身，不声称真实 jieba 分词验收。
- 嵌入：SentenceTransformer 模型提供方边界替身，目标客户端不替换；真实磁盘缓存、分批顺序、跨实例合并、坏文件恢复、Windows 替换/清理权限故障、真实线程同步验证二次缓存检查；模块配置缺 dotenv/显式 HF_ENDPOINT。
- 质量：真实文件树、损坏/缺失产物、过期 mtime、反馈与会话，真实 Prometheus 指标；指标和事件旁路故障不阻断报告。
- 健康：HTTP requests 边界替身验证请求路径、头、超时、成功/降级/异常矩阵；Chroma 探活使用真实 SQLite 表计数及缺表失败。
- 向量：真实临时 Chroma 目录和向量、空输入、错误维度数量、元数据筛选/截断、迁移集合、复制镜像；客户端构造失败仅在供应商边界注入故障，随后使用真实 PersistentClient 和真实临时镜像恢复。

全部文件写入 pytest `backend/tests/_sandbox_tmp`；未写真实 output、读取实际 .env 或发出供应商 HTTP/HF 请求。使用已授权计划的测试补证流程及 test-driven-development、systematic-debugging、verification-before-completion；不启动 goal/Harness/state。

## 执行与局部原始计数

固定配置 `docs/testing/coverage-backend-2026-10-12.ini`，生产分母仍为整个 backend，未按本任务缩小。候选 Python 为 `.tmp/backend-quality-venv-20261012/Scripts/python.exe`，通过 `PYTHONPATH` 注入锁定 coverage 7.6.12。

环境：`PYTHON_DOTENV_DISABLED=1`、`HF_HUB_OFFLINE=1`、`TRANSFORMERS_OFFLINE=1`、`PYTHONUTF8=1`；`PYTHONPATH=D:/graghRAG-agent/.tmp/coverage-runtime-py312-20261012;D:/graghRAG-agent/backend`，独立 `COVERAGE_FILE=D:/graghRAG-agent/.tmp/parser-helpers-final.coverage`。

```text
.tmp/backend-quality-venv-20261012/Scripts/python.exe -m coverage run --rcfile=docs/testing/coverage-backend-2026-10-12.ini -m pytest backend/tests/test_parser_index_readiness.py backend/tests/test_runtime_helpers_readiness.py backend/tests/test_doc_processor_behaviors.py backend/tests/test_embedded_vector_readiness.py -q --basetemp=backend/tests/_sandbox_tmp/parser_helpers_final
.tmp/backend-quality-venv-20261012/Scripts/python.exe -m coverage json --rcfile=docs/testing/coverage-backend-2026-10-12.ini -o .tmp/parser-helpers-final.json
```

最终快照完整局部组合：54 passed / 1 failed，pytest/coverage exit 1，13.31 秒；JSON 导出 exit 0。日志 `.tmp/parser-helpers-final.log`，原始数据 `.tmp/parser-helpers-final.coverage`，JSON `.tmp/parser-helpers-final.json`，退出码文件 `.tmp/parser-helpers-final-exit.txt`。末次调整旧 Table query 协议测试，使其断言有效正整数上限和数据保持，而不把实现的 5000 硬编码为业务契约；最终复跑与前轮计数一致。表中为最终局部原始计数，无需合并历史数据即可各达双 95，但有红测，不能声称验收通过。最终完成核对时间 2026-10-13 15:19 +08:00，限定三文件 `git diff --check` exit 0。

| 模块 | 覆盖行/生产行 | 行比例 | 覆盖分支/生产分支 | 分支比例 |
|---|---:|---:|---:|---:|
| doc_processor | 408/416 | 98.0769% | 178/186 | 95.6989% |
| embedding | 143/143 | 100% | 29/30 | 96.6667% |
| index_registry | 223/226 | 98.6726% | 61/62 | 98.3871% |
| services/health_checker | 107/107 | 100% | 24/24 | 100% |
| services/quality | 168/168 | 100% | 59/60 | 98.3333% |
| vector_store | 117/121 | 96.6942% | 44/46 | 95.6522% |

未覆盖项可从 JSON 原始 `missing_lines`/`missing_branches` 查看：TYPE_CHECKING 真分支不属于正常运行；DOCX 对当前 body 元素反查失败分支在 python-docx 正常对象模型下不可达；每个 chunk 均由目标函数构造有效 metadata，缺 metadata 分支不可由该链自然产生。向量 get/add 的缺 metadata 或 None 标量返回分支无法由当前真实 Chroma 固定投影自然产生，未伪造目标函数返回刷覆盖。embedding 剩余 import 分支依赖 dotenv 是否检查到实际 .env，本任务禁止读取该文件。以上均未增加 ignore/skip。

## 实际阻塞与交接

红测 `test_real_indexes_snapshots_restore_and_rank` 已重复复现：真实 DuckDB `query(top_k=5)` 有行，但 `snapshot_table_index` 调 `_serialize_table_index` 固定 `query(top_k=5000)`；当前 `table_index._validate_limit` 只接受 0..1000。ValueError 被吞为 `rows=[]`，恢复随后宣称成功而丢失表行。已交主任务协调者；因生产代码不在本 Agent 所有权内，未擅自修复，不改断言/xfail/skip。须先使快照合法且保留真实表数据，再重跑本组合与最终全量固定范围覆盖。

快照核对（2026-10-13 15:16 +08:00）：测试 parser `7e10fca9bbfe5f7eb7e34d12a28247e5df0541807f267430674305d5f6d7ec44`，helpers `5517dacd50d13516d56bf4de8db8e1645e3bba2de971da4fa1417702120514b2`；生产 index_registry `129fd58ffc584ae9f21cb4587e91c8b1cd8174b71c3948d672c197d0592ef066`。该快照尚未修红测；其他 Agent 后续修改需重新验证。总体工程双 90、安全、真实供应商和其他子项目门槛由主任务独立执行，本报告不替代。
