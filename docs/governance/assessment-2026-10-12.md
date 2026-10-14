# GraphRAG 历史评估修复进度核查（2026-10-12）

## 2026-10-13 后续整改增量核实（覆盖对应历史状态）

本段是已验证增量，不重新计数全部62项；下文矩阵保留原审计快照。完整最终阶段代码/测试/扫描及快照见[双90验收报告](../testing/2026-10-13-to90-verification.md)，后端1496通过、前端122通过、rag_eval74通过，三个完整相关子项目分别行/分支双90。整体仍受Chroma4唯一公告及实际发布验证阻塞，不以覆盖率关闭全部业务缺口。

| 原编号 | 当前增量状态 | 证据与剩余边界 |
|---|---|---|
| 40 | 部分修复 | 后端uv锁/新独立候选版本一致；Docker/CI文本消费锁，前端Node22/pnpm冻结安装与build通过。GraphPage公网vis-network/CDN、SBOM及实际镜像/发布仍未完整关闭，不能称完整供应链已修。 |
| 41 | 部分修复 | frontend完整29文件含正式widget测试/覆盖脚本及真实Chromium通过，rag_eval完整12文件及后端完整90文件均双90；独立质量审查通过。可信远程CI/保护分支、ESLint吞失败及真实供应商验收仍未闭合。 |
| 56 | 部分修复 | GraphPage effect加入visReady/viewMode，真实红测与浏览器首次初始化/切回通过；不声称已解决轮询数据更新导致重建及视口保留的全部产品问题。 |
| 57 | 部分修复 | UploadPage卸载/取消清timer，按任务代际隔离晚到入库和轮询回调；真实红绿、完整前端122及独立18专项。页面刷新后的任务持久化及阶段done语义未由本轮完整验收。 |
| 62 | 已修复（当前本地前端锁范围） | react-router迁移至7.18.4，Node22冻结安装、完整345依赖官方audit零公告、路由与真实Chromium通过。原npm锁归档、pnpm为唯一有效锁；不外推外部CDN或生产部署安全。 |

新增本轮实际发现并关闭：跨组织归档、飞书卡片构造500、缺签名/URL验证绕过、错误签名密钥、widget来源HTML注入、KG保留/高水位及表格查询注入、索引失败写空/测试污染。各项代码及红绿/独立证据见最终阶段报告。飞书重放、研究身份及外部供应商/部署仍明确开放，原其余条目未据“测试全通过”自动改成已修复。

> **同日修复后更新**：下文保留首次只读审计的历史快照。后续已处理#1/#2/#3/#4/#50，五项原风险在本地适用范围标为“已修复”，详见 [修复后代码与测试证据](../testing/2026-10-12-p0-verification.md)。P0专项84通过，全量705通过/22失败，双覆盖率未验证，无提交。其余57项未重新评定，原计数不得当作修复后计数；完整企业/供应商验收未通过。

核查对象为 D:/graghRAG-agent 当前工作区，包含未提交实现与测试。HEAD：`46b202c3e400741fd569f024412c0745f224a538`。仅审查并生成报告，未修复业务代码、未提交。源文件哈希见 [工作区快照](assessment-2026-10-12-source-manifest.json)。

## 结论与口径

62 项具体问题：**已修复 2、部分修复 30、未修复 28、已不适用 0、待验证 2**。已修复的两项 #46/#47 是 Skill 元数据/引用及指令优先级问题；不能解释为企业核心业务已经验收。大量增量实现存在，但原问题跨入口、跨生命周期的闭环仍不完整。

- 已修复：原条目所述缺陷已关闭，当前代码与本轮适用验证支持；不扩张到原条目之外的行为。
- 部分修复：有明确增量实现，但原条目仍有缺口、旧开放入口仍残留或必要验收不足。
- 未修复：当前代码可直接确认原风险逻辑仍在。可以凭静态证据判断，不必执行有破坏性的复现。
- 已不适用：受影响入口或前提已移除且有证据；本轮没有此类条目。
- 待验证：受影响发行包、部署条件或漏洞数据库无法从当前工作区确定。其他状态里的“待实测”不意味着整项状态应改为待验证。

