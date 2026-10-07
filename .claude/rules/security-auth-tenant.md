---
paths:
  - "backend/**/*.py"
---
# 规则：认证、鉴权与租户隔离

> 来源：developer-kit `python-security-expert` + 本项目已落地的 auth/middleware，用于防止后续开发回退。
> 对应 backlog B01/B02/B03/B04（零认证、跨文档越权、删除越权、来源伪造）。

## 现状（已落地，勿回退）

- `auth.py`：API Key 认证中间件
- `middleware/jwt_middleware.py`：JWT 认证
- `middleware/tenant_middleware.py`：`X-Project-Id` → `request.state.tenant`
- `server.py` 已挂载认证 + JWT + 租户 + 限流 + request_id 中间件

## 铁律（新代码必须遵守）

### 鉴权
- 新增路由**必须**纳入鉴权中间件覆盖范围；公开端点需显式声明 `public`
- 文档/任务/图谱查询**必须先校验归属**，再返回数据：
  - `document_id` 必须限定在授权文档子集内（禁止只写响应不限制检索范围）
  - 跨文档检索前校验文档权限
- 删除操作：先查存在性（不存在返回 404），**禁止字符串前缀推断**（`doc_` 传错会变空前缀删全库）

### 租户隔离
- 所有数据访问带 `owner_id` / `tenant_id` 过滤
- 图谱**禁止全局单例 `G_grounded` 直接暴露**——按租户/文档构建独立视图
- 新增数据表时预留 `owner_id` 字段（+ 未来 `tenant_id`）

### 来源与证据
- 检索/问答来源**仅接受真实工具执行产生的结构化证据**，绑定 `tool_call_id`
- 禁止把用户提交的任意 JSON 当证据（防来源伪造）
- 节点/证据保存真实 `doc_id` + 版本，防热更新跨版本错配

### 敏感数据
- API Key / Token 仅放 `.env`，禁止硬编码、禁止进日志
- 路径拼接用 `Path.resolve()` + `is_relative_to()` 防穿越
- OSS 用私有桶 + 短时签名 URL，禁止公网可读 URL（`oss_uploader.py` 需核查）
