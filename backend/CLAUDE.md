# Backend — CLAUDE.md

## 项目概述

GraphRAG 多模态知识图谱问答系统后端服务。
FastAPI + LangGraph Agent + DeepSeek，提供 RESTful API。

## 启动方式

```bash
# 1. 激活虚拟环境
source D:/graghRAG-agent/backend/.venv/Scripts/activate

# 2. 进入后端目录
cd D:/graghRAG-agent/backend

# 3. 安装依赖（二选一）
uv pip install -r requirements.txt      # 不读锁文件，适合快速起环境
#   —— 或 ——
uv sync --locked                        # 按 uv.lock 精确复现（推荐）

# 4. 启动服务 (端口 8000)
uvicorn server:app --host 0.0.0.0 --port 8000 --reload --limit-max-requests 0 --timeout-keep-alive 300
```

## 依赖管理（uv 锁文件）

`pyproject.toml` 是依赖的**权威清单**；`requirements.txt` 为兼容 Docker/CI 的手写副本，
两者一致性由 `tests/test_supply_chain.py` 强制（不一致即测试失败）。

- **权威清单**：`pyproject.toml` —— 改依赖请改这里，再同步 `requirements.txt`
- **锁文件**：`uv.lock` —— 锁定全部依赖版本 + 哈希
- **导入冒烟**：`python scripts/check_imports.py` —— 校验真实入库链路依赖齐全

> ⚠️ **锁文件绑定阿里云镜像**：生成时用了
> `--default-index https://mirrors.aliyun.com/pypi/simple/`，205 个包的 registry
> 与 794 个下载 URL 均写死该地址（无"中性"写法）。
> - 重新解析依赖须带同一参数，否则本机直连 pypi.org 会超时：
>   `uv lock --default-index https://mirrors.aliyun.com/pypi/simple/`
> - CI 已设 `UV_DEFAULT_INDEX`（见 `.github/workflows/ci.yml`），**勿删**
> - ⚠️ 下载 URL 也写死在锁文件里 —— 在无法访问 `mirrors.aliyun.com` 的环境构建，
>   需**重新生成**一份指向该环境可达镜像的锁文件，仅改环境变量无效

## API 端点

| Method | Path | 说明 |
|---|---|---|
| GET | `/` | 服务信息 |
| GET | `/docs` | Swagger UI |
| POST | `/api/v1/ingest` | 上传文档并触发索引 (PDF→MinerU, DOCX/XLSX→本地解析) |
| GET | `/api/v1/status/{task_id}` | 查询索引进度 |
| POST | `/api/v1/query` | KG 知识图谱问答 (LangGraph Agent) |
| POST | `/api/v1/rag/query` | 增强 RAG 问答 (多路召回 + RRF + 溯源) |
| GET | `/api/v1/health` | 健康检查 |
| GET | `/api/v1/documents` | 已索引文档列表 |
| DELETE | `/api/v1/documents/{doc_id}` | 删除文档 |
| GET | `/api/v1/graph/{document_id}` | KG 图谱数据 (vis.js) |

## 模块架构 (对齐 rag-engineering-blueprint-v1.0)

```
doc_processor.py    — §2.1 文档处理 (PDF/DOCX/XLSX 多格式解析 + 智能分块)
embedding.py        — §2.2 Embedding (text-embedding-3-small + 缓存 + 归一化)
vector_store.py     — §2.3 向量数据库 (ChromaDB + HNSW + 元数据过滤)
retrieval.py        — §2.4 检索模块 (5步流水线: 预处理→向量化→多路召回→Rerank→过滤)
prompt_builder.py   — §2.5 Prompt 模块 (四段式模板 + Token 预算控制)
generator.py        — §2.6 LLM 生成模块 (答案生成 + 溯源验证 + 兜底策略)
kg_builder.py       — KG 构建 (10类企业实体 + 10种边关系 + schema_version)
worker.py           — 索引 Worker (MinerU→BridgePipeline→LangExtract→KG + DOCX/XLSX本地路由)
```

## 环境要求

- Python 3.12 (uv 虚拟环境)
- `.env` 文件已配置 DeepSeek API Key
- KG 数据位于 `output/kg/` (nodes.json + edges.json)
- ChromaDB 向量数据位于 `output/vectordb/`

## Phase 0 新增模块 (enterprise-evolution-blueprint §3)

