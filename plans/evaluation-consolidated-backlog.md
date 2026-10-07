# GraphRAG Agent 评估报告合并去重 · 统一整改 Backlog

> **生成日期**：2026-09-17
> **来源**：三份独立评估报告交叉合并去重
> 1. `【研发项目评估】· GraphRAG Agent 知识图谱.pdf`（branch `main @ 88c5e68`，产品形态分层评估）
> 2. `GraphRAG_Enterprise_Assessment.md`（v1.0 2026-09-11，企业级就绪度改造方案，D01–D17）
> 3. `GraphRAG(1).md`（安全/正确性审查，62 条缺陷 + file:line + 工时）
>
> **合并原则**：同一缺陷在报告中可能以不同编号/角度出现，本表按「根因」归并为一条，保留所有来源的代码证据与工时上限。
>
> ⚠️ **基线提示**：三份报告均基于 2026-09-11 前后代码快照。当前工作区有大量已修改文件（见 git status），落地前须逐条回核对当前代码。

---

## 零、结论共识（三份报告交叉验证）

| 维度 | 判定 |
|------|------|
| **算法/数据处理能力** | ✅ 成熟。grounding → bbox_norm → page_idx → 前端节点引用的**全链路溯源真实落地**，非概念化能力，是区别于普通 RAG demo 的核心差异化资产 |
| **工程底座** | ❌ 仅原型级。认证、状态管理、存储、部署、文档五大模块均不满足交付标准 |
| **总定级** | "可运行、不可交付"，不满足企业级生产就绪 |
| **技术栈选型** | ✅ 无需换栈。MinerU / LangGraph+LangChain+DeepSeek / React18+TS+Vite+Tailwind+Zustand 全部合理 |
| **建议演进方向** | 单机版收尾 → 在线工具 → 企业版；SaaS 暂不排期 |

**唯一实质性分歧 — 存储选型**：
- 企业级方案 MD 主张直接上 **Neo4j**；
- PDF 报告主张**单机版先落 SQLite** 收尾，Neo4j 属高阶形态；
- 安全清单不选边，仅要求"事务存储 + 原子切换 + tombstone"。
- **本 backlog 裁定**：SQLite 先行（单机版落地前提），Neo4j 作为在线工具/企业版的可替换后端，通过 `GRAPH_BACKEND` 开关隔离（见 D01）。

---

## 一、P0 — 架构阻断 / 安全红线（不修复不可交付）

