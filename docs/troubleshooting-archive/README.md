# Troubleshooting Archive

本目录是**只读历史归档**。所有报告的关键结论已回流到对应 Layer 规范文档；保留原文件用于回查问题发生时的现场上下文。

## 归档原则

- 报告内容**已回流**到规范文档后才能归档到此目录
- 归档时必须用 `git mv`（保留 history），不要 `rm` + `git add`
- 归档后**禁止再编辑**这些文件；新发现回到规范文档迭代
- 若发现回流不完整，先补规范文档，再来此查阅原报告

## 归档索引

| 文件 | 主题 | 已回流到 |
|------|------|---------|
| ACCESSKEY_TROUBLESHOOTING.md | OSS AccessKey 配置 | `langextract/docs/bridge-pipeline-specification-v1.0.md` |
| OSS_INTEGRATION_GUIDE.md | OSS 接入步骤 | 同上 |
| OSS_INTEGRATION_SUCCESS.md | OSS 验证清单 | 同上 |
| CODE_REVIEW_FINDINGS.md | 后端 Critical 三问题 | `integration/backend-api-architecture-v1.0.md` |
| FINAL_RESOLUTION_REPORT.md | server.py 启动顺序 | 同上 |
| ISSUE_RESOLUTION_SUMMARY.md | 健康检查/文档列表/KG 校验 | 同上 |
| QUERY_FIX_REPORT.md | 查询接口修复 | 同上 |
| TRANSFORMER_CLEANUP_REPORT.md | 无用依赖清理 | 同上 |
| FILE_UPLOAD_SOLUTIONS.md | 上传链路 | `integration/backend-api-architecture-v1.0.md` + `integration/frontend-system-design-v1.0.md` |
| LOCAL_FILE_UPLOAD_GUIDE.md | 本地上传流程 | 同上 |
