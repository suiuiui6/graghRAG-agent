# Five P0 Fixes Implementation Plan

**Goal:** 修复评估 #1/#2/#3/#4/#50，沿用现有身份、租户和文档契约，不替换核心组件。

**Architecture:** 在既有认证链建立可信principal；由统一资源授权服务按owner/真实项目成员约束资料。新旧查询在检索前取得授权文档的独立KG。旧全局索引缺少稳定document_id时，受限请求仅走授权KG，显式要求无法安全隔离的来源返回503，不降级全库。管理员无文档限定查询保持现有主路径。

**Tech Stack:** FastAPI、NetworkX、JWT、JSON文件、pytest。

这是已有Bug的精简维护流程，输入为当前工作树与历史审计；不启动新项目或重新设计全架构。用户已授权处理这五项；复用现有规范，新增的最小拒绝行为回流API规范。

## 所有权与依赖

- debugger：只读根因和边界报告 `docs/review/2026-10-12-p0-root-cause.md`。
- auth coder：auth.py、JWT/tenant middleware、resource_access.py、必要的auth_service.py、test_p0_authorization.py。
- MinerU coder：worker.py、mineru_client.py、缓存回归测试及test_p0_mineru_isolation.py。
- 主负责人：server注册顺序与资源守卫、documents/ingest/query/rag_query/graph路由、request-scoped KG模块及API集成测试、规范/记忆。
- reviewer：独立上下文只读复核最终变化与测试质量；阻断项关闭后交付。

## 执行及验收

- [x] 写并执行失败回归：未知doc_删除返回404且临时上传原件保持不变；合法删除仅删除该文档精确登记路径；越界/链接拒绝。
- [x] 认证默认拒绝、真实JWT/管理key/托管key可用；refresh不可作access、伪造project拒绝、read key不可delete；旧无归属仅admin。
- [x] 新入库记录owner与org/project；状态、文件、图谱按同一资源授权，不信任用户提供身份。
- [x] 请求独立加载授权KG、附真实文档和版本；单文档/部分授权用户不能使用全局agent、全局索引或旧会话历史。无法隔离的数据源明确拒绝。
- [x] 完整task_id独占MinerU目录；同前缀并发任务不混，残留目录不能覆盖；任意历史缓存即使显式开启也不得作为新文档成功结果。
- [x] RED→GREEN日志；真实临时文件/tenant/key依赖的API集成测试，模型与云调用仅在不可避免的生成边界替身，不冒称供应商验收。
- [x] 独立审查并修复阻断意见；相关回归、静态检查、全量后端测试及覆盖能力核查；未知/未达90%双指标禁止commit/push。
- [x] 规范回流、归档验证报告、memory索引与日期记录更新；保留其他任务修改。

## 限制

本轮不读取.env、不修改真实生产资料、不外发文档或调用付费模型。历史文档不猜测归属；仅admin可管理，后续由可信管理员做归属迁移。受限RAG只支持可证实隔离的KG，未绑定文档/用户的旧session不复用。全局目录/导出/血缘等尚无资源过滤的接口对非admin拒绝，不能通过另一个入口绕过资料授权。

双覆盖率是提交门槛；不通过仍可交付未提交修复和明确的验证状态。当前Windows为audit-only-windows。

## 最终验证状态

本地五项修复和独立复审完成，P0专项84通过；全量705通过22失败。覆盖能力核查已执行，但双覆盖率没有测量，漏洞扫描未执行。上述检查项完成不表示全量/提交门槛通过；禁止commit/push。详见 `docs/testing/2026-10-12-p0-verification.md`。
