# 五项 P0 修复独立代码审查

日期：2026-10-12。输入：当前未提交工作树、`docs/plans/2026-10-12-p0-security-fixes.md`、`docs/review/2026-10-12-p0-root-cause.md`。本次是独立上下文静态审查；没有修改生产代码，没有把原有研究改动视为本轮重写。采用 requesting-code-review 的独立检查方式。工作树仍被负责人修改，以下行号对应首次审查读取，复核记录应追加在本文。

## 审查总结

首次审查发现 Critical 1、High 1、Medium 3、Low 0，详见下方历史问题及末尾复核记录。负责人修正后再次逐段静态复核，五项问题的生产代码路径均已关闭，当前未发现遗留阻断问题；测试执行和提交门槛须以负责人保存的实际证据判断。

## 问题清单

### 🔴 Critical：用户禁用或管理员降权后旧凭据仍保留权限

文件：`backend/middleware/jwt_middleware.py:116–132`；关联 `backend/services/auth_service.py:181–200`、`backend/services/resource_access.py:19–20`。

认证 middleware 直接把签名 claims 的 roles 复制到 principal，没有查询当前用户；托管 key 也仅确认 created_by 非空。`disable_user` 删除用户 JSON、`update_roles` 写新角色，均不改变旧 JWT claims。因此被禁用或已经降权的管理员仍可用未过期 JWT 穿过 `is_admin`，访问全部历史文档、删除文档及全局资料接口；托管 key 创建者被禁用后亦保留其个人 owner 资料访问。根因文档要求检查当前有效用户和当前权限，此处仍未落实。

建议：JWT 和托管 key 均加载可信服务端用户，用户不存在立即拒绝。JWT principal 使用当前用户角色；托管 key 保持 scope 交集且不得继承全局 admin。旧 ADMIN_API_KEY 仍可使用明确服务管理员 principal。测试用真实临时 users JSON，覆盖签发后 disable_user / update_roles 的立即失权。

```python
# before
roles = payload.get("roles", ["viewer"])
request.state.user = {"user_id": payload["sub"], "roles": roles, "auth_type": "jwt"}

# after（示意）
user = get_auth_service().get_user(payload["sub"])
if user is None:
    return JSONResponse(status_code=401, content={"detail": "需要有效认证"})
request.state.user = {"user_id": user.user_id, "roles": user.roles, "auth_type": "jwt"}
```

### 🟠 High：无授权文档或空有效图仍触发模型

文件：`backend/routes/query.py:249–254`、`backend/routes/rag_query.py:232–244`；调用证据 `backend/retrieval.py:2668`、`backend/retrieval.py:279–345`。

新用户无 document_id 查询时 authorized_documents 返回空列表，旧 query 随后仍构建 agent 并 invoke。受限 RAG 即便空图也调用 generator → retrieve → preprocess_query；后者在空资料判定前调用模型。generator 最终对空 chunks 确实会确定性拒答，但不能阻止此前的查询预处理模型调用。这与计划“没有授权文档明确无数据且不调用 LLM”不一致，也使空权限用户能消耗付费模型请求；缺失/空版本资料亦有同样问题。

建议：加载授权 grounded 图后，在节点数为零时返回稳定 no-data QueryResponse，早于 agent/检索器/生成器构建。保留来源/会话隔离检查。两个路由分别加空 docs、空 nodes、全 ungrounded 图用例，供应商边界触达即失败。

```python
# before
snapshot = authorized_graph(docs, root)
result = RAGGenerator(pipeline, config=generation).generate(req.query, ...)

# after（示意）
snapshot = authorized_graph(docs, root)
if snapshot.number_of_nodes() == 0:
    return QueryResponse(query=req.query, answer="没有可查询的授权资料。",
                         sources=None, metadata={"document_ids": [], "status": "no_data"})
```

### 🟡 Medium：缺失 type 的 JWT 默认视为 access

文件：`backend/middleware/jwt_middleware.py:117`、`backend/middleware/jwt_middleware.py:187–194`（行号随负责人修改漂移）。

`payload.get("type", "access")` 接受未声明用途的签名 token；decode_token required claims 没有 type。现有 refresh 拒绝测试的 payload 同时缺 issuer，因此该测试即使移除 access 类型检查仍然失败，不能单独证明 refresh 被拒绝。

建议：必须显式 type=access；refresh 使用完整且有效的 issuer/sub/exp/type，另加缺 type 的签名 token 用例。此问题无需持有签名密钥的攻击者即可利用并不成立，风险是跨用途/历史 token 混用，不能描述为任意伪造签名。

```python
# before
if payload and payload.get("type", "access") == "access":

# after
if payload and payload.get("type") == "access":
```

### 🟡 Medium：原子发布前缺少最小产物校验，ZIP 验收仍为替身

