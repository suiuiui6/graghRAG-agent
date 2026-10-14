# R2 静态代元数据投影与消费者有界验证

结论：**局部兼容，超范围有限浮点数过滤仍 FAIL，禁止选型/生产替换放行**。未改生产代码、主锁、原 output、.env 或研究 Gold；无提交、推送、部署。

## 最终快照与实际执行

冻结目录：`docs/testing/vector-replacement-r2-20261014/`。`freeze-manifest.json` 保存 UTC、实际完整命令、退出码、输入执行前后 SHA256 及归档文件 SHA256。输入前后一致。归档包含原 76 项夹具/真值、历史失败/日志与早期 L2 40 项结果；数据库仅在独占 `.tmp/vector-replacement-mvp-20261013/r2/`。

最终离线执行 `r2/freeze_r2.py` exit 0 表示归档成功，**不表示全部测试通过**。其子命令分别为：

| 命令（相对仓库根） | exit | 结果 |
|---|---:|---|
| `.tmp/vector-replacement-mvp-20261013/.venv/Scripts/python.exe .../r2/lance_truth.py` | 0 | 原 76 项，Chroma 1.5.9 真值对 Lance 0.40.0，差异 0 |
| `.tmp/backend-quality-venv-20261012/Scripts/python.exe .../r2/boundary_probe.py chroma` | 0 | 44 项实际 Chroma 真值写入 |
| `.tmp/vector-replacement-mvp-20261013/.venv/Scripts/python.exe .../r2/boundary_probe.py lance` | 1 | 40 项匹配，4 项失败；完整细节见 `boundary-lance.json` |

执行使用正规 `require_escalated` 离线进程，未读取 provider/.env。不是产品全量测试或双 90 提交证据。

## 已验证范围

- 原 76 项动态 key→内部 mN presence/type/value 投影差分不变；内部名独立于用户 key，mapping 与 schema 同代持久化。
- 新 40 项覆盖负数、负小数、int64 最小/最大及相邻端点、in/nin、空匹配。元数据恢复逐 key 比较精确值和 Python 类型；未用浮点容差评元数据，超过 2^53 的整数不转 float。
- fresh Lance connection 重开并直接从 schema 恢复 mapping，元数据精确往返。
- AST 深度、逻辑宽度、节点预算、in 长度及新增 key、int 溢出、非有限 float 共 7 项明确拒绝。512 预算统计 AST 访问节点，不等于展开后 Expr 总节点；in/nin 另有每列表 64 上界。这些是探针局部限制，非获批公共契约。
- 3 个过滤（部分命中、负数范围、空集）×k=1/3/20 共 9 个 cosine prefilter 精确 top-k，通过独立 NumPy cosine 全候选排序与 score=(1+cosine)/2 公式检查。距离绝对容差 2e-7、score 1e-7 仅用于向量浮点计算；ID 排序精确相等。无 ANN，无并列距离。早期 L2 历史单独保留，不替代本轮 cosine 证据。

## 失败与后续设计边界

四项均为 `$gt` 查询 literal ±1e100，分别针对 int/float 混合 `number` 及全 float `float_only`。Chroma 全部 OK；投影编译器因先 `int(value)` 并检查 int64 范围全部抛 `ValueError: query conversion exceeds tested int64 boundary`。原始错误类及命中 ID 保留在 JSON，未按夹具特判或改写结果。

实际 `number > -1e100` 的 Chroma 结果排除了 int64 最小值、包含其余整数，与数学超范围常量 true 不符，提示饱和转换可能性，**尚未建立完整转换真值契约**。本轮停止猜测修复，保持 compiler 不变。后续需独立设计/真值核查饱和转换及各比较操作，再按真实语义泛化实现并复验消费者。

OK/REJECTED 匹配只比较状态及成功 ID，不证明异常分类、信息、公共错误契约完全一致。未覆盖全量有限数值域、完整无限 metadata 契约。

完整 VectorStore adapter、增量 key/backfill、多写者 schema 演化、应用级 snapshot 屏障、并发崩溃/强制终止、真实数据迁移、100K 扩测、产品全链与提交门槛均 **NOT_RUN**。本报告是隔离评估证据，不能视为生产替换完成。冻结后交独立 reviewer 复核。
