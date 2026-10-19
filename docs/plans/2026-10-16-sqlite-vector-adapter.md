# SQLite向量适配器 R8 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: 使用 subagent-driven-development 或 executing-plans 逐任务执行。各负责人不是独占工作区，不得覆盖其他修改。

**Goal:** 保留现有合法数据规模，补齐分配前检查、分批精确检索和完整项目Chroma合同，并同步三个索引消费者。

**Architecture:** 固定SQLite内部schema、分片载荷、单读事务页面与评分；BM25单遍token化，最终模型仍O(N)。仅私有副本实施，生产不切换。

**Tech Stack:** R7派生Python3.12.15/SQLite3.54.0/NumPy2.5.4，真实Chroma1.5.9 oracle，现有rank_bm250.2.2。

## Phase 1 / P0 消费者与真实分页（可先独立实施）

归属consumer coder：仅 `.tmp/sqlite-r8-consumers-20261016/backend/` 下 `index_registry.py`、`build_indices.py`、`run_evaluation.py`、`routes/rag_query.py` 及 `tests/test_r8_paged_consumers.py`。候选接口归属adapter coder：独占 `.tmp/sqlite-vector-r8-20261016/backend/` 下 `vector_store.py` 和 `tests/test_r8_snapshot_pages.py`。共享接口先明确 `iter_record_pages` 返回对齐ids/documents/metadatas字典，单迭代持有同一快照；兼容门面get仍全量。

- [ ] 固化私有源码复制与输入SHA，复用锁定环境，不修改生产文件。
- [ ] 先写失败测试：三个消费者只消费单遍页面，不调用全集get；137条/页17的最后页不漏、ids与metadata不串行；空集合返回原空行为。
- [ ] 运行私有测试 `python -m pytest tests/test_r8_paged_consumers.py -q`，记录实际失败及退出码。
- [ ] 索引构建器逐页产生Chunk；rank_bm25无tokenizer参数接收单遍token生成器，保留最终chunks一次，不保留全集tokenized。TableIndex保持table优先及无table的全集回退。
- [ ] 真SQLite两连接测试：第一页后并发新增/删除，后页仍同一generation；提前关闭迭代器和异常释放读事务。
- [ ] 运行 `python -m pytest tests/test_r8_paged_consumers.py tests/test_r8_snapshot_pages.py -q`；实际原BM25与新模型逐查询scores、chunk映射一致，三个入口均有行为证据。命令python须替换为验证后私有环境绝对路径并记入receipt。

## Phase 2 / P0 资源与分批评分

归属adapter coder：私有 `vector_store.py`、拆分的 `sqlite_vector_store.py`、`sqlite_vector_payload.py`、`tests/test_r8_resources.py`、`tests/test_r8_scoring.py`。拆分文件须由此负责人独占修改。

- [ ] 红测：大于旧候选4096维/1000批/10000总记录/1000top_k合法请求成功；恶意转换钩子、周期metadata不执行副作用；末项非法不写任何前项。
- [ ] 流式校验和编码到私有磁盘暂存，事务提交；文本/JSON/向量内部片段预算约束每块，不拒绝合法总量。磁盘不足回滚，临时资源清理。
- [ ] 同一读快照扫描过滤再评分；普通块256条/8MiB可调，超块单向量分维计算稳定范数/点积，超块metadata走单行或分片并记录峰值，绝不建全集矩阵。
- [ ] 备份hash和复制分块执行，验证后解析，可信期望值来自调用者；取消额外总快照限额。
- [ ] 运行 `python -m pytest tests/test_r8_resources.py tests/test_r8_scoring.py -q`。断言块1/17/256的完整结果一致、最后块最优被发现、过滤先于top_k、并列稳定；子进程记录峰值，分别报告O(块)、O(k)、最大逻辑单行及最终输出内存，不冒称常量RSS。

## Phase 3 / P0 完整项目兼容

归属oracle coder：私有 `tests/test_r8_chroma_contract.py`、`tests/test_r8_consumers_integration.py`；适配器修复仍由adapter coder负责。

- [ ] 真实锁定Chroma oracle登记全部现役门面及私有get合法/非法行为；零向量不沿用原型拒绝政策，未批准新增能力限制一律不得实施。
- [ ] 对照metadata默认/None/JSON列表/宽整数/缺键/bool/负零/浮点formatter、全where组合与错误类别；独立精确数学评分对照，ANN真并列只比等价集合。
- [ ] 运行 `python -m pytest tests/test_r8_chroma_contract.py tests/test_r8_consumers_integration.py -q`，复跑既有R4b/R6边界套件。保存版本、seed、源快照、每个反例；未消除数值反例不得声称完整兼容。

## Phase 4 / P1 独立复审及交付

- [ ] 独立reviewer核合同、资源实测、无范围缩减及新输入复验；root复制最终快照复跑同命令，冻结源码/锁/报告/退出码。
- [ ] 回流设计及memory；明确最终BM25 O(N)、全量get O(返回量)、top_k O(k)、磁盘暂存代价。生产切换、旧数据迁移、性能SLO与全原生审计仍未执行。
- [ ] 如需提交，先按 `docs/testing/README.md` 当前策略完成全部相关子项目全量行/分支各≥90%及漏洞扫描；专项通过不等于提交准入，本计划无commit/push步骤。