```
logging_config.py   — §3.1 结构化日志 (structlog JSON → stdout + 文件轮转)
metrics.py          — §3.2 Prometheus 指标 (Counter/Histogram/Gauge + /metrics 端点)
auth.py             — §3.3 API Key 认证 (SHA-256 哈希 + Bearer Token 中间件)
kg_store.py         — §3.4 KG 版本管理 (v{N}/ 子目录 + versions.json)
```

## 工程规则 (Phase 0 新增，Layer 5)

### 日志规则
- 格式: JSON Lines, 每行一条记录
- 必含字段: `timestamp`, `level`, `logger`, `request_id`, `event`
- 可选字段: `action`, `latency_ms`, `user_id`, `extra`
- 输出: stdout (JSON) + `output/logs/app.log` (滚动, 保留 30 天)
- 禁止: 在日志中输出 API Key / Token / Secret; 禁止 print() 用于业务日志
- request_id: FastAPI 中间件自动生成 UUID4，注入 contextvars

#### 关联字段语义（2026-09-18 补充）
- `request_id`：由 `request_id_middleware` 经 `set_request_id()` 绑定，标识**当前 HTTP 请求**
- `task_id`：由 `run_real_pipeline` 顶部的 `task_scope(task_id)` 绑定，标识**后台入库任务**
- `job_phase="background"`：仅在后台任务上下文中出现。**看到它就意味着同一行里的
  `request_id` 是「入队该任务的请求」的 id，不是当前执行请求的 id** —— 后台任务
  可能跑几分钟，期间原请求早已结束。
- 后台任务**不依赖** contextvars 从请求上下文继承（该继承实测可行但无契约保证，
  且 `server.py` 的 lifespan 恢复路径根本没有请求上下文），一律用 `task_scope` 显式绑定。

#### 脱敏（`redact_sensitive` processor）
- 处理器链顺序**不可调换**：`… → format_exc_info → redact_sensitive → JSONRenderer`。
  `format_exc_info` 必须在前，先把 `exc_info` 元组渲染成 traceback **字符串**，
  再对整条（含 traceback）脱敏；反过来会把 traceback 整条毁掉。
- `format_exc_info` 会 pop 掉 `exc_info` 键并改名为 `exception`，因此**键名规则里
  写 `exc_info` 是死条目**（永远匹配不到）。traceback 的保护靠**值扫描**。
  也**不要**把 `exception` 加进敏感键 —— 那会整条丢弃堆栈，比泄露更糟。
- **字段命名陷阱**：脱敏按**键名含 `token`/`key`/`secret` 等段**整体替换，不看值类型。
  所以 `file_access_token_set=bool(...)` 会被整键替换成 `"[REDACTED]"`，布尔值也读不到。
  需要保留可读性的字段请避开这些词段（例：用 `file_access_enabled`）。
- `[REDACTED]` 的含义是「此处出现了匹配敏感模式的键或值」。深度上限 `_MAX_DEPTH=6`、
  单容器元素上限 `_MAX_ITEMS=200`。

### 错误码规则（2026-09-18 新增）
- 定义在 `backend/errors.py`（**顶层 stdlib-only**，可被 `worker.py` 的同步线程池路径
  与 CLI 脚本复用；FastAPI 相关 import 只在 `register_exception_handlers` 函数体内懒加载）
- 命名：`PIPELINE_<STAGE>_<REASON>`，STAGE ∈ {MINERU, BRIDGE, EXTRACTION, GROUNDING,
  KG_BUILD, PARSE}，REASON ∈ {AUTH, RATE_LIMIT, SERVER, TIMEOUT, PARSE, IO, EMPTY, UNKNOWN}
- **只收录可达组合**（28 个成员 = 25 个 `PIPELINE_*` + 3 个边界码）。不可达成员即
  「惰性豁免」——由 `tests/test_errors.py::test_no_unreachable_error_codes` 拦下
- 新增 provider 必须二选一入表（`_PROVIDER_CODE_MAP` 或 `_PROVIDER_HTTP_ONLY`），
  否则鉴权/限流失败会静默降级为 UNKNOWN
- 外部调用一律走**单一入口** `classify_external_error(exc, *, stage, provider, body_code=)`，
  不要在调用点重复 if/elif 分支
- **注意 MinerU 的错误是 HTTP 200 + body `code != 0`**（负数业务码），
  不走 HTTP 状态码，必须传 `body_code=` 才能识别鉴权失败
- 分层：`PipelineError.message` 是**运维向**（可进日志），`user_message(code)` 是
  **终端用户向**（进响应体）。`PipelineError.__str__` 只返回安全 message
