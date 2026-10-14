# R4b 数值入口独立代码复核

审查日期：2026-10-14。独立 reviewer 上下文；使用 `requesting-code-review` 的需求/实现/证据检查组织方式。仅写本报告及 `.tmp/vector-ingress-r4b-review-20261014/`，未改生产、主锁、真实数据或 `.env`，未提交、推送、部署。

## 审查总结

R4b 在本次数值隔离 MVP 的已声明范围内通过独立复核，未发现新增阻断缺陷。新问题统计：Critical 0、High 0、Medium 0、Low 0；既有公共错误兼容及 formatter 全域等价限制仍 OPEN，不据此关闭完整 H2 或允许生产替换。

输入为 `docs/contracts/2026-10-14-vector-ingress-semantics.md`、`docs/testing/2026-10-14-vector-ingress-r4b.md` 及最终冻结目录。冻结清单 SHA256：`82dbe6ed1397bc348ecfa8c4429270d5942431ef0763bd5eedbbaa9f7dd6fbe6`。开始及结束亲自核验全部 110 文件，零漂移；旧 r4 清单全部 81 文件也核验零漂移。相关作者/根任务全套结果仅作为检查过的证据，不算本人全套重跑。

## 代码与断言审查

- `generic_filter.py:11–18, 94–104`：相对 r4 的行为差异确为删除标量、集合两处原始 Python int 幅度 cap，另更新语义说明。query 先经过通用 parser，再保留 U64 超 I64 的拒绝 guard；超 U64 的 long_integer 可自然进入有限 F64。没有按特定数字、ID、oracle 表或 readback 表分支。
- `parser_port.py:6–35`：对照锁定 serde_json 1.0.149 `de.rs` 默认非 float_roundtrip 路径的 u64 累积、整数溢出截位及指数补偿、decimal 溢出、POW10 乘除与非有限拒绝。运行时仅 Python stdlib，不查询 Chroma、不调用 Rust helper。Rust helper只在本次独立测试中充当 oracle。
- `generic_filter.py:36–50`：raw metadata JSON 与兼容读回 JSON 独立；原始 record int 的 signed I64 限制仍在，bool 通过 exact type 分类，不混成 int。未以 query 的宽整数能力放开 record typed API。派生值写入比较列而非覆写 raw payload。
- `generic_filter.py:94–104`：先验证原 Python 同类元素，再由解析后首元素选 F64/as_f64 或 I64/as_i64 路径；没有将各原始 literal 独立 OR/AND 后跳过首类型规则。known/unknown key 都先经过数值合法性检查。
- `generic_filter.py:16–18`：只在记录兼容值侧把浮点零规范为正零，query 和 raw 路径保留符号；`fresh_matrix.py` 对 raw 及 compat 均有 exact type 与 `struct.pack` 位比较，未单用 Python `==` 掩盖负零或舍入漂移。
- `wide_matrix.py` 检查144条件及旧32接受状态/成功ID；`fresh_matrix.py` 检查128条件及读回；`ingress_matrix.py` 保留 raw/compat 检查。成功与拒绝分别比较；异常类没有被当作已兼容。固定 limit 对本测试小数据集足够，不能推断真实分页能力。
- 查验作者 red/green manifests 及根任务复制复跑 manifest，根任务27份证据文件全部 hash 一致。历史嵌套 `final/archive.py`、`final/finalize.py` 仍存在且指旧归档，本人未执行这些脚本。它们不是当前候选运行时依赖。

## 本人实际执行

证据位于 `.tmp/vector-ingress-r4b-review-20261014/audit-receipt.json`、`final-receipt.json`、`fresh-chroma.json`、`fresh-lance.json`；脚本均在同一专属目录，源候选两文件与冻结文件逐字节相同。所有下列命令实际退出 0。

1. `.tmp/vector-replacement-mvp-20261013/.venv/Scripts/python.exe .tmp/vector-ingress-r4b-review-20261014/audit.py`：seed `202610141731`，新增4096 finite binary64 的 Python query token及4096 Rust serializer token、1024随机宽整数、10边界，共9226 parser差分。与既有锁定 serde_json Rust helper 的类型、as_i64/as_u64及as_f64 bits比较零差异。helper退出0；SHA256 `ee9765916d41550a204dc39ec60dfd2cd0dc277b0db258199ebbc38b837e1df6`。这是实际输入集的验证，不是全域证明。
2. `.tmp/backend-quality-venv-20261012/Scripts/python.exe .tmp/vector-ingress-r4b-review-20261014/fresh_matrix.py chroma`：正规 `require_escalated` 离线真实 Chroma，seed改为独立 `202610141731`，128条件oracle生成，退出0。
3. `.tmp/vector-replacement-mvp-20261013/.venv/Scripts/python.exe .tmp/vector-ingress-r4b-review-20261014/fresh_matrix.py lance`：正规 `require_escalated` 真实 Lance，同seed128条件零差异，退出0；raw与compat逐位/类型核验通过，覆盖±0、±最小subnormal、±最大finite及首类型逆序。
4. `.tmp/vector-replacement-mvp-20261013/.venv/Scripts/python.exe .tmp/vector-ingress-r4b-review-20261014/final_receipt.py`：结束时重新核110源hash、候选副本hash、fresh fixture绑定、128结果及根任务27证据hash，退出0。

真实依赖两命令设置 `PYTHON_DOTENV_DISABLED=1`、`HF_HUB_OFFLINE=1`、`PYTHONDONTWRITEBYTECODE=1`；只写独占临时合成数据库。未在 sandbox 重跑已知挂起的真实依赖。

本人未重跑原76/44/162、312+84、144+32或9 cosine全套；已阅读冻结及根任务实际复制复跑证据，不把它们改称独立执行。未执行生产全量、双90、安全扫描、迁移、并发恢复或完整adapter测试。

## 问题清单与既有开放边界

未发现本补丁新增需要 before/after 修复的缺陷，故无虚构问题或代码改写建议。以下为合同已明确的限制，不关闭：

- 公共adapter错误兼容：候选 `ValueError` 与 Chroma `InvalidArgumentError` 的类/消息不同；本轮矩阵验的是接受状态与成功ID，没有证明客户端错误契约等价。后续adapter应独立定义错误映射与调用者测试。
- 记录formatter：当前 `json.dumps` token用作Rust serializer的有界近似；本次独立样本和已有样本的parser成功不能证明任意 binary64 全域等价。后续须给出可审计证明或明确受支持域，不能用继续累加随机样本宣称证明完成。
- 静态generation、资源限制与native/并发/恢复等仍是原型能力边界，不能推广为完整替换验收。

## 优化建议汇总

优先保持 H2 为部分修复、整体替换 BLOCKED，并将实际执行范围和未执行项随交接保存。后续完整adapter先完成错误契约与消费者验证，再解决record formatter全域依据或正式范围约定；最后按独立计划验收schema增量、分页快照、并发恢复、native安全与迁移。本报告不授权改变这些范围，也不构成提交门槛通过证明。
