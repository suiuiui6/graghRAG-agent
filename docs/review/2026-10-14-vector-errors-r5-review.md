# R5 公共异常边界独立最终审查

日期：2026-10-14。审查结论：本轮隔离异常修复及所测消费者范围条件通过，无新增未关闭的实现阻断。完整替换仍 BLOCKED；日志安全、已知兼容 GAP 和 formatter 等原门槛不关闭。问题统计：本轮 High 2项已关闭（评分、巨大整数向量）；既有生产准入 P0 继续开放。

## 输入与独立证据

最终冻结 `docs/testing/vector-errors-r5-20261014/r5-freeze-manifest.json` SHA256 `43d38e03549f64762734d1d0339c7c87c3c4361346b1cb390983c3b293269d4c`，284文件。独立逐文件核 SHA 后复制到 `.tmp/vector-errors-review-20261014/snapshot-final/`；旧 R4b 110文件也亲核无漂移。独立执行后再次核最终私有284文件无漂移，exit0。当前异常合同 SHA256 `dcfc66e6d97fb95478a4341225b95330626d53c9a46d7668b5f0ab49c6262051`；以其纠正后的 Chroma 记录/NaN 事实为准，不沿用旧 I64 假设。

实际命令：

```text
.tmp/backend-quality-venv-20261012/Scripts/python.exe .tmp/vector-errors-review-20261014/prepare_snapshot.py snapshot-final
.tmp/vector-errors-testenv-20261014/.venv/Scripts/python.exe .tmp/vector-errors-review-20261014/independent.py snapshot-final
```

两命令 exit0；第二命令为正规 require_escalated 离线执行，ANONYMIZED_TELEMETRY=FALSE、HF_HUB_OFFLINE=1。实际 Lance 合成数据、私有数据库，不读取 .env 或供应商接口。独立结果 `independent-result-snapshot-final.json`、冻结收据 `snapshot-final-receipt.json`、实际处理器日志 `actual-logs-snapshot-final/app.log` 在 reviewer 独占目录。原263私有副本和 `independent-result.json` 保存先前裸 OverflowError 红观察；该诊断脚本收集 finding 后 exit0，不能冒称此 reviewer 命令 exit1。作者有效失败退出码红证据另见冻结收据。

## 问题清单与关闭依据

### 🟠 High CLOSED：新门面评分与现役消费者约定不一致

- 位置：最终 `probe_store.py:46`；现役 `backend/vector_store.py:173–175`。
- Before：`score = 1. - row['_distance']`，正交0、反向-1。
- After：`score = round(1. - row['_distance'] / 2., 4)`。
- 独立新夹具 north/east/south，以 `[0,1,0]` 查询真实 Lance，实际评分分别1、0.5、0。原9 cosine验证不直接覆盖新 ProbeStore；本次独立门面执行补上该缺口。

### 🟠 High CLOSED：巨大整数向量裸 OverflowError 逃逸

- 位置：最终 `probe_store.py:12–18`。
- Before：直接 `math.isfinite(v)`，`10**400` 触发裸 OverflowError，缺公共 code。
- After：仅在纯有限数验证处窄捕 OverflowError，转 `VectorInputError('invalid_input', operation) from exc`；没有把 backend ValueError 统一归输入。
- 独立旧263副本确实观察到裸 OverflowError；最终284同一输入返回 invalid_input，关闭。此为候选支持域拒绝，不推导 Chroma 同样拒绝。

## 分类、消费者与安全复核

- 静态确认显式输入分支直接抛类型化错误；JSON/parser 已知异常局部转换。compile/encode/constructor 末尾动态 `_public_boundary` 包装其余原生 Exception，先透传应用错误，不捕 BaseException。`StaticProjection.__init__` 虽在 ProbeStore own open 块外，已有自身包装；独立注入 `pa.schema` TypeError 实际返回 storage_unavailable，无构造裸异常缺陷。
- 独立非法输入为 bool/int 混合集合、unknown 字段 U64 literal、单元素 and：均 invalid_filter，且 table.search 断言不执行。合法输入注入 col ValueError/TypeError 均为 storage_unavailable，未被误归 invalid_filter。
- 公共异常为自己的稳定类，operation 固定内部集合；无供应商类名伪装，无 TypeError 继承；storage 不继承 ValueError。固定安全公共 message，cause 内部保留。批长保留 ValueError 及安全 `Length mismatch`，见静态实现与作者有效用例。
- 独立运行真实 retrieval 三个 AST 函数、真实 source_control/evidence_trace 和 ThreadPoolExecutor，连接实际新合成 Lance：命中 executed/count1、实际无匹配 executed/count0；backend TypeError 与 ValueError 注入分别 failed/countNone、search 恰好一次，不误触旧签名 fallback。这是实际函数 subset，不是完整 module/worker/API 集成。
- 实际 logging_config 处理链 format_exc_info → redact_sensitive → JSONRenderer 不是空壳。独立新 marker 经实际消费者 warning 后仍在最终日志；api_key 模式值已脱敏。不能从安全 str/public_dict 推导全日志安全，也不能声称系统完全无 scrubber。日志任意原值防泄漏继续 P0 OPEN，不删 cause 或忽略日志制造通过。

## 明确限制与优化建议汇总

1. 生产准入优先处理内部 cause 诊断与实际日志脱敏，复验真实处理器和消费者。
2. Chroma 真实接受 metadata `2**63`/`2**64`/`-2**63-1` 并读回 float，以及含 NaN 的 query vector；候选策略拒绝是明确 compatibility GAP。已读作者冻结 Chroma15原始观察，本 reviewer 未重跑 Chroma，不把分类归一化当成功兼容。记录 I64 限制不再声称为真实 Chroma 必然边界。
3. read/scan 的10000上限是有限探针，不是全量分页；增删改、完整 VectorStore API、固定代快照、并发恢复/迁移均未实现。本轮不能称完整 adapter。
4. formatter 任意 binary64 等价、原生安全及完整生命周期保持开放。真实 worker/API/provider全链、本 reviewer 全旧专项及产品全量双90 NOT_RUN；作者/root历史实跑不能改写成 reviewer 执行。

本 reviewer 仅写审查报告及独占 tmp，未改产品、主锁、.env、真实数据、Gold、旧冻结或提交/推送/部署；任务负责人统一归档证据与更新 memory。