| 编号 | 缺陷 | 根因 | 证据位置 | 修复方向 | 工时上限 |
|------|------|------|----------|----------|----------|
| **B01** | 零认证 + CORS 通配：任意人可删文件、烧额度 | 11 个端点无鉴权依赖；`allow_origins=["*"]` | `server.py:47-53,64-70` | 网关层最小认证（Basic Auth / IP 白名单）先行；再建 OAuth2+API Key+RBAC | 32–56h |
| **B02** | `document_id` 只写响应不限制检索范围，跨文档错配来源 | 检索未绑定授权文档子集 | `routes/query.py:195-207,262` | 检索前校验文档权限，绑定授权子集，节点/证据保存真实 doc_id+version | 16–32h |
| **B03** | 删除文档后内存图谱未失效，已删资料仍可被检索/回答 | 删除未 tombstone，未通知 worker 刷新 | `routes/documents.py:56-87` | 删除时先撤权/写 tombstone → 通知刷新快照 → 在途请求限流 | 8–16h |
| **B04** | 删除按字符串前缀推断，`doc_` 传错变空前缀 → **已复现删除全部原件** | 未校验文档存在，前缀推断 | `routes/documents.py:56-82` | 先查询并授权真实文档，未知 ID 返回 404，仅按资产清单精确删除 | 4–8h |
| **B05** | 删除异常被吞仍返回 `deleted`，未清理缓存/OSS，接口成功≠数据销毁 | 无资产清单、无重试 | `routes/documents.py:61-85` | 建原件+派生产物清单，按清单可重试删除，状态分 pending/deleted/failed | 16–32h |
| **B06** | OSS 上传失败复用旧缓存顶替结果，旧文档内容被当新文档入库 | 无匹配缓存回退逻辑 | `worker.py:63-84` | 移除无匹配缓存回退，仅按原文件哈希+解析版本+配置校验后复用；失败标 FAILED | 4–8h |
| **B07** | 任务先标 done 再持久化，失败时用户仍见成功、查询读旧图 | 状态机缺 committing 态 | `routes/ingest.py:51-87` | 增 committing 态，仅持久化+可查询版本发布成功后标完成 | 8–16h |
| **B08** | 输出目录 `task_id[:8]` 仅 16 种取值，不同任务覆盖/混用解析结果 | 短前缀 + 一位随机 | `worker.py:240-245` | 完整 UUID 独占目录，校验产物后原子发布，禁复用残留目录 | 4–8h |
| **B09** | JSON 直接覆写 + 线程锁，进程中断损坏文件、多进程丢更新 | 无事务、无原子切换 | `routes/__init__.py:25-50`、`kg_builder.py:146-149` | 元数据用事务存储，图谱在临时版本目录校验后原子切换 | 16–32h |
| **B10** | 敏感外发：未签名对象 URL；CLI 向 file.io 上传原件 | 桶权限未验证、第二方上传入口 | `oss_uploader.py:51-59`、`pipeline.py:149-158` | 私有桶 + 短时签名 URL + 出站策略；删除 file.io 死入口 | 16–32h |
| **B11** | SSRF：用户 URL 仅校验协议前缀，上游地址直接交 curl | 无域名/IP/重定向/大小限制 | `routes/ingest.py:103-123`、`worker.py:229-245` | 限制 HTTPS 域名、解析 IP、重定向目标、出站网络与下载大小 | 8–16h |
| **B12** | 上传先整读内存再判断大小，并发大文件耗尽内存 | `max_upload_size` 未生效 | `routes/ingest.py:136-143`、`server.py:44` | 网关限请求体 + 应用分块写盘累计限额 + 并发/磁盘配额 | 8–16h |
| **B13** | ZIP 解压无未压缩体积/文件数/成员类型限制，炸弹包耗尽磁盘 | 仅进程超时 | `worker.py:239-248` | 解压前校验成员路径/总大小/压缩比，拒绝链接与越界路径 | 8–16h |
| **B14** | Token 明文进命令行参数（curl），进程可查询窃取 | curl 子进程 + 参数拼接 | `worker.py:200-203,216-219` | 换 httpx 客户端，日志脱敏，只返回稳定错误码+request_id | 6–12h |
| **B15** | 日志输出文件路径/对象 URL，日志与进程参数暴露风险 | print 原样输出 | `worker.py:165-183,207-225` | 受控 HTTP 客户端 + 统一日志脱敏 | 6–12h |
| **B16** | 依赖清单失实：缺 `oss2`、`langextract`，干净安装后真实入库必失败 | requirements 与代码导入不一致 | `requirements.txt:1-11`、`worker.py:188,245` | 补全并锁定运行依赖，区分演示/provider 依赖，加 import 冒烟测试 | 4–8h |
| **B17** | 提示词注入 + 来源解析未限 ToolMessage，零工具调用仍返回 sources | 文档内容直接进上下文；用户节点 JSON 也可成证据 | `routes/query.py:143-145,171-173,207-259` | 结构化 claims+citations，限不可信内容指令权限，仅接受真实工具执行产生的证据 | 16–32h |
| **B18** | 任务/进度仅存 Web 进程内存，重启丢状态、多 worker 404、无恢复取消 | `_tasks` 字典 | `routes/ingest.py:19-20,123,159-172` | 持久化任务表 + 独立 worker + 租约/幂等/有限重试/取消/DLQ/TTL | 24–48h |
| **B19** | 同步 `agent.invoke()` 阻塞事件循环，拖慢其他 API 与健康探针 | 异步函数内同步调用 | `routes/query.py:194-207` | 改 `await agent.ainvoke`，CPU 密集任务入受限执行池 | 6–12h |
| **B20** | 假健康检查：按密钥长度判上游正常，坏凭据/坏图也通过 | 静态硬编码 + Token 长度 | `routes/health.py:62-88` | 拆分 liveness/readiness，验证激活图版本与本地依赖，未就绪返 503 | 8–16h |

