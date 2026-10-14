# 认证、租户、机器人行为验证

日期：2026-10-13。维护流程使用 Superpowers，未启用 goal/Harness。仅本地专项证据，不代表全后端或项目双 90 门槛通过；未提交、推送或部署。

## 范围和隔离

新增 `backend/tests/test_auth_tenant_readiness.py` 的 44 个参数化场景。复用 `tests.test_p0_resource_routes.resource_app`，使用真实 JWT 签发与验证、真实 AuthService/TenantService/ApiKeyManager、临时 JSON、真实审计文件、FastAPI 路由和真实错误处理器。覆盖本地登录开发门、登录/刷新/撤销、用户权限与失效、OIDC state 一次性消费、组织/成员/项目权限和资源不存在矩阵、损坏记录/成员撤销/孤儿记录、飞书签名/配置/告警上限/降级、API key 限流与声明类型。

认证逻辑和目标路由没有 mock；OIDC 和飞书仅替换 `requests.post/get` 外部 HTTP 边界，未连接供应商，也未读取 `.env`。用户、OAuth state、租户、API key、审计及索引产物均隔离到临时目录。pytest 既有真实依赖测试另外组合回归；其各自边界以原测试为准，不将外部 HTTP 替身声称为供应商集成。

## 实际红测与最小修复

Run 3：31 passed、5 failed。跨组织归档用例返回 200，违背预期 404：组织 A 的 org_admin 可以归档组织 B 的项目。`routes/tenants.py` 的 archive 原来只校验 A 的权限后按裸 project_id 归档。修复先读取项目并核验 `proj.org_id == org_id`，不存在或不相等均 404，之后才归档。红测保留，并同时断言外组织项目没有变成归档状态。

另外四个飞书告警场景失败：配置启用且 alerts 非空时返回 500。`routes/bot.py` 调用 `build_error_card(title=..., message=...)`，而真实 FeishuClient 只接受 message。修复使用现有 message 参数，再写入返回卡片的 `header.title.content`。保留 critical/default 严重度、FIRING 标题、summary 和最多 5 张卡片的精确断言。

两项生产修复在红测后取得根任务明确文件归属授权。未修改其他生产文件。规范待根任务回流到有效 backend API 文档；本报告不替代有效规范或独立评审。

## 最终执行证据

候选隔离解释器：`.tmp/backend-quality-venv-20261012/Scripts/python.exe`。环境变量：`PYTHONPATH=.tmp/coverage-runtime-py312-20261012;backend`（执行时用绝对路径），`PYTHON_DOTENV_DISABLED=1`、`HF_HUB_OFFLINE=1`、`TRANSFORMERS_OFFLINE=1`、`PYTHONUTF8=1`；`COVERAGE_FILE=.tmp/auth-tenant-readiness.coverage`（绝对路径）。本机 TestClient/asyncio 使用获准的 sandbox 外运行，避免受限 loopback/socketpair 问题。

从仓库根目录实际执行：

```powershell
./.tmp/backend-quality-venv-20261012/Scripts/python.exe -m coverage run --rcfile=docs/testing/coverage-backend-2026-10-12.ini -m pytest backend/tests/test_auth_tenant_readiness.py backend/tests/test_p0_authorization.py backend/tests/test_phase2.py -q --basetemp=.tmp/auth-tenant-pytest-5
./.tmp/backend-quality-venv-20261012/Scripts/python.exe -m coverage json --rcfile=docs/testing/coverage-backend-2026-10-12.ini -o .tmp/auth-tenant-readiness.json
```

第一条退出码 0，106 passed、1 个 Starlette/AnyIO 弃用 warning，12.60 秒；第二条退出码 0。前一版 run 4 为 98 passed；补齐 JWT 和租户缺失更新行为后重新执行为最终 run 5。

固定 ini 保持全后端第一方范围与分支统计，未增加排除、降低门槛、删除断言或跳过用例。专项只执行上述三个测试模块，不能用下表当全量验收。原始数据与机器报告：`.tmp/auth-tenant-readiness.coverage`、`.tmp/auth-tenant-readiness.json`。

| 模块 | 已覆盖行 / 全行 | 已覆盖分支 / 全分支 |
|---|---:|---:|
| middleware/jwt_middleware.py | 116 / 117 | 51 / 52 |
| routes/auth.py | 84 / 86 | 24 / 24 |
| routes/tenants.py | 117 / 119 | 28 / 28 |
| routes/bot.py | 84 / 84 | 30 / 30 |
| services/auth_service.py | 137 / 139 | 24 / 24 |
| services/tenant_service.py | 216 / 216 | 72 / 72 |

所有六模块专项行、分支均超过 95%。JWT 唯一未覆盖分支是解码后拒绝空白 sub；审计异常降级等少量行仍未被此次专项执行。其他模块及全部子项目验收、漏洞扫描、独立评审和规范回流由根任务汇总。

## 最终源码 SHA-256

```text
backend/routes/tenants.py EBB522F2D883D89655C23104290ED3C84A6994DAB4EAE594AE79EA468F9C468F
backend/routes/bot.py B0ED91C1789EE4DD3A38C5F82BC0B77F9C56C01389333D7AD52D711CD55EE922
backend/tests/test_auth_tenant_readiness.py 40AED55A2097AFF699EEF6B1AB2D55C69C5FBECCFBE7AC4E2A6C612704A2CE61
backend/middleware/jwt_middleware.py F5574887CCEFC1CC4A3F6177A28E2E52EBDB3F2361101C5CB7FD4CDD5E4D7ACB
backend/services/auth_service.py 3B862D1010388EB149FEDC523283105D0102692923C5F9E4CFFE56690966818C
backend/services/tenant_service.py A5EC55A20CD87F5CA13B0090375EF18405BF7E298B6CF819E7AA4E7AFA7804A5
backend/routes/auth.py 122AAB393839EB47A6C054FA0CE9EA0F0F7D596E16C48E9180EE80E8E64ADCE1
```

