# Chroma 1.5.9 数值入口兼容合同（隔离候选，未放行生产）

## 已复现根因

真实隔离 Chroma 1.5.9 中，Python binary64 `±0x1.fffffffffffffp+62` 经 add 后，embeddings_queue.metadata JSON 仍是 `±9.223372036854775e+18`；embedding_metadata.float_value 和 API get readback 已变 `±0x1.0000000000000p+63`。证据 `.tmp/vector-ingress-debug-20261014/real-probe.json`，同目录脚本、exit0及日志；全合成显式向量，无模型。

首个确定偏离位置是日志重放的 JSON 数字解析：官方 tag 1.5.9 `rust/log/src/sqlite_log.rs:358` serde_json::to_string 保存 metadata，`:292` serde_json::from_str::<UpdateMetadata> 重放；Python rust.py add直接PyO3 metadata，get/query where先json.dumps，再bindings.rs652/700 RawWhereFields::from_json_str。不能用查询路径代替证明记录路径。

官方根 Cargo.toml 声明 serde_json 1.0.133（semver范围），tag Cargo.lock实际锁1.0.149，crate SHA256 `83fc039473c5595ace860d8c4fafa220ff474b3fc6bfdb4293327f1a37e94d86`。锁源码de.rs639非float_roundtrip分支把十进制significand先cast f64，再乘/除POW10；这存在双重舍入。feature启用情况仍需构建图/真实独立输入实证，不能从根Cargo声明推断整个发布wheel的feature。

## 待验证最小方案

保留原始payload值与类型，另派生兼容metadata值和查询literal。记录派生过程必须模拟Rust serializer的十进制输出及默认parser；查询派生过程模拟Python json.dumps输出及parser，两路径分别验证。API兼容readback返回派生metadata；原payload为审计/重建保留，不得把精确保真payload误称兼容旧API readback。

parser应按源码泛化significand/u64 overflow/exponent/POW10逻辑，不得查oracle/readback表或按夹具特判。原始int正向u64大于i64可保持u64 Number，但Where先检查is_f64/is_i64，两个类型guard均为false，因而拒绝；U64.as_f64本身可以转换，拒绝原因不是as_f64不可用，负i64下溢可成为f64；需独立源码及探针确认范围和拒绝类。最终候选不依赖Chroma，Rust helper仅离线验证工具，不能查询时编译。

## 验收及限制

必须对独立随机finite binary64、边界相邻值、极大极小值、signed zero、指数格式、范围外原始int分别核raw/log/store/query/readback；保留红证据及真实get/query差分、旧H1消费者。任何不能证明安全模拟的子域明确拒绝并记录兼容差异；不得声称H2或整体替换关闭。生产/主锁/旧r2/r3/原数据不改，无commit/push/deploy。

## 2026-10-14 独立算法验证结果（可供r4隔离原型执行）

已审批构建独立Rust helper（serde_json=1.0.149，独立Cargo.lock/target；离线初次缺serde_core后正规下载，最终offline --locked build exit0）。临时parser_port.py审计移植de.rs数字路径，保留serde_json MIT/Apache许可证及源码来源；只接受合法JSON number tokens，不自行接受NaN/Infinity。

- 固定seed20261014生成12000独立finite binary64。query路径Python json.dumps tokens、record路径exact f64 bits→锁Rust serializer tokens，各12000，再8个整数/负零边界：24008与Rust Value解析类型及f64逐位差分零。
- 两序列化路径98处token格式不同，但12000对parsed bits差异零。这是明确输入集的实证，不能推断任意binary64全域等价。
- 真实Chroma1.5.9另用该独立输入前1200，add/log/get readback与parser(json.dumps(raw))逐位差分零；96个eq/gt/lt条件的get/query均与派生float比较相符。
- 原Python int应在入口保留类型。查询JSON解析：正数<=u64保留U64（<=i64时as_i64可用），负数绝对值<=2^63保持I64，超过下端点可变F64；不能把正2^63直接float化来规避旧拒绝。完整u64以上行为需后续边界验证，r4明确保留有界拒绝域。

r4允许复用临时审计port作为隔离实现起点：metadata派生兼容值及query数值先经json.dumps→port，原payload独立保留。compat API readback返回派生metadata，存档raw另给明确接口；不能改变现有冻结。审计证据充分支持已测域及H2反例修复尝试，但Python/Zmij任意float最短表示全域等价尚未证明，H2整体关闭和生产替换须独立评审后判定。未执行生产全量/双90，无提交。