- 顶层边界用 `raise ... from exc` 保留原始 traceback
- HTTP 状态码映射：`_AUTH`→401，`_RATE_LIMIT`→429，边界码 422/503/500，
  其余阶段失败→502（注意 `INTERNAL_ERROR` 字面以 `_ERROR` 结尾，必须**先**判，否则被误映射成 502）
- 异常边界在 `server.py` 的 `register_exception_handlers(app)`（**必须在 `include_router` 之前**），
  响应体 `error` + `detail` **双写**（兼容期），待前端改读 `error.code` 后删 `detail`

### 指标命名规则
- 前缀: `rag_` (所有指标)
- 格式: `rag_{domain}_{metric}_{unit}` 如 `rag_requests_total`, `rag_retrieval_candidates`
- 类型: Counter (累计值), Histogram (延迟/分布), Gauge (瞬时值)
- 标签: `endpoint`, `source` (检索路径), `status` (成功/失败), `error_type`
- 端点: `GET /metrics` (Prometheus 格式, 不含认证)

### API Key 认证规则
- 传输: `Authorization: Bearer <key>` Header
- 存储: SHA-256 哈希存内存, 原文仅 `.env` (`ADMIN_API_KEY=sk-xxx`)
- 白名单: `/health`, `/metrics`, `/docs`, `/redoc`, `/` 免认证
- 错误码: 401 (无 Key), 403 (Key 无效)
- 禁止: API Key 出现在日志/错误信息/响应体中

### KG 版本管理规则
- 路径: `output/kg/doc_{id}/v{1,2,3,...}/nodes.json` + `edges.json`
- versions.json: `{doc_id, versions: [{version, created_at, nodes, edges, status}], active_version}`
- 写入: 新 ingest 自动创建递增版本号, 不覆盖旧版本
- 热重载: 版本切换后 5 秒内 NetworkX 图重新加载
- 清理: 保留所有版本, 手动删除 (未来可配置保留策略)

## Phase 1 新增模块 (enterprise-evolution-blueprint §4 + §10)

```
domain_dict.py          — §10.1 领域词典 (YAML → 内存索引 → Query 改写)
conversation.py         — §10.2 多轮对话会话管理
config/domain_dict.yaml — HSE 种子数据 ~80 条
routes/domain_dict.py   — 领域词典 CRUD
routes/feedback.py      — §4.1 答案反馈端点
services/feedback_store.py — 反馈持久化
services/query_history.py   — 查询记录存储
```

## 工程规则 (Phase 1 新增，Layer 5)

### 领域词典规则
- 格式: YAML, 结构 `term → {synonyms, abbreviations, related, entity_type, category, description}`
- 存储: `backend/config/domain_dict.yaml` (种子数据) + 数据库/JSON (用户自定义)
- 加载: 服务启动时全量加载到内存 dict，修改后热重载 (无需重启)
- Query 展开时机: 检索前 preprocess_query 阶段
  - Layer 1 (同义词): 展开到 query → 增加多 Query 路召回命中率
  - Layer 2 (缩写): 替换为标准术语 → 提升向量检索精度
  - Layer 3 (关联术语): 不展开到 query → 注入 Prompt 上下文提示

### 多轮对话规则
- session_id: UUID4, 由前端生成并传递 (可选，不传则单轮)
- 会话存储: `output/conversations/{session_id}.json`
- 轮次上限: 单会话最多 20 轮 (超限自动截断最早轮次，保留最近 20 轮)
- 超时: `last_active` 距当前超过 30 分钟 → `is_active = False`
- 清理: 非活跃会话保留 7 天后自动删除 (cron)
- 指代消解: 最近 3 轮历史 + 当前问题 → LLM 改写为自包含查询
- 上下文注入: Prompt 中注入最近 3 轮对话摘要 (不超过 800 tokens)

### 反馈规则
- 存储: `output/feedback/{feedback_id}.json`
- 状态机: `open` → `acknowledged` → `resolved`
  - `open`: 用户刚提交, 待处理
  - `acknowledged`: 管理员已查看, 处理中
  - `resolved`: 问题已修复 (KG 已更新 / 答案已修正)
- 关联: feedback 必含 query_id (关联查询记录) + 可选 chunks_cited (用户认为有问题的引用)
- 禁止: 反馈中不存用户答案全文 (可引用 query_history 中的记录)

