# H2 数值入口独立审查（进行中）

2026-10-14；master / 46b202c。只负责本评审与 `.tmp/vector-ingress-review-20261014/`，不修改产品、主锁、旧冻结或原数据。采用 requesting-code-review 的独立上下文及阻断问题闭环方法；本文件中未执行事项不计验证。

## 审查总结

Python wrapper、官方日志与默认数字解析机制已独立核实，通用移植通过独立执行差分，**批准合同进入隔离 r4 实现**。当前 H2 为 1 项 High、待 r4 独立最终复验，整体替换仍未放行。

## 已核机制与来源

- 安装版本源 `.tmp/backend-quality-venv-20261012/Lib/site-packages/chromadb/api/rust.py`：491–500 `bindings.add` 直接传 metadata；443 get、587 query 通过 `json.dumps(where)` 传 Rust。
- `api/models/CollectionCommon.py` 225–259：normalize/validate 后将 metadata 经 `_apply_sparse_embeddings_to_metadatas` 传出。普通稠密向量案例不得借用 embedding 的 float32 路径解释 metadata 漂移。
- 已读现行 numeric 合同与旧独立报告：312 原始模型76偏差、4 readback 漂移仍是反例；经验 readback 归一化不成为候选算法。原始 int 上下端不对称仍需入口机制解释。
- 官方 tag 1.5.9 源码本地副本已独立读取：`.tmp/vector-ingress-debug-20261014/bindings.rs` 439 的 metadata 为 `Metadata`，embedding 为 `Vec<Vec<f32>>`；700 query 使用 `RawWhereFields::from_json_str`。`sqlite_log.rs` 358 `serde_json::to_string(&metadata)` 写日志，292 `serde_json::from_str(metadata_str)` 重放为 `UpdateMetadata`。记录确实存在 serde JSON 往返，不能将 embedding float32 强加到 metadata。
- `Cargo.toml` 45 `serde_json = "1.0.133"` 是版本范围；初次读取 `Cargo.lock` 仅32768字节且尾行不完整，已通知 debugger。尚未以其声明精确解析版本或 feature；还需检查类型反序列化及 where 校验和实际差分，才可定位第一次舍入。
- 后续完整 `Cargo.lock` 272967 bytes、尾部完整；8439–8449 显示 serde_json 1.0.149（checksum `83fc039473c5595ace860d8c4fafa220ff474b3fc6bfdb4293327f1a37e94d86`），依赖 zmij。workspace manifest 无显式 float_roundtrip，但不据此排除其他 crate 的 feature 合并。
- 独立读取 debugger `real-probe.json`：5条真实记录中，两个相邻端点的 embeddings_queue 日志十进制串仍是原始 ±9.223372036854775e18；embedding_metadata.float_value 与 readback 为 ±9.223372036854776e18。对这两个样例，首次漂移发生于日志序列化后、写 SQLite metadata 前；get/query 在 eq/gt/lt 上一致响应折叠值。此处是证据读取，尚非本评审独立重跑。

## 问题清单

### 🟠 High H2：原始输入与解析比较值必须分层（OPEN）

位置：`.tmp/vector-numeric-r3-20261014/generic_filter.py` 33–39、55–58；现行 numeric 合同入口章节。

原候选直接把 Python float 写入派生 float 列，查询也直接使用 Python float。旧真实 oracle 显示入口解析后可能不同，因而仅修 float→i64 饱和不足以保证原始输入的过滤结果。

建议：先确认版本锁定的 JSON 解析机制，记录和查询走各自正确次数的相同解析算子；只对比较列派生值做转换，原始 metadata JSON 保真。禁止 fixture 值/ID/key 特判、readback 查表及调用 Chroma 作为候选兼容层。

```python
# before
comparison_float = raw_float
# after（概念接口，尚不是已验证实现）
raw_payload = preserve_python_metadata(metadata)
comparison_float = version_bound_ingress(raw_float, path='record')
query_float = version_bound_ingress(query_literal, path='query')
```

## 优化建议汇总

1. 核实 RustBindings→日志 JSON/serde_json→SQLite 的记录路径，以及 where→serde_json 的查询路径；对首次漂移保留逐层证据及 int 上下界错误类型。
2. 若机制确认，可采用独立锁定的小 Rust 解析 helper 或经充分证明的通用复刻；Python `json.loads` 不能未经差分证明代替 serde_json。新依赖不修改主锁，独立安全扫描不等于整个 native 依赖安全清零。
3. 修复后独立冻结复跑312 raw、84边界、76/44/162矩阵、9 cosine；额外构造未见浮点输入，核记录/查询共同转换、原 payload 类型和值、错误状态与类。旧76失败证据保留。

