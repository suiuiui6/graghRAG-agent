1. `graghRAG-agent/backend/server.py` 第65-70行，业务接口缺少身份认证和资源授权，服务对不可信用户开放时可导致文档泄露、数据删除和模型额度滥用；严重等级：严重（P0），修复预估：32-56h，方案：接入企业 SSO，在文档、任务、图谱及检索工具层统一实施用户、租户和文档权限校验。

2. `graghRAG-agent/backend/routes/query.py` 第195-207、262行，`document_id` 只写入响应而未限制检索范围，查询文档A可能引用文档B并错误标注来源；严重等级：严重（P0），修复预估：16-32h，方案：检索前校验文档权限，绑定授权文档子集，并为节点和证据保存真实文档ID及版本。

3. `graghRAG-agent/backend/worker.py` 第240-245行，`task_id[:8]` 仅保留固定前缀和一位随机字符，输出目录只有16种取值，不同任务会覆盖或混用解析结果；严重等级：严重（P0），修复预估：4-8h，方案：使用完整UUID创建独占目录，校验产物后原子发布，禁止复用有残留的目录。

4. `graghRAG-agent/backend/worker.py` 第63-80行，OSS上传失败后直接使用任意历史解析缓存，可能把旧文档内容作为新文档成功入库；严重等级：严重（P0），修复预估：4-8h，方案：移除无匹配缓存回退，仅允许按原文件哈希、解析版本和配置校验后的缓存复用。

5. `graghRAG-agent/backend/oss_uploader.py` 第51-59行、`backend/pipeline.py` 第149-158行，解析链路依赖未签名对象URL，独立CLI还会向file.io上传原件，存在敏感资料外发风险，实际桶权限未验证；严重等级：高（P1），修复预估：16-32h，方案：统一使用私有桶、短时签名URL和出站策略，敏感资料采用受控解析并明确供应商留存边界。

6. `graghRAG-agent/backend/routes/ingest.py` 第103-123行、`backend/worker.py` 第229-245行，用户URL仅校验协议前缀，上游下载地址直接交给curl；若地址可被操纵，存在SSRF和异常下载风险，尚未证实可访问本机内网；严重等级：高（P1），修复预估：8-16h，方案：限制HTTPS域名、解析IP、重定向目标、出站网络和下载大小。

7. `graghRAG-agent/backend/routes/ingest.py` 第136-143行，上传先整文件读入内存再判断大小，并发大文件可能耗尽内存；`server.py` 第44行的 `max_upload_size` 不能代替请求体限额；严重等级：高（P1），修复预估：8-16h，方案：网关限制请求体，应用分块写盘、累计限额、超限清理，并限制并发和磁盘配额。

8. `graghRAG-agent/backend/worker.py` 第239-248行，ZIP解压仅设置进程超时，没有未压缩体积、文件数及成员类型限制，异常压缩包可能耗尽磁盘；严重等级：高（P1），修复预估：8-16h，方案：解压前校验成员路径、总大小和压缩比，拒绝链接及越界路径，在受限目录解压并清理失败产物。

9. `graghRAG-agent/backend/security.py` 第6-12、25-52行，文件token与限流状态仅在进程内，且localhost绕过校验，多实例和部分代理配置下会出现校验不一致或防护绕过；严重等级：高（P1），修复预估：12-24h，方案：按文档授权签发短时访问凭据，配置可信代理，采用按用户、租户和接口划分的共享限流及并发配额。

10. `graghRAG-agent/backend/worker.py` 第165-183、207-225行，日志输出文件路径和对象URL，curl参数携带Authorization凭据，存在日志与进程参数暴露风险；严重等级：高（P1），修复预估：6-12h，方案：改用受控HTTP客户端，统一日志脱敏，客户端仅返回稳定错误码和request_id。

11. `graghRAG-agent/backend/requirements.txt` 第1-11行，缺少真实入库必需的 `langextract` 和 `oss2`，干净安装后离线演示能运行但真实入库会失败；严重等级：高（P1），修复预估：4-8h，方案：补全并锁定运行依赖，区分演示与provider依赖，增加干净环境导入和入库合约测试。

