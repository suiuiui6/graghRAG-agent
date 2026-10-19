# 项目文档索引

项目约束：[AGENTS.md](../AGENTS.md)。接续入口：[memory](../memory/index.md)。复用方法：[patterns](../patterns/index.md)。

## 新文档分类

- [需求](requirements/README.md)
- [总体与详细设计](design/README.md)
- [接口与数据契约](contracts/README.md)
- [开发计划](plans/README.md)
- [设计与代码评审](review/README.md)
- [测试、覆盖率及证据](testing/README.md)
- [协作工作流](governance/agent-workflow.md)
- [归档规则](archive/README.md)

## 现有权威规范（保留原位）

- Layer 1：[MinerU API](../langextract/docs/MinerU-API-Specification.md)、[MinerU 配置](../langextract/docs/MinerU_MVP测试配置指南.md_v1.0.md)、[LangExtract Pipeline](../langextract/docs/LangExtract-Pipeline-Specification.md)
- Layer 2：[桥接流水线](../langextract/docs/bridge-pipeline-specification-v1.0.md)
- Layer 3：[Agentic KG RAG](../langextract/docs/agentic-kg-rag-specification-v1.0.md)、[集成架构](../integration/Agentic-RAG-Architecture.md)
- Layer 4：[PRD](../integration/multimodal-rag-prd-v1.0.md)、[后端 API](../integration/backend-api-architecture-v1.0.md)、[前端设计](../integration/frontend-system-design-v1.0.md)
- [企业演进蓝图](../integration/enterprise-evolution-blueprint-v1.0.md)
- [既有 plans](../plans/)、[既有 Superpowers 设计](superpowers/specs/)、[既有 Superpowers 计划](superpowers/plans/)
- [治理文档](governance/)、[历史排障](troubleshooting-archive/)

索引提供导航，不复制规范正文。当前工作范围以具体任务 memory 和批准的计划为准；此索引不代表仓库所有未完成任务均已验收。

- 2026-10-15：[公开开发隔离与结构适配契约](contracts/2026-10-14-development-isolation-adapters.md)、[P0/A预算实测](review/2026-10-15-development-p0-a-budget.md)、[执行复核](review/2026-10-15-development-execution-review.md)、[资源独立审查](review/2026-10-15-development-resource-review.md)。仅开发资源profile，未做质量比较或留出验证。

- 2026-10-14：[数值入口合同](contracts/2026-10-14-vector-ingress-semantics.md)、[R4b宽整数修复及专项证据](testing/2026-10-14-vector-ingress-r4b.md)。仅隔离候选，生产替换未放行。

- 2026-10-14：[公共异常契约](contracts/2026-10-14-vector-error-semantics.md)、[消费者审计](review/2026-10-14-vector-error-consumer-audit.md)、[R5隔离验证](testing/2026-10-14-vector-errors-r5.md)。实现/复核状态以报告为准，宽记录/NaN向量和日志原因链仍有开放边界。

- 2026-10-12：[历史评估核查](governance/assessment-2026-10-12.md)、[五项P0修复后证据](testing/2026-10-12-p0-verification.md)、[独立复审](review/2026-10-12-p0-code-review.md)。

- 2026-10-12：[双覆盖率与漏洞扫描实测](testing/2026-10-12-coverage-security.md)、[覆盖范围独立审查](review/2026-10-12-coverage-scope-review.md)。

- 2026-10-13：[双90最终阶段验收及剩余优先级](testing/2026-10-13-to90-verification.md)、[最终局部独立复审](review/2026-10-13-readiness-final-independent.md)、[rag_eval范围复审](review/2026-10-13-rag-eval-readiness-review.md)、[向量库安全决策包](design/2026-10-13-vector-security-decision.md)。