负责人统一更新 memory。尚未执行 r4、提交、推送、部署或产品全量测试。

## 合同独立确认及实测

读取 `docs/contracts/2026-10-14-vector-ingress-semantics.md` 与 `parser_port.py`：实现按合法 token 的 u64 累积、溢出截位、指数与 binary64 POW10 乘除通用计算，没有 oracle 查表或值特判。该方案具备可执行修复路线，允许进入隔离 r4；不能跳过最终真实 oracle 与新浮点输入复验。

实际命令（质量解释器 `.tmp/backend-quality-venv-20261012/Scripts/python.exe`）：

| 私有脚本 | exit | 结果 |
|---|---:|---|
| `.tmp/vector-ingress-review-20261014/port_differential.py` | 0 | 原 seed 12000 finite float、两路径与8边界共24008，Rust helper/移植逐位及类型差分0 |
| `.tmp/vector-ingress-review-20261014/new_float_differential.py` | 0 | 独立seed2026101409，新6000 finite float、两路径与8边界共12008，差分0 |

helper SHA256 `ee9765916d41550a204dc39ec60dfd2cd0dc277b0db258199ebbc38b837e1df6`；使用 debugger 锁定 serde_json 1.0.149 的 helper 可执行副本，不调用 Chroma 作为候选兼容层。新seed驱动使用相同报告文件名，当前私有 JSONL/报告保存新12008输入，原24008结果另有本次工具退出记录与 debugger 冻结。未把算法helper实测冒称独立新Chroma复跑。

### 🟡 Medium 合同措辞修正：U64拒绝原因（已反馈）

独立取得官方 tag `rust/types/src/where_parsing.rs`：235/244、424/463 先 `is_f64()` 后 `is_i64()`；303/316 的 set 按首元素相同分类。正2^63 为U64，两个 guard 均false而拒绝；负LO-1可被默认JSON解析为F64再进入float分支。不能写成U64的 `as_f64` 不可用，它实际可返回值，关键是类型 guard 不进入该分支。

```rust
// before（错误解释）
// u64.as_f64() is unavailable
// after（官方实际分支）
if operand.is_f64() { /* float */ }
else if operand.is_i64() { /* integer */ }
// U64 > i64::MAX satisfies neither guard.
```

完整源位于私有tmp `where_parsing.rs`，已告知 debugger 可复制冻结。metadata.rs首段下载timeout exit1仅产生不完整文件；后续range取余段exit0，本审查使用的是完整独立where_parsing文件，不以不完整metadata作为where机制证据。

## r4 编码中静态反馈

### 🟠 High H3：集合首元素解析类型决定全列表转换（待修复）

位置：r4 `generic_filter.py` compile 的 in/nin 分支；官方 where_parsing.rs 303–319。

原始 Python 同类型 int 列表经过 JSON parser 后可成为混合I64/F64。官方按首元素类型分支：float-first 对全列表 `as_f64`，int-first 对全列表 `as_i64`。所以 `[LO-1, LO]` 可接受，而 `[LO, LO-1]` 的后项F64使整个集合拒绝。逐项 `_scalar` 后简单OR/AND会错误接受后者，也不能保留前者把整列表转float的语义。已将源码与反例通知 coder/root，要求真实逆序探针与修复。

```python
# before
reduce(op, [scalar(v) for v in raw_values])
# after（行为要求）
parsed_values = parse_each(raw_values)
values = convert_entire_set_by_first_parsed_type(parsed_values)
reduce(op, [scalar_already_parsed(v) for v in values])
```

另已反馈：当前 query ingress 会接受大于u64的原始int进入F64，合同却将其列为未验证有界拒绝域；应补实际宽整数边界与明确支持域，或在入口显式拒绝。NUMERIC_RULES 旧 unresolved 文案应与最终范围同步。

### 🟠 High H4：负零兼容readback必须按位核验（待修复）

位置：r4 encode 派生metadata；fresh_matrix.py 使用数值 == 的readback核验。

独立真实命令：质量解释器执行 `.tmp/vector-ingress-review-20261014/record_bits_probe.py`，正规提升离线、exit0。6条合成记录显示 raw -0.0 bits `8000000000000000`，Chroma readback +0.0 bits `0000000000000000`；+0、±最小subnormal、±maxfinite均保持bits。结果 `record-bits-chroma.json` 已保存，通知coder补记录零规范化和位级断言，最终冻结暂缓。不能仅凭 `-0.0 == 0.0` 声称metadata完全一致。

```python
# before: misses signed zero
assert compat == chroma_readback
# after: raw and compat audited independently
assert pack(raw_float) == pack(original_float)
assert pack(compat_float) == pack(chroma_float)
```
