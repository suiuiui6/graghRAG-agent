# 2026-10-12 历史评估复核：交付、前端与 Skill

只读核对当前工作树（含未提交改动），来源为 Desktop/GraphRAG(1).md 的 36–41、45–49、56–62 共 18 项。未读取 .env，未联网，未运行真实供应商请求、部署或浏览器。外部 goal 安装包与仓库内 Harness 只代表当前本机证据，不代表历史公开仓库已同步。

## 审查总结

已有依赖锁、认证审计、监控、部署与备份代码，原报告“完全没有”的说法已过时；但前端生命周期和生产验收仍有明确缺口。本分组：已修复 2、部分修复 10、未修复 4、已不适用 0、待验证 2。风险分布：High 12、Medium 6（沿用原项风险，62待核实）。

## 逐项修复矩阵

| 原项 | 状态 | 剩余优先级 | 当前代码与测试证据 | 剩余工作 |
|---|---|---|---|---|
| 36 | 部分修复 | P1 / High | frontend/src/pages/QueryPage.tsx:66 读取 docId，108–111 向 API 传 documentId/sessionId；backend/conversation.py:145、160–161、187、398–409 有用户字段、持久化及三轮历史改写；frontend/src/lib/queryContract.test.ts:9–28 检查字段转发（本次未执行）。 | QueryPage:75–94、135–140 仍以全图欢迎语及统计展示文档范围；需明确当前文档范围，补浏览器路由切换、多轮隔离及 TTL 验收。不能以存在 user_id 字段证明隔离已验收。 |
| 37 | 部分修复 | P1 / High | backend/services/health_checker.py:47–90 已有真实 HTTP 探测；backend/routes/health.py:111–134 已纳入缓存结果及 runtime_recovery；但 106–110 仍按密钥长度标组件正常、148 kg_store 固定 ok，探针空缓存时 overall 可 healthy，HTTP 不返回503。test_phase3.py:283–294 只断言状态枚举，未验证坏密钥与就绪拒绝。 | 分离存活与就绪，未知缓存不作为通过；MinerU 探测84行把401/404当ok需修正。 |
| 38 | 部分修复 | P1 / High | backend/server.py:318–322 request_id、379–381 metrics；backend/logging_config.py:112–122 绑定上下文；backend/services/audit_logger.py 已实现审计，test_phase3.py:67–106 有读写/过滤测试；backend/metrics.py:14–48 有请求、耗时及上下文预算；deploy/prometheus/alerts.yml:7–69 有质量、错误率和时延告警。 | 未见完整供应商账单/金额账本与全链路传播验收；告警配置存在不等于已触达演练。本次未执行审计测试。 |
| 39 | 部分修复 | P1 / High | Dockerfile.backend:31–35 非reload启动与healthcheck；docker-compose.yml:10–29 持久卷和容器运行；backend/services/backup.py:78、217–269 备份/恢复/预恢复快照，test_phase2.py:277–320 有备份验证测试；deploy/cd-deploy.sh:35–59 发布与健康轮询。 | backend/start.sh:7–13 原混用脚本仍在；Compose无独立worker服务，CD仅以HTTP200判成功、未自动回滚，TAG变量与Compose build配置未形成镜像切换闭环；未执行TLS、容量、任务续跑、恢复与回滚演练。 |
| 40 | 部分修复 | P1 / High | backend/uv.lock 和 frontend/package-lock.json 已存在；.github/workflows/ci.yml:79–136 有依赖与密钥扫描。但 backend/requirements.txt:5起仍宽松下界，Dockerfile.backend:15–16 按该文件pip安装；frontend/src/pages/GraphPage.tsx:9–19仍加载公网CDN且无SRI。frontend无pnpm-lock.yaml，但CI:46、192要求pnpm --frozen-lockfile。 | 让实际CI/镜像消费锁，统一pnpm锁；vis-network本地打包；补SBOM/许可证/历史密钥扫描证据。实际供链测试2通过1失败，详见下文。 |
| 41 | 部分修复 | P1 / High | backend/tests已大量新增权限、来源、热更新、预算、恢复等测试；CI:175–193运行后端测试及前端类型检查。frontend/src/lib/queryContract.test.ts已有契约断言，但package.json:6–10无测试脚本且CI没有执行该文件/浏览器状态测试。CI:47 ESLint以|| true吞失败。 | 补真实供应商入库/删除/并发验收以及前端主流程，修复现有失败；本次不以测试文件数量认定真实依赖集成通过。 |
| 45 | 部分修复 | P1 / High | 本仓库无原goal-skill/goal目录；本机 C:/Users/14156/.codex/skills/goal/SKILL.md:44要求的 Harness references/runtime-stages.md、core/flow.md 及 adapters/codex/host-map.md 当前安装目录均存在。 | 原缺文件现象在本机已补齐，但无固定跨包版本和干净安装/完整执行证据，不推断公开发行已解决。 |
| 46 | 已修复 | P2 / High | harness-engineering/superpowers/harness-engineering/SKILL.md:1–4已有name/description，14–19正确指向包内runtime及宿主适配；scripts/validate_harness_skill.py:15–38列必需资源并检查存在。本次运行该validator exit0：OK: shared harness-engineering structure present。 | 此状态仅关闭原“description及引用缺失”缺陷，不包含真实宿主流程验收。 |
| 47 | 已修复 | P2 / High | 新canonical SKILL.md已无原优先于宿主声明；adapters/codex/host-map.md:13明确AGENTS可能具有更高优先级、不能假定bundle覆盖冲突。静态结构validator通过。 | 持续保留权限冲突行为评测；本次未触发写操作检验。 |
| 48 | 待验证 | P1 / High | 本机goal/scripts/test_goal_guard_integration.py:17由GOAL_RUN_GUARD_INTEGRATION控制，49–60默认skip且缺Guard时仍skip；当前GraphRAG CI无该独立包集成发布门禁。 | 未获取原goal发行仓库最新CI，不能断言外部CI仍未启用；Windows仅audit-only-windows，不能宣称机械阻断已验收。 |
| 49 | 部分修复 | P1 / High | Harness validator:15–38有文件存在检查，scripts/test_behavior_evals.py:160–172将缺响应标not-run，已超出原只查文字；docs/reviews/2026-07-12-harness-engineering-skill-review.md:9–18记录行为not-run；manual-replay目录有后续宿主输出，但本次未独立重放评分。 | 新增的schema/录制机制不能证明Agent遵守，需固定兼容包、完整引用图及真实独立行为评测。 |
| 56 | 未修复 | P2 / Medium | frontend/src/pages/GraphPage.tsx:66–138初始化effect仅依赖[data]，不依赖visReady/viewMode；134–138清理销毁网络；221、248条件挂载视图；41–50每10s重新setData导致重建。 | 首次CDN就绪和切回画布可能直到轮询更新才初始化，布局反复重置。补依赖/画布生命周期管理及增量更新/视口保留，浏览器复现尚未执行。 |
| 57 | 未修复 | P2 / Medium | UploadPage.tsx:26–53 interval轮询与恢复effect无卸载清理，55–85提交返回后才startUpload；useAppStore.ts:50–68普通内存store、61以st.id <= step将当前步骤也视为done。 | 提交前锁定、单次可取消轮询、隔离旧响应、持久化taskId、准确阶段状态；未执行浏览器测试。 |
| 58 | 未修复 | P2 / Medium | frontend/src/lib/api.ts:10–30 fetch、刷新和重试均无内建deadline；QueryPage.tsx:238–246仅页码/bbox且链接为固定/graph。 | 加AbortController/超时、原件安全预览与span高亮、稳定节点深链接；未执行浏览器网络悬挂测试。 |
| 59 | 部分修复 | P1 / Medium | CLAUDE.md:37–43现有规范索引已改为langextract/docs与integration路径，旧链接问题部分消除；但 backend/pipeline.py:151–154、integration/pipeline.py:153–156仍存在file.io原件上传且两套CLI副本并存。 | 明确停用/归档旧CLI或统一受控上传核心，防止只修API留下外发入口；本次未上传文件。 |
| 60 | 未修复 | P2 / Medium | 当前本机goal/SKILL.md:40仍明确 emit the five-field reply and stop，即使Confirmation not-required也停止。 | 按原建议允许已授权明确维护继续，同回合通过结构化状态记录；本仓库无法替外部Skill修改/发行验收。 |
| 61 | 部分修复 | P2 / Medium | harness-engineering/evals/skill-evaluation/iteration-3/benchmark.md:3–18已新增4场景并报告时间/token，迭代1的1.91倍不能直接代表当前版本；但5/5为断言分数而非5次重复，with_skill为compact brief而非完整实际包（5行），总体95% vs100%。 | 补重复抽样、独立盲评真实变更及同预算比较；不把compact brief的token优势外推为完整Skill收益。 |
| 62 | 待验证 | P2 / Medium | frontend/package.json:14仍^6.28.0；package-lock.json:3569–3590实际react-router/react-router-dom锁为6.30.3。 | 本次未联网刷新漏洞数据库，也未执行pnpm/npm audit；不能仅凭版本升级判两条通告已修复。需对具体GHSA受影响区间、SPA可达性和安装锁执行安全复核及深链接测试。 |

