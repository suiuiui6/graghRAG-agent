# 前端依赖兼容整改证据

本轮保留React18、Router6、Tailwind3与Vite6主版本，在声明范围内解析更新；Vite安全下限6.4.4、PostCSS8.5.29，其他依赖采用实际兼容解析版本。未执行audit fix --force或自动主版本迁移。packageManager固定pnpm10.33.3，新增pnpm-lock.yaml及.nvmrc=22；原npm锁原样归档到docs/archive/frontend-package-lock.pre-pnpm-2026-10-12.json，Docker与CI使用pnpm冻结安装，避免旧锁继续部署。

实际执行：pnpm import、pnpm update --ignore-scripts、pnpm install --frozen-lockfile --ignore-scripts（官方registry），后两项exit0。最初import不支持--registry参数，已改为npm_config_registry后执行，没有声称首次错误通过。

本机原Node18.20.8/pnpm10.33.3的TypeScript+Vite build exit0。随后从nodejs.org下载Node22.23.3 Windows ZIP并对官方SHASUMS256逐字节SHA256核验，隔离在.tmp；运行Node22.23.3/pnpm10.33.3冻结安装和build均exit0，源码变更无UI重写。Node22日志分别为 `2026-10-12-node22-frozen.log`、`2026-10-12-node22-build.log`，退出码各自文件为0；ZIP版本/哈希收据 `2026-10-12-node22-runtime.txt`。未修改系统Node，未构建Docker（daemon不可用）。

pnpm audit --json --registry=https://registry.npmjs.org：288依赖，剩4公告（high1/moderate3/critical0/low0），exit1。原始 `2026-10-12-remediated-pnpm-audit.json` 与exit文件保留：

| 依赖 | 公告数/严重性 | 扫描给出的修复边界 |
|---|---|---|
| react-router | 2 / moderate | >=7.18.0，当前6.30.6不满足 |
| braces | 1 / high | vulnerable<=3.0.3，patched<0.0.0（无发布修复） |
| postcss-selector-parser | 1 / moderate | >=7.1.6，Tailwind3的传递6.x不满足 |

首次npm审计“16受影响依赖项”为聚合包项，本轮“4公告”为pnpm advisory计数，不能直接相减宣称修复12个漏洞。仍需为Router7、Tailwind4/替代依赖制定兼容方案、UI行为验证与独立评审；本轮不擅自override不兼容传递主版本或ignore公告。前端覆盖配置/测试尚不完整，build与类型检查不等同双覆盖达标。整体gate保持BLOCKED。
