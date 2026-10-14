# 权限矩阵（Layer 6f 运行时隔离）

> 来自 OpenHarness 的 environment 子系统，定义 Agent 与服务的权限边界。

## Agent 权限表

| Agent | 可用工具 | 禁止操作 | 典型场景 |
|-------|---------|---------|---------|
| chatbot-planner | Read, Glob, Grep, WebSearch | Write, Edit, Bash | 设计新页面 / 新流程，只读探索 |
| chatbot-coder | Read, Write, Edit, Bash, Glob, Grep | 无（受 deny hooks 约束） | 写代码 / 改代码 |
| chatbot-reviewer | Read, Glob, Grep | Write, Edit, Bash | 代码静态审查，建议 `run_in_background: true` |
| chatbot-debugger | Read, Glob, Grep, Bash | Write, Edit | 联调遇到具体故障，只读 + 诊断命令 |

## 服务权限表

| 服务 | 可访问资源 | 禁止操作 | 凭证来源 |
|------|-----------|---------|---------|
| backend (FastAPI) | Neo4j `kg_prod` / OSS bucket / DeepSeek API | 不得写入 `kg_eval` | `.env` |
| rag_eval | Neo4j `kg_eval` (只读) / backend `/api/query` (只读) | 不得修改 backend 代码 | 复用 `backend/.env` |
| langextract | OSS bucket / MinerU API / DeepSeek API | 不得访问 Neo4j | `langextract/.env` |
| frontend | backend `/api/*` | 不得直接访问 Neo4j / OSS | 无凭证（通过 backend 代理） |

## Deny Hooks（全局拦截规则）

以下命令在 `.claude/settings.local.json` 中配置，任何 Agent 调用 Bash 工具时触发拦截：

1. `rm -rf /*` — 防止递归删除根目录
2. `git push --force*` — 防止强制推送覆盖远程历史
3. `git push -f*` — 同上（简写形式）
4. `*DROP DATABASE*` — 防止删除整个数据库
5. `*DROP TABLE*` — 防止删除表
6. `*MATCH (n) DETACH DELETE n*` — 防止清空 Neo4j 图谱

## Sandbox 策略（暂缓）

当前项目处于维护期，暂不启用 Docker / VM 沙箱隔离。触发条件：

- 需要运行不可信第三方代码（如用户上传的插件）
- 需要测试破坏性操作（如数据库迁移回滚）
- 需要多租户隔离（如 SaaS 化部署）

届时参考 OpenHarness 的 sandbox 子系统设计。

## 审计日志

- Agent 工具调用日志：`.claude/logs/` (Claude Code 自动记录)
- 后端 API 访问日志：`backend/logs/app.log` (FastAPI 中间件)
- Neo4j 查询日志：Neo4j 自带审计功能（生产环境启用）

## 权限变更流程

1. 提出变更需求（如 debugger 需要 Write 权限）
2. 在本文档中更新权限表
3. 修改对应 Agent 的 `.claude/agents/*.md` frontmatter `tools` 字段
4. 提交 PR，由 chatbot-reviewer 复审
5. 合并后生效

## 参考资料

- OpenHarness environment 子系统：https://github.com/walkinglabs/awesome-harness-engineering
- Claude Code 权限模型：https://docs.anthropic.com/claude/docs/claude-code-permissions
