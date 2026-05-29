# 后端修复计划 v1.0

> 基于 chatbot-reviewer 后端审查结果

## Issue 统计: 3 Critical · 10 High · 10 Medium · 5 Low

---

## Phase 0: 安全与泄露 (P0)

### #1 API Key 明文泄露 — `.env:6,16`
- **改**: 移除真实 Key，创建 `.env.example` 模板占位，立即轮换泄露的 Key
- **文件**: `.env`, **新建** `.env.example`

### #2 CORS 配置错误 — `server.py:36`
- **改**: `allow_credentials=True` → `False`，或 `allow_origins` 改为具体列表
- **文件**: `server.py`

### #3 路径遍历漏洞 — `documents.py:61`
- **改**: `FileResponse(filepath)` 前用 `os.path.realpath()` 校验路径在 `UPLOADS_DIR` 内
- **文件**: `documents.py`

---

## Phase 1: 线程安全与逻辑缺陷 (P1)

| # | 问题 | 文件 | 改动 |
|---|---|---|---|
| 4 | query_count 非原子 | `query.py:178`, `__init__.py` | `threading.Lock` 保护 increment |
| 5 | _docs_store 读无锁 | `documents.py:14`, `graph.py:28` | 暴露 `get_docs_snapshot()` 加锁读 |
| 6 | FILE_URL 静默丢弃上传 | `ingest.py:129` | 用户上传文件时忽略 FILE_URL，或返回 409 |
| 7 | reload_kg() 竞态 | `query.py:84` | 先构造新 KG → 再原子交换全局引用 |
| 8 | 上传大小不一致 | `server.py:33` vs `models.py:27` | 统一为 200MB，提取到 `config.py` |
| 9 | fromisoformat("Z") 不兼容 | `documents.py:55` | Z → +00:00 兼容 Python <3.11 |
| 10 | 空 KG 图 truthy | `query.py:196` | `G_grounded.number_of_nodes() > 0` |
| 11 | Health 全硬编码 ok | `health.py:61` | 检查 Token 是否配置，返回 `degraded` |
| 12 | except:pass 吞诊断 | `worker.py:148+` | 改为 `logger.warning(f"...: {e}")` |
| 13 | _agent 无锁 | `query.py:150` | 双重检查锁 |

---

## Phase 2: 性能与代码质量 (P2)

| # | 问题 | 改动 |
|---|---|---|
| 14 | HTTPException 函数内 import | 移到 top-level |
| 15 | PositionMap O(n) → O(log n) | 二分查找 `bisect` |
| 16 | BASE_DIR 重复5处 | 新建 `config.py` 统一路径 |
| 17 | _tasks 内存重启丢失 | 持久化 `output/tasks_store.json` |
| 18 | _get_model 每次 load_dotenv | 移到模块级一次调用 |
| 19 | _count_kg_nodes 可能重复计数 | 子目录存在时跳过默认 KG |
| 20 | 边缺 key 静默跳过 | 加 `logger.warning` |
| 21 | _tasks[id] 可能 KeyError | `.get()` 防御 |
| 22 | _item_to_text 重复分支 | 删除 L91 不可达 `page_number` 分支 |
| 23 | subprocess 超时被吞 | 单独 catch `TimeoutExpired` |

---

## Phase 3: 架构增强 (P3)

| # | 改动 |
|---|---|
| 24 | `print()` → `logging` 结构化日志 |
| 25 | 路由中业务逻辑 → `services/` 层 |
| 26 | 类型注解统一为 `X \| None` (PEP 604) |
| 27 | `language` 参数传递到 MinerU API |
| 28 | KG 文件增加 `schema_version` 字段 |

---

## 新建文件清单

| 文件 | Phase |
|---|---|
| `.env.example` | P0 |
| `config.py` | P2 |
| `services/kg_service.py` | P3 |
| `services/agent_service.py` | P3 |
| `services/ingest_service.py` | P3 |

### 预估工时: 14 小时 (P0:1h + P1:4h + P2:3h + P3:6h)
