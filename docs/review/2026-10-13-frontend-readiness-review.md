# 前端与生产范围独立审查（2026-10-13）

审查总结：Vite React 应用升级及已列出的局部修复在当前快照通过独立测试、构建和依赖审计。发现正式发布的独立 widget 被遗漏于覆盖范围，并在该脚本复现来源 HTML 注入；因此不能以 backend 90 文件＋Vite 28 文件宣称完整第一方生产范围通过。问题统计：Critical 0、High 2、Medium 1；另有其他子项目分类/验收待补。

本审查使用默认项目维护流程，未启用 goal/Harness，未改生产、测试、配置、memory、冻结、凭据或用户 output；仅拥有本报告。已读根 AGENTS、memory/index 与今日记录、测试规范、前端 readiness/final-summary、配置、源码和新增测试。using-superpowers 的 SUBAGENT-STOP 对受派子任务适用；采用 verification-before-completion 的实际证据要求。不将网络边界替代称为真实供应商/后端集成。

## High

### 1. 来源标签产生可执行 HTML

🟠 High — `frontend/public/chat-widget.js:150–163,580–585`

`addSources` 把 API `sources[].label`、`entity_type` 拼接为字符串传入通用 `createElement`，后者赋给 `innerHTML`。来源内容可能来自文档或抽取输出，嵌入页面会接受这些内容生成的 DOM。独立真实脚本 jsdom probe 用 `<img src=x onerror="window.pwn=1">` 作 label，获得 `.source-label img` 且 `onerror` 原样保留。jsdom 的 outside-only 模式未执行事件处理器，已确认危险 DOM sink，不冒称浏览器事件已触发。Shadow DOM 不构成脚本安全边界。

优化建议：通用字符串 children 使用 `textContent`，必须渲染的静态图标/已转义 Markdown 单独明确处理；补真实 widget 的恶意 label/type、答案转义、失败后重试测试。

```js
// before
if (typeof children === 'string') el.innerHTML = children;
// after（同时复核所有静态 HTML 调用者）
if (typeof children === 'string') el.textContent = children;
```

### 2. Vite 发布的第一方 JS 未进入全生产分母

🟠 High — `frontend/vitest.config.ts:12–13`；`Dockerfile.frontend:24`、`Dockerfile.backend:31–32`；`backend/routes/static.py:12–21`

当前 include 仅 `src/**/*.{ts,tsx}`。但 `frontend/public/chat-widget.js` 是第一方正式功能，独立构建后的 `frontend/dist/chat-widget.js` 确实存在，Nginx 镜像复制完整 dist，后端镜像还显式复制并由公开 `/static/chat-widget.js` 服务。企业演进蓝图约3196行将它定义为 Engine-Vue 集成组件，不能按历史样例/第三方排除。React `src/components/ChatWidget.tsx` 的测试没有执行这个 IIFE，不能共享覆盖率结论。

优化建议：预先固定前端生产范围，纳入 public 第一方 JS，补独立脚本行为覆盖并重算行/分支原始计数；或以有明确契约的独立可执行子项目分别测量，不能省略。

```ts
// before
include: ['src/**/*.{ts,tsx}']
// after（在正式范围盘点与测试落地后）
include: ['src/**/*.{ts,tsx}', 'public/**/*.js']
```

## Medium

### 3. 上传卸载 cleanup 仍不能约束已经发出的异步请求

🟡 Medium — `frontend/src/pages/UploadPage.tsx:26–57,64–67,84–87`

本轮 cleanup 正确停止现有 interval，现有回归验证离开后不再发请求。但若 `ingest` 尚未 resolve 时导航离开，cleanup 此刻没有 timer；随后 handleUpload/handleUrlUpload 仍会执行 `pollTask`，在已卸载组件建立新 interval。已发出的 getStatus 也没有生命周期/任务代次检查，可能在卸载或重置后覆盖全局上传状态。现有测试只覆盖同步完成 ingest 和已经创建 timer 的卸载，未覆盖这一时序。

