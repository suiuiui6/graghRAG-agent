# 向量存储替换设计与隔离 MVP 评估

R3局部修复（2026-10-14）：[修复证据](../testing/2026-10-14-vector-numeric-r3.md)及[独立复验](../review/2026-10-14-vector-numeric-review.md)关闭原4项有限大float过滤拒绝（H1有界范围）。原76、原44、新162稳定条件零差异；9cosine消费者通过。H2原始record/query入口舍入及超I64 Python int兼容仍OPEN，原始312中的76模型偏差未回写。当前仍不允许把局部修复等同完整替换。

数值语义后续修订（2026-10-14）：已形成并独立确认[版本绑定的有界转换合同](../contracts/2026-10-14-vector-numeric-semantics.md)。r3仅按该合同修复有限float比较分支；原始metadata及查询literal入口舍入、超范围Python int不对称行为另标H2 OPEN。下方r2失败为历史实证，不回写其结果；局部修复不能自动解除完整替换与原生安全门槛。

## 2026-10-14 隔离r2边界结论

动态metadata投影已取得原76案例局部零差异；扩展44个真实差分案例中原40匹配，新增4个有限超大浮点条件与Chroma不一致。当前编译器强制转int64而拒绝，Chroma合法返回；负超界条件对int64最小值还显示端点转换行为，普通数学常量替代亦不能假定正确。9组过滤后cosine top-k及旧score公式验证通过，不消除上述过滤阻断。

本轮停止猜测修复，保留真实FAIL并等待独立复核，证据见`docs/testing/2026-10-14-vector-replacement-r2.md`。下一步须先固定超界literal/记录类型/端点的真实转换真值及公开契约取舍，才重开受影响numeric分支；不重启无关设计、不以浮点容差或缩小合法输入掩盖差异。当前仍否决直接产品替换；完整适配、增量schema/回填、全局快照、崩溃恢复、原生安全审计及迁移均未验收。

日期：2026-10-13。状态：设计修订；首轮独立设计意见已关闭，真实MVP随后发现过滤差异，本轮仅重开过滤语义并待定点复核及用户确认候选。原生Lance表达式映射直接替换已否决，不能产品集成。

授权范围：设计、官方能力核实、独立锁环境 MVP 评估。本文不授权生产集成、数据迁移、依赖替换或发布；未修改生产/测试/锁/.env/Gold/output。沿用项目默认工作流，不创建或恢复 goal/Harness 状态。设计者唯一写入本文件，memory 由主负责人汇总。

## 1. 需求分析与背景

核心需求：在保留文档入库、检索、删除和恢复行为的前提下，评估替换仍有未修公告的 Chroma 依赖。

输入：[安全决策](2026-10-13-vector-security-decision.md)、根 AGENTS.md、memory/index.md 与今日记录、[RAG 蓝图](../../integration/rag-engineering-blueprint-v1.0.md)、[项目工作流](../governance/agent-workflow.md)。读取工作区分支为 master，大量其他任务修改存在并保留。安全决策中 Chroma 1.5.9 的 4 唯一 GHSA/无 patch 为已有扫描事实；嵌入式缓解不等于扫描清零。本文不重新认定全项目测试状态。

用户场景：worker 写入显式 embeddings；查询路由/机器人以多路召回组合向量结果；进程重启恢复 BM25/Table；管理接口统计健康、备份及恢复；研究链保留冻结索引身份。前端页面和业务 API 无新增需求。

## 2. 页面/模块清单与消费者盘点

