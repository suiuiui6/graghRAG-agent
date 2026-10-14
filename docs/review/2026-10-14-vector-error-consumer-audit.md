# 向量公共异常边界：现有消费者只读审计

日期：2026-10-14。范围：现役 `backend/vector_store.py`、直接调用方、`errors.py` 与 R4b 冻结输入。使用 systematic-debugging；仅新增本文件，无生产、依赖锁、环境、数据或 Gold 修改，无提交。本审计没有执行 Chroma/Lance 依赖或真实生产；历史真实依赖结果与本轮执行明确分开。

## 故障摘要

- **现象**：R4b 已测成功结果和接受/拒绝状态一致，但拒绝类、消息不一致。例如冻结 `wide-integer-chroma.json:9-10` 是 `InvalidArgumentError / Invalid where clause`，候选 `generic_filter.py:15` 抛 `ValueError`；`fresh-lance.json:11359` 同样记录 ValueError。旧真实 Chroma 的空集合过滤在 `chroma-truth-1791897325903702500.json:194` 则本来就是 ValueError。
- **复现条件**：历史真实冻结已包含 U64 查询拒绝、集合解析类型不一致等案例；本轮未重复运行真实依赖。另本轮用 AST 从现役文件提取 `_search_vector_store_with_projection`，仅执行该函数和内存 Store 软件边界：第一次 search 抛 ValueError/OSError 时各调用一次并传播；抛 TypeError 时调用两次，第二次返回 [] 即整体返回 []。命令 `.tmp/backend-quality-venv-20261012/Scripts/python.exe -`（PowerShell here-string 输入），退出码 0；实际输出 `ValueError calls=1 raised=ValueError`、`OSError calls=1 raised=OSError`、`TypeError calls=2 returned=[]`。此为兼容重试的确定复现，不是存储引擎故障实测。
- **影响范围**：隔离候选异常兼容验收；未来接入时所有向量召回、向量写入及全量读取旁路。现役生产尚未替换。

## 根因分析

第一次偏离异常契约的位置是候选输入编译/编码/数字解析直接抛裸 ValueError（冻结 `generic_filter.py:15,38,45-47,82-106`，`parser_port.py:7,26,30`），没有表达“校验阶段、拒绝原因、存储执行失败”的公共语义。仅按异常类或消息改标签无法区分故障来源；Chroma 自身合法拒绝也不全属于同一异常类。

### 全部公开入口与现有语义

| 入口（现役文件行） | 输入/无结果行为 | 异常当前去向 |
|---|---|---|
| `VectorStore.__init__:46-79` | 建目录、PersistentClient、建集合 | 缺依赖 ImportError；第一次 client 的任何 Exception 触发镜像重试，第二次及建集合错误传播。该广泛镜像策略不能作为新 adapter 的通用错误分类规则 |
| `add_chunks:83-117` | 长度不等在 :95 抛 ValueError；空输入无操作；展平 metadata 后 add | 其余 vendor/存储异常直接传播 |
| `delete_by_source:119-128` | get 后仅有 ID 才 delete；无匹配无操作 | get/delete 错误传播，不能转成成功删除 |
| `delete_by_chunk_ids:130-133` | 空 IDs 无操作 | delete 错误传播 |
| `search:137-190` | query；合法空结果返回 []；分数为 `round(1-distance/2,4)`，支持投影 | 过滤、数值、向量及存储错误均传播 |
| `get_by_ids:192-213` | 空 IDs 直接 []；不存在 IDs 返回 [] | 读取错误传播 |
| `count:216-218` | 返回真实计数 | 错误传播，不能返回 0 |
| `list_sources:220-229` | 空集合返回 []，排序去重 | get 错误传播 |
| `get_collection_info:231-239` | 依赖 count/list_sources | 任一步错误传播，不能伪造健康 |
| `create_migration_collection:243-254` | 委托同类构造新集合 | 同构造边界 |
| `create_vector_store:312-323` | 工厂委托构造 | 同构造边界 |

`_parse_chroma_metadata:301-305` 的 JSON 解码失败转字段 [] 是结构字段解析的既有行为，不是允许把数据库读取失败变为结果 []。

### 数据流与消费者