优化建议：把计时器生命周期由 taskId/status 驱动的 effect 管理，清理时标记失效；晚到响应在更新全局状态前检查当前任务/代次，或明确实现可取消请求。此项为源码时序分析，未额外新建测试冒称已复现。

```ts
// before: 请求完成后无条件启动组件计时器
const resp = await api.ingest(fd)
startUpload(resp)
pollTask(resp.task_id)
// after: 请求可写入任务登记，组件 effect 负责计时器
const resp = await api.ingest(fd)
startUpload(resp)
// useEffect([taskId, status]) 创建/清理轮询，并检查失效标志
```

## 独立执行证据与测试质量

环境 Node 22.23.3、pnpm 10.33.3。普通沙箱运行 pnpm 因 node_modules realpath EPERM 失败（exit1），获准后复跑。实际命令在 frontend，PATH 前置 `.tmp/node22-runtime/node-v22.23.3-win-x64`：

- `pnpm.cmd test:coverage --coverage.reportsDirectory=../.tmp/frontend-independent-review-coverage`：7文件/104通过/0失败/0跳过；JSON 原始行775/807=96.0346964064%，分支753/816=92.2794117647%。独立报告写 .tmp，未覆盖原作者报告。
- `pnpm.cmd build`：tsc/Vite 成功，1869 modules；dist 同时含正式 widget。
- `pnpm.cmd audit --registry=https://registry.npmjs.org --json`：345依赖、advisories/actions/muted均空、所有严重度0。上述顺序命令最终进程 exit0，各工具输出均成功；未给每项另造退出码文件。
- 原作者50项前输入清单逐项 SHA256 对当前文件比较：drift0。独立覆盖文件集合/原始计数与原报告一致；types.ts 保留并自然擦除到0，不是人为排除入口或 runtime。main/App 实际执行。28个范围只证明已声明的 TS/TSX 范围，不能覆盖遗漏脚本。
- 三个独立离线 widget probe：①来源恶意HTML产生img/onerror，失败；②同payload答案为字面文本且无img，通过；③首次网络失败后再ask，calls2/error=offline/answers1，通过。执行为 Node stdin + jsdom + fs读取实际生产脚本，等待window.load后eval，模拟fetch只返回夹具；exit0代表探针正常执行，并不代表第一项安全通过。最初试验手动DOMContentLoaded可能重复初始化，已用等待load的版本复跑，最终三项结果如上。

新增测试包含有效行为断言：token刷新重试与清理、登录/匿名切换、真实路由入口、空/null/错误响应、文档删除后刷新、查询失败恢复可输入、上传阶段/终态/连续网络失败停止、graph销毁/重建/聚焦、聊天转义与反馈状态。存在 any/as never 和密集一行表达式，降低可读性但未发现用弱化生产行为/ignore/skip制造覆盖通过。测试中的api spy、fetch/vis替代只验证边界软件行为。

AppShell Hook 订阅移至顶层，匿名→认证变化测试有效；Graph effect 加visReady/viewMode，受控引擎创建/返回重建断言有效。Router7仍使用React18声明式router，真实入口及可选参数/未知路径通过。Tailwind4 official PostCSS、@config及base层reset符合当前应用；已检查真实 Chromium 绿色日志/receipt，桌面32px/900px、移动16px、表格/字体/Markdown等有实际断言。本人未重复浏览器运行，因此该部分是独立证据审阅，不冒称独立浏览器执行；jsdom七条 navigation Not implemented 输出未隐藏。

## 完整范围盘点与待补项