12. `graghRAG-agent/backend/routes/ingest.py` 第19-20、123、159-172行，后台任务和进度仅保存在Web进程内，重启丢状态，多worker轮询可能404，任务缺少恢复和取消机制；严重等级：高（P1），修复预估：24-48h，方案：使用持久化任务表与独立worker，加入租约、幂等、有限重试、取消、失败队列和TTL。

13. `graghRAG-agent/backend/routes/__init__.py` 第25-50行、`backend/kg_builder.py` 第146-149行，JSON直接覆写且仅用线程锁，进程中断可能损坏文件，多进程可能丢更新，节点与边也可能版本不一致；严重等级：高（P1），修复预估：16-32h，方案：元数据改用事务存储，图谱在临时版本目录完成校验后原子切换。

14. `graghRAG-agent/backend/routes/ingest.py` 第51-87行，任务先标记done再持久化文档和刷新图谱，后续失败时用户仍看到成功，查询可能继续读取旧图；严重等级：高（P1），修复预估：8-16h，方案：增加committing状态，仅在持久化和可查询版本发布成功后标记完成，失败进入可重试状态。

15. `graghRAG-agent/backend/routes/documents.py` 第56-87行，删除文档后未失效问答内存图谱，已删除资料仍可能被检索和回答；严重等级：高（P1），修复预估：8-16h，方案：删除时先撤权或写tombstone，再通知所有worker更新快照和缓存，并限制在途请求返回已撤回证据。

16. `graghRAG-agent/backend/routes/documents.py` 第61-85行，删除异常被吞掉后仍返回deleted，且未清理解析缓存与OSS对象，接口成功不代表资料实际销毁；严重等级：高（P1），修复预估：16-32h，方案：建立原件及派生产物资产清单，按清单可重试删除，区分pending、deleted和failed，并制定保留及备份删除策略。

17. `graghRAG-agent/backend/routes/query.py` 第109-116、204-249行，查询使用旧Agent但来源读取最新全局图，热更新没有版本顺序保护，答案与引用可能跨版本错配；严重等级：高（P1），修复预估：12-24h，方案：将graph、agent和version绑定为不可变快照，请求全程使用同一快照，发布使用版本校验或串行协调。

18. `graghRAG-agent/backend/routes/query.py` 第54-67行、`backend/routes/graph.py` 第87-105行，节点ID按目录或列表顺序重新编号，同一ID在不同视图或增删文档后可能指向不同实体；严重等级：高（P1），修复预估：12-24h，方案：使用包含文档和版本的稳定实体ID，统一查询、图谱和证据接口的标识规则。

19. `graghRAG-agent/backend/routes/query.py` 第203-212行，Agent初始化位于异常捕获外，空消息结果会触发 `IndexError`，导致当前请求500，但不等于整个服务必然宕机；严重等级：高（P1），修复预估：4-8h，方案：先校验消息列表与终态类型，将初始化、执行、解析和序列化纳入错误边界，区分配置错误、超时和内部错误。

20. `graghRAG-agent/backend/worker.py` 第206-248、274-303行，上游提交、轮询和抽取缺少统一的有限重试与总截止时间，且未持久化上游任务ID，恢复时可能重复提交或长时间占用资源；严重等级：高（P1），修复预估：12-24h，方案：分类处理401、429、5xx和超时，使用退避重试，持久化provider_task_id并限制阶段及任务总耗时。

21. `graghRAG-agent/backend/kg_builder.py` 第49-97行，图谱仅有同页共现、同类型和顺序相邻三种结构边，不能证明业务事实关系，多跳可能把可达性误当因果或归属；严重等级：高（P1），修复预估：32-64h，方案：按业务域定义关系schema，抽取有方向、限定条件、时间和原文证据的三元组，分离结构边与事实边。

22. `graghRAG-agent/backend/routes/query.py` 第32-42行，使用无向简单图 `nx.Graph` 加载多关系数据，同一实体对的关系会被覆盖，方向和边属性也丢失；严重等级：高（P1），修复预估：6-12h，方案：改用MultiDiGraph或显式关系集合，保留edge_id、方向、属性和证据，并测试序列化往返一致性。

