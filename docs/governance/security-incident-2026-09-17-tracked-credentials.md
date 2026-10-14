# 安全事件记录：仓库内跟踪真实凭据

> **日期**：2026-09-17
> **发现方式**：Task 6（密钥扫描）引入 `detect-secrets` baseline 时由扫描器命中
> **严重级**：高
> **状态**：处置中

---

## 一、事实

`detect-secrets` 在生成基线时命中两个真实凭据，且**已被 git 跟踪并进入历史**：

| # | 文件 | 变量 | 形态 | 状态 |
|---|------|------|------|------|
| 1 | `backend/.env.backup:6` | `MINERU_API_TOKEN` | JWT，402 字符（HS512，`clientId=lkzdx57nvy22jkpq9x2yw`） | **已于 2026-08-22 过期** |
| 2 | `backend/.env.backup:16` | `LANGEXTRACT_API_KEY` | `sk-` 前缀，35 字符（DeepSeek） | **形态为真实密钥，按已泄露处理** |

- **注入提交**：`5e331ab`（"refactor: 将 yujia-engineering 改名为 harness-engineering"，2026-05-29）
- **当前 HEAD 仍含该文件**：`git show HEAD:backend/.env.backup` 可读到上述两个变量
- **`.gitignore` 未覆盖**：根 `.gitignore` 仅忽略 `.env` / `.env.local` / `.env.production` / `.env.*.local`，**不匹配 `.env.backup`**；`git check-ignore backend/.env.backup` 无输出

## 二、同时发现的其它跟踪问题

| 文件 | 问题 |
|------|------|
| `backend/.env_local_test` | 被跟踪；仅含 `FILE_URL`（非密钥），但属配置残留 |
| `backend/backend.log`、`backend_final.log`、`backend_new.log` | 运行日志被跟踪，可能含请求路径/URL 等运维信息 |
| `langextract/mvp_deepseek_test.py:27` | 硬编码同一 DeepSeek key；**当前未跟踪**，一旦 `git add` 即再次泄露 |

## 三、处置（按 2026-09-17 决策：轮换 + 停止跟踪，不重写历史）

### 必须人工完成（本文件无法代劳）

- [ ] **轮换 `LANGEXTRACT_API_KEY`**：登录 DeepSeek 控制台作废 `sk-a99ecf…`，生成新 key 写入本地 `.env`（`.env` 已被忽略，不会再次入库）
- [x] `MINERU_API_TOKEN` 已于 2026-08-22 过期，无需轮换；下次申请时不要写入被跟踪的文件

### 代码侧处置

- [ ] `.gitignore` 补 `.env*`（覆盖 `.env.backup` / `.env_local_test` 等所有变体），`!.env.example` 例外
- [ ] `git rm --cached backend/.env.backup backend/.env_local_test`（保留本地文件，仅停止跟踪）
- [ ] `git rm --cached` + 忽略 `backend/*.log`
- [ ] `langextract/mvp_deepseek_test.py` 改为从环境变量读取，清除硬编码 key
- [ ] `.secrets.baseline` **不得**收录 `backend/.env.backup` 的两条 finding（否则等于白名单化真实凭据）

### 未执行（需独立决策）

- [ ] **历史清理**：`git filter-repo` / BFG 从历史中剔除该文件，然后 force-push
  - **未执行原因**：破坏性操作，会使所有现有 clone 失配，协作者需重新 clone
  - **风险**：不清理则凭据永久留在 `5e331ab` 及之后所有提交里，任何能 clone 仓库的人都能取得
  - **缓解**：凭据轮换后，历史中的旧值即失效，实际风险大幅下降——这也是本轮选择"轮换 + 停止跟踪"而非重写历史的依据

## 四、教训（回流至规范）

1. **`.gitignore` 的 `.env` 规则不足以覆盖 `*` 变体**。`.env` 只匹配字面量；`.env.backup`、`.env_local_test`、`.env.old` 全部漏网。规范应写 `.env*` + `!.env.example`。
2. **`git add -f` 与早期提交的疏漏会绕过后续所有防护**。该文件在 `5e331ab` 入库时 `.gitignore` 可能已存在，但**已被跟踪的文件不受 `.gitignore` 影响**——这是 Git 的常见陷阱。
3. **检测器只在被引入时才生效**。仓库长期存在该凭据却无人发现，直到 Task 6 引入 `detect-secrets`。说明"提交前自检"（铁律 2）需要自动化（pre-commit + CI），不能依赖人工。

## 五、后续

- Task 6 的 `secret-scan` job 与 `.pre-commit-config.yaml` 照常提交（这正是发现该问题的手段）
- 历史重写作为独立阻塞任务另行排期
