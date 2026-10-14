# 向量存储替换设计独立评审

日期：2026-10-13。评审者与设计者独立上下文；只写本报告，未改产品、设计、锁、环境、数据或研究冻结。

## 审查总结

设计正确限制在已授权的设计/隔离 MVP，消费者盘点基本完整，过滤、cosine 分数、安全审计及旧数据保护方向合理。初审发现 High 1 项、Medium 2 项，设计者修订后定点复核均关闭；当前未关闭设计问题 0 项。结论：**设计评审通过，可继续隔离 MVP；不代表候选验收、选型完成、产品集成或迁移通过**。

输入快照：`docs/design/2026-10-13-vector-replacement-design.md`，SHA256 `637b1bab9ba38ce72049ca8ec83f5ab4f523cbacce318964e65645824d015109`，共 125 行；分支 `master`，HEAD `46b202c3e400741fd569f024412c0745f224a538`。工作区存在大量其他修改，本报告结论绑定该设计文本而非整项目快照。

复核快照：同文件 SHA256 `2a1e7bde67942a13bf8ad2bc6b681b708fb2ad6a6942ac04d6b2b43a0b026c95`，139 行。下方保留初审问题及原行号作为闭环记录；最终状态以文末定点复核为准。

已读取根 AGENTS、memory/index 及今日记录、安全决策包；采用 requesting-code-review 的独立评审组织方式。只读核对 VectorStore、三处 `_collection.get`、研究身份 SQL、health/catalog、backup、index_registry、部署/依赖入口；未启动生产客户端或执行候选探针，LanceDB MVP 运行证据不属于本报告。

## 问题清单

### 🟠 High H1：分页导出与应用备份的一致性单位未落定

位置：设计文件第 61、69、78、95 行。

问题：设计要求“一致性 snapshot”，但目前只描述单 collection 写锁、恢复时停写，以及静态 >5000 条导出核验；尚未规定导出过程中固定哪个读版本，或应用备份如何同时冻结所有 collection、向量 manifest 和 BM25/Table。跨页写删会造成 offset 导出漏行/重复；各 collection 单独一致也不代表应用级同代。现 `backend/services/backup.py:26-35` 的清单未包含 runtime artifacts，`backend/index_registry.py:21-24` 的 BM25/Table 分别持久化且没有与向量共同 generation；不能把现存能力当作同代保证。

必要修订：在 Phase C 固定协议，Phase D 前关闭。可选最小方案为全局维护屏障（阻止并排空入库/删除和辅助索引更新）后导出；或固定存储读版本/事务并给所有相关 artifact 建一致身份。必须说明快照覆盖范围、稳定分页顺序/游标、版本固定方法、文件与 manifest 发布次序、崩溃清理、Windows 开放句柄导致切换失败时的处理；无须为此先建设新在线服务。BM25 可明确由固定向量快照重建；Table 无法重建时，必须包含其 artifact 或报告不可恢复。

文字示例（before → after）：

```text
before: >5000合成记录分页导出总数、ID/metadata/vector hash一致。
after: 导出固定一个已提交版本；稳定分页期间并发写删不改变导出ID集合。
       应用备份在全局屏障内绑定全部collection与可恢复辅助artifact；
       manifest最后发布，恢复仅激活完整且校验成功的一代。
```

验收：隔离两 collection，分页期间另一进程写删；逐页合并必须恰等于一个预登记快照，无重复/遗漏。并发更新辅助 artifact 的备份应等待/拒绝或得到明确同代快照；在复制及 manifest 发布前后终止进程，恢复只能选择完整旧代或完整新代。仅静态 hash 一致或普通目录 copy 不算通过。

### 🟡 Medium M1：原向量保真与检索浮点容忍应分别定义

位置：设计文件第 63、65、91、107 行。

问题：保留“原向量/dtype”和迁移“原向量值全量对账”尚未规定编码；检索误差 ≤1e-5 不能覆盖原值保真。若候选 schema 将 Python float/float64 直接转 float32，排序可以通过而迁移摘要已变化。当前真实旧库 dtype 尚未盘点，因此这不是已发生的数据损坏。