23. `graghRAG-agent/backend/kg_builder.py` 第25-38行、`backend/routes/query.py` 第64-67行，实体直接按抽取结果建节点，多文档仅合并子图，缺少别名、消歧和跨文档实体对齐；严重等级：高（P1），修复预估：24-48h，方案：优先按领域主键对齐，补充规范化名称与别名召回，对歧义保留候选和人工确认，合并后保留独立来源。

24. `graghRAG-agent/backend/bridge.py` 第33-53行，仅规范化待匹配文本而未同步处理full.md，短前缀匹配成功后又按全文长度计算区间，可能产生错误字符位置；严重等级：高（P1），修复预估：12-24h，方案：优先使用解析块ID，或建立规范化文本到原文的偏移映射，并校验完整匹配内容。

25. `graghRAG-agent/backend/bridge.py` 第204-206、222-233行，分段文本strip后仍使用原始段首偏移，导致实体字符坐标错位并影响页码及bbox溯源；严重等级：高（P1），修复预估：3-6h，方案：保留原始分段文本，或按实际删除的前导字符数量修正offset，统一坐标空间。

26. `graghRAG-agent/backend/bridge.py` 第54-66行、`backend/grounding.py` 第59-81行，找不到文本时仍人为分配连续区间，后续只要位置命中就标grounded，不存在的内容也可能显示已溯源；严重等级：高（P1），修复预估：8-16h，方案：未匹配内容标记unmapped并隔离，只有通过原文对齐及坐标校验的证据才能标grounded。

27. `graghRAG-agent/backend/schema.py` 第30-36行、`backend/grounding.py` 第25-31、73-81行，跨块区间退化为首块位置，未知文档偏移默认0，bbox缺少范围与单位校验，可能生成错误来源；严重等级：高（P1），修复预估：12-24h，方案：支持多span来源，未知doc_id明确失败，校验字符区间、页码、坐标单位和框范围。

28. `graghRAG-agent/backend/bridge.py` 第71-88行、`backend/worker.py` 第283-303行，表格及图片溯源主要依赖标题，缺少单元格结构、表头继承和图像证据链，复杂表格与图表问答可靠性不足；严重等级：高（P1），修复预估：24-48h，方案：保存表格行列、单元格来源及单位，数值计算使用确定性工具，视觉问题独立路由并建立专项标注集。

29. `graghRAG-agent/backend/kg_builder.py` 第115-129行、`backend/worker.py` 第142-144行，持久化图谱丢失字符跨度和块类型，metadata为空，缺少原文件哈希及模型、prompt、解析器版本；严重等级：高（P1），修复预估：16-32h，方案：建立文档版本、构建manifest和source_span，节点及关系引用稳定证据ID，记录配置版本和产物校验和。

30. `graghRAG-agent/backend/routes/query.py` 第132-145行，检索仅做全图子串扫描并按插入顺序截取前15项，缺少相关性排序、分页和聚合机制，同义词及列表问题容易漏召回；严重等级：高（P1），修复预估：24-48h，方案：先建立chunk与全文检索基线，再评估向量融合及重排，枚举和统计问题使用分页或聚合工具。

31. `graghRAG-agent/backend/routes/query.py` 第149-167行，多跳工具只返回邻域节点，仍按起点直接边取关系，二跳以上关系会退化为connected，无法证明推理路径；严重等级：高（P1），修复预估：12-24h，方案：返回有序路径及每条边的方向、类型和证据，限制跳数与展开数量，并做路径级排序。

32. `graghRAG-agent/backend/models.py` 第31-35行、`backend/routes/query.py` 第151-167、207行，API声明的工具调用预算未执行，工具跳数和返回数量无硬边界，可能造成过量遍历、长尾延迟和费用失控；严重等级：高（P1），修复预估：12-24h，方案：实施总时间、token、金额和工具调用硬预算，约束参数范围，遍历过程中限额并抑制重复调用。

