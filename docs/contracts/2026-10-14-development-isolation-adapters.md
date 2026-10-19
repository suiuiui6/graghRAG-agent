# 公开开发隔离入库与结构适配契约 v1

项目graphrag-paper-001，M2_OPEN。用户2026-10-14明确授权新请求名deepseek-flash，并补隔离开发入库、范围适配和P0/A预算。继承公开开发远程授权，企业资料和留出不在范围；旧Gold/源码/模型请求/回执冻结不回写。仅开发资源探索，不运行语义比较或新方法门禁。

## 身份与边界

新模型请求必须deepseek-flash；修改backend/.env唯一模型赋值及active默认模型解析，保留显式函数参数覆盖能力。所有新模型调用逐次记录请求/响应模型、fingerprint、usage和缓存。请求别名及同fingerprint不证明固定权重。旧deepseek-chat收据保留。

兼容补充：官方API文档2026-10-14核查flash默认thinking enabled，而旧29份chat别名回执无reasoning_content。为保持既有非思考预算行为，新flash请求显式thinking disabled；requests实际JSON必须top-level thinking，不能错误套SDK参数extra_body。SDK按extra_body展开。仅识别DeepSeek flash/v4模型，不向自定义其他模型附供应商字段。原LangExtract provider不转发extra_body，隔离研究factory需显式包装SDK create传入，记录这一预算兼容适配，不改第三方库。参考https://api-docs.deepseek.com/guides/thinking_mode/。

P0选择真实document_id授权KG入口：rag_query→authorized_graph→原生KG-only RetrievalPipeline/RAGGenerator→真实QueryResponse（4000字符截断）。不改路由为多路、不用BM25代替、不手造KG事实。独占副本内调用真实路由函数，研究管理员身份fixture不等于JWT/中间件/完整HTTP验收；标签P0_NATIVE_SCOPED_KG，明确与旧未冻结的多路设想区别。

现役DOCX/XLSX Ollama入库缺本地模型，不能偷换成flash后称原生。隔离开发采用已有PDF远程LangExtract→grounding→KG的实际组件，对已核canonical提供格式桥接；不是重新执行MinerU上传解析。记录此入库适配、索引构建资源和边界。不能将无grounding节点强制标grounded；若生成空图或无可用授权节点，真实no_data为可用性结果，不造节点补齐。

## 结构输入与范围规则

新增研究适配模块，不修改旧scope_v2/canonical/questions/Gold。HTML重新读取原XHTML，核现blocks的XPath、tag/text及源/解析SHA。标题只来自h1–h6，pre内注释不能成为标题；表格按真实同一table祖先分组，混合/嵌套结构弃权。

PDF使用已有Poppler XML的bold/font及原节点顺序证据生成标题，再在相同pages.json页内唯一匹配归一空白的完整标题行，映射原canonical Unicode坐标。XML y坐标异常，不按y聚类；缺字体证据或匹配不唯一弃权，不用Gold页码/目标列表裁剪。结构节点包含source_id、kind、start/end、level/number/title、原件XPath或PDF页/节点/font证据。定位为LF Unicode半开区间，整源提取成本单列。

单章节默认包含子节，到下一同级/上级；显式连续范围仅接受连接符、同父同深度顺序端点及完整中间编号。反向/缺节/重复/跨父级/离散多选弃权。开头表格只在首个子节前定位唯一table，必要引导语/直接说明保留；多个候选弃权。代码伴随说明问题保留整节。不得读Gold、按题号路由或硬编码六题范围；NIST第3节先读全节（含子节），不以列表Gold裁剪。

A调用原assemble_scope，字节预算与token明确分开；范围输入按8000字符顺序无重叠分块，使用上轮冻结S相同map/reduce提示和输出上限，全部map后一次reduce。不得将遍历完成当语义穷尽。

## 真实隔离与索引

运行根为新独占.tmp目录；复制backend有效Python/必需静态schema（不含.env/output/tests/venv），独占CWD/TEMP/缓存/lineage/docs_store/KG。导入前设置HF离线配置防隐式联网；不得导入server启动lifespan，不操作原生产目录/collection。软件锁与既有环境核对后使用，不安装或替换依赖。该路径/进程隔离为audit-only-windows，不声称原生代码机械沙箱。

