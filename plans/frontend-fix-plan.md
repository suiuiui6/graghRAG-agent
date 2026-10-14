# 前端修复计划 v1.0

> 基于 chatbot-reviewer 前端审查 + 前后端联调审查结果

## Issue 统计: 3 Critical · 8 High · 7 Medium · 4 Low

---

## Phase 0: 关键修复 (P0)

### #1 XSS 漏洞 — QueryPage.tsx:58
- **改**: 删除 `renderMarkdown()` + `dangerouslySetInnerHTML`，用已安装的 `react-markdown` + `remark-gfm` 替代
- **文件**: `QueryPage.tsx`

### #2 侧边栏统计硬编码 — AppShell.tsx:9
- **改**: 新增 `api.getStats()` → store → AppShell 动态读取
- **文件**: `AppShell.tsx`, `useAppStore.ts`, `api.ts`

### #3 vis-network 双重加载
- **改**: 从 `index.html` 移除 CDN script，从 `package.json` 移除 vis-network npm 包。保留 CDN 作为 GraphPage 唯一加载方式。若 CDN 加载失败，显示错误提示而非空白页。
- **文件**: `index.html`, `GraphPage.tsx`, `package.json`

---

## Phase 1: 功能缺陷 (P1)

| # | 问题 | 文件 | 改动 |
|---|---|---|---|
| 4 | TYPE_COLORS 重复定义 | `QueryPage.tsx`, `constants.ts` | QueryPage 从 constants 导入 |
| 5 | 下载/预览按钮同URL | `DocumentsPage.tsx` | 预览改为 `<Link to={/preview/\${docId}}>`，或移除预览 |
| 6 | 首次加载错误不显示 | `DocumentsPage.tsx:15` | 移除 `if (!loading)` 条件 |
| 7 | `<a href>` 替代 `<Link>` | `UploadPage.tsx`, `DocumentsPage.tsx` | 全部改为 `<Link to>` |
| 8 | useAppStore 全量订阅 | `AppShell.tsx`, `DocumentsPage.tsx` | 改为 selector 写法 |
| 9 | 移动端缺少 HealthPage | `AppShell.tsx:64` | 移除 `.slice(0,4)` |
| 10 | GraphPage 用原始 fetch | `GraphPage.tsx`, `api.ts` | `api.ts` 新增 `getGraphAll()` |
| 11 | useRef 类型不精确 | `UploadPage.tsx`, `GraphPage.tsx` | `useRef<Type \| null>(null)` |

---

## Phase 2: 代码质量 (P2)

| # | 问题 | 改动 |
|---|---|---|
| 12 | `any` 类型滥用 | 定义 `SourceItem`/`GraphNode`/`GraphEdge` 接口 |
| 13 | 缺少 404 路由 | 新建 `NotFoundPage.tsx` |
| 14 | docId 路由参数未消费 | `useParams()` 读取并传入 `api.ask()` |
| 15 | 欢迎消息硬编码 | 从 store 读取当前文档名 |
| 16 | CDN 无降级 | 随 #3 解决 |
| 17 | ENTITY_TYPES 硬编码 | 从 health/stats API 动态获取 |
| 18 | alert() 代替 toast | 改用 `toast.error()` (sonner 已安装) |

---

## Phase 3: 架构增强 (P3)

- **A**: 提取共享组件 (LoadingSpinner/ErrorBlock/EmptyState/StatBox)
- **B**: `React.lazy()` 代码分割 5 个页面 + `<Suspense>`
- **C**: `<ErrorBoundary>` 根级包裹
- **D**: Vite proxy 增加 `VITE_API_BASE_URL` 环境变量

---

## 联调专项修复

| # | 问题 | 改动 |
|---|---|---|
| I-1 | 轮询 catch 为空 → 永远卡住 | `UploadPage.tsx` 增加失败计数器 + 10次上限 |
| I-2 | ingest() 错误丢失后端详情 | `api.ts` 解析后端 JSON error body |
| I-3 | 字体 CDN 国内不可达 | `tailwind.config` 增加中文字体 fallback |
| I-4 | `query_count` 非线程安全 | 后端加 `threading.Lock` |
| I-5 | CORS 配置违反规范 | `server.py` 移除 `allow_credentials=True` |

### 预估工时: 8-9 小时