来源主线为桌面 GraphRAG(1).md；其仓库副本已校验哈希相同。企业评估方案另有 D01–D17，已单列 [17项架构建议对照](assessment-2026-10-12-enterprise.md)，避免与具体缺陷编号混用。PDF文本提取异常，未可靠读取其正文，本轮不声称覆盖其中可能独有的问题。

本轮不读取 .env，不运行真实删除/外发/付费模型请求，不执行生产部署和灾备演练。测试文件存在、mock回归通过、历史报告通过都不等于真实依赖集成验收。报告中的行号针对本轮工作树，后续编辑会移动。

## 剩余优先级

1. **P0：先保护数据与授权边界。** #50 未知 `doc_` 可使上传文件匹配前缀为空；#3 `ingest_` 任务 ID 截前8字符仅一位随机值；#1/#2 缺资源授权、旧查询不限定文档；#4 显式启用缓存仍可复用无内容匹配的旧解析结果。禁止用“新主链已有改进”关闭仍开放的旧入口风险。
2. **P1：恢复正确的提交、撤回与引用。** #12–18 任务状态、原子持久化、DONE发布顺序、删除失效、图/Agent快照和稳定ID；#24–29 原文映射、跨span和证据持久化；#22/#31 保留方向、多关系与完整证据路径。
3. **P1：统一查询执行与交付验收。** #34 伪来源、#35 两个async查询中的同步调用；#6–10 下载/上传/解压与凭据暴露；#37/#40/#41 就绪探针、实际构建用锁和真实依赖回归。刷新主服务保留集与发布门禁，逐结论事实支持不能由引用ID合法率替代。
4. **P2：产品体验和工程整理。** #51–58 文件名、配置、幂等、OCR/页数、响应真实性、画布、上传轮询、超时及原件定位；独立Skill发行和漏洞状态按 #45–49/#60–62 单独验收。

建议验收顺序：未知文档删除必须404且原件不变；并发入库目录独占；跨租户与跨文档访问被拒；失败/重启任务可恢复；入库成功后新版本可查询；删除后所有入口与在途请求不再返回撤回证据；字符位置可逐条回到原件；最后再做容量、成本和交付演练。

## 实际验证结果

| 执行集 | 本轮结果 | 边界 |
|---|---|---|
| worker上传回退、MinerU错误、日志脱敏、供应链4模块 | 56 passed / 1 failed | 传输与接缝有monkeypatch；不是真实供应商集成 |
| retrieval_stage_metrics + eval_keyword_normalization | 8 passed | 排名/指标局部测试，不代表真实模型问答质量 |
| Phase 2，排除Endpoints | 28 passed / 5 failed / 6 deselected | 本地文件测试；目录/导出/质量失败，路径夹具与生产实现的根因未独立验证 |
| 交付审查单独重跑供应链 | 2 passed / 1 failed | 与第一行供应链测试重叠，不重复累计通过数 |
| Harness结构validator | exit 0 | 仅结构，不是真实宿主流程与Guard阻断 |
| RAG扩大集合两次 | 中止 | 长时间无输出，不能计通过；详见专题报告 |

供应链失败：扫描将 research/test_deepseek_scope_pilot.py 的 pytest 导入归入运行依赖，pytest 实际在dev组；这是扫描边界/组口径问题，不能当作真实入库缺 langextract/oss2 的证明。环境还报告未知 timeout 配置，不能假定 pytest-timeout 已生效。

[Phase 2执行记录](assessment-2026-10-12-phase2-test-record.md)；完整命令和测试限制见三个专题报告。[历史release gate](../../iteration-2/eval-2-existing-components/rag_eval/release_gate_report.json)生成于2026-07-04且passed=false，仅供历史回查，不代表当前版本实测结果。本轮没有重新跑真实模型、浏览器、容器、TLS、云桶ACL、备份恢复/回滚或漏洞数据库刷新。

## 62项逐项矩阵

代码证据中的路径相对仓库；行号可在对应专题报告与当前文件中核对。测试栏明确区分本轮通过、覆盖线索与缺少验收。

