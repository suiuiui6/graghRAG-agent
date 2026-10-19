# SQLite R8 消费者 R2 独立复审

审查总结：旧审查两项 Medium 均在本冻结 R2 专项范围关闭，原29例及3例新增独立边界全部通过。新增问题统计：Critical 0、High 0、Medium 0、Low 0；本结论不包含尚待提供的 adapter 最终组合。

## 输入及范围

读取根 AGENTS、memory/index 与2026-10-17记录、2026-10-16 SQLite设计/计划及旧消费者审查。分支 master，存在大量其他任务修改；仅写 `.tmp/sqlite-r8-r2-review-20261017/` 与本报告。按using-superpowers的SUBAGENT-STOP，本专项子Agent跳过该技能流程。未修改冻结、生产或共享环境。

冻结：`docs/testing/sqlite-r8-consumers-r2-20261017/manifest.json` SHA256 `63d4084f6ad92d6df1e80c3132e1ff9ac9ff385f9d392df20eb64d4ae8206f8d`。66项逐文件核验一致；复制source到独立目录，运行前后逐文件hash一致。

## 旧问题逐项关闭

1. **Medium：首次取值/空耗尽未close**。冻结 `source/backend/index_registry.py:214–234` 已将首次next、空返回、tokens及BM25构建纳入统一finally。原首次RuntimeError/StopIteration两例通过；新增正常耗尽恰好close一次通过。ImportError仍在创建iterator之前返回，新增不可消费Reader证明缺rank时既不触碰也不close待回退输入。
2. **Medium：rag无能力对象不返回None**。冻结 `source/backend/routes/rag_query.py:38–43` 以callable分页能力或旧collection能力选择。原无能力对象返回None及page-only真实行为通过；新增不可调用iter_record_pages=None且无collection对象也返回None。

修复前：首次next在finally外；rag只判断None。修复后：首次读取位于finally内；rag检查分页接口callable或legacy collection。与旧审查建议一致，无进一步修改建议。

缺rank回退回归：build/eval × 有/无table四例全部通过，TableIndex分别接收唯一末页table或完整19条记录；页面异常close、137条/17页、BM25分数映射、真实SQLite快照并发变更及DuckDB观察原专项均通过。缺rank仍不关闭调用者随后必须消费的输入，保持回退契约。

## 实际验证

命令及准确退出码见 `.tmp/sqlite-r8-r2-review-20261017/receipt.json`，日志 `review.log`，hash核验 `verified.json`。Python使用 `.tmp/sqlite-r8-integration-env-20261017/.venv/Scripts/python.exe`，运行三个测试文件 `test_r8_paged_consumers.py`、`test_independent_edges.py`、`test_r2_review_edges.py`，参数 `-B -X utf8 -m pytest ... -q -p no:cacheprovider`。

最终 **32 passed in 4.79s，pytest exit 0**。初次新增正常耗尽用例漏传Chunk必需content_type，31通过1夹具错误，exit1；修正独立测试后全套复跑。保留 `fixture-error.log`，该错误未归于产品。

## 优先级及限制

下一步：收到 adapter 最终源码后独立核组合；当前只关闭消费者R2两项问题。最终BM25/chunks/TableIndex与legacy全量get仍O(N)，没有证明严格RSS上限。provider全链、全量backend、双90覆盖与漏洞扫描未执行，不构成提交或生产准入。未提交、推送、部署；memory由root汇总。



适配器core独立审查及其R2 schema闭环另见[独立报告](2026-10-17-sqlite-adapter-core-review.md)，消费者专项与adapter专项证据分开记录。
