# P0 根因与修复交接（#1、#2、#3、#4、#50）

日期：2026-10-12。范围：现有 backend 工作区；参考 `docs/governance/assessment-2026-10-12-backend.md`，复用企业蓝图 §6.1/§6.6/§7.1 及 backend API 契约。不修改产品代码，不读取 `.env`，不对真实资料发请求或清理。主进程负责规范回流、实现、独立评审和 memory 汇总。

## 故障摘要

| 编号 | 现象与最小触发条件 | 影响范围 |
|---|---|---|
| #1 | 未设置管理密钥时受保护请求直接通过；已设置时有效 JWT 还会被管理密钥门拒绝。路由没有资源级授权。 | documents 列表/下载/删除/chunk_count、ingest/status、旧 query；其他读图/导出/主 RAG 路径必须防旁路。 |
| #2 | `/query` 提交 document_id=A，仍调用绑定全部图的全局 Agent，metadata 却标 A。 | 单文档查询泄漏其他文档内容；来源与回答不可信。 |
| #3 | 不同任务 `ingest_a0000000`、`ingest_a1111111` 的解析目录都为 `ingest_a`。 | 同一首位十六进制字符的任务共享 result.zip 和解压文件，最多只有 16 个目录。 |
| #4 | 显式开启 allow_cached_mineru_output，直传与 OSS 失败，目录里有另一文档产物。 | 其他资料被静默当成本次文件入库。 |
| #50 | DELETE `/documents/doc_`，即使该文档不存在，空前缀匹配全部 uploads 文件。 | 所有上传源文件可能被删除；短前缀同样可误删多份。 |

### 验证边界

本轮已逐段读取真实代码和调用关系。使用 backend Python 执行纯表达式，确认 #3 两不同 task 的前8位相等（输出 `collision True ingest_a`）；确认 #50 `doc_` 匹配两个不同任务的合成文件名（输出 `delete_doc_ ['ingest_a_first.pdf', 'ingest_b_other.pdf']`），没有实际删除文件。AST 检查 #2 req.document_id 仅在第311行出现。上述命令均退出0。

复杂认证脚本执行持续 running 无输出，未取得结果；后续单行缓存脚本首次因系统临时目录写权限失败，改到工作区.tmp后运行时其他coder已经把selector改为返回None，故不能作为原实现缓存红测。**未完成完整HTTP链运行时复现或真实依赖回归，不声称通过**。下面的测试仍是实现验收门槛。本文行号和根因对应读取时的修复前代码，其他agent并行修改可能使行号漂移。临时脚本已删，不作为产品实现交付。

## 根因分析

### #1：认证、租户解析、对象授权之间没有可信连接

- 第一次偏离：`backend/server.py:305–313` 按 auth、JWT、tenant 注册，Starlette 后注册先执行，因此 tenant 在 JWT 设置 user 之前执行，得到默认空身份。
- `backend/auth.py:61–64` 未配 ADMIN_API_KEY 放行全部；有 key 时只比 key hash，JWT 即使已验证也会在内层 auth 被拒。
- `backend/middleware/jwt_middleware.py:103–106` 对 `sk-` 直接跳过，ApiKeyManager 实际生成 `sk-graphrag-`，下方 validate 分支不处理正常管理 key；无 key配置时其不认证也可进入资源路由。
- JWT 接受有签名的 refresh token 当 access token，未强制 exp/sub/issuer/type；内置开发 secret 不能成为生产默认。有效签名只证明签发来源，不能让失效用户或陈旧成员关系继续授权。
- tenant 使用客户端 X-Project-Id，没有验证项目存在/归属组织/活跃状态，也没有因缺少会员拒绝。`TenantService.get_user_orgs()` 无会员返回虚构的 default/org_admin，不能作为授权依据。解析异常被吞掉并回退 scope。
- 文档和任务对象没有 owner_user_id/org_id/project_id，ingest 后 add_doc 也不保留它们；documents/status/query 不检查 Request.user/tenant。
- `_check_scope` 仅看 path 前缀，read:catalog 可以匹配 DELETE documents；粗粒度 scope 不能替代 HTTP method 和资源授权。

现有字段来源：JWT.user_id 来自验证后的 sub；roles 来自签名 claim；User 模型有 user_id/roles，无 org。Project 有 project_id/org_id/created_by/is_archived；Organization 有 org_id/is_active；OrgMembership 有 org_id/user_id/role，移除成员写 removed_at 并由 get_member 排除。ApiKeyRecord 有 created_by/scopes/revoked/expires_at，**没有组织项目绑定字段**。请求体 user_id、org_id、roles 及任何同名 header 均不可建立身份；X-Project-Id 仅作选择器。

### #2：文档选择参数没有进入任何检索边界

`routes/query.py:247` `_get_agent()` → 全局 `_build_agent(G_grounded)` → `_load_all_kgs()` 全盘聚合 → 工具闭包访问全部节点。req.document_id 仅在 `:311` metadata 处使用。sources 又从全局 G_grounded 读取，存在重载竞争。`kg_store.py:462–485` 有 org/project 路径过滤但无授权文档白名单；org/project 任一缺失时仍回退全局目录。节点加载未统一写真实 document_id/version，dN_ 是目录顺序编号，不适合作资源归属。