建议：Phase C 明确 canonical 原向量编码、dtype 和维度来源；必要时保留原值列/字节表示，再派生搜索列，禁止静默有损转换。将分数容忍、搜索计算精度和迁移原值对账分开；当前合成 MVP 添加不能由 float32 精确表示的 float64 值、非单位向量和极小有限值。真实旧库有损转换仅可在后续明确评审/授权后接受。

文字示例：

```text
before: 归一化用于计算，原向量另保留。
after: 原值以声明dtype的规范编码持久化并逐值/规范字节对账；
       搜索列与归一化是派生数据，score容忍不适用于原值迁移。
```

验收：同一合成输入在写入、子进程重开、导出、快照恢复后原值规范摘要不变；另报精确排名与 score 误差。当前可实施合成探针，不读取真实源。

### 🟡 Medium M2：本轮消费者探针和后续全链验收需要明确拆开

位置：设计文件第 83-96、115-118 行。

问题：第 6 节称“隔离 MVP 验收矩阵”，其中消费者项又要求真实适配运行 worker、机器人、health、backup 等；但本轮明确禁止产品集成。行内“先验证最小消费者契约”未列明边界，易使两候选因没有改生产而被误判失败，或将合成门面测试误报为全链通过。

建议：为每项增加 `当前隔离探针 / Phase D集成验收` 范围。当前只在隔离 harness 中以显式路径/合成 embeddings 验证门面入参返回值及全量导出；不导入会启动真实服务、加载 .env 或访问默认 output 的模块。现役消费者真实适配、HTTP健康键兼容、全链备份及研究移除依赖检查保持 NOT_RUN，未来另授权执行。

文字示例：

```text
before: 消费者：以真实适配运行worker→查询/机器人……
after: 当前：真实候选+隔离门面契约探针；无生产模块改写。
       Phase D：worker/机器人/BM25/Table/health/catalog/backup/CLI真实适配回归。
       当前NOT_RUN不等于候选失败，也不能记成全链PASS。
```

## 已核实的正确边界与待验证项

- 三处外部 raw collection 读取确在 `backend/routes/rag_query.py:43`、`backend/build_indices.py:22`、`backend/run_evaluation.py:537`；`hasattr(_collection)` 的旧重建判断也应随未来消费者迁移更新。设计已覆盖，无新增遗漏阻断。
- health/catalog 将 `embedding_metadata` 行数当 chunk 数不可靠；改为中立 count 合理。保留 `chromadb` 键一版兼容属于待确认契约，不能未经决定删掉。
- 研究 `local_scope_v2/source_mapping_v2/isolation_snapshot` 直接依赖旧 SQL/目录身份；不可因新门面可用就修改历史冻结。正式部署移除 Chroma 可与隔离离线旧库读取环境并存，最终需查锁、实装、镜像及 import 全链，不能只改 requirements。
- `_prepare_sqlite_safe_mirror` 会删同名临时目录并复制库，新设计取消隐式可写分叉正确；属于显式待接受的行为变化，不是本轮可直接改产品的授权。
- 分数公式及三个 JSON metadata 字段的解析与当前实现相符；缺失/null/bool/数字、非法 where、重复 ID 仍必须对锁 Chroma 合成库差分。AST/Expr 不天然消除字段名和类型语义差异。
- SQLite 精确扫描与 Lance 精确模式均只是候选。推荐 SQLite 作为最小依赖基线有理由，但在真实正确性、规模与安装审计通过前不视为已选定。200ms/1GiB/500ms 明示待确认预算，未作为既有产品承诺；100K/512 仅合成评估点。
- 无新增前端/全文搜索/ANN需求；中立 export/health/snapshot 是解除现有旁路依赖所需能力，范围合理。未知 API、dtype、Windows 锁与并发需记录 FAIL/NOT_RUN，不能用理论补实测。

## 官方来源独立核实（2026-10-13）