1. 普通召回：`retrieval.py:738` → 投影包装 `:1273` → VectorStore.search → 引擎。包装 `:1279-1280` 对任何 TypeError 重试不含投影参数的签名。必须保持 storage 异常不继承 TypeError；更长期应按调用签名/明确能力协商兼容，不能按执行期间所有 TypeError 猜旧签名。
2. 多路并发：`retrieval.py:551-558`，正常 [] → `executed/candidate_count=0`；异常 → `failed/reason=recall_failed/candidate_count=None`，其余路仍融合。候选不得提前吞故障；异常统一后依然应到达此边界。多查询 `:587` 也用投影包装；retrieval rescue `:2779-2780` 同样记录 failed。
3. 写入：`worker.py:828-829` 构造/写入 → `:840-848` 所有非 ImportError 故障记录 `embed_failed`，回调 `embed=failed`、`PIPELINE_EXTRACTION_ERROR`、`degraded=True`；继续 BM25/Table。缺依赖 `:832-839` 是 skipped/degraded。此次应保留该业务选择；改变任务终态需另做产品契约。安全公共 message 很重要，因为 `:846` 用 str(e) 回调。
4. 路由启动：`routes/rag_query.py:150-153` 构造错误使 vector_store=None，日志 `vector_store_init_failed`，其他路径继续；BM25 重建 `:168-173` 外层吞可选优化失败。`rag_retrieve:482-486` 对初始化不可用：显式 enabled_sources/include_evidence_trace 是 HTTP503，其余是带 `pipeline not ready` 的空响应。这与查询成功零命中不能混为一谈。
5. 请求边界：`errors.py:398-408` 未处理普通异常 → HTTP500 / INTERNAL_ERROR / 安全固定用户消息；PipelineError 由 `:366-381` 特殊处理；RequestValidationError 由 `:383-396` → 422。**裸 ValueError 和 InvalidArgumentError 均不自动变 422。** `classify_external_error:277` 将 ValueError/TypeError 归响应 PARSE，但向量调用链未调用该函数，不能拿它做向量通用映射。
6. `_collection` 旁路：`routes/rag_query.py:43`（启动重建）、`build_indices.py:22`（CLI，无 try，失败退出）、`run_evaluation.py:537`（重建索引，`:557-558` 打 WARN 后继续）。未来必须统一到 adapter 的明确 scan/read API 或受同异常映射的兼容 facade；只包 search/add 不覆盖它们。当前 `hasattr(_collection)` 也是能力依赖。源码扫描排除了 output 历史副本及虚拟环境；未见其余第一方生产旁路。

### 类与消息依赖结论

扫描第一方 backend 生产及测试，未发现导入/捕获 `chromadb.errors.InvalidArgumentError` 的业务分支；vendor 自身代码及 output 历史环境不作第一方消费者。现有明确向量异常断言为 `tests/test_runtime_helpers_readiness.py:296` 的 `pytest.raises(ValueError, match='Length mismatch')`，以及 `:324` 缺依赖 ImportError 消息；未来需要保留或在批准契约变更中明确更新。没有证据要求复刻 Chroma 所有错误文字。既有 wire ErrorCode/安全消息、失败遥测与降级终态才是直接消费者行为。

## 修复方案（给隔离 MVP coder，非生产集成授权）

新增纯 stdlib 公共异常模块于独占新 MVP 副本，定义 `VectorStoreError(Exception)`，子类 `VectorInputError` 与 `VectorStorageError`。采用固定安全 message、机器 code（例如 invalid_filter / invalid_record / invalid_vector / unsupported_capability / storage_failure）、operation 和显式 stage（validate / execute / decode），保留 `raise ... from exc`。不继承 TypeError；不把 vendor message、SQL、路径或 metadata 值放安全 message。长度不等可定义 `VectorInputError(VectorStoreError, ValueError)` 保留 ValueError 消费者，但本轮必须明确其消息兼容，不据此让 storage 错误继承 ValueError。

最小阶段结构：