---

## 二、P1 — 工程化交付短板（影响运维/扩展/正确性）

### 2.1 存储与图谱正确性

| 编号 | 缺陷 | 证据位置 | 修复方向 | 工时上限 |
|------|------|----------|----------|----------|
| **B21** | 检索 O(N) 全图子串扫描，无索引/排序/分页/聚合，漏召回 | `routes/query.py:132-145` | chunk+全文检索基线 → 向量融合+重排；枚举/统计用分页/聚合工具 | 24–48h |
| **B22** | 多跳工具只返回邻域节点，二跳以上退化为 connected | `routes/query.py:149-167` | 返回有序路径+每条边方向/类型/证据，限跳数/展开数，路径级排序 | 12–24h |
| **B23** | 工具调用预算未执行，跳数/返回数量无硬边界，费用失控 | `models.py:31-35`、`routes/query.py:151-167,207` | 总时间/token/金额/调用次数硬预算 + 参数范围约束 | 12–24h |
| **B24** | 图谱仅有同页共现/同类型/相邻三种结构边，不能证明事实关系 | `kg_builder.py:49-97` | 按业务域定义关系 schema，抽有向/限定/时间/证据的三元组，分离结构边与事实边 | 32–64h |
| **B25** | `nx.Graph` 无向简单图，同实体对关系被覆盖，方向/属性丢失 | `routes/query.py:32-42` | 改 MultiDiGraph 或显式关系集合，保留 edge_id/方向/属性/证据 | 6–12h |
| **B26** | 实体直接建节点，缺别名/消歧/跨文档对齐 | `kg_builder.py:25-38`、`routes/query.py:64-67` | 按领域主键对齐，补规范化名称+别名召回，歧义留候选人工确认 | 24–48h |
| **B27** | 节点 ID 按目录/列表顺序重编号，不同视图指向不同实体 | `routes/query.py:54-67`、`routes/graph.py:87-105` | 稳定实体 ID（含 doc+version），统一查询/图谱/证据标识规则 | 12–24h |
| **B28** | 查询用旧 Agent 但读最新全局图，热更新无版本顺序保护 | `routes/query.py:109-116,204-249` | graph/agent/version 绑定为不可变快照，请求全程用同一快照 | 12–24h |
| **B29** | 持久化图谱丢字符跨度/块类型/metadata 空/缺原文件哈希与版本 | `kg_builder.py:115-129`、`worker.py:142-144` | 建文档版本+构建 manifest+source_span，记录配置版本与校验和 | 16–32h |

### 2.2 溯源正确性（grounding 链路）

| 编号 | 缺陷 | 证据位置 | 修复方向 | 工时上限 |
|------|------|----------|----------|----------|
| **B30** | 仅规范化待匹配文本未同步 full.md，短前缀匹配+全文长度算区间错位 | `bridge.py:33-53` | 优先用解析块 ID，或建规范化文本→原文偏移映射 | 12–24h |
| **B31** | 分段 strip 后仍用原始段首偏移，实体坐标错位影响页码/bbox | `bridge.py:204-206,222-233` | 保留原始分段文本，或按删除前导字符修正 offset | 3–6h |
| **B32** | 找不到文本仍人为分配连续区间，位置命中即标 grounded，不存在内容也显示已溯源 | `bridge.py:54-66`、`grounding.py:59-81` | 未匹配内容标 unmapped 隔离，仅原文对齐+坐标校验通过的证据标 grounded | 8–16h |
| **B33** | 跨块区间退化为首块、未知 doc 偏移默认 0、bbox 缺范围/单位校验 | `schema.py:30-36`、`grounding.py:25-31,73-81` | 支持多 span 来源，未知 doc_id 明确失败，校验区间/页码/坐标 | 12–24h |
| **B34** | 表格/图片溯源靠标题，缺单元格结构/表头继承/图像证据链 | `bridge.py:71-88`、`worker.py:283-303` | 保存表格行列/单元格来源/单位，数值用确定性工具，视觉问题独立路由 | 24–48h |

