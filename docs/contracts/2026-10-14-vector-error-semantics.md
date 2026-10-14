# 向量隔离候选公共异常契约

状态：隔离R5已实现，所测范围经独立复核条件通过；完整替换仍BLOCKED。用户已确认继续定义错误映射、真实依赖验证及浮点支持范围；本轮不修改生产代码、主锁、数据或发布行为。

## 目标与取舍

沿用替换设计的 invalid_filter / invalid_dimension / storage_unavailable 边界，补齐可验证的异常类型与消费者行为。采用候选自己的稳定异常和安全消息，保留原异常为 cause。拒绝复制 Chroma 类名或解析供应商消息来伪装兼容；也不把所有 ValueError 统一判为输入错误。Chroma 和候选原始异常身份分别保存，比较本应用所需的错误类别、失败状态和成功结果。供应商异常类型逐字一致不再作为本应用的目标，不能因此宣称供应商完整API兼容。

## 分层映射

所有公开候选错误均继承 Exception，具有稳定 code / operation / retryable / 安全 message；operation取内部固定枚举，不接受原始请求文本；不继承 TypeError，避免现有 retrieval 对旧 search 签名的重试路径。输入错误可继承 ValueError，明确与存储故障区分。公共str(error)及序列化字段不含原始filter、metadata、向量、文件路径或底层异常文本；候选边界不主动记录这些内容。底层异常通过显式cause保留，不序列化到公共消息。异常链traceback仍可能包含底层文本，不能宣称cause已脱敏或允许面向用户输出完整traceback。

独立消费者复核发现`backend/retrieval.py:560`用`exc_info=True`记录失败，可能输出完整cause链。必须捕获真实函数日志用合成敏感标记验证；公共消息安全和现有消费者日志安全分开判定。本轮不修改生产日志策略，若链暴露标记则如实保留P0开放项，不能删除cause或忽略该日志来制造安全通过。未来集成前须明确内部诊断保留与日志脱敏策略并复验实际消费者。

| 边界 | code | 处理原则 |
|---|---|---|
| 过滤结构、literal、数值解析、集合类型 | invalid_filter | 在执行存储查询前验证；已知parser错误在该边界转为类型化错误，非可重试 |
| 向量维度不符 | invalid_dimension | 明确维度校验，非可重试 |
| metadata、批长或非有限向量非法 | invalid_input | 明确输入校验，非可重试 |
| 静态generation不支持新增键等能力边界 | unsupported_capability | 不误称坏输入或存储故障，非可重试；不得自行丢字段 |
| 实际文件、连接、查询失败及未分类backend异常 | storage_unavailable | 已校验输入之后发生；抛出带cause的故障，非空结果；未证幂等/瞬态性时retryable=false |

本轮不无证据细分 lock_timeout/corrupt_snapshot。既有设计仍要求未来分别验证这些故障；当前不把一个坏路径试验称为覆盖所有存储故障。KeyboardInterrupt/SystemExit等BaseException不捕获。是否成功与返回空集合独立：真正无匹配返回[]，故障抛异常。

实现必须在显式输入校验点直接raise对应类型；仅纯JSON/parser调用边界转换已知输入异常。禁止给整个compile()包`except ValueError -> invalid_filter`：其中还构建Arrow/Lance表达式，表达式构建及执行阶段剩余异常均按backend故障处理并保留cause。用明确标记为故障注入的backend ValueError和TypeError验证该分类，且通过真实retrieval消费者断言search只调用一次，不能触发旧签名重试。

## 调用方与测试要求

消费者审计列出真实文件行号、异常类型分支、向量路failed遥测、worker降级和API错误边界。隔离测试通过实际消费者函数与真实合成存储验证成功、零命中、非法输入及存储失败；不复制一个简化消费者充当真实产品。不可执行的worker/API全链明确NOT_RUN，无供应商调用或环境密钥读取。故障注入可用于验证特定异常分支，但须与真实依赖产生的错误单列，不能冒充真实I/O。

已核第一方没有按Chroma InvalidArgumentError身份分支；`backend/tests/test_runtime_helpers_readiness.py`有ValueError且消息包含`Length mismatch`的明确断言。隔离候选批长错误须保留该安全短语和ValueError兼容，其他供应商内部错误文本不承诺逐字复制。实际检索遥测要求成功零命中为executed/count=0，而失败为failed/count=None；worker既有embed_failed/degraded及HTTP INTERNAL_ERROR边界仅审计，未实际执行不得称集成通过。