```python
# before: compile/encode 与 vendor 的 ValueError 无区分
filter_sql = compiler.compile(where)
return table.search(vector).where(filter_sql).to_list()

# after: 只在已知输入验证阶段映射；引擎执行 ValueError 仍是 storage
try:
    filter_sql = compiler.compile(where)
except ExplicitFilterValidationError as exc:
    raise VectorInputError(code='invalid_filter', operation='search') from exc
try:
    return table.search(vector).where(filter_sql).to_list()
except Exception as exc:
    raise VectorStorageError(code='storage_failure', operation='search') from exc
```

不要凭消息子串判断 `Invalid where clause`；让 compiler/parser/encode 的显式验证产生可区分内部类型或在极窄已确认校验块转换。parser 数值溢出经调用上下文分别归 invalid_filter / invalid_record，有限大 float 不应因幅度直接拒绝；U64 guard、集合首类型语义保持 R4b。新键未支持增量 schema 是 unsupported_capability，不假装非法 metadata。执行后 backend ValueError、TypeError、OSError/IO、schema/Arrow/SQL错误都是 storage_failure；非有限输入及格式拒绝必须在执行前完成。storage_failure 不承诺全部可重试。

只有真实无匹配/合法空输入返回 []/0/无操作；任何存储故障必须抛出。所有公开读写、count/scan/info 与构造均需同边界设计；本轮 MVP 应逐项列已实现/未实现，不能包装部分方法便声称完整 adapter。

## 已有覆盖与有效回归建议

- `test_embedded_vector_readiness.py:51` 真实显式二维向量验证持久化、过滤、score、删除及新进程读取；未覆盖非法过滤、数值溢出和真实 IO 故障。
- `test_runtime_helpers_readiness.py:290-325` 真实 Chroma 空操作、长度拒绝、投影、迁移及缺依赖；`:328-345` 仅第一次构造 PermissionError 软件注入，其后真实镜像 client，不能称真实文件锁复现。
- `test_source_control.py:211-220` 验证 KG失败 vs BM25空；`:246-257` 是 vector rescue **embedding**失败，不是 vector storage失败；`test_retrieval_generation_readiness.py:675-684` 同样仅 embedding故障。不能把这些用例说成已覆盖存储错误传播。
- `test_worker_quality_behaviors.py:480-547` embed-failed 注入来自 embedding_client，Store.add_chunks只记录，不覆盖存储写入异常。需补 actual add_chunks失败后回调 embed=failed/degraded、日志事件、后续索引仍执行。
- 必补：known/unknown key 下合法无匹配与非法语法/空或混合集合；record signed-I64溢出、query U64 guard与超U64有限 F64、非有限/超范围 JSON；每例断言公共类型、code、operation/stage和cause，不只看 REJECTED。
- 必补：真实 Lance/SQLite 临时目录生命周期故障（可复验的缺失/损坏/不可访问路径按平台实际行为选择）及 backend ValueError/TypeError/OSError 确定边界注入。两种证据分开标注；无法可靠复现的真实故障不冒充通过。
- 必补：用实际候选调用现役提取/私有复制消费者，storage failure 必须 search 仅执行一次、外层 trace failed/countNone；真正无匹配为 executed/count0；同样测多查询、rescue、worker、构造降级、scan旁路。保留旧签名 Store 的明确兼容用例。
- 历史 R4b 只比较接受/拒绝状态的矩阵需新加公共分类对照；Chroma源类型/消息仅作诊断保存，两个实现按同一语义契约归一化，再断言结果。不能只给 JSON 中 class 改标签。
- 保留全部旧红/绿 freeze；新独占 MVP、最终代码哈希、真实依赖命令/退出码及独立 reviewer 重跑绑定。formatter 支持域继续标 version-bound experimental；不建立夹具 allowlist，不静默精度降级。

## 规范文档检查

已暴露遗漏：入口合同记录接受/拒绝及数值规则，但缺公共异常类型、阶段分类、no-match与storage失败、旁路和消费者降级的契约。建议 root 在 `docs/contracts/2026-10-14-vector-ingress-semantics.md` 增加公共异常节并在向量替换设计引用；记录 Chroma1.5.9/锁 parser 与 formatter 未证明域。现有 HTTP状态/worker终态继续保持，在集成前单独决定需要的 wire 映射，不能由裸 ValueError 推导 HTTP422。该审计不改变生产规范或声称替换放行。