33. `graghRAG-agent/backend/routes/query.py` 第143-145、171-173、207-259行，文档内容直接进入模型上下文，缺少提示注入边界、逐结论证据校验及冲突处理，存在回答被引导或结论无支持的风险，尚未做真实模型攻击验证；严重等级：高（P1），修复预估：16-32h，方案：结构化生成claims与citations，限制不可信内容的指令权限，验证证据支持并在不足或冲突时拒答。

34. `graghRAG-agent/backend/routes/query.py` 第214-249行，来源解析没有限定ToolMessage，用户提交的节点JSON也能成为证据，已复现零工具调用仍返回sources；严重等级：高（P1），修复预估：8-16h，方案：仅接受真实工具执行产生的结构化证据，绑定tool_call_id，区分检索结果与实际引用，并验证每个引用对应受支持结论。

35. `graghRAG-agent/backend/routes/query.py` 第194-207行，异步接口直接调用同步 `agent.invoke()`，慢模型调用会阻塞事件循环并拖慢其他API及健康探针；严重等级：高（P1），修复预估：6-12h，方案：改为await agent.ainvoke，将同步及CPU密集任务放入受限执行池，补充并发和取消测试。

36. `graghRAG-agent/frontend/src/pages/QueryPage.tsx` 第12-17、59-68行，未读取文档路由参数且只发送当前问题，从单文档入口进入后范围丢失，多轮追问也没有历史上下文；严重等级：高（P1），修复预估：12-24h，方案：读取并传递documentId，明确显示范围；需要多轮时增加用户隔离的conversation_id、历史存储、上下文预算和TTL。

37. `graghRAG-agent/backend/routes/health.py` 第62-88行，按密钥长度判断上游正常，整体状态和kg_store固定为健康，坏凭据或坏图也可能通过探针；严重等级：高（P1），修复预估：8-16h，方案：分离liveness与readiness，验证激活图版本和本地依赖，缓存受控上游探测结果，未就绪返回503。

38. `graghRAG-agent/backend/server.py` 第56-62行、`backend/routes/query.py` 第261-267行，仓库未见全链路追踪、用户操作审计、费用账本及SLO告警，出现错误答案或费用激增时难以定位和追责；严重等级：高（P1），修复预估：16-32h，方案：统一request/task/trace ID，记录阶段延迟、失败率、队列、模型成本及索引版本，建立脱敏审计和可演练告警。

39. `graghRAG-agent/backend/start.sh` 第7-13行，开发脚本混用Bash与Windows激活路径并使用reload对外监听，仓库未见生产部署、备份恢复、回滚及容量验证闭环；严重等级：高（P1），修复预估：24-48h，方案：提供版本化生产部署与独立worker，设置TLS、资源限额及持久化存储，完成备份恢复、任务续跑和发布回滚演练。

40. `graghRAG-agent/backend/requirements.txt` 第1-11行、`frontend/index.html` 第10-11行，Python依赖只有版本下界，图谱库通过无SRI的公网CDN加载，存在构建漂移、供应链和内网不可用风险；严重等级：高（P1），修复预估：8-16h，方案：生成依赖锁及SBOM，固定运行时，将vis-network纳入本地构建，并增加漏洞、许可证和密钥历史扫描。

41. `graghRAG-agent/backend/tests/test_demo.py` 第18-90行、`.github/workflows/ci.yml` 第22-31行，现有测试主要覆盖离线演示，真实入库、权限、删除、热更新及并发缺少回归，前端状态测试也未在该CI调用；严重等级：高（P1），修复预估：24-48h，方案：将本次复现转为修复后的回归测试，补API合约、故障恢复、权限矩阵和浏览器主流程验证。

42. `graghRAG-agent/iteration-2/eval-2-existing-components/rag_eval/run_inference.py` 第164-183行，评测自建四工具Agent，线上服务仅使用两个工具，且评测绕过HTTP及来源组装，历史分数不能代表当前接口质量；严重等级：高（P1），修复预估：12-24h，方案：评测复用实际服务入口，固定代码、索引、模型、prompt及参数，保存检索中间态和最终响应。

