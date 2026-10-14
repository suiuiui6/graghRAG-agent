# 前端覆盖率、安全与兼容性验证

时间：2026-10-13 13:36 +08:00。基线 `46b202c3e400741fd569f024412c0745f224a538`，工作区未提交。执行环境 Node **22.23.3**（仓库 `.tmp/node22-runtime` 官方运行时）、pnpm **10.33.3**；依赖使用 `frontend/pnpm-lock.yaml`，`.nvmrc` 为22。默认维护流程，未操作 goal/Harness 状态、真实供应商 API、`.env` 或用户 output；无 commit/push/deploy。

## 最终结果与快照

Vite React 应用完整 `src/**/*.{ts,tsx}` 范围，行 **775/807 = 96.03469640644362%**，分支 **753/816 = 92.27941176470588%**，分别超过90%。**7个测试文件、104项通过、0失败、0跳过**；不是逐文件90%，例如GraphPage/UploadPage仍有未覆盖分支。统计依据是原始计数，不使用四舍五入跨门槛。

[机器汇总](2026-10-13-frontend-final-summary.json)、[前输入](2026-10-13-frontend-input-before.json)、[后输入](2026-10-13-frontend-input-after.json)保存生产代码、测试、配置与锁等50项输入，前后漂移0；输入清单 SHA256 为 `31cda57eb6d0845a6a1645b4d6dd8cd6903f942c34acf322eeef11edb164fabe`。独立枚举28个生产TS/TSX，与coverage JSON文件集合精确一致，缺失0、额外0。原先“30个生产文件”为估计，实际29个TS/TSX中1个为既有 `queryContract.test.ts` 测试，生产28个。纯类型 `types.ts` 保留在范围，擦除后自然0计数；`main.tsx`、`App.tsx` 均真实执行，不排入口。

原始产物：[coverage-final.json](../../frontend/coverage/coverage-final.json)、[coverage-summary.json](../../frontend/coverage/coverage-summary.json)、[lcov.info](../../frontend/coverage/lcov.info)。汇总保存前两项SHA256。只排除测试源，不添加ignore/skip、不改阈值、不删业务文件。原有查询契约脚本另行编译执行，未因其不使用Vitest API而丢失验证。

## 改动与行为断言

- 新增Vitest/v8、jsdom与Testing Library，7组测试覆盖API请求/令牌刷新/错误恢复、权限与路由、Zustand状态、上传/文档/查询/健康/质量/目录、实体与血缘/图谱、管理页面、真实React入口。网络与图谱引擎等外部边界替代，组件与API封装使用实际实现；这些不是后端真实依赖集成证明。
- AppShell原来在认证分支内重复调用store Hook，匿名→登录会破坏Hook顺序。红测保留在[初轮日志](2026-10-13-frontend-red.log)，最小改为顶层单次订阅；最终测试验证匿名→登录→退出。
- GraphPage网络初始化effect原来仅依赖data，图谱引擎就绪或从结构化视图返回时不重建网络。增加visReady/viewMode依赖；断言网络创建、销毁、返回后创建及节点聚焦，原失败同见初轮日志。jsdom使用受控vis实现，未声称真实vis CDN故障已验收。
- UploadPage原来卸载不清除轮询。本人红测离开页面后getStatus期望1次实际3次（[复现日志](2026-10-13-frontend-upload-red-recheck.log)，exit1；先前同症状[记录](2026-10-13-frontend-upload-red.log)亦保留），加入effect cleanup后[同用例通过](2026-10-13-frontend-upload-green.log)，回到页面仅建一个新计时器。未改变后台任务持久状态或取消后台任务。
- Tailwind4迁移后未分层的全局reset覆盖工具类，桌面p-8实得0px。[本人浏览器复现](2026-10-13-frontend-browser-red-recheck.log) exit1；将原reset移至base层，保留preflight、旧边框/占位符/按钮默认值及原主题；没有删改间距断言。最终真实Chromium[日志](2026-10-13-frontend-browser-green.log) exit0、[回执](frontend-browser-20261013/receipt.json)：桌面32px/900px、移动16px与侧栏/底部导航、Inter字体、原主题和圆角、文档表格、问答Markdown表格及溯源，无pageerror。截图保存在同目录。这些场景使用本地API夹具，不访问后端/供应商。

## 依赖迁移

按安全整改升级react-router-dom到7.18.4（仍使用React18声明式路由），Tailwind到4.3.3，PostCSS改官方 `@tailwindcss/postcss` 插件，CSS使用import及原JS配置。锁定Vite6.4.4、React18.3.1、Vitest5.0.4等，删除旧npm lock，统一pnpm。`frontend/CLAUDE.md`启动命令同步为pnpm。

兼容验证包含真实应用`/`重定向、query/graph可选document参数、未知路由、认证变化、Markdown、桌面/移动布局；build通过不替代浏览器验证。官方npm audit对完整锁依赖 **345项、0公告、muted为空**，未force或ignore。默认npmmirror无audit endpoint（[原始错误](2026-10-13-frontend-audit-final.json)，exit1），随后明确指定官方registry成功，不把镜像错误当0漏洞。

## 实际命令与退出码

均在`frontend/`，先将上述Node22目录加入PATH。以下为CSS修复之后的最终执行，不复用修复前报告：

| 命令 | 退出码 | 证据 |
|---|---:|---|
| `pnpm install --frozen-lockfile --offline` | 0 | [锁定安装](2026-10-13-frontend-install-final.log) |
| `pnpm test:coverage` | 0 | [全量104通过](2026-10-13-frontend-coverage-final.log) |
| `pnpm build` | 0 | [tsc与Vite生产构建](2026-10-13-frontend-build-final.log) |
| `pnpm audit --registry=https://registry.npmjs.org --json` | 0 | [官方完整审计](2026-10-13-frontend-audit-official-final.json) |
| `pnpm exec tsc src/lib/queryContract.test.ts --outDir ../.tmp/frontend-contract-final --module commonjs --target ES2020 --skipLibCheck`，随后 `node ../.tmp/frontend-contract-final/queryContract.test.js` | 0 / 0 | [原有契约退出码](2026-10-13-frontend-contract-final.exit.json)，源未变 |
| `python C:/Users/14156/.agents/skills/webapp-testing/scripts/with_server.py --server 'pnpm.cmd exec vite preview --host 127.0.0.1 --port 4175' --port 4175 -- python tests/browser_compatibility.py` | 0 | [最终浏览器日志](2026-10-13-frontend-browser-green.log) |
| `git diff --check -- frontend` | 0 | 只有LF→CRLF提示，无空白错误 |

全量日志7条jsdom“Not implemented: navigation to another Document”是其location导航能力边界；未吞掉输出，不据此声称浏览器整页导航已由jsdom完成。真实浏览器验证覆盖上述页面和布局场景，非全流程真实API验收。

## 边界与交接

本报告证明预先约定Vite应用src生产TS/TSX28文件双指标、锁定安装、构建、官方依赖审计和列举浏览器场景通过。独立历史`visualizer.html`及`prototype/`不在Vite src构建范围，未给其内联脚本测运行覆盖；CSS/HTML亦不计TS/TSX行分母，兼容性通过实际浏览器断言补证。全项目可执行子项目的完整范围与独立审查、其余子项目验收由协调者统一收口，不据本报告无条件宣称整个仓库达标。独立reviewer及协调者浏览器验收结果待关联；当前Windows仍audit-only-windows，未宣称可信CI/保护分支生效。