### 2.3 状态与任务

| 编号 | 缺陷 | 证据位置 | 修复方向 | 工时上限 |
|------|------|----------|----------|----------|
| **B35** | 上游提交/轮询/抽取缺统一有限重试与总截止，未持久化 provider_task_id | `worker.py:206-248,274-303` | 分类 401/429/5xx/超时退避重试，持久化 provider_task_id，限阶段总耗时 | 12–24h |
| **B36** | 无内容去重/幂等键/文档版本，重试重复计费，新旧版本同时回答 | `routes/ingest.py:108-123,140-159` | 按租户+内容哈希+配置版本去重，幂等键，stable_id+active_version | 16–32h |
| **B37** | OCR 选项未传 MinerU，页数用章节数代替，选项无效/页数错 | `worker.py:157,192-205` | 强类型选项逐项传递，页数从解析元信息取 | 4–8h |

### 2.4 可观测性 / 审计 / 安全补强

| 编号 | 缺陷 | 证据位置 | 修复方向 | 工时上限 |
|------|------|----------|----------|----------|
| **B38** | 全链路无追踪/审计/费用账本/SLO 告警 | `server.py:56-62`、`routes/query.py:261-267` | OTel + 统一 request/task/trace ID + 阶段延迟/成本/索引版本 + 脱敏审计 | 16–32h |
| **B39** | 无 OTel：print 当日志（85 处）、21 处吞异常、无 metrics/traces | 全后端 | structlog JSON + trace_id + Prometheus 指标 + `/metrics` | 16–32h |
| **B40** | 文件 token 与限流仅进程内，localhost 绕过校验 | `security.py:6-12,25-52` | 短时访问凭据 + 可信代理 + 按用户/租户/接口共享限流并发配额 | 12–24h |
| **B41** | 强制 load_dotenv 覆盖部署注入配置 | `server.py:7-9`、`worker.py:13-15`、`oss_uploader.py:8-10` | 集中 Settings 加载校验，生产注入优先 | 4–8h |

### 2.5 部署 / CI / 前端

| 编号 | 缺陷 | 证据位置 | 修复方向 | 工时上限 |
|------|------|----------|----------|----------|
| **B42** | 无容器化/K8s，start.sh 混用 Bash/Windows 激活路径 | `start.sh:7-13` | Dockerfile 多阶段 + docker-compose + K8s 清单 + live/ready 拆分 | 24–48h |
| **B43** | CI 简陋，无集成/契约/性能/安全扫描 | `.github/workflows/ci.yml:22-31` | 集成+契约+性能基线 ±20%+安全扫描+依赖审计阻断 | 24–48h |
| **B44** | 前端未读文档路由参数，只发当前问题，多轮无历史 | `QueryPage.tsx:12-17,59-68` | 读取传递 documentId，明确范围；多轮加 conversation_id+历史+TTL | 12–24h |
| **B45** | 前端硬编码假数据（状态灯/统计）、非法 Tailwind 类、CDN 无 SRI、emoji 替代图标、实体配色三处维护 | `AppShell.tsx:33,42-45,60-64`、`index.html:10-11`、`graph.py`/`constants.ts`/`globals.css` | 接真实数据、修类名、vis-network 本地化、启用 lucide-react、配色收敛单一真值 | 12–24h |
| **B46** | 请求无超时/取消，证据面板仅页码+bbox 无法定位原件 | `api.ts:3-12`、`QueryPage.tsx:128-156` | 超时+取消+证据带版本/span 定位+PDF 高亮预览 | 12–24h |