## Phase 2 新增模块 (enterprise-evolution-blueprint §5)

```
services/lineage_store.py — §5.1 数据血缘 (ingest/retrieval/generation 全链路记录)
routes/lineage.py         — §5.1 血缘查询 API (entity/answer/feedback/conversation/term)
services/catalog.py       — §5.2 数据资产目录 (多维统计聚合 + 趋势 + 质量预警)
routes/catalog.py         — §5.2 资产目录 API
services/kg_exporter.py   — §5.3 格式导出 (JSON/CSV/RDF/Neo4j + 词典/反馈/会话导出)
routes/export.py          — §5.3 导出 API
services/backup.py        — §5.4 备份与容灾 (tar.gz 打包/恢复/验证 + 定时任务)
services/quality.py       — §5.5 数据质量监控 (4维指标 + 自动评分 + 低质量告警)
services/lifecycle.py     — §5.6 数据生命周期 (6类保留策略 + 自动清理 + APScheduler)
routes/system.py          — 系统管理 API (backup/restore/cleanup/storage)
```

## 工程规则 (Phase 2 新增，Layer 5)

### 数据血缘规则
- 存储: `output/lineage/{entity_id}.json` — 每实体一个血缘文件
- 节点类型: document | section | extraction | entity | chunk | retrieval | generation | answer | feedback | domain_expand | conv_turn | kg_version
- 记录时机: ingest 时记录 entity→document 链；query 时记录 retrieval→generation→answer 链；feedback 提交时关联到 answer
- 查询: 支持正向溯源 (entity→document) 和反向溯源 (answer→entity→document)
- 导出: DOT 格式可视化血缘图，最多展示 3 层上下游
- 禁止: 血缘记录不存储 chunk/answer 全文，仅存 ID 引用

### 数据资产目录规则
- 统计维度: documents, entities, edges, chunks, conversations, feedback, domain_terms
- 分类: by_entity_type, by_project, by_category (domain_dict)
- 质量指标: grounded_rate, confidence_avg, entities_without_edges, orphan_entities
- 趋势: 7/30 天滑动窗口，实体增长/查询量/反馈率
- 刷新: 每次请求实时计算 (当前数据量小，未来可加缓存)
- 禁止: 目录不暴露 API Key/Token/用户个人信息

### 格式导出规则
- KG 导出: JSON (原生) / CSV (nodes.csv + edges.csv, UTF-8 BOM) / Neo4j (Cypher CREATE) / RDF (Turtle)
- 词典导出: YAML (原生) / CSV / JSON
- 反馈导出: CSV (含 query_text/answer_text/rating/comment/status)
- 会话导出: ZIP 包 (每会话一个 Markdown 文件)
- 大图导出 (>1000 nodes): 流式响应 (StreamingResponse), 不加载全图到内存
- 禁止: 导出不包含 API Key/Token; CSV 中文必须 UTF-8 BOM

### 备份规则
- 策略: 日备 (保留 7 天) + 周备 (保留 4 周) + 手动即时备份
- 备份范围: kg/ vectordb/ feedback/ conversations/ logs/ docs_store.json tasks_store.json
- 排除: embedding_cache/ (可重算), 超过 7 天的日备, 超过 4 周的周备
- 格式: tar.gz, 含 manifest.json (备份时间/节点数/边数/文件数/校验和)
- 恢复: 恢复前自动创建当前状态快照 (.pre-restore 后缀)
- 定时: APScheduler 集成到 lifespan, 每日 02:00 自动备份
- 禁止: 备份文件中不含 .env 或 API Key

### 数据质量监控规则
- 4维度: 抽取质量 (grounding_rate/confidence) / 检索质量 (path_covers/zero_result) / 用户反馈质量 (positive_ratio/negative_cluster) / 数据新鲜度 (stale_days/stale_entities)
- 指标: Prometheus Gauge + Counter, 每 5 分钟自动计算
- 告警阈值: grounding_rate < 0.5 (warning), positive_ratio < 0.5 (critical), freshness > 30d (warning)
- 前端: QualityDashboard.tsx 展示趋势图 + 低质量文档红色高亮
- 禁止: 质量评分不阻塞正常查询流程 (旁路计算)