根任务负责 memory 更新、规范回流、独立代码评审，以及最终代码快照下全量测试和覆盖率证据。后续生产代码、测试或统计配置变化须重新验证适用范围。

## 20:26 更新：独立评审后的签名契约修复（取代前述最终快照）

独立评审发现已配置 verification_token 时缺签名头仍放行。原新增测试错误地将这种行为视为兼容行为。20:16 开始重新定位，实际第一轮红测 `auth-signature-red-1.log` 为 15 failed、2 passed、退出 1：七种不完整签名头组合，普通事件与 URL verification 均返回 200；URL verification 另有验签前返回路径。事件处理器只用包装原方法的 spy 观测，未替换事件处理逻辑。

同时核对一手协议：[飞书官方 SDK request-handle.ts](https://github.com/larksuite/node-sdk/blob/main/dispatcher/request-handle.ts) 的 `checkIsEventValidated`：配置 Encrypt Key 时使用 SHA-256(timestamp + nonce + Encrypt Key + 原始 body)；仅配置 Verification Token 时，含 schema/header 的事件优先读取 header.token，否则读取顶层 token；两者皆无不执行这两种校验。[官方接收事件页面](https://open.feishu.cn/document/server-docs/event-subscription-guide/event-subscription-configure-/encrypt-key-encryption-configuration-case) 经访问未返回可提取正文，实际协议核对依据为官方 SDK 源码，未用第三方教程代替一手来源。

根任务明确修正此前“verification_token 配置必需签名头”的简化要求，选择官方模式。第二轮真实红测 `auth-signature-red-2.log` 为 18 failed、1 passed、退出 1，还证明原来使用 verification_token 计算 SHA-256 错误拒绝 Encrypt Key 正确签名，并错误解码原始 bytes。

最小修复：

- routes/bot.py：Encrypt Key 模式必须有三个非空签名头，缺头 401、错误签名 403；token-only 模式按官方 header/top-level 优先序校验 token，缺失/不匹配 401；两者同时配置时 Encrypt Key 优先。URL verification 也在认证之后返回。两者均未配置时保留现有开发兼容行为，不将其描述为生产安全配置。
- services/feishu_client.py：只用 Encrypt Key 及原始 body bytes 计算摘要；缺 Encrypt Key 返回 False；使用 hmac.compare_digest 比较摘要，替换原字符串等号。未读取真实配置、未引入第三方依赖。

测试最终新增到 81 个场景（原 44 + 37），包含 Encrypt Key-only/both、token-only 的 v1/v2/header-only 和畸形 header、正常事件/URL verification、全部七种缺头组合、正确/错误签名、错误密钥/改 body/改 nonce/改 timestamp，以及非 UTF-8 原始 bytes。之前对 missing signature 期待 200 的断言已改成配置模式下对应拒绝断言；原其他行为断言没有削弱。

最终固定 ini/环境与前节相同，COVERAGE_FILE 改为 `.tmp/auth-bot-signature-final.coverage`。实际命令：

```powershell
./.tmp/backend-quality-venv-20261012/Scripts/python.exe -m coverage run --rcfile=docs/testing/coverage-backend-2026-10-12.ini -m pytest backend/tests/test_auth_tenant_readiness.py backend/tests/test_p0_authorization.py backend/tests/test_phase2.py -q --basetemp=.tmp/auth-signature-final
./.tmp/backend-quality-venv-20261012/Scripts/python.exe -m coverage json --rcfile=docs/testing/coverage-backend-2026-10-12.ini -o .tmp/auth-bot-signature-final.json
```

退出码均 0。143 passed、1 个 Starlette/AnyIO 弃用 warning，12.41 秒。实际测试日志 `.tmp/auth-signature-final.log`；机器原始数据及报告 `.tmp/auth-bot-signature-final.coverage`、`.tmp/auth-bot-signature-final.json`。Bot 路由行 91/91、分支 34/34；其他前述六目标模块原始计数不变。新涉及 FeishuClient 总体仅行 54/61、分支 4/6；签名方法两个分支均执行，但本专项没有补其 QA 卡片等整个模块行为，不能宣称 FeishuClient 总体双 90。

最终变化文件 SHA-256（替代前节三个旧 hash）：

```text
backend/routes/bot.py 57961698EA43158AC8D88457707DD63B8A886FFF551B16F86F42C91CE6296869
backend/services/feishu_client.py 01E4C99D3F34FF478BA51DC806828C36A701452EFD524A8BCFE9FDEDC114A994
backend/tests/test_auth_tenant_readiness.py CB72CF458F7713B2B61BB2318775F7837FFFA57AB8CD7F2C21D610E1330DAD42
```

重放/陈旧时间戳有界审查：20:25 对本机 ASGI 发送两次相同合成请求，timestamp=123、相同 nonce/body/签名，真实路由均返回 200；仅使用返回 challenge 的事件，不产生业务写入。实际日志 `.tmp/auth-bot-replay-review.log`、退出 0。官方 SDK 检查中未见时间窗口或重复 nonce 状态，也未在当前有效项目规范找到精确要求，因此记录为真实缺少 freshness/去重能力的残留，未自造窗口或增加状态；不能声称已经防重放。

20:26 源码与测试冻结并交根任务安排独立复核、规范回流和重新执行全量验收。前述 106 passed 及旧 hash 仅作历史证据，不能用于当前快照最终验收。未提交、推送或部署。