---

## 三、P2 — 产品能力深化（标记补缺）

| 编号 | 能力项 | 状态 | 实施提示 | 工时上限 |
|------|--------|------|----------|----------|
| **B47** | 表格/公式/图表结构化入图 | 🔴 补缺 | extraction_examples 增示例、kg_builder 增类型、接入 Table Transformer | — |
| **B48** | 国际化 | 🔴 补缺 | i18next、SYSTEM_PROMPT 模板化、文案提取 locales/ | — |
| **B49** | 成本控制 | 🔴 补缺 | 中间件统计 Token、LiteLLM 分级、GPTCache 语义缓存 | — |
| **B50** | 溯源体验增强 | 🟡 部分有 | PDF.js 高亮、Range 请求、稳定节点深链接 | — |
| **B51** | 评测体系在线化 | 🟡 仅离线 | shadow_eval 影子测评、A/B 分流、drift 漂移告警 | 12–24h |

---

## 四、企业级基础设施演进（对应 Enterprise MD 的 D01–D17，按阶段归位）

> 与 P0/P1 有重叠的部分已并入上表（鉴权 B01、任务队列 B18、可观测 B38/B39、治理 B09）。以下为**存储与检索层**的专项改造，是 PDF 报告「在线工具/企业版」形态的前置。

| 编号 | 改造 | 说明 | 阶段 |
|------|------|------|------|
| **D01** | NetworkX+JSON → 图存储抽象层 | `stores/graph_store.py` 封装，`GRAPH_BACKEND=networkx|neo4j` 开关，SQLite 先行 | 阶段1 |
| **D02** | 单一 KG → 三路召回融合 | `retrieval/`：vector_store(ChromaDB) + keyword_store(BM25/FTS5) + fusion(RRF+Cross-Encoder) | 阶段2 |
| **D04** | 单文档 → 多文档联合检索 | Neo4j 节点加 doc_id、跨文档实体链接 `:SAME_AS`、`scope=single/global/selected` | 阶段4 |
| **D05** | 单轮 Agent → LangGraph StateGraph | `agentic_rag/`：classify→retrieve→fuse→reason→generate→validate，条件边+重试 | 阶段3 |
| **D03** | BackgroundTasks → Celery+Redis | 5 阶段拆独立 Task，`chain()` 编排，Redis 进度键 | 阶段3 |
| **D08** | 数据治理（血缘+版本+备份+PII） | KGNode 增 version/checksum、增量 UPSERT、presidio PII 扫描 | 阶段4 |

---

## 五、评测体系质量（GraphRAG(1).md 第 42–44 条专项）

| 编号 | 缺陷 | 证据位置 | 修复方向 |
|------|------|----------|----------|
| **E01** | 评测自建四工具 Agent，线上仅两工具，绕过 HTTP 与来源组装，分数不代表现状 | `rag_eval/run_inference.py:164-183` | 评测复用实际服务入口，固定代码/索引/模型/prompt/参数 |
| **E02** | 用节点存在证零幻觉、按否定词判拒答、对 ID 排序算 MRR，高估质量 | `rag_eval/metrics_a2_faithfulness.py:25-47,133-140` | 分别评引用合法性/事实支持性/拒答混淆矩阵，保留真实排名算 MRR/nDCG |
| **E03** | 仅单篇 50 题 + 硬编码路径 + 原图未随仓库 | `run_inference.py:29-33` | 建 200–500 题分层保留集，去敏语料+哈希+相对路径，报告分场景+置信区间 |

---

## 六、文档与代码一致性（PDF 第七章 9 处 + 治理红线）