### 数据生命周期规则
- 会话: 活跃 30min TTL，非活跃 7 天清理 (有反馈的永久保留)
- 反馈: 永久保留
- KG 旧版本: 最多保留 10 个版本，超出删除最旧非 active 版本
- 查询历史: 90 天 (有反馈关联的保留)
- 日志: 30 天日轮转
- 备份: 日备 7 天，周备 4 周
- 定时: APScheduler 每日 03:00 执行清理
- 预览: cleanup/preview 返回将被清理的数据清单 (dry-run)
- 禁止: 不静默删除数据；清理前必须记录日志 (removed_count + category)

## Phase 3 新增模块 (enterprise-evolution-blueprint §6)

```
services/auth_service.py        — §6.1 SSO/OAuth2/OIDC 集成 + JWT 签发/刷新
middleware/jwt_middleware.py    — §6.1 JWT 验证中间件 (与 auth.py API Key 共存)
routes/auth.py                  — §6.1 登录/回调/刷新/登出/用户管理
services/feishu_client.py       — §6.2 飞书 SDK (token/消息/卡片)
services/bot_handler.py         — §6.2 消息路由 + RAG 调用 + 回复
services/card_builder.py        — §6.2 多平台消息卡片模板
routes/bot.py                   — §6.2 Bot 回调端点
services/event_bus.py           — §6.3 事件发布/订阅 + 异步投递 + 重试
services/webhook_manager.py     — §6.3 Webhook CRUD + HMAC 签名 + 投递追踪
routes/webhooks.py              — §6.3 Webhook 管理端点
services/audit_logger.py        — §6.5 审计日志 JSONL 写入 (按日分文件)
routes/audit.py                 — §6.5 审计查询/导出端点
services/api_key_manager.py     — §6.6 多 API Key 管理 + Scope 配额 + 撤销
routes/api_keys.py              — §6.6 API Key 管理端点
services/health_checker.py      — §6.7 外部依赖定时探活 (apscheduler)
```

## 工程规则 (Phase 3 新增，Layer 5)

### SSO / JWT 认证规则
- 共存: JWT 中间件与现有 API Key 中间件并行，优先级 Cookie > Bearer JWT > Bearer API Key
- JWT 签发: 使用 HS256，密钥存 .env (`JWT_SECRET_KEY` ≥ 32 字符)
- Token 生命周期: access_token 60min，refresh_token 7d
- 用户模型: user_id 来自 SSO `sub` claim，roles 从 OIDC claims 映射
- 权限: admin/editor/viewer 三级，前后端双层校验
- 白名单: `/health`, `/metrics`, `/docs`, `/redoc`, `/`, `/api/v1/auth/login`, `/api/v1/auth/callback` 免认证
- 禁止: JWT 中不存敏感信息 (密码/API Key)；refresh_token 不可用于 API 访问

### 消息 Bot 规则
- 平台: 一期仅飞书，二期扩展钉钉/企微
- 签名: 飞书事件必须验签 (X-Lark-Signature) + 消息体 AES-256-CBC 解密
- 回复: 富文本卡片格式，含 👍👎 按钮回调 Phase 1 反馈系统
- 限流: Bot 请求独立 rate limit (bot_rate_limit)，不计入用户配额
- 错误: Bot 异常不返回内部错误详情，返回通用错误卡片
- 禁止: Bot 响应中不暴露 API Key / 系统内部路径 / 堆栈信息

### Webhook 规则
- 事件: 标准化 WebhookEvent envelope (event_id + event_type + timestamp + data)
- 投递: asyncio 后台 Worker，HTTP POST 超时 10s，失败重试 3 次 (1s→5s→25s→125s 指数退避)
- 签名: HMAC-SHA256 签名 (X-GraphRAG-Signature header)
- 存储: 事件日志写入 output/events/{date}.jsonl (审计追溯)
- 投递追踪: delivery_log 记录每次投递状态 (pending/success/failed)
- 禁止: Webhook 投递不阻塞主请求流程 (fire-and-forget)

### 审计日志规则
- 格式: JSONL，每行一条审计记录，按日分文件 output/audit/audit-{date}.jsonl
- 必含字段: event, user_id, timestamp, ip, user_agent, details
- 事件分类: 认证/数据操作/文档/配置/系统/权限/导出 7 大类
- 保留: 365 天 (lifecycle.py RETENTION_POLICIES 新增 audit 策略)
- 禁止: 审计日志与运维日志混写；审计日志不记录 API Key/Token 明文