本地editable LangExtract也复制有效Python源码到运行根相邻langextract目录，记录全文件hash与实际provider/extraction/annotation.__file__；运行前后复核，不把uv.lock当editable代码身份。原根代码只读。

桥接SectionSplit/PositionMap均从全源结构与canonical生成。build_documents的strip/offset修正按原函数执行；Document ID与offset键一致。HTML无真实PDF页/bbox，文本定位单列、bbox=None，不伪造版面。保存AnnotatedDocument/GroundedExtraction的字符interval/alignment状态、源slice/hash及节点映射；serialize_kg缺interval，不能仅nodes.json称完整证据链。文档注册真实document_id/kg_path/owner_id；来源身份匹配后才执行P0题。

另列native_grounding_status、source_interval_valid、exact_text_match、alignment_status及source_slice；lookup_range原生best-effort起点映射不等于严格证据支持。保留原生状态用于真实路由，不按Gold筛节点或将fuzzy伪装exact，后续证据评分独立核实。

## 预算与账本

索引和查询分轨。受控transport只准官方HTTPS chat/completions，不打印/保存Authorization/key/原始异常正文。requests与SDK/httpx都捕获；新请求model断言flash。索引原生SDK设置timeout30/max_retries0、generation max_output_tokens4096；这些是开发资源配置，不冒称原入库已有该限制。保留原提示、分段/context/passes等行为；限制外层并发为1以便确定性资源保留，记录差异。

实际SDK接口约束：worker传ModelConfig时language_model_params分支不执行，max_output_tokens须通过隔离factory补入ModelConfig.provider_kwargs，再检查最终provider._extra_kwargs与真实HTTP payload.max_tokens=4096；provider_kwargs.max_workers=1及extract.max_workers=1同时落实并核验。仅把timeout/max_retries塞provider_kwargs无效，必须实际SDK _client.with_options(timeout=30,max_retries=0)并验证client配置。thinking通过SDK create的extra_body展开到真实JSON；发出前transport验证所有模型字段、输出限额及thinking disabled，不满足拒绝并留NOT_SENT，不能边发边猜。

2026-10-15执行前离线预检修订：全源标题桥接与原生3000字符分段规划索引40次，已准备A工作清单14次；旧24索引/64总额度不足，保留旧设计审查作为历史，正式首调用前修订。全组最多72次实际HTTP尝试，其中索引至多40，P0六题至多18（原生预处理+回答含1次内部重试），A至多14且无重试。预检只能使用假key与实际SDK本地MockTransport，不把模拟usage当真实tokens。正式执行须在锁匹配环境验证此计划及全部实际HTTPX模块的transport拦截。

每次完整messages JSON与动态reduce照计，累计≤1200000 UTF8 bytes（完整request JSON计量为更严格实现）；请求窗口1800秒。索引子进程≤600秒、P0每题≤120秒、A每次≤45秒，均按剩余时间限制。本地结束不证明远端取消。输出上限索引每次4096、P0/A主回答2048、预处理300，最大总声明输出229376 tokens（40×4096+32×2048，预处理以2048保守包络）。首次HTTP失败、缺有效usage或输出截断停止该profile，不自动重新提交未知成本请求。原生重试已发生的也照计；transport遇拒绝应使后续请求guard关闭。

保存完整messages/原输出/usage/finish/error/model/fingerprint、逐调用request/response SHA、索引与题归属、路由trace/repair/API最终输出。无usage的可能已发请求成本UNKNOWN，不记0。索引成本不摊入单题而隐匿；如摊销需另报次数假设。缓存供应商实际状态另记，不假称禁缓存。

## 验收

模型默认迁移无网络行为测试；结构适配必须先有陌生合成文档红绿（重复/缺节/代码注释/表格/页内唯一匹配/Unicode/字节不足），旧scope回归保持。生产目录和旧冻结前后hash不变；源码快照绑定实际执行。独立设计/代码/运行收据审查通过后登记profile结果；新增接口0、不替代产品全量验收/覆盖/安全门槛，无commit/push/deploy。

三臂预算只有真实可运行路径与全链usage均闭合后才能登记；任一路不可用仍写未测齐，禁止以工程不可用证明方法缺口。H1/H2空、M2开放。