| 原编号 | 状态 | 剩余优先级 | 当前代码证据与判断 | 测试证据、局限与剩余工作 |
|---|---|---|---|---|
| 1 | 部分修复 | 🔴 P0：统一资源授权，生产 fail closed；核实 SSO/API Key 两套中间件组合。 | `backend/server.py:305–313` 已安装 API Key、JWT、tenant middleware；`backend/auth.py:61–64` 未配管理密钥时允许所有请求；`backend/routes/documents.py:20–37,63–105` 全局列表和删除不检查用户/租户；`backend/routes/query.py:238–250` 未绑定授权文档。 | `test_phase4.py:338–365` 测试底层 tenant 路径过滤，不证明原 documents/query API 使用该过滤；未实测权限矩阵。 |
| 2 | 未修复 | 🔴 P0：请求绑定授权文档集合，sources 保存真实文档及版本。 | `backend/routes/query.py:247–250` 取全局 Agent；`:311` 仍仅把 req.document_id 写响应，未作为检索范围。 | research scope 测试不覆盖此旧 `/query` 路由；无专项实测。 |
| 3 | 未修复 | 🔴 P0：完整 UUID 独占目录、原子发布。 | `backend/worker.py:1154–1157,1178–1181` 两个 MinerU 入口仍用 `task_id[:8]`；`routes/ingest.py:215,248` ID 以 ingest_ 开头，前 8 字符仅一位随机值。 | 传输错误测试通过，但不覆盖目录独占/并发冲突；无碰撞写盘实测。 |
| 4 | 部分修复 | 🔴 P0：移除无哈希匹配的复用入口，或按内容哈希+配置版本校验。 | `backend/routes/ingest.py:166–170,267` 缓存默认关闭；`worker.py:282–287,1117–1141` 显式开启仍按目录字典序取无文件匹配产物。 | `test_worker_upload_fallback_chain.py:85–110` 默认关闭及显式开启测试本轮通过；`:179` 测试仍确认字典序选择。 |
| 5 | 部分修复 | 🟠 P1：所有入口采用受控供应商、私有对象短时签名，清理旧 CLI 外发。 | `worker.py:244–260,1161–1177` 默认直传 MinerU，失败仍走 OSS；`oss_uploader.py:55–63` 返回无签名 URL；`backend/pipeline.py:151–154` CLI 仍上传 file.io。 | 直传优先/OSS 回退隔离测试通过；实际桶 ACL、留存和 CLI 外发未实测。 |
| 6 | 未修复 | 🟠 P1：禁止不可信本地路径，统一 URL、DNS、重定向和出站约束。 | `backend/routes/ingest.py:187–213` 除 http(s) 还允许任意存在的本地路径；`mineru_client.py:427–428` 对上游 zip_url 直接 curl 下载，无 allowlist/IP/大小检查。 | 未进行内网探测；SSRF 的实际网络可利用性待部署验证。 |
| 7 | 未修复 | 🟠 P1：网关请求体限额，分块累计写入和超限清理。 | `backend/routes/ingest.py:244–251` await file.read() 后才检查 MAX_FILE_SIZE。 | 无并发大文件内存压力实测。 |
| 8 | 未修复 | 🟠 P1：校验 ZIP manifest、限制资源、失败清理。 | `backend/mineru_client.py:419–431` 仍 unzip -o，仅设置 timeout，未检查成员路径/类型、体积、数量、压缩比。 | 无恶意 ZIP 解压实测；不运行会损坏资料的样本。 |
| 9 | 未修复 | 🟠 P1：共享限流、按授权文档签发短期凭据、明确可信代理。 | `backend/security.py:9–14,30–34,41–44` token/限流仍进程内并 localhost 绕过。 | 日志脱敏通过不能证明多实例 token 和限流一致；未实测代理拓扑。 |
| 10 | 部分修复 | 🟠 P1：HTTP 客户端替代敏感 argv，减少路径和对象日志。 | `logging_config.py:97,189–191,245` 增加结构化脱敏；`mineru_client.py:162–169` bearer 仍放进 curl 参数；`worker.py:1096–1112` 仍记录路径/URL。 | `test_log_redaction.py` 全部通过，覆盖 token/嵌套/traceback/预签名 URL；不覆盖进程参数读取，普通路径/URL并未全部清除。 |
| 11 | 部分修复 | 🟡 P2：修正扫描边界，完成 clean uv sync 和真实入库验收后关闭。 | `backend/pyproject.toml:34–42,58–59` 声明 oss2、langextract 本地 source，存在 uv.lock；requirements 解释本地包使用方式。 | requirements 一致性测试通过；导入清单测试因研究测试误收集失败；未新建干净 venv，更未真实入库。 |
| 12 | 部分修复 | 🟠 P1：事务任务表和独立 worker，租约/恢复/取消；修复恢复后 datetime 反序列化。 | `backend/routes/ingest.py:23–54,269,279` 新增 JSON 保存但仍 Web BackgroundTasks 和本进程字典；`:292` 还直接对 loaded ISO 字符串做日期相减。 | 未做重启/多 worker 状态恢复实测。 |
| 13 | 未修复 | 🟠 P1：事务元数据，校验完版本后原子切换。 | `backend/routes/__init__.py:38–42,48–60` 线程锁+直接覆写；`backend/kg_builder.py:362–365` nodes/edges 分别覆写；`routes/ingest.py:49–51` 任务 JSON 同样直接写。 | 未做进程中断与多进程写入实测；版本目录存在不等于写入事务。 |
| 14 | 未修复 | 🟠 P1：committing 状态，仅在可查询版本发布后 DONE。 | `backend/routes/ingest.py:113–134` DONE 先保存，后 add_doc；`:146–152` reload 失败只记日志。 | 未实测持久化或 reload 故障；现有 degraded 测试不关闭此提交顺序问题。 |
| 15 | 未修复 | 🟠 P1：tombstone 撤权优先，全部运行时失效，测试在途请求。 | `backend/routes/documents.py:63–105` 删除目录/remove_doc/发事件，不调用 reload_kg 或 invalidate_rag_runtime；`routes/query.py:185–199` Agent 持续缓存。event_bus 为 webhook 投递，未见该事件联动本地缓存失效。 | 未实测删除后查询；事件发布本身不能证明撤回生效。 |
| 16 | 未修复 | 🟠 P1：精确资产清单、可重试清理，区分 pending/failed/deleted。 | `backend/routes/documents.py:68–89,101–105` 清理异常吞掉仍 deleted，没有 OSS/解析产物资产清单。 | 无端到端销毁验收。 |
| 17 | 部分修复 | 🟠 P1：每请求固定 graph+agent+version 快照，发布序列化。 | `backend/routes/query.py:87–94` swap globals 已加锁；`:247,263–300` 请求取 Agent 后从全局 G_grounded 拼来源，构建发生在锁外且无发布版本顺序校验。 | 无并发 reload 与查询引用一致性实测。 |
| 18 | 未修复 | 🟠 P1：统一文档 stable_id/版本/entity_id，图和证据共用。 | `backend/kg_store.py:485` 聚合查询仍按 doc_count 使用 dN_；`backend/routes/graph.py:101–119` 前端图按 indexed_docs 的 di 编号，顺序来自另一列表。 | 无增删文档稳定 ID 回归实测。 |
| 19 | 未修复 | 🟠 P1：先判空并校验终态，将初始化/解析纳入错误边界。 | `backend/routes/query.py:247–250` 初始化仍在 try 外；`:259` hasattr(messages[-1], ...) 的求值发生在空列表条件前。 | `test_route_error_boundary.py:24` 存在错误脱敏测试但本轮未执行；不等于空消息/初始化异常成功处理。 |
| 20 | 部分修复 | 🟠 P1：持久化 provider_task_id，统一 deadline 和阶段重试。 | `backend/mineru_client.py:300–327,388–415` 本地上传有限重试、轮询有限次并区分 retryable；`:446–475` URL 提交无同等重试；worker 上游 handle 仅内存，未形成任务总截止。 | `test_worker_mineru_errors.py` 本轮通过，覆盖401/429/超时/轮询失败/本地上传选择性重试；不覆盖 crash-resume、总 deadline。 |
| 21 | 部分修复 | P1 | `backend/kg_builder.py:116–306` 增加 reports_to、owned_by 等 7 类属性关系；但仍保留结构边，模糊/子串推断没有独立事实证据、时间与限定条件，不能证明业务因果。 | 本次未见关系事实支持性专项通过记录；需原文标注三元组集。 |
| 22 | 未修复 | P1 | `backend/services/kg_service.py:26–36` 仍是 nx.Graph，同一对节点 add_edge 覆盖关系，且仅保留 relation，edge_id/properties 丢失。 | 需方向、多边和完整属性往返测试；静态可直接确认。 |
| 23 | 未修复 | P1 | `backend/kg_builder.py:29–43` 每条 extraction 建节点；`backend/services/kg_service.py:59–62` 仅按目录序号加前缀 compose，无跨文档实体对齐。 | 现有索引测试验证召回，不验证实体消歧；需同名异人和同人别名数据集。 |
| 24 | 未修复 | P1 | `backend/bridge.py:32–42` 仅规范化 item，搜索原始 full_md，前 40 字符命中后仍以完整 normalized 长度给 end。 | 表格文本测试不覆盖偏移；需换行/多空格/相同前缀冲突回归。 |
| 25 | 未修复 | P1 | `backend/bridge.py:216–245` extract_section_text strip 后 offsets 仍为 sec.char_start。 | `test_bridge_table_body.py:23–50` 仅测试无前导空白样本；不能证明偏移修复。 |
| 26 | 未修复 | P1 | `backend/bridge.py:54–68` 未匹配仍造连续 Segment；`backend/grounding.py:59–81` 命中 Segment 即 grounded，没有文本匹配真实性校验。 | 需不存在文本不得 grounded 的负例；静态确认残留。 |
| 27 | 未修复 | P1 | `backend/schema.py:30–36` 跨块退回首块；`backend/grounding.py:27` 未知文档 offset=0，`schema.py:7–17` bbox 无校验。 | 需跨页多 span、未知 doc、逆序/越界 bbox 回归。 |
| 28 | 部分修复 | P1 | `backend/bridge.py:76–82,105–115` 已引入 table_body 可检索文本；仍将 HTML 扁平化，未保留单元格 span/表头继承；image/chart 仍主要取 caption（85–98）。 | `test_bridge_table_body.py` 验证表格数值进入抽取输入；未覆盖计算、复杂合并单元格与图像证据链。 |
| 29 | 部分修复 | P1 | `backend/kg_builder.py:325–339` 有 schema_version；末尾新增 lineage 记录。但 `worker.py:167` 仍传空 metadata，`kg_builder.py:331–340` 持久节点不含 char_interval/block_type，`schema.py:65–73` KGNode 本身不含它们。 | 新 evidence_id 的身份校验是局部进步，不能补回原始图节点已丢弃的字符跨度；需从入库到引用端的完整 manifest 回归。 |
| 30 | 部分修复 | P1 | 旧入口 `routes/query.py:113–133` 已用索引查找且有严格上限；新 `retrieval.py:1579` indexed_kg_recall、1716 BM25、1832 RRF、1877 rerank 实现混合排序。枚举/统计问题仍需分页/聚合及业务保留集证明。 | `test_kg_indexed_recall.py:116,142,158,201` 覆盖索引和限额；不证明列表完整率。 |
| 31 | 部分修复 | P1 | `backend/kg_store.py:201–243` 已从遍历当前父节点读关系，修正旧的二跳直接边退化；有 fanout 截断。但返回扁平 neighbors，无 parent/path、方向、每边证据，无法还原完整推理链。 | `test_kg_indexed_recall.py:226` 验证有界遍历；需有序路径及事实边证据测试。 |
| 32 | 部分修复 | P1 | `routes/query.py:118,163–171,219–235` 有结果限额、fanout 和 recursion_limit；`routes/rag_query.py:97–120,306–311` 请求级候选/上下文预算。未见请求预算参数统一控制旧 Agent 调用次数、金额、总截止时间。 | `test_query_budgeting.py:13,28,120,131,172,410` 有配置/截断/传递测试，但不等于统一费用/并发/截止时间。 |
| 33 | 部分修复 | P1 | `prompt_builder.py:24–29` 强制句级引用；`generator.py:1243–1292` 验证引用 ID 是否在上下文，有 canonical ID 精确匹配。但不验证引用是否支持句子事实；旧 /query 也没有逐结论校验。 | `test_query_budgeting.py:512–878` 有特定拒答/反驳回归，部分直接针对历史 Q41/Q49；需独立攻击集与未见业务保留集，不能据此声称提示注入已消除。 |
| 34 | 未修复 | P1 | `routes/query.py:269–295` 仍对所有 content 为字符串的消息解析 JSON，并从答案 regex 抽 ID；没有 ToolMessage/tool_call_id 检验。旧入口在 `server.py:358` 仍注册。 | 主 /rag/query 不再走该来源收集，但旧入口残留须单独关闭或修复；需用户 JSON 伪来源负例。 |
| 35 | 未修复 | P1 | `routes/query.py:238,250` async 中直接同步 invoke；主 `routes/rag_query.py:221,306` async 中直接 generator.generate，同样可阻塞事件循环。 | 需慢模型时并发健康探针和取消测试；静态确认两个入口均残留。 |
| 36 | 部分修复 | P1 / High | frontend/src/pages/QueryPage.tsx:66 读取 docId，108–111 向 API 传 documentId/sessionId；backend/conversation.py:145、160–161、187、398–409 有用户字段、持久化及三轮历史改写；frontend/src/lib/queryContract.test.ts:9–28 检查字段转发（本次未执行）。 | QueryPage:75–94、135–140 仍以全图欢迎语及统计展示文档范围；需明确当前文档范围，补浏览器路由切换、多轮隔离及 TTL 验收。不能以存在 user_id 字段证明隔离已验收。 |
| 37 | 部分修复 | P1 / High | backend/services/health_checker.py:47–90 已有真实 HTTP 探测；backend/routes/health.py:111–134 已纳入缓存结果及 runtime_recovery；但 106–110 仍按密钥长度标组件正常、148 kg_store 固定 ok，探针空缓存时 overall 可 healthy，HTTP 不返回503。test_phase3.py:283–294 只断言状态枚举，未验证坏密钥与就绪拒绝。 | 分离存活与就绪，未知缓存不作为通过；MinerU 探测84行把401/404当ok需修正。 |
| 38 | 部分修复 | P1 / High | backend/server.py:318–322 request_id、379–381 metrics；backend/logging_config.py:112–122 绑定上下文；backend/services/audit_logger.py 已实现审计，test_phase3.py:67–106 有读写/过滤测试；backend/metrics.py:14–48 有请求、耗时及上下文预算；deploy/prometheus/alerts.yml:7–69 有质量、错误率和时延告警。 | 未见完整供应商账单/金额账本与全链路传播验收；告警配置存在不等于已触达演练。本次未执行审计测试。 |
| 39 | 部分修复 | P1 / High | Dockerfile.backend:31–35 非reload启动与healthcheck；docker-compose.yml:10–29 持久卷和容器运行；backend/services/backup.py:78、217–269 备份/恢复/预恢复快照，test_phase2.py:277–320 有备份验证测试；deploy/cd-deploy.sh:35–59 发布与健康轮询。 | backend/start.sh:7–13 原混用脚本仍在；Compose无独立worker服务，CD仅以HTTP200判成功、未自动回滚，TAG变量与Compose build配置未形成镜像切换闭环；未执行TLS、容量、任务续跑、恢复与回滚演练。 |
| 40 | 部分修复 | P1 / High | backend/uv.lock 和 frontend/package-lock.json 已存在；.github/workflows/ci.yml:79–136 有依赖与密钥扫描。但 backend/requirements.txt:5起仍宽松下界，Dockerfile.backend:15–16 按该文件pip安装；frontend/src/pages/GraphPage.tsx:9–19仍加载公网CDN且无SRI。frontend无pnpm-lock.yaml，但CI:46、192要求pnpm --frozen-lockfile。 | 让实际CI/镜像消费锁，统一pnpm锁；vis-network本地打包；补SBOM/许可证/历史密钥扫描证据。实际供链测试2通过1失败，详见下文。 |
| 41 | 部分修复 | P1 / High | backend/tests已大量新增权限、来源、热更新、预算、恢复等测试；CI:175–193运行后端测试及前端类型检查。frontend/src/lib/queryContract.test.ts已有契约断言，但package.json:6–10无测试脚本且CI没有执行该文件/浏览器状态测试。CI:47 ESLint以 |  |
| 42 | 部分修复 | P1 | `rag_eval/run_inference.py:149–159,253–310` 已用 TestClient 调真实 /api/v1/rag/query，188–218 保留响应及分阶段召回 IDs。旧自建 Agent 问题已修，但代码/模型/索引/prompt 固定及全套当前在线复验仍不足。 | `test_query_budgeting.py:254,309,356` 与 `test_retrieval_stage_metrics.py:44–68` 有响应/排名保留测试；未在本次执行外部模型评测。 |
| 43 | 部分修复 | P1 | `run_inference.py:194–205` 保留有序阶段 IDs，`test_retrieval_stage_metrics.py:44–68` 确认不排序；A2 脚本明确改称 node_id_validity。但 `metrics_a2_faithfulness.py:24–47,154–158` 仍靠 ID/关键词及单字“无”判拒答，未做事实支持和人工校准。 | 排序失真有回归覆盖；引用合法率不能称零幻觉，拒答混淆矩阵待验证。 |
| 44 | 部分修复 | P1 | 新增 `ground_truth_multiturn_smoke.json`；但 `run_inference.py:35–40` 硬编码 D:/graghRAG-agent，`metrics_a2_faithfulness.py:66–70` 绑定特定文档图谱；主报告仍围绕 50 题。未形成 200–500 题分层业务保留集和置信区间。 | smoke 集是范围扩展，不能代替泛化证明；需去敏语料/哈希/相对路径可复现包。 |
| 45 | 部分修复 | P1 / High | 本仓库无原goal-skill/goal目录；本机 C:/Users/14156/.codex/skills/goal/SKILL.md:44要求的 Harness references/runtime-stages.md、core/flow.md 及 adapters/codex/host-map.md 当前安装目录均存在。 | 原缺文件现象在本机已补齐，但无固定跨包版本和干净安装/完整执行证据，不推断公开发行已解决。 |
| 46 | 已修复 | P2 / High | harness-engineering/superpowers/harness-engineering/SKILL.md:1–4已有name/description，14–19正确指向包内runtime及宿主适配；scripts/validate_harness_skill.py:15–38列必需资源并检查存在。本次运行该validator exit0：OK: shared harness-engineering structure present。 | 此状态仅关闭原“description及引用缺失”缺陷，不包含真实宿主流程验收。 |
| 47 | 已修复 | P2 / High | 新canonical SKILL.md已无原优先于宿主声明；adapters/codex/host-map.md:13明确AGENTS可能具有更高优先级、不能假定bundle覆盖冲突。静态结构validator通过。 | 持续保留权限冲突行为评测；本次未触发写操作检验。 |
| 48 | 待验证 | P1 / High | 本机goal/scripts/test_goal_guard_integration.py:17由GOAL_RUN_GUARD_INTEGRATION控制，49–60默认skip且缺Guard时仍skip；当前GraphRAG CI无该独立包集成发布门禁。 | 未获取原goal发行仓库最新CI，不能断言外部CI仍未启用；Windows仅audit-only-windows，不能宣称机械阻断已验收。 |
| 49 | 部分修复 | P1 / High | Harness validator:15–38有文件存在检查，scripts/test_behavior_evals.py:160–172将缺响应标not-run，已超出原只查文字；docs/reviews/2026-07-12-harness-engineering-skill-review.md:9–18记录行为not-run；manual-replay目录有后续宿主输出，但本次未独立重放评分。 | 新增的schema/录制机制不能证明Agent遵守，需固定兼容包、完整引用图及真实独立行为评测。 |
| 50 | 未修复 | 🔴 P0：先存在/授权校验，404，禁止前缀猜测，精确资产删除。 | `backend/routes/documents.py:63–89` 不校验存在；`:80` doc_id.replace("doc_", "") 对 doc_ 得空字符串，所有 fname.startswith("") 成立。 | 静态确定可达逻辑；本轮未在真实 uploads 执行删除复现。 |
| 51 | 未修复 | 🟡 P2：UUID+允许扩展名，原名仅 metadata，拒绝链接。 | `backend/routes/ingest.py:248–251` 路径仍拼客户端 file.filename，无服务端纯 UUID 存储键或目录边界校验。 | 未对真实 uploads 执行特殊名称/符号链接写入试验。 |
| 52 | 未修复 | 🟡 P2：集中 Settings，环境注入优先，生产禁覆盖。 | `backend/server.py:18`、`backend/worker.py:16`、`backend/oss_uploader.py:14` 仍 load_dotenv override=True。 | 本轮用 PYTHON_DOTENV_DISABLED=1 防止读取实际 .env；未读取敏感配置。 |
| 53 | 部分修复 | 🟡 P2：租户+哈希+配置版本去重，稳定文档 ID，明确 active_version 发布。 | `backend/kg_store.py:294–315` 有版本管理器；`backend/routes/ingest.py:194,215,248` 每次仍新 task/doc，未以内容哈希/幂等键查重，worker 产物目录按任务 ID。 | 未执行重复提交/重复计费实测；版本类存在不证明入口复用稳定文档。 |
| 54 | 未修复 | 🟡 P2：统一强类型 option 映射；以 page_idx 或解析元数据统计页数。 | `backend/routes/ingest.py:263` 传 enable_ocr；`mineru_client.py:210` 读取 is_ocr，URL payload `:453–458` 未含 OCR；`worker.py:186,204` PDF 页数仍 len(sections)。 | 传输错误测试不验证 OCR/页数合约；未真实解析验收。 |
| 55 | 部分修复 | P2 | 主入口 `routes/rag_query.py:315–338` 使用真实 retrieval score；旧 `query.py:296–313` 仍 set 无序、0.9、answer[:4000]、示例 doc ID 及按消息计工具数。主入口 fallback `rag_query.py:273–284` 也静默截断/默认 ID。 | 预算及分阶段指标测试有改善；需两入口响应真实性、显式截断、引用顺序回归。 |
| 56 | 未修复 | P2 / Medium | frontend/src/pages/GraphPage.tsx:66–138初始化effect仅依赖[data]，不依赖visReady/viewMode；134–138清理销毁网络；221、248条件挂载视图；41–50每10s重新setData导致重建。 | 首次CDN就绪和切回画布可能直到轮询更新才初始化，布局反复重置。补依赖/画布生命周期管理及增量更新/视口保留，浏览器复现尚未执行。 |
| 57 | 未修复 | P2 / Medium | UploadPage.tsx:26–53 interval轮询与恢复effect无卸载清理，55–85提交返回后才startUpload；useAppStore.ts:50–68普通内存store、61以st.id <= step将当前步骤也视为done。 | 提交前锁定、单次可取消轮询、隔离旧响应、持久化taskId、准确阶段状态；未执行浏览器测试。 |
| 58 | 未修复 | P2 / Medium | frontend/src/lib/api.ts:10–30 fetch、刷新和重试均无内建deadline；QueryPage.tsx:238–246仅页码/bbox且链接为固定/graph。 | 加AbortController/超时、原件安全预览与span高亮、稳定节点深链接；未执行浏览器网络悬挂测试。 |
| 59 | 部分修复 | P1 / Medium | CLAUDE.md:37–43现有规范索引已改为langextract/docs与integration路径，旧链接问题部分消除；但 backend/pipeline.py:151–154、integration/pipeline.py:153–156仍存在file.io原件上传且两套CLI副本并存。 | 明确停用/归档旧CLI或统一受控上传核心，防止只修API留下外发入口；本次未上传文件。 |
| 60 | 未修复 | P2 / Medium | 当前本机goal/SKILL.md:40仍明确 emit the five-field reply and stop，即使Confirmation not-required也停止。 | 按原建议允许已授权明确维护继续，同回合通过结构化状态记录；本仓库无法替外部Skill修改/发行验收。 |
| 61 | 部分修复 | P2 / Medium | harness-engineering/evals/skill-evaluation/iteration-3/benchmark.md:3–18已新增4场景并报告时间/token，迭代1的1.91倍不能直接代表当前版本；但5/5为断言分数而非5次重复，with_skill为compact brief而非完整实际包（5行），总体95% vs100%。 | 补重复抽样、独立盲评真实变更及同预算比较；不把compact brief的token优势外推为完整Skill收益。 |
| 62 | 待验证 | P2 / Medium | frontend/package.json:14仍^6.28.0；package-lock.json:3569–3590实际react-router/react-router-dom锁为6.30.3。 | 本次未联网刷新漏洞数据库，也未执行pnpm/npm audit；不能仅凭版本升级判两条通告已修复。需对具体GHSA受影响区间、SPA可达性和安装锁执行安全复核及深链接测试。 |

## 专题证据索引

- [后端、安全、入库与删除：25项](assessment-2026-10-12-backend.md)
- [RAG、溯源与评测：19项](assessment-2026-10-12-rag.md)
- [前端、CI、运维及Skill：18项](assessment-2026-10-12-delivery.md)
- [企业方案D01–D17对照](assessment-2026-10-12-enterprise.md)

本文件为核查记录，不改变规范的业务契约。后续实施修复应同步回流对应Layer规范，并按项目规则归档修复说明。当前没有修改规范来掩盖实现缺口。
