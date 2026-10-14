# 2026-10-12 双覆盖率与漏洞整改接续

**2026-10-13最终结果见[阶段证据](2026-10-13-quality-verification.md)**：新锁候选全量1065passed/1failed（真实研究冻结），有效90文件行10985/13387=82.06%、分支3306/4514=73.24%；前后快照一致。下文保留执行中历史状态，不再作为当前待测结论。

当前结论：局部整改已验证，整体门槛仍未通过；无提交、推送或部署。历史基线见 [首次扫描](2026-10-12-coverage-security.md)，执行范围见 [计划](../plans/2026-10-12-quality-remediation.md)。下述部分为执行中的记录，最终全量覆盖与新环境回归仍待补齐，不能套用旧报告。

## 已核实结果

| 项目 | 状态 | 证据 |
|---|---|---|
| 后端可修复锁漏洞 | 已修复（锁文件范围） | PyJWT2.15.1、multidict6.9.1、oauthlib4.0.0；lock check exit0；全206 registry版本扫描仅Chroma1.5.9五条原始记录，exit1 |
| Chroma/部署镜像 | 未修复/待验证 | 无fix_versions；应用PersistentClient不足以覆盖compose的Chroma服务，未套历史ignore、未扫描镜像 |
| 后端实际运行环境 | 待验证 | 原venv保留；独立候选环境消费锁下载中，旧环境通过不代表升级兼容 |
| 前端兼容升级及锁 | 部分修复 | pnpm锁冻结安装和构建exit0；审计剩4公告，高1/中3，exit1；Router7/Tailwind4迁移未实施 |
| Node22目标 | 已验证（本机构建） | 官方Node22.23.3 ZIP按官方SHA256核验；pnpm10.33.3 frozen install、tsc/Vite build exit0；不等同Docker构建 |
| Docker/CI消费锁 | 部分修复 | 后端uv.lock、前端pnpm-lock已接入；发布配置依赖四检查job；独立静态复审关闭原锁入口缺口，Docker daemon缺失未构建 |
| 隔离守卫缺文件与SQLite边界 | 已修复（正式源码恢复完整v2） | 初轮v1恢复后发现v2测试依赖.tmp；改正式路径红测4failed/3passed，原样恢复可追溯v2 SHA256 432717ba4c5193ded837af5bcd1863c37cafc18a896d2fe2255e74a943450637；最终25passed，历史副本未改 |
| CLI输出/研究测试分类 | 已修复 | 保持JSON stdout/stderr及退出码；研究test_*.py归测试角色、运行研究模块仍扫描；独立评审接受 |
| 研究当前源码与旧冻结 | 待验证，门槛阻塞 | 真实漂移保留失败，未更新冻结、旧实验或断言制造通过 |
| 双覆盖率≥90% | 未达标/新全量待测 | 固定范围不缩减；恢复生产模块自然纳入；首次65.49%行/54.09%分支不能充作当前代码证据 |

第一次整改后全量运行785passed/1failed（研究冻结）；coverage JSON导出失败，原因是研究测试在生产目录生成并删除临时Python源码。该次数据/日志保留且不作有效覆盖证据。已将夹具迁入既有tests/_sandbox_tmp目录，未改覆盖配置或编辑报告，随后48项KG/研究专项通过。后续新测试和最小修复加入后必须重新全量。

## 有效行为与边界

真实DOCX/XLSX/Markdown、JSON/YAML、NetworkX、临时ZIP、BM25及内存DuckDB用于本地行为断言；模型、向量供应商、云端和系统unzip的边界替代不当作真实供应商验收。新增测试发现并以red→green修复配置类型、空评测集、异常分类、最后轮自纠正等问题，详见 [CLI](2026-10-12-cli-behavior-tests.md)、[Worker](2026-10-12-worker-behavior-tests.md)、[Query](2026-10-12-query-behavior-tests.md)。

## 证据入口

- [后端依赖方案](2026-10-12-backend-dependency-remediation.md)、[锁检查日志](2026-10-12-remediated-lock-check.log)、[全锁审计JSON](2026-10-12-remediated-pip-audit-locked.json)、[全锁审计退出码](2026-10-12-remediated-pip-audit-locked-exit.txt)。
- [前端pnpm审计](2026-10-12-remediated-pnpm-audit.json)、[Node22校验收据](2026-10-12-node22-runtime.txt)、[Node22冻结安装](2026-10-12-node22-frozen.log)、[Node22构建](2026-10-12-node22-build.log)。旧npm锁原样归档，不再作为安装入口。
- [隔离恢复日志](2026-10-12-guard-restored.log)、[68项早期专项](2026-10-12-quality-behavior-final.log)、[配置红测](2026-10-12-mapping-red.log)、[配置绿测](2026-10-12-mapping-green.log)。
- [正式守卫SQLite红测](2026-10-12-guard-sqlite-source-red.log)、[最终正式守卫两组安全测试](2026-10-12-guard-source-final.log)；测试不再依赖.tmp守卫，模块仍是附加审计护栏，不代替OS防火墙/原生沙箱。
- [第一次整改全量日志（覆盖导出失败）](2026-10-12-remediated-backend-full.log)、[独立静态与专项评审](../review/2026-10-12-quality-remediation-review.md)。

剩余顺序：首先复核新增修复和新锁运行兼容；保留Chroma与前端未修公告并制定迁移/可达性决策；重跑有效全量覆盖，继续补行为缺口。研究冻结需独立研究版本及运行身份决策，不能当普通哈希更新。前端/其他第一方可执行子项目覆盖未完成，整体提交门槛保持BLOCKED；Windows为audit-only-windows，未宣称可信CI或保护分支已经启用。