| 目录/对象 | 来源与消费者证据 | 本次判断 |
|---|---|---|
| frontend/src 28 TS/TSX | Vite index/main/App入口；生产构建与真实组件测试 | 声明范围完整，双指标通过；不是前端全部可执行代码 |
| frontend/public/chat-widget.js | Vite public复制、独立dist文件、后端公开static route、双Docker发布与企业蓝图 | 必须纳入第一方生产范围，当前缺覆盖且有注入问题 |
| frontend/visualizer.html、prototype/index.html | CLAUDE提供python http.server静态原型预览；蓝图引用旧颜色/验证成果；vite没有多入口，dist未包含二者，Docker仅复制dist | 有依据排除当前Vite正式发布分母；应在固定策略注明是可运行历史原型。若今后作为正式工具部署应另测，不能仅凭目录名永久排除 |
| langextract/langextract | gitlink 6542a98a67c7ffb60c161c888286cafda590bbe0；origin google/langextract；package带Google版权、上游URL；本地运行包无改动。worker/pipeline/grounding消费，backend锁以editable路径安装，Docker复制 | 当前上游第三方库可不计第一方分母，必须保留真实依赖消费者验收；不能因为在仓库内就全部算第一方，也不能因为目录叫langextract就全部算第三方 |
| langextract/mvp_deepseek_test.py | 本地未跟踪MVP脚本，非上游tracked运行包；同目录仅.gitignore与本地文档改动 | 列为本地验证工具并核用途；不是当前Docker安装包生产入口。全项目工具验收若纳入，必须独立覆盖/锁与隔离规范，不用第三方身份一概豁免 |
| iteration-2/.../rag_eval | 第一方release_gate/metrics/run_inference/backend_validation等CLI，有自身规范与test_*.py；backend/tests/test_eval_keyword_normalization.py直接导入metrics_a2；query/evidence契约变化已回流其规范 | 未进入source=backend的90文件统计。属于正式评测/发布决策工具，不能仅以iteration名称排除。当前质量整改含治理/契约变动，需明确本轮相关性并建立该子项目固定全量分母/双覆盖与测试证据；目前不能声明全部第一方子项目通过 |
| mineru-mvp-test/run_mvp.py、generate_sample_pdf.py | 第一方远程MinerU MVP/样本生成脚本；独立requirements；实际后端使用backend/mineru_client.py，未找到生产import/镜像复制MVP | 本轮无源码改动且非部署消费者，可有理由不列入局部产品变更门槛；对全项目/治理验收仍需固定策略分类，不能仅以MVP目录名直接豁免。不得为验证而调用真实API/读.env |

因此相关范围不能直接宣称是“backend90＋Vite28且无遗漏”。至少正式 widget 是确定遗漏；rag_eval 是需要补范围/验收决策的第一方可执行子项目；langextract本地MVP与MinerU工具必须在策略中明示用途、相关性和排除依据。后端90的覆盖质量由另一独立评审负责，本报告不越权声称其当前通过。

## 快照与改进优先级

原输入清单SHA256：31cda57eb6d0845a6a1645b4d6dd8cd6903f942c34acf322eeef11edb164fabe（50项逐一核对，无漂移）。关键实际文件SHA256：

- public/chat-widget.js：2a0e24abc3d2f0e240a25ad9314803af87e4ab3f57576f873e6b4eccc83f7343
- UploadPage.tsx：2f1f4cc392e55acd0164c15ea3ff4a917427b8105bba9ff04373201b21bb730b
- GraphPage.tsx：849951f15eff02d97fb5414699858b9fd969309ffa8ddc769e1593f6395ba6e6
- vitest.config.ts：d26cf5ac0787207fe181a3b5baf08dbc6c7b1938ed7c44068d033677c4c5add5

1. 关闭widget来源HTML注入，新增真实独立脚本恶意输入/错误恢复断言，并扩大生产JS统计范围重跑。
2. 固定第一方可执行子项目清单与相关性，补rag_eval门槛证据或明确有证据的任务排除决定；不将模糊范围当达标。
3. 补上传ingest晚到/轮询在途/重置旧响应的生命周期断言与最小修复，复跑受影响消费者。
4. 最终快照重验覆盖、构建、安全和必要浏览器场景，再由协调者关联研究冻结、后端整体证据及发布边界。当前Windows仍audit-only-windows，无commit/push/deploy授权执行或完成声明。