| 编号 | 偏差 | 证据 |
|------|------|------|
| **C01** | 文档描述 Neo4j `kg_prod`，代码是 networkx+JSON | `docs/governance/permissions-matrix.md` |
| **C02** | 巡检命令指向 `backend/app/api/`，实际是 `backend/routes/` | `docs/governance/entropy-rotation.md` |
| **C03** | release-checklist 指向不存在 tag `d9e0cf0` | `docs/release-checklist.md` |
| **C04** | README "clone 即可用"，requirements 缺依赖装完失败 | `README`、`requirements.txt` |
| **C05** | README/标题 "多模态"，视频解析不存在 | `README` |
| **C06** | CLAUDE.md 铁律"每端点须有集成测试"，实际 5 路由零测试 | `CLAUDE.md` |
| **C07** | 子模块指针悬空（gitlink 无 .gitmodules），clone 后空目录 | `langextract/`、`harness-engineering/` |
| **C08** | `.env.example` 缺 OSS 必填四项 | `.env.example` |
| **C09** | 治理文档称颜色单一真相，实际三处维护 | `graph.py`/`constants.ts`/`globals.css` |

---

## 七、演进路径（合并三份报告后裁定）

```
P0 紧急整改（B01–B20 安全+数据完整性）
   ↓
单机版工程收尾（SQLite 持久化、分级错误码、真实启动自检、start.bat/docker-compose、成本可视化）
   ↓
图谱归属改造设计评审（在线工具前置，最高风险模块）
   ↓
阶段1–4 企业级基础设施（存储抽象 → 三路召回 → LangGraph+任务队列 → 鉴权+OTel+多文档）
   ↓
在线工具开发 → 本地化解析预研 → 企业版建设
```

**立即行动清单（P0 内最先启动的 4 项）**：
1. 补依赖锁定 + `uv lock` + `pip-audit` + pre-commit + git-secrets（对应 B16、C04）
2. 网关层最小认证（Basic Auth / IP 白名单）（B01）
3. 删除 OSS 失败兜底 + 文件名消毒 + ZIP 安全（B06/B12/B13）
4. 删除/查询的权限校验与 tombstone（B03/B04/B05）

---

## 附：代码证据索引（来自 GraphRAG(1).md，落地回核用）

| 判断 | 证据位置 |
|------|----------|
| 零认证（11 端点） | `server.py:64-70` 挂载路由无依赖注入 |
| CORS 通配 | `server.py:47-53` `allow_origins=["*"]` |
| 上传体积防护不生效 | `server.py:44`（无效参数）+ `ingest.py:130-133` |
| 文件名未消毒 | `ingest.py:136-141` 客户端原始文件名拼接 |
| 任务状态内存态 | `routes/ingest.py` `_tasks` 字典 |
| 全局单图/单例 Agent | `routes/query.py` `G_grounded` / `_agent` 双检锁 |
| 文档库内存态 | `routes/__init__.py` `_docs_store` + `threading.Lock` |
| OSS 失败数据污染 | `worker.py:64-84` 扫目录按名称倒序取第一个 |
| O(N) 全表扫 | `query.py:129` 遍历全部节点子串匹配 |
| curl 子进程 + 命令行 Token | `worker.py:200-203,216-219` |
| file.io 死入口 | `pipeline.py:149-169` |
| 假健康检查 | `routes/health.py` 静态 ok，Token 长度>10 判正常 |
| 内存限流 | `security.py:10` 进程内字典 |
| 吞异常 | 全后端 21 处 `except Exception`、1 处裸 except |
| print 当日志 | 全后端 85 处 |
| 硬编码状态灯/统计 | `AppShell.tsx:60-64,42-45` |
| 非法 Tailwind 类 | `AppShell.tsx:33` `bg-white/3` |
| CDN 强依赖 | `index.html:11-12` vis-network 引自 cdnjs |
| 实体配色三副本 | `graph.py`/`constants.ts`/`globals.css` |