| 优先级 | 模块/证据位置 | 当前行为及替换要求 |
|---|---|---|
| P0 | backend/vector_store.py | 唯一存储适配层；PersistentClient、collection、cosine、metadata 转换、持久化及异常 mirror；完整接口见第 4 节 |
| P0 | backend/worker.py:822 | embed_texts 后 add_chunks；异常走 degraded，仍继续建 BM25/Table。替换不得把存储故障误报正常完成 |
| P0 | backend/retrieval.py:1266；generator.py:1153 | search 投影，完整文本先形成证据身份再裁剪 1200 字符；metadata 白名单；支持旧签名 TypeError fallback。保留分数、来源、位置字段及证据身份 |
| P0 | backend/routes/rag_query.py:35 | 直接 `_collection.get(include=[documents,metadatas])` 全量重建 BM25，不能只保留 search |
| P0 | backend/index_registry.py | BM25/Table 内存注册、JSON snapshot/recovery 及 invalidate_rag_runtime；不直接依赖 Chroma，但需验证向量新快照与 BM25/Table 一致性 |
| P0 | backend/services/backup.py:26、:119、:217 | vectordb 整目录 copytree/tar，恢复前备份、覆盖恢复；在线直接复制不能视为新库的一致性快照 |
| P0 | backend/services/health_checker.py:92；catalog.py:132；routes/health.py:149 | 直接查 chroma.sqlite3.embedding_metadata、对外 chromadb 健康键；该表行数不等于可靠 chunk count。替换须调用中立探活/count，健康契约作兼容或显式版本化 |
| P1 | backend/build_indices.py:22；run_evaluation.py:537 | `_collection.get` 全量导出构建辅助索引；输出 Chroma 文案也需更新；research 冻结版本另处理 |
| P1 | backend/services/bot_handler.py:183 | 直接构造 VectorStore → RetrievalPipeline，必须消费同一 backend/path 配置 |
| P1 | backend/services/lifecycle.py:380 | vectordb 存储报告沿用目录归属；不能遗漏新目录或把旧库当现役 |
| P0 | backend/research/local_scope_v2.py:103；source_mapping_v2.py:69；isolation_snapshot.py:172 | 离线直接读 Chroma 内部 SQL schema/索引目录，属于研究身份消费者。冻结材料不修改、不用新适配冒充旧证据；后续新研究版本明确标明新 backend/schema |
| P1 | backend/scripts/check_imports.py:17；相关测试、部署及有效规范 | Chroma import 冒烟和实现细节断言需在未来集成阶段一致更新，不能提前删测试制造通过 |

本次有界搜索排除 output、虚拟环境、uploads、测试后发现生产 `_client` 仅在 VectorStore 内使用；`_collection` 外部旁路为上述三个全量读取点。测试中存在 `_client.get_settings` 与 `_collection` stub，未来需按行为重新核实。当前生产检索调用未传 where，但 VectorStore 公共契约明确承诺 Chroma where，不能因此删掉过滤能力。

## 3. 候选比较及推荐

仅评估以下两种；均保持本机嵌入式，不引入新 HTTP 服务或远程供应商。

| 候选 | 已核官方能力 | 非能力/未知及项目成本 |
|---|---|---|
| LanceDB 嵌入式 | Python 本地 connect/table；向量检索显式 cosine、未索引时穷举及可选 ANN；metadata prefilter；delete/filter；Arrow 列式数据与批量读取。官方 Python API 支持类型化 Expr，避免把外部输入直接拼 SQL | 非 Chroma API/where 原生兼容；需要 AST 翻译和 metadata schema。ANN 不保证精确召回；跨表事务/应用快照一致性、Windows 锁/进程可见性必须 MVP 验证。新原生轮子/Arrow 等依赖不可凭资料判安全 |
| SQLite（Python sqlite3）+ 现有 NumPy 精确 cosine | Python 3.12 官方 sqlite3 提供参数化 SQL、事务、只读 URI、backup；NumPy dot 可执行向量点积。SQLite WAL 支持同机并发读及单写者 | SQLite 本身没有向量检索；本项目需实现有界分批读取/归一化/top-k；O(N_filtered × dim)，不承诺大规模低延迟。WAL 不适用网络文件系统；连接不能随意跨线程共享；NumPy/SQLite 运行库仍需安全核查 |

**推荐：优先以 SQLite+NumPy 作为契约正确性和安全最小依赖基线，同时对 LanceDB 跑同一合成矩阵；最终选型以实际规模、延迟与审计结果决定。** SQLite 更易明确主键、批写原子性及备份语义，且 NumPy 已在 backend/uv.lock（读取时 2.5.3）；但它目前只是方案，不是已实现组件。若目标规模下精确扫描不达标，选 LanceDB 的精确模式作为首轮集成候选，再单独评审 ANN 召回取舍。不能因候选名不同就认定安全门槛通过。