必须保存修复前失败、最终通过、输入/源码/依赖hash与命令退出码；重跑受错误包装影响的数值/过滤消费者回归，旧r4b冻结不修改。执行和独立复核完成后再更新状态。

## 浮点支持范围和失败策略

当前隔离实验仅面向 Chroma 1.5.9 / 锁定 serde_json 1.0.149 默认解析行为、Python3.12 的有限binary64及原始signed I64 metadata；派生查询整数按入口合同解析。接受有限binary64用于实验不等于所有输入已认证；已有随机和边界实证绑定具体冻结输入。NaN/Inf拒绝，原payload与兼容读回分离，禁止静默float32量化、夹具特判或readback查表。

当前没有可审计的Python formatter与Zmij任意binary64等价证明，也没有识别所有潜在不等价值的可靠runtime判定；因此不能声称会逐条拦住所有未知舍入差异。失败策略是保持整个候选不得进入生产选型/迁移，遇新反例停止相应验证并重开局部设计，保留原payload与红证据。不能仅把新输入映射成invalid_input制造兼容通过。若要解除此门槛，应独立实现/采用经审查的等价formatter或明确且有依据的正式支持子域，再复验真实消费者。

R5真实新探针已推翻记录入口“Chroma必限I64”的假设：metadata `2**63`/`2**64`/`-2**63-1`均接受并读回float。候选I64是自有限制，超域拒绝按当前候选策略记录，但与原生接受为明确compatibility GAP，不计应用分类匹配。真实Chroma另接受含NaN的query_embeddings（非where literal），候选有限向量策略拒绝，同样单列差异。完整替换不得在这些已知差异未处理时放行；本轮异常类型化通过不能关闭这些数值/向量能力差异。

## 已验证出口与剩余优先级

[R5报告](../testing/2026-10-14-vector-errors-r5.md)及[独立复核](../review/2026-10-14-vector-errors-r5-review.md)绑定284文件冻结SHA `43d38e03549f64762734d1d0339c7c87c3c4361346b1cb390983c3b293269d4c`。作者最终5组异常/消费者与2项门面测试、旧专项均exit0；root私有复制5+2复跑exit0，独立reviewer新增真实Lance/实际消费者函数subset验证错误、单次调用、零命中/失败遥测与1/0.5/0评分。不是完整worker/API或生产集成验收。

| 项目 | 状态 | 证据及下一步 |
|---|---|---|
| 应用固定错误分类、公共消息与原因保留 | 已修复（所测隔离门面） | 显式输入/能力/native故障分类、非法输入不执行查询，原生ValueError/TypeError不误作请求错误；全adapter尚未实现 |
| 检索旧签名重试及空命中/失败区别 | 已修复（实际函数subset） | 实际消费者storage故障查询一次、failed/count=None；真正空命中executed/count=0 |
| 新门面评分、巨大整数有限校验 | 已修复 | 有效作者红绿及独立新夹具关闭两项High；未以原9cosine间接替代门面验证 |
| 供应商异常类名逐字一致 | 已不适用（应用契约目标） | 没有第一方身份依赖；原始供应商异常仍保留，不宣称完整供应商API兼容 |
| 实际日志任意值脱敏 | 部分修复，P0开放 | 已有processor遮API-key样式值，裸标记仍残留cause日志；公共str安全不能替代全链脱敏 |
| 宽整数记录与NaN查询向量策略 | 未修复/待产品取舍，P0 | 前者三值native接受而候选拒绝；后者有限向量约束与原生接受不同，不计分类匹配 |
| formatter全域依据、native安全及完整生命周期 | 待验证，P0 | 继续按入口合同及替换设计验收；read/scan10000探针上限不等于全量分页 |

独立测试环境原17runtime逐项固定，加test-only structlog26.1.0；18项锁=安装、漂移0、官方PyPI审计零公告。该扫描不覆盖SQLite/Lance/Arrow原生组件，也不改变现役Chroma四唯一公告。未提交/推送/部署。收尾只更新本合同状态及证据引用，最终被测代码不变。
