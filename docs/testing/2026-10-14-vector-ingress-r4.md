# R4 有界数值入口候选验证

仅隔离候选；生产替换仍 BLOCKED。未改生产、主锁、原数据或旧冻结，无提交/部署。

候选采用 serde_json 1.0.149 默认数字解析的 Python stdlib 端口。源算法出处与 MIT/Apache 许可随冻结保留；Rust helper、Chroma 仅作 oracle。metadata_json 保留原始值及类型，compat_metadata_json 和比较列使用派生值；SQLite record readback 的浮点零规范化到 +0，query 保留解析符号。record 原始 int 仍须 signed I64；query 支持负超 I64，正 U64 大于 I64 拒绝。集合先检查原 Python 同类，再按首个解析值的 f64/i64 分支转换。

实际命令入口在 `.tmp/vector-ingress-r4-20261014/`，Lance 使用 `.tmp/vector-replacement-mvp-20261013/.venv/Scripts/python.exe`，Chroma 使用 `.tmp/backend-quality-venv-20261012/Scripts/python.exe`，均正规提升、离线真实依赖。

| 验证 | 结果 |
|---|---|
| ingress_matrix.py red / green：原312raw+84 | exit1 92差异（76条件+16负超界）→exit0 零差异 |
| run_checks.py final：原76、44、162 | 五子命令全部exit0、零差异 |
| 原44消费者 | 9cosine排序/距离/score、持久schema恢复、7拒绝通过 |
| fresh_matrix.py chroma/lance | 新seed141020264，128独立float+6位级特殊值，128条件零差异 |
| 集合首类型逆序红绿 | red-set旧逐标量实现8差异exit1→修复后零差异exit0 |
| 负零readback位级红绿 | red-negative-zero.exit=1→finalize.py exit0 |

原payload按类型核验；新输入浮点逐位核验raw及compat readback（含±0、±最小subnormal、±最大finite），过滤ID单独差分。原始312模型76偏差历史未删除，旧r3脚本完整保留 numeric_matrix-r3-historical.py；r4 162脚本按新合同保留64拒绝断言，另16负超界接受在完整84真实oracle核验。

32个新增宽整数 oracle：±(2^64-1)、±2^64、±2^128、±10^309，known/unknown及eq/in。Chroma接受20、拒绝12；候选明确限制原query int绝对值不超过2^64-1，故±2^64和±2^128仍是能力差异，不能声称全整数兼容。原84拒绝状态及成功ID一致，候选 ValueError 与 Chroma InvalidArgumentError 类/消息未映射；公共adapter错误兼容仍OPEN。

最终81文件冻结与SHA见 `vector-ingress-r4-20261014/freeze-manifest.json`；final/manifest.json 绑定旧矩阵最终源码及命令退出码，final-ingress-manifest.json绑定最终raw/新float验证输入哈希。全binary64 formatter与Zmij数学等价未证明；本轮结论限定实际测试域。尚待独立复制复跑；全adapter、安全、迁移、并发恢复和全量双90不属于本验证。
