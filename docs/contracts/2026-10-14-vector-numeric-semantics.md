# Chroma 1.5.9 本地数值谓词有界合同

状态：独立 reviewer 已确认局部修复边界；不是通用数学比较或生产替换放行。绑定本地 `chromadb==1.5.9`、原 r2 候选 Lance 0.40.0。显式合成向量、`embedding_function=None`，未调用模型。

## 谓词转换

以 Chroma 实际已存 metadata 和 Rust 已解析的查询值为边界，SQLite 谓词按记录类型分支：

- int 记录，int 查询：i64 精确比较；float 查询：向零截断并饱和到 `[-2^63,2^63-1]`，再做整数比较。
- float 记录，int 查询：查询转 binary64；float 查询：使用已解析 binary64；保留 float 比较分支，不先转 i64 后再 float。
- 同一转换适用于 eq/ne/gt/gte/lt/lte；in 是 eq 的并集，nin 是 ne 的交集。
- numeric eq/range 不匹配 bool 或 missing；numeric ne/nin 包含 bool/missing。未知键正比较/in 为空，ne/nin 为全集，但仍需首先验证 literal。

官方机制证据：[Chroma tag 1.5.9 sqlite_metadata.rs](https://github.com/chroma-core/chroma/blob/1.5.9/rust/segment/src/sqlite_metadata.rs)，614–615 行 `Int(i)=>(i,i as f64)`、`Float(f)=>(f as i64,f)`；569–570 行集合相同转换。源码副本与 hash 随机器证据保存。Rust `as i64` 对本合同有限 float 的转换表现为截断与饱和；不是把超界比较替换成数学常量 true/false。

例：number > -1e100 排除 int64.min；number eq 1e100 可匹配 int64.max，但不应匹配所有大 float；fraction -1.5 转 -1 而非 -2。精确 I64 Python int 端点保持 int 分支，不经 float 中转。

## 原始 Python 输入与入口误差：独立 OPEN

真实 add/get 已观察到原始 float `nextafter(float(-2^63),+inf)` 的 readback 为 `float(-2^63)`；正端点相邻值亦有折叠。故原始 Python binary64 到存储/查询解析链不保证逐位保持。本轮没有确认第一次舍入发生的内部位置，不声称是 f32、serde 或 SQLite。f32 全量模型被实际结果推翻。

312 条件原始精确 float 模型有 76 项偏差；用真实 readback 作为记录及 float literal 的经验归一化后，谓词模型 312 项零差异。后者仅说明这些有限样例符合分层模型：**不得把 readback 查表当编译器算法或声称任意 float 的解析语义已解决**。必须保存 raw 模型差异；入口兼容仍 OPEN，禁止宣称完整 Chroma 兼容。

另存 `stable-domain-predicate-check.json`：显式排除发生 readback 漂移的两个记录及四个 nextafter 查询字面量后，240 条件对原始截断饱和/binary64 模型零差异。此子域包含精确 I64 整数端点、±1.5、±1e100、±floatmax、float(±2^63)、六比较/in/nin、number/float_only/absent。排除项仍完整保存在原 oracle 与 76 项失败报告中，局部通过不能代替完整兼容验收。

## 错误与范围

84 个附加边界均保留真实状态、类与消息：known/unknown key 上 Python int `2^63` 的六比较/in/nin 均 `InvalidArgumentError: Invalid where clause`；`-2^63-1` 则成功并表现为下端点附近 float 解析，不能笼统宣称所有超 I64 int 都被 Chroma 拒绝。±inf/nan 均 InvalidArgumentError，包括未知 key。bool eq/in 成功；bool gt 为 InvalidArgumentError；混合 int/float in 为 Python ValueError。

候选可对原始超 I64 int 采用显式能力限制并记录与 Chroma 的差异；本次修复仅批准有限 float→i64 分支。不得将未知键短路伪装为已完整验证错误契约。非有限 float 为候选明确拒绝域；不模拟 Chroma 内部非标准 JSON 解析。

## 证据与最小修复

证据目录 `docs/testing/vector-numeric-semantics-20261014/` 包含合成输入、真实 oracle、readback、原始模型红证据、源码与执行清单。脚本 `.tmp/vector-numeric-semantics-20261014/probe.py` 的正规提升离线执行 exit 0 仅证明经验归一化模型对这 312 条件一致，不是产品测试或替换验收。

coder 在新 r3 复制品修改 `_scalar`：区分原始 int/float；float 的 int 分支 clamp(trunc(q),LO,HI)，float 分支保留 q；原始 int 先做受支持 I64 检查，再考虑未知键。回归饱和上下界、正负 fraction、六比较/in/nin、全 float 列、missing/bool；保留原始入口漂移为独立失败，不特判夹具，不改旧 r2 冻结。