### API Key 管理规则
- 前缀: sk-graphrag- (便于识别)
- 存储: SHA-256 哈希，完整 Key 仅创建时返回一次
- Scope: read:query / read:catalog / read:export / write:ingest / write:feedback / write:dict / admin:system / admin:keys
- 限额: 每 Key 可配置 rate_limit_per_minute，默认 60
- 过期: 支持设置 expires_at，过期自动拒绝
- 撤销: revoked=True 后立即失效，不可恢复
- 禁止: 完整 API Key 不出现在日志/响应/审计中

### 健康检查规则
- 端点: GET /api/v1/health (已有)，增强 dependencies 字段
- 探活: APScheduler 每 5 分钟执行 DeepSeek/MinerU/ChromaDB/OAuth2/飞书 探活
- 状态: healthy (全绿) / degraded (1-2 异常) / unhealthy (核心依赖异常)
- 禁止: 健康检查响应中不暴露 API Key / 内部 IP / 端口信息

## Phase 4 新增模块 (enterprise-evolution-blueprint §7)

```
services/tenant_service.py         — §7.1 多租户 (Organization/Project CRUD + 成员管理)
middleware/tenant_middleware.py    — §7.1 租户上下文注入 (X-Project-Id → request.state.tenant)
routes/tenants.py                  — §7.1 组织/项目管理端点 (12 endpoints)
Dockerfile.backend                 — §7.2 FastAPI 容器 (Python 3.12-slim)
Dockerfile.frontend                — §7.2 Nginx + React 多阶段构建
docker-compose.yml                 — §7.2 6 服务编排 (根目录)
deploy/nginx/default.conf          — §7.2 Nginx SPA + API 反向代理
.github/workflows/ci.yml           — §7.3 GitHub Actions CI 流水线
deploy/cd-deploy.sh                — §7.3 CD 部署脚本 + 健康检查等待
```

## 工程规则 (Phase 4 新增，Layer 5)

### 多租户隔离规则
- 数据隔离: KG 图按 project_id 独立 NetworkX graph；向量按 `{org_id}_{project_id}` 命名 ChromaDB collection
- 存储路径: `output/kg/{org_id}/{project_id}/doc_{task_id}/v{N}/`
- 上下文注入: tenant_middleware 从 X-Project-Id Header 解析，注入 `request.state.tenant`
- 默认行为: 非 admin 用户不带 X-Project-Id → 自动限定默认项目；admin 不带 → 跨项目
- 白名单: `/`, `/docs`, `/health`, `/metrics`, `/api/v1/auth/*`, `/api/v1/bot/feishu` 跳过租户检查
- 权限: org_admin 可管理成员/创建项目；org_editor 可上传/查询；org_viewer 只读
- 禁止: 跨组织数据泄露；未指定 project_id 的非 admin 查询返回跨项目数据

### 容器化规则
- 基础镜像: backend=python:3.12-slim, frontend=node:20-alpine→nginx:1.27-alpine
- 健康检查: 所有容器必须有 HEALTHCHECK (backend: curl /health, frontend: wget /)
- 数据卷: graphrag_data (KG/向量/反馈/审计), chromadb_data (ChromaDB 持久化)
- 环境变量: 仅通过 .env 文件注入，不在 Dockerfile 中硬编码
- 用户: 生产容器以非 root 运行 (USER 1000)
- 端口: backend=8000, frontend=80, chromadb=8000(内部), prometheus=9090, grafana=3000
- 禁止: 在镜像中打包 .env / .venv / node_modules / output / .git

### CI/CD 规则
- 触发: push 到 master/develop 或 PR 到 master
- 阶段顺序: lint → test → build-and-push (不可跳过)
- Lint: backend=ruff, frontend=eslint (non-blocking)
- Test: backend=pytest (需 ChromaDB service container), frontend=tsc --noEmit
- 构建: Docker 多阶段构建，tag 用 git SHA，推送 ghcr.io
- 部署: CD 脚本 pull 镜像 → docker-compose up -d → 等待 health check OK (最多 60s)
- 禁止: 测试失败后继续构建；跳过 lint 直接 test

### 安全加固规则
- 非 root: 所有容器 USER 1000 (backend) / USER nginx (frontend)
- 密钥: JWT_SECRET_KEY 生产环境 ≥ 64 字符随机值，不硬编码
- CORS: 生产环境 allow_origins 锁定为具体域名列表，禁用 *
- 依赖扫描: CI 中 `pip-audit` (Python) + `pnpm audit` (Node)
- 镜像扫描: CI build 后 `docker scan` 或 `trivy`
- 禁止: .env 提交 git；Docker 镜像包含 .env 或 API Key；容器以 root 运行
