# 公共异常契约隔离修复计划

用户2026-10-14确认的下一步；复用已授权向量替换隔离MVP及既有设计，采用debugger→coder→reviewer流程，不启动goal/Harness，不提交或迁移。

1. debugger只读审计真实VectorStore及_collection消费者，输出docs/review/2026-10-14-vector-error-consumer-audit.md，核错误类型、降级/failed遥测和现有有效测试。
2. 根回流docs/contracts/2026-10-14-vector-error-semantics.md；独立reviewer复核分类与测试设计。阻断意见关闭后交coder。
3. coder独占新.tmp/vector-errors-r5-20261014/、docs/testing/vector-errors-r5-20261014/及docs/testing/2026-10-14-vector-errors-r5.md，从r4b冻结复制，不改旧快照。先有效红测试，再最小类型化异常/候选公共边界映射，不将backend ValueError无条件归为坏输入。compile混合校验与表达式构造，输入分支直接raise类型化异常，纯parser调用点转换已知异常；native表达式/执行失败均backend故障。注入ValueError/TypeError分别核故障类型及消费者单次调用，注入与真实坏路径试验分开计数。
4. 在现有独立锁环境运行真实Chroma/Lance非法条件、维度错误、坏路径/存储错误、成功和空命中；通过实际消费者函数验证TypeError回退不误触发、故障不伪装空结果。执行受影响原专项回归。mock/故障注入单列，实际worker/API/供应商未执行项保留NOT_RUN。
5. reviewer独占自己的tmp和docs/review/2026-10-14-vector-errors-r5-review.md，审最终冻结hash、错误catch阶段和有效断言，独立新输入实跑；根核实际报告、更新合同/设计/memory及剩余优先级。验证绑定最终代码，产品无变更时只核既有双90输入漂移，不冒称新跑产品全量。

验收：应用错误契约及已测真实消费者行为闭环，无新阻断；原成功ID/读回不退化，真实无匹配与故障可区分，错误消息无合成敏感标记；formatter全域及原生安全/生命周期门槛不因本轮自动关闭。