文件：`backend/mineru_client.py:426–435`；`backend/tests/test_p0_mineru_isolation.py:70–140`。

download_and_extract 在 unzip 退出成功后立即 rename result，没有检查 full.md 与 content_list。缺失产物会在后续 worker 失败，未发现因此能把无效资料入库成功；但 published result 不满足计划的“校验后发布”语义。并发测试把 curl/unzip 替换为直接写文件的函数，因此证明独占文件系统边界，不能证明真实 ZIP 解压、嵌套目录结构和缺产物不发布。

建议：发布前验证下游实际支持的产物结构；无效 ZIP 保持未发布并报明确错误。用本地 HTTP 服务提供真实合成 ZIP，保留真实 curl/unzip（或产品实际解压器）执行；覆盖有效平铺/支持的嵌套结构、缺 full.md、缺 content_list 和损坏 ZIP。

```python
# before
os.remove(zip_path)
os.rename(staging_dir, result_dir)

# after（示意）
os.remove(zip_path)
validate_mineru_artifacts(staging_dir)  # 使用实际支持的布局
os.rename(staging_dir, result_dir)
```

### 🟡 Medium：Windows junction 指向根内其他文档未拒绝

文件：`backend/services/document_snapshot.py:10–18`。

contained_asset 检查 is_symlink 和 resolve 后根包含关系，没有检查 Windows junction。目录 junction 指向根外会被包含关系拒绝，但若 doc_A 的登记 KG 路径经过指向根内 doc_B 的 junction，resolve 得到的 doc_B 仍合法，删除随后 rmtree 解析后的 doc_B。这不满足计划的链接拒绝；本审查未证明远程用户具有创建 junction 的能力，不将此等同于已证实远程利用。

建议：对路径本身及父目录同时拒绝 junction（Python 3.12 的 is_junction），Windows 条件回归用根内另一文档目录作哨兵，确保拒绝且哨兵保持不变。

```python
# before
if path.is_symlink() or any(parent.is_symlink() for parent in path.parents if parent != root):

# after（示意）
def linked(candidate):
    return candidate.is_symlink() or candidate.is_junction()
if linked(path) or any(linked(parent) for parent in path.parents if parent != root):
```

## 已检查的正确边界与测试限制

- 未配置 secret 时拒绝公共开发 secret；显式开发模式例外已经受生产环境约束。
- project header 通过真实 project/org/member；get_org 自身排除停用组织。资源对象不存在/不可见返回 404，旧无归属资料仅 admin。
- read scope 按 method 约束；托管 key 不自动视为 admin；全局 catalog/export/lineage 等由 resource guard 对非 admin 拒绝。
- documents/delete 先授权并解析受控路径，再删除精确登记文件和文档 KG；未知 doc_ 不进入删除遍历。查询失效缓存覆盖旧 agent 和主 RAG runtime。
- 单文档/受限 RAG 不初始化全局索引，不复用未绑定 session；图节点注入真实 document_id/version，来源使用当前 snapshot。
- MinerU 两入口使用完整 task_id，exclusive mkdir 拒绝同标识覆盖，显式缓存 true 不会恢复全局扫描。
- 资源路由多数测试用自定义 principal middleware，仅部分用真实 server；不能把全部路由用例称为完整认证链集成测试。授权测试当前未建真实 users，尚不能覆盖撤权。
- CORS 放在最外层以处理合法预检、chat-widget.js 加精确白名单方案合理；首次读取时尚未看到最终版本，需负责人完成后复核。

## 实际验证

执行：在 backend 中设置 `PYTHON_DOTENV_DISABLED=1`，运行 `.venv/Scripts/python.exe -m pytest tests/test_p0_authorization.py tests/test_p0_resource_routes.py tests/test_p0_mineru_isolation.py -q --basetemp tests/_tmp_review_p0`。

该进程长时间无输出，未得到收集数或测试结果后由审查者中断，退出码 1。**本次不声称任何测试通过，也不据此判断某个用例失败。** 此前组合读取命令有三条误用 backend/backend 相对路径的只读查询报错，随后已改在仓库根按实际路径读取；不是测试结果。没有供应商调用、没有真实资料清理、没有 Git 提交；全量双覆盖率未核验。

## 优化建议汇总

1. 关闭当前用户撤权缺口，使用真实临时 users 验证 JWT/key 与角色更新、删除用户的即时结果。
2. 两查询入口对空授权有效图提前返回；用供应商触达禁止断言验证。
3. 强制显式 access type；补完整 issuer 的 refresh 和缺 type 用例。
4. 最小产物验证后再发布；补真实本地 ZIP/HTTP 回归。
5. Windows 受控路径显式拒绝 junction，避免根内其他文档也成为解析目标。
6. 对负责人后续修订重新审查，并重跑受影响回归；全量测试和行/分支覆盖率证据不足仍禁止 commit/push。

