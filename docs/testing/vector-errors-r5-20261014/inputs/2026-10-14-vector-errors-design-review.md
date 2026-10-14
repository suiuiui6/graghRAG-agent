# 公共异常契约独立设计审查

审查时间：2026-10-14。输入：`docs/contracts/2026-10-14-vector-error-semantics.md`、`docs/plans/2026-10-14-vector-error-fix.md`，并核 R4b 入口合同、报告及 `generic_filter.py` 实际阶段。只读实现；未改生产、主锁、环境、数据或冻结证据，无提交。

## 审查总结

分类、消息安全、消费者语义及 formatter 阻断方向合理。发现一项 🟠 High 设计细化缺口，已补订并独立定点复核关闭，可进入隔离实现；当前开放阻断0，无 Critical。此结论不代表最终代码或生产替换通过。采用 requesting-code-review 的需求、契约、风险、可测试性检查方式；reviewer 为独立上下文，不再嵌套委派。

## 问题清单

### 🟠 High：编译阶段混合验证与原生表达式构建，需明确捕获位置

- 位置：契约第15、19行；计划第7–8行；R4b `generic_filter.py:52–107`。
- 描述：现有 `compile()` / `_scalar()` 同时执行 Python 输入验证、数字解析和 Arrow/Lance 表达式构建。只写“查询前验证”不能阻止实现把整个 compile 的 ValueError 捕获成 invalid_filter；有效输入触发的原生表达式错误将被误报为请求错误。backend TypeError 若逃逸还会触发 `backend/retrieval.py:1279` 的旧签名重试。
- 修订要求：明确验证点直接抛应用类型化输入错误；纯 JSON/parser 边界只转换已知解析异常。原生表达式构建和 backend 执行的其余 Exception，包括 ValueError/TypeError，映射 storage_unavailable 并保留 cause；先透传已有应用错误，不吞 KeyboardInterrupt/SystemExit。无需为此重写数值算法。
- Before（禁止）：

```python
try:
    expr = projection.compile(where)
except ValueError as exc:
    raise InvalidFilterError(...) from exc
```

- After（概念结构，非指定类名）：

```python
# validation sites raise InvalidFilterError directly;
# pure parser conversion is scoped inside those sites.
try:
    expr = projection.compile(where)
    return backend_query(expr)
except ApplicationVectorError:
    raise
except Exception as exc:
    raise StorageUnavailableError(operation=Operation.SEARCH) from exc
```

- 验证要求：对合法 filter 注入表达式 ValueError 与 TypeError，分别断言 storage_unavailable、retryable=false、cause 身份保留、安全消息；实际 retrieval 包装函数 search 调用恰好一次。对非法 filter 断言 backend 不被调用；成功零命中与故障遥测分别 executed/count=0 和 failed/count=None。注入证据与真实坏路径/依赖错误单列。

## 已确认边界

- 应用稳定错误不冒充 Chroma 异常，不继承 TypeError；批长保留 ValueError 和安全 `Length mismatch`。
- code/operation/message 均不能包含原始请求或底层异常文本；cause 属内部诊断，完整 traceback 仍可能泄露，不冒称已脱敏。
- unsupported_capability 独立于输入错误；失败不能返回 []。worker/API 未执行即 NOT_RUN。
- 原 payload、compat readback 与查询入口继续按 R4b 合同区分。没有 formatter 全域证明和可靠运行时子域识别时，整个候选继续禁止生产选型/迁移，不能借输入拒绝抹平新反例。
- 真实 Chroma/Lance 仅独立锁环境、合成输入、正规提升离线执行；不在 sandbox asyncio 挂起后反复重试。

## 定点复核关闭

根已在契约分层映射末段及计划第3步补入显式 raise、纯 parser 限定捕获、禁止 compile 整段 ValueError 包装、native 故障分类和两类注入/单次消费者调用。reviewer 重新读取对应原文并核 SHA256：契约 `01056e39f1a9bac1c02596e51761690bfc8a31bb72bce8308b53da8e045ce464`，计划 `c9ab9cdc52ef2485881ba35a7a23fb5ff04898a0e041828156476ee28568d494`。上述 High 设计问题 CLOSED；实际实现及测试仍待最终 R5 复核。

后续日志范围补订定点确认：已重读契约新增的公共 str/序列化安全与实际日志独立判定段，最新契约 SHA256 `17ce9be1ad1c7617c486d360da779b00ca0fba118a64777b031982cb3909bc8a`，计划 SHA 不变。日志不是“完全无 scrubber”：`backend/logging_config.py:87–98` 已有 format_exc_info → redact_sensitive → JSONRenderer，`:163–169` 明确未匹配值模式的裸 hex 可能残留。故实际消费者日志必须经真实 processor 捕获验证，fake logger/raw cause 只说明诊断内容，不能推导最终输出。此补订准确且不重开已关闭的分类设计问题；日志安全仍 OPEN 待最终 R5 实测，不删除 cause 或修改生产策略。

## 优化建议汇总

1. 已关闭设计补订项，按最新版合同/计划交 coder 隔离实现。
2. 最终 R5 审查核最终源与冻结 hash、有效红绿和旧专项回归，reviewer 使用私有新输入验证。
3. 保留 formatter 全域、完整 adapter、原生安全及生命周期开放项；本轮不触发提交、生产集成或迁移。

验证记录：PowerShell 只读读取 AGENTS、memory、合同/计划、R4b 源及报告；`git branch --show-current` 为 master，工作区已有大量未提交改动并保留。最初两次探索猜测文件名不存在，仅定位更正，未运行测试，也未据此作通过声明。任务负责人统一更新 memory，避免跨 Agent 覆盖。
