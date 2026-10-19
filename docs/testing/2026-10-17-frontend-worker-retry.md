# 前端 worker 重试验证（2026-10-17）

本轮前端全量验收通过；未修改生产代码、测试、依赖锁、覆盖范围或阈值。

## 复现与边界

上一轮 pnpm 启动的 forks worker 报 `Timeout waiting for worker to respond`，threads 运行曾被终止。本轮先直接调用隔离 Node 22.23.3，worker_threads、fork 子进程 IPC 与 inspector 子进程均成功，探针 exit 0。证明该执行环境具备这些能力；不能据此断定上一轮根因为 pnpm 的 Node 版本，亦未复现每种旧命令组合。

采用同一个 Node 22 可执行文件直接启动 Vitest，使用 threads 单 worker 限制调度并发。本次没有更改测试超时、断言或应用行为。适用范围为当前 Windows 执行环境的测试启动方式。

## 实际命令与结果

仓库根执行：

```powershell
& '.tmp/vector-errors-testenv-20261014/.venv/Scripts/python.exe' .tmp/publish-retry-front-20261017/run.py
& '.tmp/vector-errors-testenv-20261014/.venv/Scripts/python.exe' .tmp/publish-retry-front-20261017/analyze.py
```

run.py 内实际命令（cwd=frontend）：

```text
D:/graghRAG-agent/.tmp/node22-runtime/node-v22.23.3-win-x64/node.exe node_modules/vitest/vitest.mjs run --coverage --coverage.reportsDirectory=D:/graghRAG-agent/.tmp/publish-retry-front-20261017/coverage --pool=threads --maxWorkers=1
```

- 退出码 0，43.115 秒，9 个测试文件、122 个测试通过。
- 行覆盖率 927/957 = 96.8652…%；分支覆盖率 853/913 = 93.4282…%。按原始计数两项均 ≥90%。
- 固定生产范围 `src/**/*.{ts,tsx}` 与 `public/**/*.js` 共29文件，报告29文件，无遗漏或额外文件；未导入文件保持计入。
- src/public/tests、顶层 JSON、vitest.config.ts、pnpm-lock.yaml 与 .nvmrc 输入前后 SHA-256 一致。
- 外部截止100秒仅保护该运行脚本自身进程树，本次正常退出，未触发终止。

## 证据

实际日志、命令/退出码/时长 receipt、before/after 哈希、scope-check.json、coverage-final.json、coverage-summary.json、lcov 均位于 `.tmp/publish-retry-front-20261017/`。Node 探针源码 probe.cjs、probe.log 与 probe.exit 同目录。上轮失败证据保留在 `.tmp/publish-other-20261017/`，未覆盖。

本报告仅证明前端该代码快照全量测试与双覆盖率；不能替代后端、漏洞扫描、凭据检查或整体提交门槛。本轮未 commit/push。