完整官方Cargo.lock SHA256 `ccc181d8494e9f5bc0ce26999384983aa63e49cfbea1a89d5c954c7529313a4a`，272967 bytes。所有执行输入、官方源码、临时实现、原始oracle、退出码、helper锁、许可证及SHA256清单保存 `docs/testing/vector-ingress-debug-20261014/`。随机数据无生产内容、provider、密钥或Gold。

## R4b 已测语义与剩余边界（2026-10-14）

本节取代上文 r4 人为限定 U64 幅度的临时策略，历史证据不回写。查询整数由通用 JSON 数字解析器决定：正整数在 I64 上端以上且不超过 U64 上端时保留 U64，where 的 is_i64/is_f64 guard 拒绝；超过 U64 的长整数可能解析为有限 F64，不能仅因原 Python int 幅度拒绝。负向越过 I64 下端同样可能解析为 F64。解析为非有限数或无效 token 则拒绝。候选记录metadata原始int仍限signed I64，但这是候选支持域，不能描述为真实Chroma必然拒绝超界记录；R5新证据纠正该假设，见下节。

集合先验证原 Python 元素同类，再按解析后首元素分类：首元素 F64 时其余数字按 as_f64 转换；首元素 I64 时其余必须可 as_i64。顺序可改变接受/拒绝行为，不能对原始元素逐个编译后直接 OR/AND。SQLite REAL 记录读回把 -0.0 规范为 +0.0；raw payload 保留原始符号位，兼容读回与查询派生值分别处理。

[R4b 报告](../testing/2026-10-14-vector-ingress-r4b.md)保存真实 Chroma/Lance 红绿：宽整数144条件差异72→0，旧32差异16→0；原76/44/162、原312 raw+84入口、9 cosine及新128条件与6特殊值读回复验通过。110冻结文件及最终源码哈希绑定机器日志；旧r4的81冻结文件无漂移。root私有复制全专项复验exit0；[独立复核](../review/2026-10-14-vector-ingress-r4b-review.md)静态检查及另一seed9226 parser差分、真实128条件通过，未重复声称独立全套执行。已测范围局部闭环，以下完整兼容边界保留。

候选仅证明上述实际测试域的成功ID、接受/拒绝状态及所测读回位级语义。异常类/消息仍有 ValueError 与 Chroma InvalidArgumentError 差异；Python formatter 与 Zmij 任意 binary64 输出全域等价未证明。H2标记为部分修复，完整adapter、动态schema、原生安全、并发/恢复、生产集成及迁移均另行验收，不由本次数值修复放行。

后续优先级（与完整替换设计6.1/6.2共同执行）：

| 优先级 | 当前状态 | 剩余事项与证据出口 |
|---|---|---|
| P0 | 部分修复 | H2数值入口：本轮成功结果/拒绝状态已测域通过；定义公共adapter异常边界，再核真实调用方的错误处理，不能仅给ValueError改显示标签 |
| P0 | 待验证 | 记录formatter覆盖域及失败策略；保留独立Rust/真实Chroma差分，不能由随机零差异宣称全域证明 |
| P0 | 待验证 | Lance/Arrow/SQLite原生组件身份、公告及可达性审计；现有PyPI零公告不能覆盖此项，现役Chroma四唯一公告仍未修复 |
| P0 | 未修复 | 完整adapter动态schema增量/回填、固定G分页、并发写删、崩溃恢复和应用级一致快照；按替换设计实跑，静态generation探针不替代 |
| P1 | 待验证 | 规定规模/采样的性能与内存，形成具体选型和集成计划；生产集成及真实数据迁移另需用户确认 |

## R5记录入口新证据及错误契约

[公共异常契约](2026-10-14-vector-error-semantics.md)定义应用自己的分类与消费者边界，不要求供应商异常类名相同。真实Chroma新合成探针发现metadata原始Python int `2**63`、`2**64`、`-2**63-1`均可add并get为float，hex分别`0x1.0000000000000p+63`、`0x1.0000000000000p+64`、`-0x1.0000000000000p+63`。先前“record typed API必限I64”的断言被推翻；候选暂保留I64支持域及显式拒绝，三项为兼容GAP，不能用错误归一化算匹配，也不能把查询where解析规则直接套到PyO3记录入口。

另真实Chroma接受含NaN的query_embeddings；这是查询向量，不是where数值literal。候选按有限向量策略拒绝，此差异也单列，不推翻已测where非有限数拒绝。历史冻结保持原样；新证据绑定R5源码/原始回执，整体数值入口仍部分修复。