安装边界（资料核实，不代表本机可运行）：PyPI `lancedb==0.40.0`（2026-10-07 发布）有 `cp310-abi3-win_amd64` wheel，适配 Python 3.12 的候选依据；官方说明默认 x86-64 wheel 要求 Haswell/AVX2 等，旧 CPU 可能 import 即崩溃。MVP 记录实际 CPU/架构、Python 3.12 补丁版、wheel/hash、完整依赖锁与 import 结果；不自动改用兼容包或源码编译。sqlite3 的 SQLite 实际版本来自 Python 运行库而非 uv.lock，单独记录 sqlite_version/threadsafety；NumPy 按独立环境锁定精确版本，未来集成需显式声明直接依赖。

原生安全边界：MVP [SQLite运行结果](../testing/vector-replacement-mvp-20261013/sqlite-results-1791896494464615000.json)记录SQLite 3.45.3；[SQLite官方CVE说明](https://sqlite.org/cves.html)（本轮2026-10-13实查）列CVE-2025-3277/29087修复3.49.1、6965修复3.50.2、7709修复3.50.3、CVE-2026-11822/11824修复3.53.2，均高于该运行版本。版本比较不是逐项漏洞适用性或可达性证明：concat_ws问题需攻击者控制大分隔参数；6965需任意SQL；7709需控制DB内容并构造坏FTS5；2026两项需任意SQL、启用FTS5且defensive关闭。应记录实际编译能力、DB来源/恢复入口、SQL控制和defensive设置逐项核实，不能把参数绑定或不主动调用FTS5直接写成已免疫。PyPI17包审计零公告不覆盖Python自带SQLite，也不能证明Lance/Rust/Arrow及其他wheel内原生依赖均无公告。正式集成须采用受支持且覆盖适用修复的运行库/构建，或完成逐项可达性独立审查并按项目安全门槛处理未决项；未处理前不得称候选安全清零。运行库升级另走隔离验证与依赖计划，本轮不替换系统DLL、不更新原Python环境。

### 官方来源（2026-10-13 查阅）

- [LanceDB PyPI 发布页](https://pypi.org/project/lancedb/)（查阅时 0.40.0，Windows wheel/CPU 边界）；[固定版本入口](https://pypi.org/project/lancedb/0.40.0/)供锁版本复核，固定页一次访问服务500，不将该次访问当成功证据；[Python API](https://lancedb.github.io/lancedb/python/python/)（本地连接、扫描、Expr/delete）。
- [LanceDB vector search](https://docs.lancedb.com/search/vector-search)（显式 cosine、穷举/ANN 取舍）；[metadata filtering](https://docs.lancedb.com/search/filtering)（prefilter、SQL/字段限制、旧版本 chained where 差异）。不采用官方规模宣传作为本机性能证据。
- [Python 3.12 sqlite3](https://docs.python.org/3.12/library/sqlite3.html)（transaction、参数绑定、backup、mode=ro、threadsafety）；[SQLite WAL](https://www.sqlite.org/wal.html)（同机、单写者、checkpoint/持久性边界）。
- [NumPy dot](https://numpy.org/doc/stable/reference/generated/numpy.dot.html)（点积，不提供向量库/事务）。上述网页为滚动文档，MVP 必须针对最终锁版本复核 API；文档访问失败不记作已核实能力。
- [Chroma metadata filtering](https://docs.trychroma.com/docs/querying-collections/metadata-filtering)作为 where 迁移语义参考，最终差分绑定当前锁版本，不能用滚动文档的新能力冒充历史生产契约。

## 4. 组件树、数据设计与契约

组件层次：现有页面/HTTP API → worker、RAG/机器人、管理/恢复消费者 → VectorStore 门面 → 过滤 AST / metadata codec / 分数适配 / 导出与快照 → SQLite+NumPy 或 LanceDB 后端。当前 Chroma 仅在旧数据离线读取环境和受控回退包中保留，正式替换部署最终不得传递安装 Chroma。

不新增 API 端点。门面保留 constructor(collection_name,persist_dir,embedding_dim)、factory、add_chunks、delete_by_source、delete_by_chunk_ids、search、get_by_ids、count、list_sources、get_collection_info、create_migration_collection；后者是另 collection/维度，不等于存储迁移。

新增中立内部能力供未来消费者迁移：分页 export_records（显式选择 embedding/文档/metadata、全量无隐含 top-k 截断）、健康只读探测、显式一致性 snapshot/restore。优先消除三个 `_collection.get` 旁路，过渡兼容 shim 若需要只能覆盖已盘点 get 语义，不暴露任意原生 client，不把私有属性作为长期契约。

分页必须绑定不可变 export_id/generation/collection集合/schema版本/记录总数，游标包含该身份与最后一个(collection_name,chunk_id)，按唯一键顺序 keyset 分页；身份或schema不匹配立即失败，不能混用活库OFFSET页。SQLite导出在同一只读事务快照内或读已封存backup；Lance固定table version集合且禁止回收所需版本，锁版本若不能可靠固定则只从停写封存副本读取。逐页记录ID/摘要，终页核总数与集合摘要；并发写删不能让同一导出漏项、重复或混代。

数据模型：collection manifest = schema_version/backend/collection_name/embedding_dim/metric=cosine/embedding_model_identity（未知保留 UNKNOWN）/dtype/generation；record = collection_name + chunk_id 唯一键、原文、原向量、原始 flat metadata 与结构化 metadata。source_file/project_id/content_type/page_idx 等可索引列必须与原始 metadata 同事务/同版本更新；未知字段保留。当前 entity_types/section_path/entity_ids 是 JSON 字符串，读取解析为数组；None 写成空字符串，空字符串/缺失/0/bool 与数值不可混同。新存储不得擅自重嵌入或改写旧字段。

向量保真单独验收：manifest记录源导出dtype、维度、字节序、编码与每向量摘要；原值使用明确的IEEE754 little-endian float32或float64二进制原始载荷保存，不以JSON默认格式或归一化向量替代。源只提供Python数值且无法证明原存储dtype时记录UNKNOWN及导出binary64基准，不能声称恢复了入库前精度。SQLite用BLOB+dtype/shape；Lance原值保存在binary列，检索vector列是明确标记的派生表示。若Lance检索列用float32而源binary64不可精确表示，dry-run必须量化转换数量、max absolute/relative error、排名/score变化，不能用score误差≤1e-5作为原向量迁移容忍。原载荷逐字节/规范编码hash一致才称无损；派生检索精度变化需用户明确决定。未批准降精度时，候选须支持原精度检索或按原值对全部过滤候选精确计算，不能只对float32 top-k重排后声称精确。

search 输出固定 chunk_id/text/score/source=vector/metadata；distance=1-cosine，score=round(1-distance/2,4)=round((1+cosine)/2,4)，相同/正交/反向应为 1/0.5/0。显式指定 cosine，不使用 Lance 默认 L2。归一化用于计算，原向量另保留；拒绝维度错误、零向量和非有限值（历史坏值须单列阻塞，不能静默丢弃）。精确并列按 chunk_id 稳定排序；旧 HNSW 近似/并列顺序差异报告，不假定逐位相等。text_char_limit/metadata_keys 保留现有投影语义和完整文本身份链。

过滤兼容范围：标量字段直等值、$eq/$ne/$gt/$gte/$lt/$lte、$in/$nin，以及嵌套 $and/$or。必须编译锁定Chroma的完整语义，而非将操作符逐个机械换成SQL/Expr。不得把JSON字符串字段隐式升级数组contains。原public where未限制metadata键集合，不能以固定字段白名单拒绝合法未知键并声称兼容；“安全解析合法键”与“仅允许已建物理列”是不同约束。

真实差分（[MVP机器汇总](../testing/vector-replacement-mvp-20261013/filter-differential-summary.json)，18case/6条合成记录，13相同、5不同）已确认：①source $ne/$nin在Chroma包含缺字段记录b，Lance SQL NULL排除b；②active:1与page:true在Chroma合法且结果为空，当前mapper因literal type拒绝；③未知missing_field $ne anything在Chroma匹配全部6条，mapper因白名单拒绝。这些是特定锁版本/夹具的实证，不能外推未经测试的所有比较/类型组合。当前原生映射结论为NATIVE_CAPABILITY_PASS_COMPATIBILITY_BLOCKED，直接替换否决；其余已评审设计不因此重开。

修订编译设计：保留每record完整metadata的key存在位与显式值类型（missing、bool、int、float、str分别编码；不要由SQL NULL或Python bool继承int来推断）。已知物理列仅为加速投影，另有同代键/类型/值语义表示支持合法任意metadata键；键作为数据literal/参数绑定，不作为外部SQL标识符。未知于schema的合法键按全体记录缺失处理，不能报unknown field。AST叶节点先计算presence/type条件，再执行旧库定义的比较；已证实$ne/$nin显式包含缺字段，错类型等值返回false而非raise。对于尚未实证的错类型否定/数值int-float混比/混合集合等，必须补差分后固定真值表，不靠SQL三值逻辑或对$eq取反猜测；$and/$or组合使用该真值表，并验证嵌套结果集合。

R2真值核实进行中：执行者76case Chroma探针发现int字段与float字面量1.5比较时存在转为1后的旧库语义，同时>2^53的int仍保持整数区分。该发现要求按字段真实类型保留旧库转换/比较顺序，禁止把所有metadata数字统一转float64或用epsilon近似等值；普通cosine数值容差完全不适用于metadata谓词。R2最终差分、报告及冻结尚待执行者收口，不据此宣称过滤已兼容，也不从局部case推广所有运算符的转换规则。

SQLite使用参数绑定的存在/类型谓词，Lance优先类型化Expr组合显式存在位和比较；若后端对任意键/类型组合不能精确下推，则在同一不可变版本对完整过滤候选执行受控metadata语义求值，再进行精确top-k，不可先截top-k后过滤。不得回退无过滤搜索。非法运算符、表达式形状、字面量、空列表/多键叶等仅在旧Chroma也报错时按兼容错误处理；合法输入不可因列类型或缺字段新增拒绝。资源上限若比旧库新增限制，应单列为待用户接受的契约变化，不能混入“兼容通过”。where_document/全文搜索不在现有public search签名内，不增功能；Chroma新运算符另盘点评审。

写入：MVP 先刻画 Chroma 重复 ID/批内重复行为，再确定兼容策略；禁止默认换成 upsert。collection 维度在空库 manifest 即固定，写前全批校验；批提交失败不可部分成功而谎报完成。SQLite 单写事务+有限 busy timeout；Lance 应用层按 collection 进程间写锁防检查/写入竞态，跨进程读取刷新及提交原子性需实证。不新增无界内存向量缓存。

Lance 专项约束：官方 Python API 的 read_consistency_interval=None 不检查其他进程更新，必须配置有界可见性或显式刷新，再实测 worker→长期查询进程。首轮精确模式显式 bypass_vector_index（或无索引且验证执行计划）；量化 ANN 的 _distance 可能是压缩表示距离，不能直接当原向量 cosine 分数通过兼容验收，未来若启用须重排并核实原向量距离。

## 5. 交互流程、异常与恢复

- 入库 → 校验 chunks/向量长度和类型 → 在同一 collection 写入 → 成功后更新现有辅助索引；失败沿用 worker degraded/error 分类，检索健康明确显示向量路不可用。
- 查询 → 验证向量/过滤 → 先过滤再精确排序 → 返回现有 score/位置 metadata → 多路召回与证据身份消费；空库/无匹配返回 []，损坏/锁超时返回可辨认故障，不能伪装空库。
- 删除 → 精确 ID/source predicate → 原子提交 → count/来源列表/重开均无残留；不存在 ID 为幂等无操作。跨向量/BM25/Table 删除一致性沿用现有业务能力并显式验收，不假称替换自动补齐全部删除链。
- 恢复 → 停写并关闭/失效缓存 → 恢复至新目录 → manifest/hash/count/可查询性校验 → 切换 generation → 重建/恢复 BM25/Table → 再开放流量。失败保留旧目录与最后有效 artifact。
- 当前 `_prepare_sqlite_safe_mirror` 在异常时删同名临时目录并复制旧库，会形成隐式可写分叉；新库**不复制这一策略**。路径/锁失败必须显式失败；需要 mirror 诊断时只允许唯一临时目录+只读快照+来源/hash/只读状态，不可接收入库、不可回写生产。此行为变化需用户接受。

应用一致快照协议（未来集成必需，当前并不存在）：所有影响任一collection及BM25/Table的写、删、建索引、恢复/创建collection路径必须经过同一跨进程全局写屏障；锁顺序固定全局屏障→按名称排序collection锁。屏障覆盖一次业务写至辅助索引提交结束，单collection锁不能保证应用一致性。备份持全局排他屏障，等待在途操作结束并阻止新操作；校验各索引对应的数据身份，不能给既有不同步artifact补同代标签。对同一G封存全部collection及BM25/Table（SQLite用backup，Lance用固定版本集合或关闭后完整副本），记录各自版本/计数/hash，在独立staging目录写manifest并校验完整性。校验后以同卷原子替换仅发布一个active-manifest指针，所有消费者按该指针加载G；不得逐个文件覆盖活跃代次。失败只留下未发布staging，不改变最后有效指针，重开可辨别未完成G。恢复也持屏障，失效旧缓存，完整验收G后原子发布；任何现存绕过屏障写者均阻断应用备份一致性放行。原子性/崩溃恢复须在Windows真实文件语义下验证，不能只靠设计推断。

Loading：现有任务进度与 runtime warmup；Empty：0 records/无匹配；Error：明确 storage_unavailable/invalid_dimension/invalid_filter/lock_timeout/corrupt_snapshot，保留现有 API 错误边界。无新增前端布局，桌面/移动页面行为沿用；后续只验证 Upload/Query/Health 的 loading/degraded/empty 不回归。

## 6. 验收分层（本文件不声明任何探针已通过）

### 6.1 本轮已授权的最小隔离契约 MVP

独立根目录/每候选独立 Python 3.12 uv venv、独立 pyproject/uv.lock、合成数据，无 .env/模型/API/真实 output 访问。所有路径显式传入且运行前断言不在生产/研究冻结目录。证据记录候选版本/锁/脚本/输入 hash、CPU/RAM/OS/Python/SQLite、命令/退出码/日志/机器报告及峰值 RSS；每项不能用 mock 代替候选真实依赖。

| 优先级 | 验收项 | 输入与通过标准 |
|---|---|---|
| P0 | 安装/安全 | Windows Python3.12 锁同步、wheel/hash、import、安装版本零漂移；锁与实际安装 pip-audit 无未处理公告。另记录SQLite版本/编译选项/defensive、原生二进制身份及官方公告/适用性范围；3.45.3低于多项官方fix，原生可达性未审不能称安全清零，PyPI零公告不替代原生审查 |
| P0 | 基本真实 I/O | 2维已知向量 + 512维随机种子；批写/读取/count/list_sources/collection 隔离；子进程重开值及维度不变；migration collection 不污染旧 collection |
| P0 | cosine/投影 | 同向/正交/反向 1/0.5/0；随机数据对独立 NumPy 公式 top-k 和 round(score,4) 一致（浮点阈值另记未四舍五入误差 ≤1e-5）；k大于数量/空库/文本裁剪/metadata 白名单 |
| P0 | 原值/精度 | binary32、binary64中不能由float32精确表示的值、极小/极大有限值；导出/重开原载荷dtype/编码/hash完全一致。检索派生列转换单独报告，不能借score容差掩盖原值丢失 |
| P0 | 完整过滤 | 第4节每个运算符、逻辑嵌套、缺失/类型/JSON字段/中文/引号；先回归已失败5case，再覆盖各操作符×字段缺失/存在×bool/int/float/str/非法literal、未知合法键、空集合/嵌套/复合否定；与锁Chroma结果ID集合/成功或错误类别一致。恶意键/字符串按合法数据literal或与旧库一致的错误处理，不拼SQL；过滤后足量返回。当前18case中5差异，兼容BLOCKED，不算该行通过 |
| P0 | 写/删边界 | 长度/维度/NaN/Inf/零向量/批内及存量重复ID；按source/ID删、重复删；失败无半批写入；重开无残留 |
| P0 | 并发/故障 | 至少2写进程+4读进程，交叉 add/delete/read；确认已提交可见和锁超时明确；写中终止子进程/磁盘不可写/坏manifest，重开旧或新完整批，无隐式镜像分叉 |
| P0 | 导出/恢复 | 最小5001条合成记录、多页游标固定版本；并发写删时该次导出总数、ID/metadata/raw-vector hash与固定G完全一致；存储快照恢复独立目录全量核验，损坏拒绝激活。此处是单候选探针，不是应用级backup验收 |
| P0 | 隔离消费者契约 | 仅在独立探针内模拟已盘点的门面调用/全量读取形状；真实候选I/O。不得修改或启动现役worker/路由/管理消费者；不把探针自带适配认作生产适配完成 |
| P1 | 最小性能记录 | 先5001×512维，批100/1000、top20、无过滤/1%及10%选择性；30预热+至少100查询，记录p50/p95/p99、吞吐/RSS/重开耗时，单写及混合负载；本轮先获取事实，不据未确认预算判产品合格 |

### 6.2 未来产品集成门槛（本轮 NOT_RUN，独立于 MVP 成败）

- P0：授权集成后，以真实适配执行worker→查询/机器人、BM25缺失重建、Table恢复、catalog/health、backup/restore和CLI全量导出；本轮未执行不计为MVP失败，也不得算通过。
- P0：两collection与BM25/Table的隔离应用协调器探针，在并发写删期间触发全局屏障备份；逐项证明同G与相同ID身份、写入等待/释放、坏snapshot拒绝、发布前/后崩溃只激活完整旧G或新G。未来还须对真实产品的所有写者执行同样验证，探针不能替代生产屏障集成证据。
- P1：取得实际典型规模和预算后，建议补1K/10K/100K×512维规模曲线、同机混合负载及内存测量。100K是后续建议评估点，不是本轮最小MVP要求或用户已承诺容量。

性能临时决策阈值待用户确认：实际典型规模及增长一档下，向量检索 p95≤200ms，单进程峰值RSS≤1GiB，4并发查询无错误且p95≤500ms；这些是建议预算，不是既有产品承诺。不达标不静默降精度/范围：评审 Lance 精确模式或单独提 ANN recall gate。真实数据规模尚未读取，矩阵规模只是合成评估点。

### 6.3 当前证据状态及范围

[MVP报告](../testing/2026-10-13-vector-replacement-mvp.md)由执行者维护；本次过滤修订直接核对上述机器差分汇总，避免把报告的早期“尚未运行”段落当最新事实。Lance原生查询/跨连接追加能力探针与完整适配兼容是两个结论；差分5项未关闭前不得选作直接替换。并发12次append成功时出现Windows latest_version_hint访问警告，需在MVP报告保留并评估，不能由追加成功推出崩溃安全。固定generation/5001分页、完整top-k NumPy差分、Chroma重复ID差分、多进程写、强制终止/断电、RSS/规定采样规模、应用屏障、真实数据盘点与全链适配等未运行项以机器汇总NOT_RUN为准，不视为兼容通过，也不混为已授权最小原生I/O失败。本文不替代执行者的最终证据冻结和独立MVP审查。

## 7. 数据迁移只读 dry-run 与回退设计

本轮只制定协议，不打开生产 Chroma client（初始化可能写文件），不导出真实记录，不迁移数据。未来获授权后先确认停写或一致备份窗口；源含 SQLite/WAL/HNSW，不能只拷一个 sqlite 文件。对一致不可变副本建立文件清单/hash，旧 Chroma 依赖留在隔离离线读取环境；任何 client 初始化写操作仅发生在可丢弃副本。

dry-run 默认仅读副本并写独立审计报告：枚举所有 collections、真实数量/维度/ID唯一性、documents/metadata/embedding 完整性、非有限/零向量/未知dtype、字段类型分布、目录/mirror真实身份。完整向量经 Chroma public get(include=embeddings,documents,metadatas) 对封存副本分页提取；不要凭 embedding_metadata SQL 假定拿到完整 HNSW 向量。导出项对 (collection,id) 建摘要，报告只存摘要/计数不泄露文本。按第4节记录源dtype/编码和原载荷hash，另列新检索表示的精度变化/影响/待用户决定，未决不得切换。任何缺向量/坏字段列出隔离项并阻止切换，不能猜模型重建。

未来 staging import 必须额外显式 apply 授权，目标为独立新目录；数量/ID集合/原文及metadata canonical hash/维度/原向量值全量对账，再做固定抽样和边界检索。旧 HNSW 与精确检索的 top-k 差异区分并列/ANN误差/真实丢失，精确参考排名为主；消费者回归后才提切换方案。

回退单位是旧应用/锁环境 + 旧一致索引 + 同代 BM25/Table artifacts + 配置manifest；不是把新库目录改名为 Chroma。首轮切换安排停写窗口，验证前不接收新写入；验证失败直接切回完整旧快照。新库接受写入后不能简单回滚，否则丢新数据：需明确停写、导出增量并审核反向导入，或接受恢复点损失的产品决定。无可靠增量日志时禁止自动回退。旧库回退仅作为带风险隔离恢复方案，仍有未修公告，不能声称完成安全交付。

## 8. 实施计划与阶段出口

| Phase | 优先级 | 可执行步骤 | 验收标准 |
|---|---|---|---|
| A 设计核定 | P0 | 独立 reviewer 复核本文件契约/旁路/安全/迁移；主负责人关闭意见并向用户呈现候选与取舍 | 独立评审记录无阻断，未宣称候选已跑；用户确认产品取舍 |
| B 已授权隔离评估 | P0 | coder 在独立锁环境实现最小真实候选 I/O探针，执行6.1矩阵；不改现役后端 | 每项PASS/FAIL/NOT_RUN、日志和hash；安装/安全/正确性失败候选淘汰或重开局部设计；6.2未授权产品集成单列NOT_RUN，不混入MVP通过/失败 |
| C 选型与详细计划 | P0 | 按真实矩阵比较候选、固定schema/where/重复ID语义/预算；独立评审实施计划 | 推荐绑定实测快照，用户确认选型与后续集成授权 |
| D 后续产品集成 | P0 | 改 VectorStore 及全消费者旁路、健康/备份/恢复/规范；更新锁及行为测试 | 全链真实依赖通过、受影响子项目全生产行/分支分别≥90%、安装/锁扫描通过；不修改研究冻结 |
| E 后续数据/发布 | P0 | 授权后 dry-run→staging import→独立对账→停写切换演练；按实际授权发布 | 旧源保护、对账/回退通过、外部副作用另获授权；未执行不得记完成 |
| F 可选扩展 | P2 | 仅性能证据要求时评估 Lance ANN及标量索引 | 单独召回/延迟预算与评审，不在首轮替换暗中启用 |

用户需要确认的产品取舍：①实际规模/增长与建议性能预算；②是否接受精确检索与原HNSW在并列/近似命中上的可解释排序变化及有证据的派生检索精度变化（原载荷仍无损保留）；③故障时取消隐式可写mirror，明确degraded；④健康键chromadb是否保留一版兼容别名；⑤未来迁移停写窗口与新库写入后回退RPO。这些不阻止当前已授权合成MVP；生产切换依赖答案及独立评审。

当前结论：设计与官方有界能力盘点已形成，首轮设计意见已关闭；本轮真实差分推翻原生过滤直接映射，过滤协议按实证局部修订并待定点复核。MVP完整兼容仍BLOCKED，不能视为选型或集成放行。旧数据只读盘点、迁移、生产集成、提交和部署未执行；未改现役生产代码或研究冻结。

2026-10-14数值入口增量：以[入口合同](../contracts/2026-10-14-vector-ingress-semantics.md)及[R4b冻结报告](../testing/2026-10-14-vector-ingress-r4b.md)为准。serde_json默认数字路径的通用port替代经验归一化；查询长整数不再人为限制为U64幅度，集合按首解析类型转换，raw payload与兼容readback分离，记录负零按SQLite REAL读回处理。已测宽整数144/旧32、原312+84及既有过滤/消费者回归零差异；仅局部兼容证据，不取代6.1未执行矩阵。异常类兼容、formatter全域边界、动态schema、原生安全、并发及恢复仍阻止选型和产品集成；H2部分修复，独立复审状态以最终报告为准。

2026-10-14公共异常增量：用户确认应用错误映射与浮点支持范围，见[异常契约](../contracts/2026-10-14-vector-error-semantics.md)和[R5隔离报告](../testing/2026-10-14-vector-errors-r5.md)。采用自己的固定安全消息/分类与cause，不复刻供应商类名；显式验证错误与native构造/执行故障分层，保留真实检索failed/空命中区别及旧签名兼容边界。新真实记录探针纠正“Chroma记录必限I64”假设：2**63/2**64/LO-1均接受并读回float，而候选仍限I64；原生接受NaN查询向量而候选拒绝，均为未解决兼容GAP。实际日志有脱敏processor，但裸标记在cause链仍残留，公共str安全不等于最终日志完全脱敏。以上与formatter、native安全和生命周期共同保持生产放行阻断，不因应用异常局部修复清零。
