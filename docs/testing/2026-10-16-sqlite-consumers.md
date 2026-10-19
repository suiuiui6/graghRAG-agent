# R8 消费者分页专项（Phase 1）

仅私有副本实施，生产文件、生产数据、`.env`、R7/R6冻结目录未修改。新冻结包为 [sqlite-r8-consumers-20261016](sqlite-r8-consumers-20261016/receipt.json)，后续适配器组合测试须另建产物，不覆盖此包。

## 修改

`paged_chunks.py` 将 candidate `iter_record_pages(page_size=256)` 对齐页面转换为 Chunk；单次迭代保持一个快照。旧 Chroma 不具备该接口时保持单次全集 `get`，不采用 offset 伪造一致性。页面列长度错误明确失败，`finally` 主动关闭源迭代器。

`routes/rag_query.py`、`build_indices.py`、`run_evaluation.py` 三处共用迭代器并主动关闭。后两者提取可调用构建函数，原 main 路径使用同函数；构建脚本新增 main guard，导入不再自动连接数据库。

`index_registry.py` 对单遍 Chunk 输入仅保留最终列表，真实 rank_bm25 0.2.2 接收 token 生成器，不传 tokenizer 参数（其源码此参数会调用 Pool.map）。TableIndex 保留 table 优先及无 table 时全部 Chunk 回退；rank 缺失仍消费完整输入构建 TableIndex。

最终 BM25 词频、Chunk、TableIndex 及持久化 JSON 仍为 O(N)；此次消除候选全集原始 results 与 tokenized 中间列表，不声称常量内存。兼容门面全集 get 本身仍 O(返回量)。

## 实际验证

使用已有独立 `.tmp/backend-quality-venv-20261012/Scripts/python.exe`，非 R7 运行库。完整命令、版本、退出码见 receipt，源码及日志逐文件 SHA256 见 manifest。

- 初次红：7 failed / 1 passed，exit 1；三个调用方尚未分页/缺提取函数、单遍输入返回耗尽迭代器。
- rank 缺失专项红：1 failed / 19 deselected，exit 1；TableIndex 漏全集回退。
- 最终绿：20 passed / 4.62s，exit 0。

真实 SQLite WAL 合成数据验证三个实际调用方：137条、每页17、最后页不漏；真实 BM25 得分与原全量 token 算法逐元素相同；并发删除/新增保持原快照；早 close 与三入口 token 化异常均及时释放；TableIndex 使用真实 DuckDB（观察其 ingest 输入，未替换计算）验证选择语义；空集合、已有索引跳过及 legacy 单 get 合同有证据。

红测期间旧构建脚本导入触发空 Chroma 创建，已核路径由私有副本 `__file__` 推导，仅写私有 `backend/output/vectordb`，未读取生产数据。绿实现 main guard 已消除此导入副作用。

候选适配器实际组合、完整 backend 测试、全量双90覆盖、安全扫描及 provider 链尚未执行。此次没有提交、推送、部署或迁移，不构成生产准入或完整项目验收。

## 2026-10-17 R2 修订

独立审发现的两个 Medium 已在私有副本修复：首次 `next`（包括空耗尽、异常）移入共享 `try/finally`，确保可关闭输入释放；rag helper 同时保留仅分页能力对象的支持和无读取能力对象返回 None 的旧回退。rank 未安装时仍保留尚未消费的输入给 TableIndex。

新增独立测试原样复制后实际红测：`3 failed, 26 passed in 10.58s`、exit 1。修复后在新锁定隔离集成环境执行原20项及独立9项：`29 passed, 1 warning in 5.38s`、exit 0。实际 Python3.12.15、SQLite3.54.0、NumPy2.5.4、rank_bm25 0.2.2、DuckDB1.5.5。warning 为该环境尚未安装 pytest-timeout 导致 timeout 配置项不识别；未改配置或屏蔽warning。

新冻结 [R2回执](sqlite-r8-consumers-r2-20261017/receipt.json) 包含准确命令、退出码、运行库身份及源码hash；[manifest](sqlite-r8-consumers-r2-20261017/manifest.json) 覆盖66项，SHA256 `63d4084f6ad92d6df1e80c3132e1ff9ac9ff385f9d392df20eb64d4ae8206f8d`。新包源码逐文件与实际被测试的私有源码核验一致，原66项冻结包全部hash无漂移。R2独立复核待root安排，不能把本次作者绿测称为独立复核；适配器组合及全项目准入仍待执行。