### #3：唯一任务标识在落盘前被截断

`worker.py:1154–1157,1178–1181` 两个 MinerU 入口使用 task_id[:8]；`routes/ingest.py` 三个入口生成 ingest_ + 8 hex。保留的 8 字符包含 7 字符固定前缀，随机空间由 2^32 降为 16。`mineru_client.download_and_extract:419` exist_ok=True 加 unzip -o 允许覆盖，成功前亦可见半成品。

### #4：缓存命中只验证目录形状

`worker.py:1117–1141` 仅检查 full.md 与 content_list 存在，按名字倒序挑选；`:282–287` 接受客户端开启此全局扫描。没有输入哈希、解析参数、模型/版本或租户绑定。用户 opt-in 无法证明数据相等。

### #50：未知 ID 先触发删除，再更新元数据

`routes/documents.py:63–89` 在查找存在性和授权前直接删目录和遍历上传文件。`doc_id.replace('doc_', '')` 对 doc_ 得空字符串，`fname.startswith('')` 恒真。即使修复空字符串，前缀猜测仍不是精确资产归属。

## 修复方案

### 最小授权策略（实现前写入有效契约）

1. 使用单一凭据分派入口，外层验证凭据 → 解析可信 tenant → 路由授权。避免两个 middleware 对同一 bearer 各自作互斥判定。必须保护全部资源路径，未配置认证不能默认公开；开发 bypass 如保留须显式配置且生产禁止。白名单精确匹配，refresh 仅在 refresh 端点消费。
2. JWT 必须校验签名、固定算法/issuer、必需 sub/exp、access 类型，拒绝 refresh、空 sub、开发 secret 的生产配置。用户仍活跃和当前成员权限从服务端记录取得；测试只用临时生成的签名密钥。
3. 正常 API key 必须走 ApiKeyManager.validate，真实检查撤销、有效期；scope 同时约束 method 和 path。不能因 sk- 字样直接信任。明确旧 ADMIN_API_KEY 为服务管理员 principal（不能默认是匿名用户）。受限 key 复用 created_by 的真实活跃用户成员关系并应用 scope 交集，或没有明确归属则拒绝资源操作；不将所有 API key 变成 admin，不从请求声明中补 org/project。
4. tenant：X-Project-Id → get_project → derive project.org_id → get_org 与 get_member(principal.user_id)；拒绝不存在、归档、停用、跨组织和非成员。无 header 时仅从真实有效成员组织中选默认项目，不能使用 get_user_orgs 的伪造 default 行。membership 加载失败 fail closed。
5. 将 owner_user_id/org_id/project_id 写入 task，传入 background worker，并在 doc 发布时复制；必须由 Request 的验证上下文生成。角色最小矩阵：org_viewer 可读/query/status；org_editor 可 ingest 并管理允许的项目文档；org_admin 可项目文档管理；全局 admin 可审计管理。具体 delete 权限以本次明确契约为准，不以路径 scope 推断。
6. 共享 authorize_document / authorize_task，在列表过滤、下载、删除、chunk_count、query、status 都使用。精确对象不存在或不可见统一404，未认证401、已认证无操作能力403。旧对象缺归属字段时**仅已认证全局 admin 可读/管理**，不能自动赋 default 公开。主 RAG、graph、export 若仍全局读取，要么接同一白名单，要么暂时限admin，不能保留绕过通道。

### #2：每请求固定授权图和来源快照

before：`agent = _get_agent()`；metadata.document_id=req.document_id。

after（示意）：

```python
docs = authorized_documents(request, operation='query')
if req.document_id:
    docs = [authorize_document(request, req.document_id, 'query')]
snapshot = load_document_snapshot(docs)  # 仅逐个精确目录，不扫描全局
agent = _build_agent(snapshot.graph)
result = _invoke_legacy_agent(agent, req.query, language=req.options.language)
sources = extract_sources(result, snapshot.graph)
```

使用现有 KgVersionManager 读取每个授权文档 active_version，统一 canonical doc_id 与目录映射，不能在裸id和doc_之间反复猜测。载入节点/来源注入真实 document_id、version；SourceNode 增可选字段兼容旧客户端。metadata 改为实际文档集合/版本，禁止伪造固定 doc_a1b2c3d4。没有 document_id 时查询全部**授权**文档，不是全库；没有授权文档返回明确无数据且不调用 LLM。工具、邻居搜索、sources 必须共用本请求 snapshot。不要根据 dN_ 前缀推断归属；全局遗留平面 KG 不能安全拆分时仅允许admin的全库模式，不让指定doc查询偷偷回退它。

### #3：独占 staging 与原子发布