负责人补充：无输出测试可能受 Windows socketpair 沙箱权限限制，实际 API 测试将由负责人提权运行。本审查没有独立确认卡住原因，停止继续测试，后续仅静态复核。

## 修订后独立复核

本节对应负责人落盘后的最新工作树；下方结论是静态复核，不将负责人消息里的运行数字转述为本人执行结果。

| 首审问题 | 状态 | 已读取的关闭证据 |
|---|---|---|
| 用户禁用/降权后旧凭据保权 | 静态关闭 | jwt_middleware 在 JWT access 分支查 get_auth_service().get_user，用户不存在 401，并使用当前 user.roles；托管 key 亦验证 created_by 当前用户存在。test_current_user_roles_and_disable_revoke_existing_access 使用临时真实 users，签发后降权与禁用，分别断言新角色及 JWT/key 401。 |
| 空授权有效图调用模型 | 静态关闭 | query 在 _build_agent 前检查空 grounded snapshot；受限 rag 在 RetrievalPipeline/RAGGenerator 构建前检查空 grounded snapshot，返回 metadata.status=no_data。两 endpoint 的无授权资料用例在 agent/generator/global init 边界触达即失败。 |
| 缺失 type 默认 access | 静态关闭 | decode_token required claims 包含 type；资料请求只接受 payload.get('type') == 'access'。缺 type 用例与 test_valid_refresh_token_cannot_access_documents 使用真实签发的完整 refresh token，独立断言拒绝。 |
| 发布前缺失产物校验 | 静态关闭 | download_and_extract 在 rename 前校验 full.md 和 *_content_list.json 必须为真实受控文件、非 symlink/junction；content_list 必须可解析为 JSON list，失败使用 PIPELINE_MINERU_PARSE 且未发布。测试新增真实合成 ZIP，缺文件/坏 JSON/非 list/链接产物均断言不发布。 |
| 根内 junction 指向其他文档 | 静态关闭 | contained_asset 对自身及 parents 统一 linked 判断，包括 is_symlink 与 is_junction；versions.json 亦走该校验。删除用例覆盖根内另一文档 symlink 和 Windows junction，断言 409、原件与另一文档节点文件保持存在。 |

兼容修正也已检查：CORSMiddleware 最后注册而在认证外层处理合法预检，实际请求继续认证；PUBLIC_PATHS 仅精确公开 `/static/chat-widget.js`，测试保留后缀子路径 401。MinerU runtime 恢复优先扫描完整任务的已发布 result、兼容旧一级目录、排除 .working-* 及链接和非文件产物；新增 test_p0_runtime_sources 对新/旧布局排序、半成品、各级链接和目录伪装文件作行为断言。

仍需准确表述验证范围：真实 ZIP 回归替换下载为本地文件复制，并以独立 Python zipfile 进程代替 Git/MSYS unzip，证明真实 ZIP 解压及产物验证逻辑；它不证明公网 HTTP 下载或产品所用 unzip 可执行文件的完整兼容。资源路由主体夹具继续使用自定义 principal middleware，真实 server 的认证、跨用户任务与 CORS 用例另行覆盖；不能把全部用例泛称完整生产认证链。

建议补充但不阻断本轮代码交付：空有效图用例增加“有授权 doc 但 nodes 为空/全 ungrounded”分层断言，以直接覆盖当前生产早退条件；供应商 HTTP 与实际 unzip 工具在具备环境时单独验收。审查者未继续执行 API 测试，未核验全量双覆盖率，仍不提供 commit/push 许可。

### 最后兼容修正复核

再次只读检查 `routes/rag_query.py`、`middleware/jwt_middleware.py`、`services/resource_access.py` 及新增路由测试：

- rag_summarize 显式接收 Request，并调用 rag_query(req, request)，因此摘要入口复用当前身份、document_id 授权、请求独立 KG、session/source 限制及空图早退。没有绕回全局索引的独立摘要分支。
- resource guard 加入 rag/summarize；read:query scope 同时加入该路径，POST 例外仍是三个精确查询路径集合，未让其他 read scope 支持写方法。
- read:catalog 加入 files 路径；GET 文件仍由 serve_uploaded_file 的 contained_asset 和 authorized_documents 精确 filepath 匹配约束，不会仅凭 scope 公开全 uploads。DELETE files 不会通过 read method 检查。
- 空授权资料禁止触达模型测试已纳入 rag/summarize，能覆盖 Request 传递遗漏导致的入口异常；本审查未执行该用例。

这批兼容修正未发现新的静态阻断问题。负责人通知全量测试存在研究依赖/兼容失败并在继续核查；审查者没有运行该轮全量测试，也未独立核实失败归因，不能将其描述为全部非本轮问题或全量通过。最终交付应保留实际失败清单、修正后的重跑结果和覆盖率状态。