- [LanceDB 0.40.0 固定发布页](https://pypi.org/project/lancedb/0.40.0/) 本轮访问成功：存在 Windows x86-64 `cp310-abi3` wheel，发布日期 2026-10-07；wheel SHA256 `aaea68920b88e3d0b84a9ec84bc1585ad04239b9ca1bfcd1e491c2c12bffddc2`。发布文件存在不证明本机 import/CPU/运行可靠性。
- [LanceDB Python API](https://lancedb.github.io/lancedb/python/python/) 支持类型化表达式，说明默认读一致性检查关闭；跨进程可见性必须显式配置并验证。其单表事务能力不证明应用级多表与辅助 artifact 事务。
- [LanceDB filtering](https://docs.lancedb.com/search/filtering) 说明 prefilter 与 postfilter 返回数量差别；不能拿 postfilter 充当兼容过滤。文档的规模宣传不纳入本机性能结论。
- [SQLite WAL](https://www.sqlite.org/wal.html) 说明单写者、同机约束，并提示 WAL 模式读操作也可能 SQLITE_BUSY；探针必须覆盖读路径锁超时/恢复，不可只测写锁。滚动官方文档须继续绑定最终锁版本验证。

## 优先级与验收边界

1. 当前持续执行已授权合成最小 I/O；在设计中明确 H1/M1/M2 的责任阶段，MVP报告逐项 PASS/FAIL/NOT_RUN。
2. 选型前固定 dtype/过滤/重复ID/读版本及可恢复性契约；补 H1 并发快照探针，不以正常重开代替崩溃/恢复验证。
3. 真实候选证据、实际规模与用户产品取舍齐备后再提出集成计划。全链消费者、双90、锁/安装安全、备份恢复通过前不移除现役 Chroma、不迁移/提交/发布。

## 修订定点复核

- **H1 CLOSED（设计层）**：修订第 63 行规定固定 export 身份、唯一键 keyset、SQLite事务/封存backup及Lance固定版本/封存副本；第 85 行规定全写者全局屏障、固定锁序、全部collection与辅助artifact身份校验、staging及单active-manifest原子发布。第 104、111 行增加并发分页与跨collection/辅助artifact备份、发布前后崩溃验证。当前代码无此协调器，未来必须用真实Windows文件语义和全部产品写者证明；文字修订不等于机制已实现。
- **M1 CLOSED（设计层）**：第 67、100、120 行区分原载荷与派生搜索列，记录dtype/字节序/编码/hash；未知源dtype保留UNKNOWN，不能冒称恢复入库前精度。新增float64非float32可表示输入；降精度影响单列且待用户决定，score容忍不得代替原值对账。
- **M2 CLOSED**：第 91-106 行限定本轮隔离门面/真实候选探针；第 108-112 行将真实产品消费者、应用屏障与较大规模评估单列后续NOT_RUN；Phase B出口同步。没有将未授权生产修改塞入当前MVP。

复核无新增阻断。锁版本API、Chroma差分、并发/崩溃、安装审计、性能、应用屏障均仍需实际证据；其中任一失败只重开受影响候选/协议。设计评审通过不能解除现有Chroma安全公告及项目其他交付阻塞。

### 阶段1差分回流的局部复核

后续设计SHA256 `fc0f393613cc20c6cfae41aea31e247fd7ca7808dcd316963b8797d5a7f7ae3d` 已定点复核。18项真实合成差分发现5项缺失/类型/未知键语义差异后，设计仅重开过滤：固定metadata白名单改为动态安全键表示，显式presence/type/value；合法未知键按缺失语义处理；未证实错类型否定/int-float组合先补真值表；无法精确下推时在固定G全部候选上语义过滤后再精确top-k，禁止先截断。资源限制作为新增契约变化单列；当前过滤验收明确BLOCKED，并保留Windows警告和未运行范围。

上述回流合理，设计层无新增阻断；当前原生mapper兼容差异并未由文档自动关闭。阶段1独立执行及兼容阻断见 [MVP审查](2026-10-13-vector-replacement-mvp-review.md)，后续r2应保留旧冻结并另行独立核实。

验证记录：本轮仅只读源码/设计核对、Git分支/HEAD/状态查询和官方网页核实；相关 shell 查询 exit 0，未执行产品测试/候选探针/安全扫描，不给出整体通过声明。根负责人负责 memory 接续；本报告不越权编辑其他文件。
