# Widget 与上传异步生命周期修复验证

本轮关闭前端独立审查的两个 High（来源 HTML 注入、正式 public 脚本漏入覆盖分母）及上传生命周期 Medium。采用默认 Superpowers 维护流程，未启用 goal/Harness；本报告只证明前端最终快照，不代替后端、评测工具或全项目验收。未读取 `.env`、调用真实供应商、修改研究冻结或用户 output，未提交、推送或部署。

## 修复及契约

- `frontend/public/chat-widget.js`：通用 `createElement` 字符串 children 使用 `textContent`。全部调用点已核对：标题、欢迎语、来源 label/type、按钮、样式均按文本赋值；数组 children 继续追加 DOM。明确保留两个 HTML 边界：先转义 API 文本的 `renderMarkdown` 输出，以及纯静态 loading 模板。没有新增可接收外部 HTML 的通用入口。
- `frontend/src/pages/UploadPage.tsx`：由 `[taskId,status]` effect 独占轮询计时器，cleanup 标记 active=false；每个响应在修改共享 store 前核对当前任务和 indexing 状态。单任务最多一个在途轮询请求。ingest 代次、挂载状态、提交时 file/task 身份检查阻止卸载、重置、替换文件或重复提交后的晚到响应污染现任务。返回页面仍恢复 store 中正在进行的任务；没有取消已提交后端任务。
- `frontend/vitest.config.ts`：固定生产范围扩为 `src/**/*.{ts,tsx}` 与 `public/**/*.js`，实际 29 文件，包含全部 28 src 文件和正式 widget IIFE；保留类型擦除文件、入口及未导入代码。没有减少分母、ignore/skip 或降低阈值。

协调者需将上述契约回流对应有效前端/widget规范。历史原型不在当前 Vite dist 中，范围分类沿用独立评审；构建确认 `dist/chat-widget.js` 与 public 源 SHA256 一致。

## 红绿与行为证据

新测试拥有实际 DOM/API 行为断言，原 104 项测试未删除或削弱。最初实际运行 108 项：104 pass、4 fail，见 [红测日志](frontend-widget-upload-20261013/widget-upload-red.log)。失败分别为未转义标题变成 img 后文本丢失、卸载后 ingest 创建隐藏 poller、旧成功响应令新任务变 done、旧错误响应仍轮询旧 task。命令中 vitest 的实际失败为 exit1；当时 PowerShell 包装随后 `Get-Content` 导致包装进程 exit0，不把包装码当测试通过。此前独立评审已真实复现来源 label 的 img/onerror sink，本轮完整 payload 断言同时覆盖 label、type、答案和标题。

最小源修后 4 专项通过。最终新增 18 项（合计 122）：真实 shipped IIFE 动态 import、恶意 title/answer/source label/type、Markdown 多种结构及转义、面板/键盘/输入 resize/空问/loading 并发保护、session 连续性、组织项目 header、双向反馈/重复反馈/缺 query_id、网络/HTTP/detail/无 JSON/空错误后的重试；deferred Promise 覆盖卸载 ingest、在途轮询 success/error、新任务替换、reset、重复 ingest、文件替换与返回恢复。原 API token 刷新重试及清理测试保持执行。边界 fixture 不等同真实后端或供应商集成。

## 最终快照与实际命令

分支 master，HEAD `46b202c3e400741fd569f024412c0745f224a538`，工作区包含其他任务改动，本轮没有清理或回退它们。隔离 Node 22.23.3 PATH 前置 `.tmp/node22-runtime/node-v22.23.3-win-x64`，pnpm 10.33.3。普通沙箱访问 node_modules realpath 出现 EPERM；通过工具自动审批后执行适用命令，不绕过产品测试。

53 项最终输入 [manifest](frontend-widget-upload-20261013/input-manifest.json) SHA256：`88e7356ceefccf79fa1fb9b8f11110cb11b66ea8d41faab2c5a3cc0182a0356d`；覆盖完成后逐项 hash 复核 drift=0。机器汇总见 [final-summary.json](frontend-widget-upload-20261013/final-summary.json)。

| 在 frontend 执行的命令 | 退出码 | 结果及证据 |
|---|---:|---|
| `pnpm.cmd test:coverage --coverage.reportsDirectory=../docs/testing/frontend-widget-upload-20261013/coverage` | 0 | 2026-10-13 20:07:36 开始，90.38 秒；9 文件/122 passed/0 failed/0 skipped，[日志](frontend-widget-upload-20261013/coverage.log) |
| `pnpm.cmd build` | 0 | tsc＋Vite，1869 modules，[日志](frontend-widget-upload-20261013/frontend-widget-build.log) |
| `pnpm.cmd install --frozen-lockfile --ignore-scripts` | 0 | 锁文件无需变更、already up to date，[日志](frontend-widget-upload-20261013/frontend-widget-frozen.log) |
| `pnpm.cmd audit --registry=https://registry.npmjs.org --json` | 0 | 345 dependencies，各严重度 0、advisories/actions/muted 空，[JSON](frontend-widget-upload-20261013/frontend-widget-audit.json) |
| `python .../with_server.py --server 'pnpm.cmd exec vite preview --host 127.0.0.1 --port 4175' --port 4175 -- python tests/browser_compatibility.py` | 0 | 真实 Chromium 桌面 32px/900px、移动16px/导航、文档表格、查询 Markdown/来源详情，[日志](frontend-widget-upload-20261013/frontend-widget-browser.log)、[回执](frontend-browser-20261013/receipt.json) |
| 同上 server＋`python tests/widget_browser.py` | 0 | 真实 dist/widget，恶意 answer/label/type 无 img，window.pwn undefined，引用展开/反馈，[日志](frontend-widget-upload-20261013/frontend-widget-security-browser.log)、[回执](frontend-widget-browser-20261013/receipt.json) |

浏览器夹具初次运行因启动 React GET 无 request body 导致测试自身 NoneType.get 失败，已用仅收集 POST 修正；以 expect_request 替代固定等待后复跑 exit0。没有通过改生产行为掩盖该夹具错误。最终 Vitest 七条 jsdom navigation Not implemented 输出保留于日志，真实 Chromium对应导航另有实际断言。

全前端原始行覆盖 **927/957 = 96.8652037618%**，分支 **853/913 = 93.4282584885%**；两项原始计数均满足 90%，不使用四舍五入跨线。机器证据：[coverage-summary](frontend-widget-upload-20261013/coverage/coverage-summary.json)、[coverage-final](frontend-widget-upload-20261013/coverage/coverage-final.json)、[lcov](frontend-widget-upload-20261013/coverage/lcov.info)。widget 单文件行 99.28%、分支94.18%；子项目门槛是固定全部生产文件两项合计，并非声称每个文件均90%。

关键源 SHA256：widget `1c5600bfa3264bd316c6dbcc034decf49b264737de218be96dfed827d7372055`；UploadPage `50e3c5077f7710752b1ea5e507904b8acf3a6e3842d1062b24dbe8fc1a5e33ce`；vitest配置 `cfb61202010cf0b631eeb9b05c367d358f66811c3d90ce27185f206852b75c87`。

仍需协调者的独立复审及全项目门槛合并；Windows 为 `audit-only-windows`，不宣称 CI/分支保护已启用或整体交付完成。memory 由根协调者统一更新。
