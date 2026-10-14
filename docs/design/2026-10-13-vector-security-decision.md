# Chroma剩余公告处理决策包

状态：待用户选择；未替换组件、未迁移数据、未降低安全门槛。

2026-10-13重新查询安装候选精确185 registry版本，pip-audit退出1，Chroma1.5.9仍5原始记录/4唯一GHSA，所有fix_versions为空。GitHub官方公告仍标None patched：

- https://github.com/advisories/GHSA-f4j7-r4q5-qw2c
- https://github.com/advisories/GHSA-36p7-vc44-83pf
- https://github.com/advisories/GHSA-xph7-9rjv-w5fr
- https://github.com/advisories/GHSA-2wm9-hf6c-p5cr

已完成的缓解：当前VectorStore固定PersistentClient、代码控制collection配置；移除compose/CI未使用独立HTTP服务。真实临时持久化、过滤、删除及子进程重开验证通过。此缓解不改变包漏洞扫描结果，不使用ignore或重命名包掩盖公告，也不证明运行中的历史部署已改。

建议路线：进入向量存储替换设计和隔离MVP评估，确认候选后再集成。保留`VectorStore`消费者契约：批量chunks+显式向量、按ID读删、按source删、metadata过滤、cosine排序/原score映射、count/list_sources/health以及持久化重开。候选必须在独立锁环境用合成数据验证这些功能，并测当前典型规模的查询/写入、维度异常、并发写入及恢复边界；不能先升级主依赖再试错。

迁移门槛：先只读盘点旧Chroma向量/文档/元数据格式；迁移工具默认dry-run，校验数量、ID、向量维度、元数据和抽样排序，不覆盖旧目录；集成前独立设计评审及用户确认。不能假设现有原文或embedding模型可重建全部向量。正式迁移/发布另按实际授权执行。最终移除Chroma依赖须全链消费者测试、全生产双90、锁与安装审计、备份恢复通过，不以组件消失但功能缺失换扫描零。

备选路线：保留当前嵌入式缓解并等待上游发布可验证修补。扫描与交付继续BLOCKED；用户知悉风险并不等于漏洞已修，不能自动把包扫描改成通过。

需要的决定：是否允许进入上述核心组件替换设计/MVP路线。依据根AGENTS“新功能先总体设计，再详细设计，独立评审后修改与复核……用户确认设计与计划后持续推进”，现有补测/局部安全修复授权不应默认为已接受存储能力或迁移策略变化。
