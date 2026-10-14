# 历史评估后端复核：1–20、50–54

> 同日修复后：#1/#2/#3/#4/#50的最新状态、代码和实际测试见 [P0核验](../testing/2026-10-12-p0-verification.md)。下表保持修复前审计证据，不能据此断言风险仍开放；其他条目没有自动关闭。

审计日期：2026-10-12。对象为当前工作区（包含未提交代码），不是仅 HEAD。本文不修改实现，不读取 `.env`，不调用外部服务。历史材料仅作为待核实的问题列表。

## 实际执行的验证

在 backend 目录设置 `PYTHON_DOTENV_DISABLED=1` 后执行：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_worker_upload_fallback_chain.py tests/test_worker_mineru_errors.py tests/test_log_redaction.py tests/test_supply_chain.py -q --basetemp tests/_tmp_assessment_backend_20261012
```

结果：**56 passed、1 failed、3 warnings，35.92 秒**。失败为 `tests/test_supply_chain.py:111–150::test_code_imports_are_declared` 将 `research/test_deepseek_scope_pilot.py` 的 pytest 导入判为未声明运行依赖；pytest 实际在 pyproject 的 dev 组，故这是扫描边界/依赖组识别问题，不代表 langextract 或 oss2 仍缺失。警告还指出本环境不识别 pytest 的 `timeout` 配置（未安装或未加载 pytest-timeout）。传输层测试 monkeypatch subprocess，缓存测试替换 worker 接缝，属于隔离回归，**不是项目铁律要求的真实供应商集成验收**。

下表“无专项实测”表示本轮未执行相应运行时复现，不表示全仓库不存在相关测试。静态明确的缺陷仍可判未修复；对云端桶权限、SSO 部署、网络可达性不作推断。

## 逐项结果

| 原编号 | 状态 | 当前代码证据（相对仓库路径及行号） | 测试证据与不足 | 剩余优先级及动作 |
|---|---|---|---|---|
| 1 | 部分修复 | `backend/server.py:305–313` 已安装 API Key、JWT、tenant middleware；`backend/auth.py:61–64` 未配管理密钥时允许所有请求；`backend/routes/documents.py:20–37,63–105` 全局列表和删除不检查用户/租户；`backend/routes/query.py:238–250` 未绑定授权文档。 | `test_phase4.py:338–365` 测试底层 tenant 路径过滤，不证明原 documents/query API 使用该过滤；未实测权限矩阵。 | 🔴 P0：统一资源授权，生产 fail closed；核实 SSO/API Key 两套中间件组合。 |
| 2 | 未修复 | `backend/routes/query.py:247–250` 取全局 Agent；`:311` 仍仅把 req.document_id 写响应，未作为检索范围。 | research scope 测试不覆盖此旧 `/query` 路由；无专项实测。 | 🔴 P0：请求绑定授权文档集合，sources 保存真实文档及版本。 |
| 3 | 未修复 | `backend/worker.py:1154–1157,1178–1181` 两个 MinerU 入口仍用 `task_id[:8]`；`routes/ingest.py:215,248` ID 以 ingest_ 开头，前 8 字符仅一位随机值。 | 传输错误测试通过，但不覆盖目录独占/并发冲突；无碰撞写盘实测。 | 🔴 P0：完整 UUID 独占目录、原子发布。 |
| 4 | 部分修复 | `backend/routes/ingest.py:166–170,267` 缓存默认关闭；`worker.py:282–287,1117–1141` 显式开启仍按目录字典序取无文件匹配产物。 | `test_worker_upload_fallback_chain.py:85–110` 默认关闭及显式开启测试本轮通过；`:179` 测试仍确认字典序选择。 | 🔴 P0：移除无哈希匹配的复用入口，或按内容哈希+配置版本校验。 |
| 5 | 部分修复 | `worker.py:244–260,1161–1177` 默认直传 MinerU，失败仍走 OSS；`oss_uploader.py:55–63` 返回无签名 URL；`backend/pipeline.py:151–154` CLI 仍上传 file.io。 | 直传优先/OSS 回退隔离测试通过；实际桶 ACL、留存和 CLI 外发未实测。 | 🟠 P1：所有入口采用受控供应商、私有对象短时签名，清理旧 CLI 外发。 |
| 6 | 未修复 | `backend/routes/ingest.py:187–213` 除 http(s) 还允许任意存在的本地路径；`mineru_client.py:427–428` 对上游 zip_url 直接 curl 下载，无 allowlist/IP/大小检查。 | 未进行内网探测；SSRF 的实际网络可利用性待部署验证。 | 🟠 P1：禁止不可信本地路径，统一 URL、DNS、重定向和出站约束。 |
| 7 | 未修复 | `backend/routes/ingest.py:244–251` await file.read() 后才检查 MAX_FILE_SIZE。 | 无并发大文件内存压力实测。 | 🟠 P1：网关请求体限额，分块累计写入和超限清理。 |
| 8 | 未修复 | `backend/mineru_client.py:419–431` 仍 unzip -o，仅设置 timeout，未检查成员路径/类型、体积、数量、压缩比。 | 无恶意 ZIP 解压实测；不运行会损坏资料的样本。 | 🟠 P1：校验 ZIP manifest、限制资源、失败清理。 |
| 9 | 未修复 | `backend/security.py:9–14,30–34,41–44` token/限流仍进程内并 localhost 绕过。 | 日志脱敏通过不能证明多实例 token 和限流一致；未实测代理拓扑。 | 🟠 P1：共享限流、按授权文档签发短期凭据、明确可信代理。 |
| 10 | 部分修复 | `logging_config.py:97,189–191,245` 增加结构化脱敏；`mineru_client.py:162–169` bearer 仍放进 curl 参数；`worker.py:1096–1112` 仍记录路径/URL。 | `test_log_redaction.py` 全部通过，覆盖 token/嵌套/traceback/预签名 URL；不覆盖进程参数读取，普通路径/URL并未全部清除。 | 🟠 P1：HTTP 客户端替代敏感 argv，减少路径和对象日志。 |
| 11 | 部分修复 | `backend/pyproject.toml:34–42,58–59` 声明 oss2、langextract 本地 source，存在 uv.lock；requirements 解释本地包使用方式。 | requirements 一致性测试通过；导入清单测试因研究测试误收集失败；未新建干净 venv，更未真实入库。 | 🟡 P2：修正扫描边界，完成 clean uv sync 和真实入库验收后关闭。 |
| 12 | 部分修复 | `backend/routes/ingest.py:23–54,269,279` 新增 JSON 保存但仍 Web BackgroundTasks 和本进程字典；`:292` 还直接对 loaded ISO 字符串做日期相减。 | 未做重启/多 worker 状态恢复实测。 | 🟠 P1：事务任务表和独立 worker，租约/恢复/取消；修复恢复后 datetime 反序列化。 |
| 13 | 未修复 | `backend/routes/__init__.py:38–42,48–60` 线程锁+直接覆写；`backend/kg_builder.py:362–365` nodes/edges 分别覆写；`routes/ingest.py:49–51` 任务 JSON 同样直接写。 | 未做进程中断与多进程写入实测；版本目录存在不等于写入事务。 | 🟠 P1：事务元数据，校验完版本后原子切换。 |
| 14 | 未修复 | `backend/routes/ingest.py:113–134` DONE 先保存，后 add_doc；`:146–152` reload 失败只记日志。 | 未实测持久化或 reload 故障；现有 degraded 测试不关闭此提交顺序问题。 | 🟠 P1：committing 状态，仅在可查询版本发布后 DONE。 |
| 15 | 未修复 | `backend/routes/documents.py:63–105` 删除目录/remove_doc/发事件，不调用 reload_kg 或 invalidate_rag_runtime；`routes/query.py:185–199` Agent 持续缓存。event_bus 为 webhook 投递，未见该事件联动本地缓存失效。 | 未实测删除后查询；事件发布本身不能证明撤回生效。 | 🟠 P1：tombstone 撤权优先，全部运行时失效，测试在途请求。 |
| 16 | 未修复 | `backend/routes/documents.py:68–89,101–105` 清理异常吞掉仍 deleted，没有 OSS/解析产物资产清单。 | 无端到端销毁验收。 | 🟠 P1：精确资产清单、可重试清理，区分 pending/failed/deleted。 |
| 17 | 部分修复 | `backend/routes/query.py:87–94` swap globals 已加锁；`:247,263–300` 请求取 Agent 后从全局 G_grounded 拼来源，构建发生在锁外且无发布版本顺序校验。 | 无并发 reload 与查询引用一致性实测。 | 🟠 P1：每请求固定 graph+agent+version 快照，发布序列化。 |
| 18 | 未修复 | `backend/kg_store.py:485` 聚合查询仍按 doc_count 使用 dN_；`backend/routes/graph.py:101–119` 前端图按 indexed_docs 的 di 编号，顺序来自另一列表。 | 无增删文档稳定 ID 回归实测。 | 🟠 P1：统一文档 stable_id/版本/entity_id，图和证据共用。 |
| 19 | 未修复 | `backend/routes/query.py:247–250` 初始化仍在 try 外；`:259` hasattr(messages[-1], ...) 的求值发生在空列表条件前。 | `test_route_error_boundary.py:24` 存在错误脱敏测试但本轮未执行；不等于空消息/初始化异常成功处理。 | 🟠 P1：先判空并校验终态，将初始化/解析纳入错误边界。 |
| 20 | 部分修复 | `backend/mineru_client.py:300–327,388–415` 本地上传有限重试、轮询有限次并区分 retryable；`:446–475` URL 提交无同等重试；worker 上游 handle 仅内存，未形成任务总截止。 | `test_worker_mineru_errors.py` 本轮通过，覆盖401/429/超时/轮询失败/本地上传选择性重试；不覆盖 crash-resume、总 deadline。 | 🟠 P1：持久化 provider_task_id，统一 deadline 和阶段重试。 |
| 50 | 未修复 | `backend/routes/documents.py:63–89` 不校验存在；`:80` doc_id.replace("doc_", "") 对 doc_ 得空字符串，所有 fname.startswith("") 成立。 | 静态确定可达逻辑；本轮未在真实 uploads 执行删除复现。 | 🔴 P0：先存在/授权校验，404，禁止前缀猜测，精确资产删除。 |
| 51 | 未修复 | `backend/routes/ingest.py:248–251` 路径仍拼客户端 file.filename，无服务端纯 UUID 存储键或目录边界校验。 | 未对真实 uploads 执行特殊名称/符号链接写入试验。 | 🟡 P2：UUID+允许扩展名，原名仅 metadata，拒绝链接。 |
| 52 | 未修复 | `backend/server.py:18`、`backend/worker.py:16`、`backend/oss_uploader.py:14` 仍 load_dotenv override=True。 | 本轮用 PYTHON_DOTENV_DISABLED=1 防止读取实际 .env；未读取敏感配置。 | 🟡 P2：集中 Settings，环境注入优先，生产禁覆盖。 |
| 53 | 部分修复 | `backend/kg_store.py:294–315` 有版本管理器；`backend/routes/ingest.py:194,215,248` 每次仍新 task/doc，未以内容哈希/幂等键查重，worker 产物目录按任务 ID。 | 未执行重复提交/重复计费实测；版本类存在不证明入口复用稳定文档。 | 🟡 P2：租户+哈希+配置版本去重，稳定文档 ID，明确 active_version 发布。 |
| 54 | 未修复 | `backend/routes/ingest.py:263` 传 enable_ocr；`mineru_client.py:210` 读取 is_ocr，URL payload `:453–458` 未含 OCR；`worker.py:186,204` PDF 页数仍 len(sections)。 | 传输错误测试不验证 OCR/页数合约；未真实解析验收。 | 🟡 P2：统一强类型 option 映射；以 page_idx 或解析元数据统计页数。 |

统计（25 项）：已修复 0，部分修复 9，未修复 16，已不适用 0，待验证 0。此统计采用“历史条目的整个风险闭环”口径；部分修复并不否认已完成的默认直传、默认禁缓存、日志脱敏、依赖声明等工作。部分条目的部署效果仍待验证，不能将所有单元测试通过推定为企业上线验收。

## 优先改进与示例（建议，未修改实现）

1. P0 先处理目录碰撞、未知 ID 批量删除、跨文档查询及资源授权，再关闭无匹配缓存开关。
2. P1 完成任务事务和发布顺序、删除撤回、请求快照，再处理下载解压约束、共享限流、敏感 argv。
3. P2 补 OCR/页数、配置和文件名规范、幂等；修复依赖扫描误报并做干净环境验收。

目录修复 before/after：`task_id[:8]` → `task_id`（随后使用独占创建和原子发布，不能只改字符串即宣称完整关闭）。删除 before/after：`fname.startswith(doc_id.replace("doc_", ""))` → `doc = lookup_authorized_document(doc_id)`，不存在返回404，仅迭代 `doc.assets` 精确删。空消息 before/after：`hasattr(messages[-1], "content")` → 先 `if not messages: raise ...`，再读取末消息并校验类型。来源快照 before/after：独立读取 `_agent` 和 `G_grounded` → 在锁下取得单一不可变 snapshot，在检索和来源组装全程持有它。