## 本次实际执行

1. `PYTHON_DOTENV_DISABLED=1 backend/.venv/Scripts/python.exe -m pytest backend/tests/test_supply_chain.py -q`：2 passed / 1 failed，耗时19.26s。失败是test_code_imports_are_declared：research/test_deepseek_scope_pilot.py导入pytest被判未声明（test_supply_chain.py:146）。这是扫描范围/开发依赖声明口径待修的门禁失败，不能推断运行服务缺pytest。出现Unknown config option: timeout，表示当前本机pytest-timeout能力未证实。
2. `backend/.venv/Scripts/python.exe harness-engineering/superpowers/harness-engineering/scripts/validate_harness_skill.py harness-engineering/superpowers/harness-engineering`：通过，exit0。仅证明本次静态结构验证。
3. 主审查进程另外执行phase2（排除Endpoints）：28 passed / 5 failed / 6 deselected。失败涉及catalog build/search/type、export kg json、quality grounding；初步存在fixture切目录与catalog模块级KG_DIR路径不一致的可能，未完成根因复现，不能认定生产资产损坏。

## 优化建议汇总

1. P1：统一实际构建锁与包管理器、修复已有门禁失败；关闭CLI外发入口；让health在未就绪时503，并修正MinerU 401当健康。
2. P1：为当前实现补真实入库/权限/删除/快照/并发集成验收、备份恢复与镜像发布回滚演练；完整费用账本与告警演练。
3. P2：集中修复GraphPage和UploadPage生命周期、QueryPage范围展示与来源定位、请求超时，建立浏览器状态回归。
4. 独立Skill包：先固定跨包版本及Guard发布门禁，再补真实宿主行为重放、重复盲评；不要将Windows审计当机械保护。

## 代表性 before / after 建议（未修改实现）

- GraphPage.tsx:138：before `}, [data])`；after 按实际画布挂载时机触发初始化并将初始化与DataSet更新拆开，监听`data/viewMode/visReady`，更新数据时保留位置及缩放。
- UploadPage.tsx:47–53：before effect只启动轮询；after effect返回clearTimeout/abort清理，使用await完成后再安排下一次轮询，并在提交前原子置uploading。
- api.ts:15：before直接fetch；after统一组合调用者signal和deadline的AbortController，finally清理计时器，并限制刷新/重试在总deadline内。
- health_checker.py:84：before `resp.status_code < 500`；after仅接受明确约定的成功状态，401/403/404进入degraded，并将readiness失败映射HTTP503。