所有 ingest 入口生成 ingest_ + 完整 uuid4().hex；两 worker 入口移除 [:8]。download_and_extract 内在 output/mineru 下创建带 task UUID 和 attempt UUID 的独占 staging；下载、解压及最小产物校验完成后，在同一文件系统 rename 到完整task目录。目标已存在须拒绝覆盖或验证同任务manifest后明确幂等返回，不能 exist_ok=True/unzip -o 到已发布路径。失败仅清理本次 staging；重试重新生成 attempt，旧成功目录不可覆盖。任务ID若来自非服务端调用也要验证格式并检查路径包含关系。

### #4：先移除不安全复用

最小修复：worker 不再调用 `_find_cached_mineru_output()`，允许字段为兼容保留但 true 时在产生副作用前返回明确4xx（或按约定忽略且绝不复用）；不得仅改默认值。删除误导性 hint 和文档。更完整缓存需要 tenant+输入内容 SHA256+标准化解析配置+解析器/模型版本的 manifest，并核验产物哈希，属于后续功能。旧缓存没有 manifest 时绝不能自动迁移为命中。更新现有“应选择字典序目录”测试，改断言无关产物永不复用。

### #50：先精确查授权记录，再删资产

before：遍历 fname.startswith(doc_id.replace(...))。

after：`doc=authorize_document(request, doc_id, 'delete')`，仅删 doc.filepath 及记录的精确 kg_path/assets。每项用 resolve 与允许根的 commonpath 判断，拒绝 symlink/junction 指向根外；URL/外部本地原始资料不得视为应用拥有的上传资产。去掉目录双前缀猜测和 uploads 扫描。对历史记录没有资产清单的情况只清理已记录且受控的 filepath/确定KG目录，不猜测其他文件；未知/doc_立即404且零副作用。清理失败不能谎报全部 deleted，最小允许报告失败并保留可重试记录。删除后撤权/失效全局运行时与主 RAG，否则已删资料还可查询。

## 真实本地依赖回归设计

使用 backend 独立 Python 环境与 pytest；PYTHON_DOTENV_DISABLED=1。所有 stores/uploads/mineru/KG/tenant/key/user/audit 根指向 pytest tmp_path，禁止打开现有 output/资料。注意 TenantService(base_dir=...) 当前仅建目录，读写仍使用 ORGS_DIR/PROJECTS_DIR/MEMBERS_DIR 全局量，测试必须完整配置这些根，或先修为实例路径；不能误写真实 tenants。

- 真实 FastAPI/Starlette middleware + HTTPX/TestClient，不替换认证函数。创建临时用户、组织、成员、项目及 API key JSON；真实 JWT签名验证。断言无凭据/篡改/过期/refresh/未知sk key均拒绝；合法JWT与admin key均能进入；read:catalog key不能DELETE；撤销key和移除成员后立即失权。替换 Request.state 的测试不证明认证闭环。
- A/B两个组织、各两个项目，真实JSON文档/任务与上传文件。列表/下载/chunk_count/status/query/DELETE 对跨组织、跨项目、伪造body user_id、伪造X-Project-Id、未知/归档project、缺成员/已移除成员返回预期拒绝。旧无owner对象只有admin可见。未知 doc_、短prefix、合法单doc删除均确认其他哨兵文件及metadata字节不变。
- 真实 KgVersionManager 与 NetworkX、两文档不同唯一词，验证只加载授权图，邻居跨文档也不可达；active版本变化不会让sources引用其他snapshot。LLM若用本地可控服务，只替换供应商边界，不替换授权/loader/检索工具；另行需要真实供应商集成时记录为独立验收，不能称本地stub等于云端实测。
- MinerU下载用本地 HTTP fixture 服务提供两份真实合成 ZIP，真实解压/文件系统，两个首8位相同任务并发，断言目录不同、内容不混、没有共享result.zip。重复task、重试、下载中断、缺full.md/非法产物必须不发布。任务目录/staging目录只检查tmp_path。
- 默认和显式缓存true、各种URL/file入口、直传/OSS失败矩阵：旧无关缓存保持不变，永不进入bridge/入库，不返回DONE。修复后补红测再运行既有worker回退/错误测试；如移除cache参数需要更新契约和调用方兼容测试。

建议命令：在 backend 下 `.venv/Scripts/python.exe -m pytest tests/test_p0_authorization.py tests/test_p0_document_scope.py tests/test_p0_mineru_isolation.py tests/test_p0_safe_delete.py -q --basetemp tests/_tmp_p0_20261012`，文件为拟新增，当前未执行。相关全量生产代码行/分支覆盖率分别≥90%及真实依赖检查仍是提交前独立门槛，本文不构成提交授权。

## 规范文档检查

企业蓝图 §7.1 已要求项目隔离，但缺失安全验证/旧数据/服务key/默认组织的明确语义，示例直接信任header亦有缺陷。应回流：认证分派顺序与fail closed、JWT access/refresh类型、API key method+resource scope、项目选择器真实成员验证、旧无归属仅admin。

Backend API query/ingest/documents/status 契约补实际文档/版本来源、无文档参数范围、未知ID零副作用、受控资产清单、完整任务UUID与原子产物发布、禁无匹配缓存。无需为普通Bug重做全部蓝图；完成规范回流后按治理要求归档历史排障记录，保持本文件作为当前交接证据。
