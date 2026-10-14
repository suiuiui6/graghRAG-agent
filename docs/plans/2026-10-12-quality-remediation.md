# 双覆盖率与漏洞整改计划

本轮是用户“那再继续执行”授权的维护接续。输入为根 AGENTS、测试规范及 [首次测量](../testing/2026-10-12-coverage-security.md)。不修改研究冻结哈希、用户原始资料或覆盖率分母来制造通过，不提交 Git。

## 步骤与所有权

- [ ] 后端依赖 coder：仅 pyproject.toml、uv.lock、requirements.txt；基于官方/扫描版本证据做兼容更新，保留 Chroma 未修复项，核验 lock --check 和全锁扫描。验证前不改运行环境。
- [ ] 前端依赖 coder：package.json、现有 package-lock.json、pnpm-lock.yaml、必要 Node 版本配置；优先兼容升级，不 force 主版本迁移；pnpm 构建、类型检查和审计。无同主版本修复的项记录迁移边界。
- [ ] debugger：只读核对研究隔离缺文件、CLI 输出规范、研究 pytest 分类、冻结漂移；给出来源可追溯的最小修复建议，不更新历史冻结。
- [ ] 主协调者：补 kg_builder、doc_processor 的图关系、格式解析、真实临时文件、元数据和异常行为测试。发现缺陷先红测再修复，保持原断言。
- [ ] coder 按根因恢复隔离安全模块、修正真实策略冲突；不将研究完整性失败静默移出验收。
- [ ] 独立 reviewer 复核依赖、测试行为与安全边界；阻断项关闭后在受控环境验证依赖一致性、全量测试及固定范围行/分支计数。
- [ ] 追加机器可读报告、原始日志、命令/退出码/快照；规范及 memory 回流。

2026-10-13阶段核实：后端锁升级/check/锁扫描、新候选环境同步及版本漂移0已完成；前端pnpm冻结安装、Node22构建和扫描已完成但剩4公告；真实行为补测、正式v2守卫恢复和独立复审已完成。新候选测试适配独立75passed，最终全量/覆盖在跑。上列未勾选条目包含未关闭的安全/全量/提交条件，不把局部完成等同整阶段通过；后续以最终报告分项状态为准。

## 行为测试中发现的最小修复（执行授权接续）

红测先于对应生产修改；不修改历史冻结及评分公式。独立reviewer另行复核。

- 主协调者：doc_processor.load_project_id_mapping 非对象JSON按既有“无效返回{}”契约处理。
- CLI coder：run_evaluation.run_full_eval 拒空查询；domain_dict.search 英文缩写统一大小写；kg_store.load_graph 原始空端点必须先拒绝再加文档前缀；bridge.build_documents 去前空白后更新准确原文offset。仅上述函数最小修改。
- Worker coder：errors.classify_external_error 具体requests/httpx超时、JSON和HTTP状态不得被通用OSError吞掉；保持stdlib-only、业务码优先和wire枚举。
- Query coder：self_correction.correct 校验初始与最后一次生成，不增加max_rounds生成预算；不改引用/数值启发式算法。
- 新测试归属按上述角色独占文件；所有人保留其他任务改动，统一全量及最终证据由主协调者负责。

## 验收与边界

每个阶段记录已通过与未通过，不把扫描完成视为风险清零。后端必须全量第一方生产文件行和分支分别 ≥90%，前端及其他相关可执行子项目必须按测试规范逐个测量，所有规定测试通过，方可讨论提交。当前前端缺覆盖测试配置；历史研究冻结对应旧生产源码，真实漂移必须留证并阻止复用旧实验为当前代码证明。

固定覆盖配置沿用 docs/testing/coverage-backend-2026-10-12.ini，新增生产文件自然纳入；运行环境/源码变动后重跑，首次报告保留。供应商未授权网络调用、真实生产部署与研究实验执行不在本轮范围。