43. `graghRAG-agent/iteration-2/eval-2-existing-components/rag_eval/metrics_a2_faithfulness.py` 第25-47、133-140行及 `run_inference.py` 第265行，用节点存在证明零幻觉、按否定词判断拒答，并对ID排序后计算MRR，会高估质量或误判优化收益；严重等级：高（P1），修复预估：16-32h，方案：分别评估引用合法性、事实支持性和拒答混淆矩阵，保留真实排名计算MRR及nDCG，并用人工标注校准。

44. `graghRAG-agent/iteration-2/eval-2-existing-components/rag_eval/run_inference.py` 第29-33行、`REPORT_FINAL.md` 第3-7行，评测仅覆盖单篇论文50题且依赖硬编码本地路径和未随仓库提供的原图，企业场景泛化与复现证据不足；严重等级：高（P1），修复预估：24-48h，方案：建立200-500题分层业务保留集，提供去敏语料、哈希、相对路径和运行清单，报告分场景结果及置信区间。

45. `goal-skill/goal/SKILL.md` 第25、47-59行，引用的Harness执行文件在本次审查的公开Harness提交中缺失，直接组合两个仓库可能在执行阶段阻断，Fullstack是否补齐未验证；严重等级：高（P1），修复预估：8-16h，方案：补齐或修正跨仓库引用，固定兼容版本，增加安装文件、协议及完整执行流程校验。

46. `harness-engineering-skill/superpowers/harness-engineering/SKILL.md` 第1-7、137-143行，canonical入口缺少description且引用不存在的宿主适配文件，存在宿主发现或加载失败风险；严重等级：高（P1），修复预估：8-16h，方案：提供单一标准安装入口，统一相对路径基准，补齐宿主适配包并测试干净安装、触发和引用加载。

47. `harness-engineering-skill/superpowers/harness-engineering/SKILL.md` 第61行，声明方法论优先于冲突的宿主行为或本地指令，可能引导模型错误处理权限和指令层级；严重等级：高（P1），修复预估：3-6h，方案：明确宿主高优先级约束和用户授权优先，Skill仅管理已授权范围内的流程，实际安全边界由宿主权限执行。

48. `goal-skill/goal/scripts/test_goal_guard_integration.py` 第17、62-73行、`.github/workflows/ci.yml` 第11-22行，Guard集成默认跳过且CI未开启，测试通过不能证明真实执行门禁有效；严重等级：高（P1），修复预估：12-24h，方案：增加固定Guard版本的隔离集成发布门禁，按宿主实测阻断、恢复和关闭行为，必需测试禁止静默skip。

49. `goal-skill/goal/scripts/validate_goal_skill.py` 第177-223行、`harness-engineering-skill/tools/check_integrations.py` 第10-25行，验证偏重预期文字和仓库可达性，缺失执行引用仍可通过检查，不能证明Agent实际遵守流程；严重等级：高（P1），修复预估：16-32h，方案：增加跨包引用图检查、真实Agent行为评测和独立评分，记录工具调用、变更、违规恢复、耗时与token。

50. `graghRAG-agent/backend/routes/documents.py` 第56-82行，未校验文档存在且按字符串前缀删除文件，传入不存在的 `doc_` 会变为匹配空前缀，已复现删除全部上传原件；严重等级：高（P1），修复预估：4-8h，方案：先查询并授权真实文档，未知ID返回404，仅按文档资产清单精确删除，禁止前缀推断。

51. `graghRAG-agent/backend/routes/ingest.py` 第132-143行，保存路径直接拼接客户端文件名，特殊名称可造成写入失败，特定目录或符号链接条件下还存在越界风险，默认环境任意写未证实；严重等级：中（P2），修复预估：3-6h，方案：存储键仅使用服务端UUID及允许扩展名，原文件名单独保存，写入前检查目录边界并拒绝符号链接。

52. `graghRAG-agent/backend/server.py` 第7-9行、`backend/worker.py` 第13-15行、`backend/oss_uploader.py` 第8-10行，多处强制加载.env覆盖部署注入配置，可能使用过期密钥或错误服务地址；严重等级：中（P2），修复预估：4-8h，方案：集中使用Settings加载和校验配置，生产注入优先，禁止开发.env覆盖现有变量。

