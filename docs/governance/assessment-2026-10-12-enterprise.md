# 企业评估 D01–D17 对照补充

本表对照桌面 `GraphRAG_Enterprise_Assessment(1).md`（标注日期 2026-09-11）的改造建议。它与 62 项缺陷清单是两套编号，不能把 D01 等同于缺陷 #1。状态针对整项范围；指定技术选型没有落地，不自动等于业务风险必须通过该选型解决。这里的测试文件引用仅证明覆盖代码存在；实际执行结果以本轮三个专题报告和 Phase 2 测试记录为准。

| 项 | 状态 | 当前代码证据 | 测试证据与边界 | 剩余优先级 |
|---|---|---|---|---|
| D01 图存储 | 部分修复 | `backend/kg_store.py:293` 版本管理、`:403` 装载；`:439` 仍 NetworkX Graph；没有该报告提出的 Neo4j 按需查询实现 | 有版本管理实现，缺少事务、多进程发布与容量证据；Neo4j 导出不等于 Neo4j 存储 | P1：先解决原子发布和稳定ID，按规模决定数据库 |
| D02 混合检索 | 部分修复 | `backend/retrieval.py:469` 多路召回、`:1832` RRF、`:2889` 重排预算；`backend/vector_store.py:37` 向量存储 | `test_hybrid_retrieval_trimming.py`、`test_query_budgeting.py`；旧 query 仍保留简单检索，无法整项关闭 | P1：统一开放入口、真实服务质量回归 |
| D03 任务编排 | 部分修复 | `backend/routes/ingest.py:27` 任务加载、`:38` JSON 保存；`:158` 仍 BackgroundTasks | 持久化状态不等于可恢复执行；缺独立 worker、租约和多实例验证 | P1 |
| D04 多文档 | 部分修复 | `backend/kg_store.py:462` 多图合并；新检索链支持范围参数，但旧入口范围与资源授权未闭环 | 参见 62 项 #2/#23/#36；跨文档联合检索不等于实体对齐 | P0：权限与范围；P1：实体对齐 |
| D05 多轮推理 | 部分修复 | `backend/self_correction.py:20` 有界校正循环；旧入口使用 LangGraph create_agent，新主链为检索生成流程 | 自校正模块存在不能证明完整 classify/retrieve/reason/validate 状态图已接入；缺真实多跳路径支持性验证 | P1 |
| D06 认证鉴权 | 部分修复 | `backend/auth.py:54` API Key 中间件；`backend/middleware/jwt_middleware.py:92` JWT；租户与API Key服务存在 | 参见 #1/#9，资源级授权及默认放行仍须复核；不能以 JWT 模块存在判定已闭环 | P0 |
| D07 可观测性 | 部分修复 | `backend/metrics.py:159` RAG 指标；结构化日志、audit_logger、deploy/prometheus 和 Grafana 配置存在 | `test_log_redaction.py` 等；未获得完整 OTel 分布式追踪、费用账本、告警演练证据 | P1 |
| D08 数据治理 | 部分修复 | `backend/services/lineage_store.py:23` 血缘；`backend/services/backup.py:38` 备份/校验/恢复；图版本管理 | 本轮 Phase 2：28通过、5失败；备份等本地验证不替代 RPO/RTO、备份删除、PII治理及多进程一致性验证 | P1 |
| D09 部署运维 | 部分修复 | 根目录 `docker-compose.yml`，前后端 Dockerfile，`deploy/` 有 nginx 和监控配置 | 参见 #37/#39；未运行容器、TLS、恢复与回滚演练；未见该报告要求的 Helm 闭环 | P1，是否K8s由交付目标决定 |
| D10 CI/CD | 部分修复 | `.github/workflows/ci.yml:49` SAST、`:85` 依赖审计、`:124` 密钥扫描，测试和发布门禁已有配置 | 配置不是远端执行成功证据；前端 lint 有 `|| true`，测试覆盖及真实服务门禁仍有限 | P1 |
| D11 重试/DLQ | 部分修复 | `backend/generator.py:284` 有界重试；worker/mineru 客户端错误处理已有增量 | 参见 #12/#20；未见任务执行恢复、DLQ和worker故障演练的完整闭环 | P1 |
| D12 在线评测 | 部分修复 | `rag_eval/run_inference.py` 已走主服务路由，`release_gate.py` 有机器门禁；`backend/services/quality.py:26` 质量监控 | 旧 `release_gate_report.json` 为2026-07-04历史NO-GO，不能代表当前工作树；未见 shadow/AB/drift 完整实现或本轮真实模型回归 | P1 |
| D13 前端架构 | 部分修复 | `frontend/src/lib/api.ts` 已统一客户端，页面已扩展 | 仍使用 Zustand/页面状态；未见 BFF、TanStack Query和离线队列闭环；这些选型也不是企业就绪的必选技术 | P2；超时/取消与范围显示优先 |
| D14 表格公式图表 | 部分修复 | `backend/table_index.py:14` 表格索引；`test_bridge_table_body.py:5` 表体回归；worker构建运行时表格索引 | 有表格改进，缺完整单元格来源、公式/图表语义及专项标注验收 | P1：数值可靠性；P2：扩展能力 |
| D15 国际化 | 未修复 | `frontend/package.json` 无 i18next；页面仍中文固定文案，未见 locales 抽离 | 未找到国际化专项测试；不影响仅中文目标交付 | P2，取决于用户市场 |
| D16 成本控制 | 部分修复 | `backend/config.py:83` 上下文预算、`:93` 重排预算；`backend/routes/rag_query.py:408` 暴露预算；缓存已有实现 | `test_query_budgeting.py`、尾延迟测试；缺租户金额硬上限、完整费用账本和模型路由闭环 | P1 |
| D17 溯源体验 | 部分修复 | `frontend/src/pages/QueryPage.tsx:239` 页码面板，EntityDetailPanel展示来源 | 参见 #58；未见 PDF.js 原件高亮闭环，底层位置正确性仍受 #24–29 影响 | P1：先保证溯源正确，再优化预览 |

结论：架构建议中已有大量增量实现，但不能据此宣告企业交付完成；优先修复开放入口的权限、数据错配与删除风险，再做架构扩展。
