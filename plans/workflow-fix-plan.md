# 项目工作流修复计划 v1.0

> 基于 chatbot-reviewer 全项目流程审查 + 前后端联调审查结果

## Issue 统计: 4 Blocker · 6 High · 7 Medium · 4 Low

---

## Phase 0: 阻断性修复 (P0) — 必须立即解决

### B1: 后端 FastAPI 服务未构建
- **现状**: `backend/` 下 `server.py`/`models.py` 等缺失，无法启动 Web 服务
- **解决**: 按 `backend-api-architecture-v1.0.md` 实现 `server.py` + routes + models
- **文件**: 新建 `server.py`, `models.py`, `routes/*.py`

### B2: 前端 dist/ 不存在
- **现状**: 前端从未构建，`dist/` 目录不存在，TypeScript 编译未经验证
- **解决**: 执行 `npm install && npm run build`
- **文件**: `frontend/`

### B3: 根目录缺少 .gitignore
- **现状**: `integration/.env` 含真实 Key，若从根目录初始化 git 会泄露
- **解决**: 创建根 `.gitignore`，覆盖 `.env`, `.venv/`, `__pycache__/`, `node_modules/`, `dist/`, `output/`
- **文件**: 新建 `.gitignore`

### B4: API Key 硬编码泄露
- **现状**: `agentic_rag_mvp.py:36` + `integration/.env` 含真实 Key
- **解决**: 从源码移除，移到 `.env` 并通过环境变量读取。立即轮换 Key
- **文件**: `agentic_rag_mvp.py`, `integration/.env`

---

## Phase 1: 架构对齐 (P1)

| # | 问题 | 解决 |
|---|---|---|
| H1 | 核心逻辑在 integration/ 而非 backend/ | 将 `pipeline.py` 重构为可导入模块 (抽取 `run_pipeline()` 函数) |
| H2 | 前端缺 Vite index.html | 创建 `frontend/index.html` 含 `<div id="root">` + `<script type="module" src="/src/main.tsx">` |
| H3 | `langextract/.gitignore` 错误排除 CLAUDE.md | 从该 `.gitignore` 移除 `CLAUDE.md` 行 (L110) |
| H4 | MinerU 解析结果重复存储 | 统一缓存到 `data/mineru-cache/` |
| H5 | 前端未运行 tsc 类型检查 | `npx tsc --noEmit` 修复所有类型错误 |
| H6 | docs_store.json 不存在 | 实现文档索引注册表，与服务启动时创建 |

---

## Phase 2: 流程优化 (P2)

| # | 问题 | 解决 |
|---|---|---|
| M1 | Zustand Store 与设计偏离 | 按 `frontend-system-design-v1.0.md` 拆分为 4 个独立 store |
| M2 | integration/ 无测试 | 为 bridge.py + grounding.py 添加单元测试 |
| M3 | ENTITY_TYPES 硬编码 | 从后端 stats API 动态获取 |
| M4 | API 类型定义与后端规范不一致 | 与 Pydantic 模型逐字段对齐 |
| M5 | pipeline.py 是 CLI 不可被 import | 抽取 `run_pipeline()` 可调用函数 |
| M6 | agentic_rag_mvp.py 路径硬编码 | 参数化 nodes_path/edges_path/api_key |
| M7 | vis.js 用 `declare const vis: any` | 改为 `import { Network } from 'vis-network'` |

---

## Phase 3: 规范完善 (P3)

| # | 问题 | 解决 |
|---|---|---|
| L1 | 配色不一致 (PRD vs 原型 vs React) | 统一到 PRD §5.2 配色表 |
| L2 | 缺 .env.example 模板 | 为 frontend/backend 创建 |
| L3 | GraphPage API 端点未定义 | 后端新增 `/api/v1/graph/all` 或前端改用已有端点 |
| L4 | visualizer.html 与 GraphPage 功能重复 | 保留 visualizer.html 为独立 demo，React GraphPage 为主要实现 |

---

## 联调专项: 前后端接口一致性

| # | 问题 | 后端 | 前端 |
|---|---|---|---|
| I-1 | ingest() 错误丢弃后端详情 | 返回 `{"detail": "..."}` | 解析 JSON error body |
| I-2 | 轮询 catch 为空 | — | 加失败计数器 + 上限 |
| I-3 | 字体 CDN 国内不可达 | — | `tailwind.config` 加中文字体 fallback |
| I-4 | `/graph/all` 端点不存在 | 新增端点 | — |
| I-5 | CORS 配置违反规范 | `allow_credentials=False` | — |
| I-6 | 下载 MIME 类型写死 | 按扩展名设置 MIME | — |
| I-7 | Upload 大小不一致 | 统一 200MB | — |

---

## 执行优先级

```
P0 阻断 → P1 架构对齐 → P2 流程优化 → P3 规范完善
```

### 预估总工时: 5-7 天

| Phase | 工时 |
|---|---|
| P0 | 1.5 天 |
| P1 | 2 天 |
| P2 | 2 天 |
| P3 | 1 天 |