53. `graghRAG-agent/backend/routes/ingest.py` 第108-123、140-159行，每次提交生成新任务且无内容去重、幂等键和文档版本管理，重试可能重复计费，旧新版本可能同时回答；严重等级：中（P2），修复预估：16-32h，方案：以租户、内容哈希和配置版本去重，使用请求幂等键，并维护文档stable_id及active_version。

54. `graghRAG-agent/backend/worker.py` 第157、192-205行，OCR选项未传递给MinerU，页数使用章节数量代替，导致选项无效或显示错误页数；严重等级：中（P2），修复预估：4-8h，方案：按真实API合约定义强类型选项并逐项传递，页数从解析元信息或page_idx去重获取，统一零基索引和展示页码。

55. `graghRAG-agent/backend/routes/query.py` 第247-264行，相关度固定为0.9，来源无稳定顺序，答案静默截断，无文档时返回示例ID，工具调用数也按消息计数；严重等级：中（P2），修复预估：4-8h，方案：未计算分数则不展示，按真实引用排序，显式标记截断，使用真实文档ID并逐个统计工具调用。

56. `graghRAG-agent/frontend/src/pages/GraphPage.tsx` 第63-69、131-149、213-237行，画布随视图切换重建但初始化仅依赖data，切回时可能暂时空白；轮询还会反复销毁布局，浏览器行为尚未实测；严重等级：中（P2），修复预估：6-12h，方案：按画布生命周期初始化或保持挂载，使用DataSet增量更新、版本检测和视口保留。

57. `graghRAG-agent/frontend/src/pages/UploadPage.tsx` 第26-53、73-85行、`frontend/src/stores/useAppStore.ts` 第29-48行，轮询缺少卸载清理，提交前未锁定状态，刷新丢taskId，运行步骤又可能显示已完成；严重等级：中（P2），修复预估：6-12h，方案：提交前设uploading，使用可取消的单次轮询，隔离旧响应，持久化任务标识并按真实阶段状态展示。

58. `graghRAG-agent/frontend/src/lib/api.ts` 第3-12行、`frontend/src/pages/QueryPage.tsx` 第128-156行，请求无截止时间，证据面板仅显示页码和bbox，无法直接定位原件，网络悬挂和人工核验体验不足；严重等级：中（P2），修复预估：12-24h，方案：增加超时与取消，证据携带文档版本及span定位，接入安全PDF高亮预览和稳定节点深链接。

59. `graghRAG-agent/CLAUDE.md` 第22-35行、`backend/pipeline.py` 第149-158行、`integration/pipeline.py` 第149-158行，规范引用失效且存在多套流水线副本，上传安全策略已漂移，修复一处不能覆盖所有入口；严重等级：中（P2），修复预估：8-16h，方案：统一可执行核心供API、CLI和评测复用，归档旧原型，自动校验内部链接并标注实际架构边界。

60. `goal-skill/goal/SKILL.md` 第39-43行、`goal/scripts/validate_goal_skill.py` 第140-146行，即使无需确认也强制结束分类回合，已授权的低风险维护可能被额外用户回合阻断；严重等级：中（P2），修复预估：4-8h，方案：按风险决定是否暂停，已有授权的明确维护同回合继续，用结构化状态替代固定话术约束。

61. `harness-engineering-skill/evals/skill-evaluation/iteration-1/benchmark.md` 第3-29行，效果评测仅三个单轮任务，使用skill平均token约为未使用的1.91倍，无法据此证明稳定收益；严重等级：中（P2），修复预估：16-32h，方案：按任务类型多次重复、盲评真实变更质量，同时报告置信区间、失败率、回合数和成本，并比较相同预算下的结果。

62. `graghRAG-agent/frontend/package.json` 第14行，React Router依赖命中 `GHSA-wrjc-x8rr-h8h6` 和 `GHSA-337j-9hxr-rhxg` 中危通告，实际可利用性尚未证实，其中SSR场景未见于当前SPA；严重等级：中（P2），修复预估：4-8h，方案：核对受影响路径，升级兼容修复版本并回归路由及深链接，对不适用通告保留可复查说明。
