# SQLite＋NumPy完整项目适配器设计（R8）

2026-10-17执行闭环：[最终验证](../testing/2026-10-17-sqlite-vector-r8-final.md)。用户已确认保留合法规模；资源前置/载荷分片/公开metadata流式写、同快照分页及三个真实消费者完成隔离组合，root50项＋3子测试通过；独立消费者32、core29＋3子测试通过；最终335差分及2public往返通过。真实Chroma重复/近重复索引查询会不稳定缺ID，候选按已确认精确扫描完整返回min(k,N)，不宣称全域ANN逐ID一致。生产集成、迁移、全量双90及全原生审计仍另验；下方设计候选等待确认描述为起草历史，现以此更新及最终证据为准。

状态：2026-10-16用户明确选择保留现有合法数据规模，并同步改造三个全量读取消费者；本修订待独立复核。未生产切换。承接R7真实运行库验证及R4b/R6数值、R5错误合同。“完整”指项目VectorStore及现存消费者所需合同，不是Chroma全部服务端API。现役代码与数据不动，旧冻结目录不修改。

## 路线及取舍

推荐固定SQLite记录schema＋独立metadata兼容解释器＋NumPy精确分批评分。动态metadata无需ALTER或schema回填；过滤先于top-k。相比重新引入LanceDB，此路线避免已发现的Rust原生公告阻断；相比仅包一层R7 Store，它覆盖真正消费者而非只读写向量。代价是扫描为O(ND)，不承诺HNSW性能或距离逐bit相同。

## 接口与兼容范围

隔离候选实现与现役 `backend/vector_store.py` 同签名：构造collection_name/persist_dir/embedding_dim；add_chunks、delete_by_source、delete_by_chunk_ids、search、get_by_ids、count、list_sources、get_collection_info、create_migration_collection及create_vector_store。提供兼容 `_collection.get` 所需ids/where/include/documents/metadatas返回形状，覆盖 `backend/routes/rag_query.py` 的直接调用；不将它遗漏为私有实现。任意其他私有API必须先盘点实际引用再确定准入。

保留Chunk metadata构建/解析、None转空字符串、三个JSON列表字段、空批次/no-op、长度不符ValueError的Length mismatch短语、source去重排序、info字段及迁移集合维度隔离。search返回chunk_id/text/score/source='vector'/metadata；score按现役公式round至4位，文本切片及metadata_keys规则与现役一致。重复ID、get顺序、空where、负切片参数、默认维度/延迟绑定等未凭猜测决定；由锁定Chroma1.5.9真实合成oracle登记结果后实现。

旁路消费者包括 `backend/build_indices.py:22`、`backend/run_evaluation.py:537`、`backend/routes/rag_query.py:43`；三者改为同一读快照内分页构建，共用 `backend/index_registry.py` 的增量token化入口。页面ids/documents/metadatas三列对齐，返回原始flat metadata；不能分页仅返回第一页。兼容 `_collection.get` 保留全量返回语义及固有O(返回量)内存，不引入8MiB返回总量拒绝条件。BM25最终模型、chunks及TableIndex仍可O(N)，本轮消除全量运输副本和完整tokenized暂存，不声称最终索引常量内存。

where支持现役Chroma接受的scalar隐式eq、eq/ne/gt/gte/lt/lte/in/nin及and/or组合，包含缺失键、bool/数字区别、字符串、列表首类型、混合数值、I64/U64/有限binary64边界、负零、宽record及读回。复用已验证数值入口合同，重新绑定SQLite执行路径。formatter任意binary64全域等价尚无证明：新增真实差分及源码依据，任何反例保留阻断，不以随机全绿声明全域证明。新键应在写入后立即可过滤，不做静默丢字段或类型强制归一。

有意变化仅沿用用户已确认的非有限向量invalid_input。R7零向量拒绝不是新适配器批准政策；先实测Chroma零向量行为，若无法兼容再单独请求产品决定。ANN并列排序不稳定与精确扫描须明确区分：有唯一距离的top-k比较ID及4位score；真正距离并列核验等价候选集合，独立另测候选自身ID稳定并列。不以放大容差掩盖非并列排名/舍入差异。

## 资源与异常边界

用户批准保留现有合法数据规模：删除新增4096维、1000批次/top_k、10000记录、1MiB单记录、8MiB总返回和100MiB总快照限额；不将内部预算变成新的合法输入拒绝条件。256条/8MiB仅为普通块目标，可调小用于验证。超块单行使用单行路径，超块向量以分维窗口计算稳定范数和点积；不建立N×D全集矩阵。新存储应将大载荷分片保存，避免SQLite单行上限成为新增能力限制；本机磁盘/SQLite物理极限须报告真实storage_unavailable而非空结果。现存API输入与输出对象本身的内存不可由块预算消除。

分配前检查shape/dtype/长度/合法标量，不能先np.asarray全集再检查。合法大list/ndarray按窗口转换与编码；object钩子不得意外执行，容器类型拒绝须由实际项目入口/oracle证明非法，不能另造限制。文本UTF8和metadata JSON使用增量编码与私有临时文件/分片，不先构造巨大完整编码副本；周期与不合法类型按既有合同拒绝。整个批次先流式校验到私有磁盘暂存，再单事务写入，末项错误不得留下前项；暂存空间不足回滚并清理。固定SQLite整行长度只约束内部片段，不约束合法逻辑记录总长。

单次只读事务固定数据视图，游标逐条读取过滤字段和向量片段，不加载全部documents。分块过滤后稳定缩放归一化评分，top-k堆保存至多min(k,N)个(id,score)，最后只读取命中记录。k和结果总量不设新限额；O(k)堆及结果内存明确计入。参数化SQL及受控schema，过滤不可拼接外部SQL；不得过滤后只扫描前N个或达到累计扫描预算就成功返回。扫描结果等价不分块参考算法，分块大小变化不改变输出。

错误沿用R5/R6 typed合同；invalid_input/invalid_filter/invalid_dimension/unsupported_capability与storage_unavailable分离，不继承TypeError以免retrieval重试；失败不可伪装空列表。公共诊断不包含原输入，cause内部保留并经既有安全日志路径验证。逐连接硬化继承R7；多集合命名不能成为路径穿越入口；不复刻现役静默镜像故障恢复。

## 验证出口与执行次序

执行前补充：所有消费者对 `iter_record_pages` 取得的迭代器必须以try/finally主动close，正常耗尽、异常及早停都验收，不依赖GC。consumer与adapter分别开发后由root复制到新私有组装目录运行组合测试，不能引用不存在的跨目录测试。

2026-10-16真实oracle发现数值阻断：201条定向舍入边界输入中，直接binary64余弦→4位round与Chroma结果有81条不同。数学参考仅证明扫描实现正确，不能证明Chroma得分兼容。后续必须复现实际float32规范化/距离路径并在相同输入复验；不扩大容差、改变score合同或忽略边界。合法大finite原始向量若在float32投影中变非有限，写/查行为需分别按oracle及用户已有决定核实，不自动扩展拒绝政策。

设计细化（只读消费者盘点后）：metadata=None只生成现役四个默认字段，普通metadata对象中的None转空字符串，不能混为同一种默认构建。排名堆以未round原始得分排序，最终格式化才round；扫描与命中payload读取共用同一连接和事务。

分块预算覆盖id/metadata/vector而不只矩阵；普通块预算不足先刷新，超块单行走分片/单行路径，不能借SQLITE_LIMIT_LENGTH拒绝逻辑大记录。只有命中行才读document；逐行组装输出但不截断其总量。严格RSS上限仍需独立进程/OS预算，不能由载荷限制推导。BM25将逐页chunks保留一次，并向rank_bm25 0.2.2传无tokenizer的单遍token序列生成器，最终频次模型/chunks O(N)真实计入；TableIndex保留原有table优先/无table回退全集规则，不漏最后页。

兼容声明基于现有合法规模；不存在用户未批准的容量拒绝例外。新增 `iter_record_pages` 在一次调用生命周期内持有同一只读事务，采用稳定keyset游标，关闭/异常均释放；禁止跨连接OFFSET读取不同generation。扫描、过滤、评分、命中载荷都使用同一快照。大单行页面允许只有该行，记录实际最大单行内存；若需严格小于单行的内存必须使用字段分片流，不能宣称普通页面接口已经实现。备份/恢复使用分块hash与分块复制，先可信hash验证再解析，取消总快照额外上限。

1. 独立审查本设计；修正阻断项后用户确认设计，形成具体编码计划。仅新建 `.tmp/sqlite-vector-r8-20261016/` 隔离候选，使用R7锁定运行库；不覆盖R7/R6。
2. 先有效红测试：非法shape/恶意转换钩子、metadata周期/类型，合法超块batch/记录/维度/输出不拒绝，SQL内部片段长度及暂存失败回滚；spy验证非法对象拒绝先于转换/存储，合法大输入按窗口转换不建立完整编码副本，再修实现。
3. 真实SQLite分块查询与独立不分块数学参考对照；块1/17/256一致，评分结构块+k，计入输入/输出/单行物化例外；空/全过滤/第末块最优/并列/极端有限向量、读快照期间并发写删、真实资源不足错误和连接关闭。结构断言及子进程峰值内存观察分别报告，不冒充严格OS内存上限。
4. 锁定Chroma1.5.9隔离oracle比较全部门面、metadata roundtrip、过滤接受/拒绝及成功ID、4位score、创建重开/多集合/删除/新增字段；保存实际命令、版本、seed、差异和失败证据。复跑R4b/R6已有已测域；数值/formatter新增反例必须处理，未处理不得标完整兼容。
5. 私有复制实际retrieval和rag_query消费者运行合成数据，覆盖成功/空/输入错误/真实存储失败，记录完整或subset执行范围。worker/provider全链未执行须单列，不使用真实凭据或生产材料。
6. 独立代码及新输入复审，root最终快照复跑，冻结源码/锁/报告/退出码；规范与memory回流。生产集成、现有数据迁移及发布另行决定；任何提交仍受全相关子项目全量双90与漏洞扫描门槛约束，专项测试不是提交准入。

验收：上述三类目标逐项证据通过才关闭；实际oracle未覆盖或失败处标待验证/部分修复，不通过缩小兼容域宣称完成。
