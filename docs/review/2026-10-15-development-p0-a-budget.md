# flash迁移、隔离入库与P0/A开发预算实测

2026-10-15，graphrag-paper-001，M2_OPEN。

**用户要求的模型请求名迁移、隔离开发入库、范围结构适配及两臂资源补测已执行。** 六题P0查询12次请求、8161 tokens；A自动范围读取14次、24907 tokens。建库另计40次、119241 tokens。共66次、152309 tokens，无失败、重试、截断或未知用量。没有进行语义评分或三臂受控质量比较，未证明新方法缺口。

## 模型迁移及实际生成条件

backend/.env唯一LANGEXTRACT_MODEL_ID改为deepseek-flash，其他bytes未变；更新active缺省、环境解析、显式函数覆盖及模型缓存分区。backend/.env.example与有效架构规范同步。旧deepseek-chat历史收据及旧scope/canonical/Gold未改，前轮73预算产物hash复核不变。

新66份实际请求和供应商响应model均为deepseek-flash，fingerprint均为`aeb56401ca74e127821c4f9126dcb669`；同fingerprint不能认证固定权重。新请求显式关闭thinking，保持旧chat别名回执未启用思考的条件。requests使用顶层thinking，SDK使用extra_body展开，原生LangExtract生产配置使用受支持的reasoning_effort none；自定义其他模型不附DeepSeek字段。官方默认思考及开关语义见[Thinking Mode](https://api-docs.deepseek.com/guides/thinking_mode/)。

**实际wire温度必须分轨：P0/A的26请求均temperature=0.0；索引40请求全部省略temperature，供应商有效默认未知。** 原生lx.extract(temperature=0.0)在ModelConfig路径未传至最终请求。保留首调用前registration原件，另有[登记澄清](development-budget-20261014/registration-clarification.json)及逐轨wire字段，不把顶层登记0当作已测索引温度。该差异阻止固定索引随机性的声明，不影响已收到的用量累计。

## 隔离入库与基线身份

两源均为已核文字开发材料：LinuxCNC回零HTML与NISTIR8091，原文/解析/题目hash沿用已接受开发版。H1/H2仍空。实际运行独占目录`.tmp/public-dev-budget-20261015-r2`，复制145份有效后端/LangExtract源码及配置，不含.env、生产output或企业材料。源码路径与hash逐模块核验；软件环境为既有锁匹配Python3.12.8环境，未安装新依赖。路径隔离称audit-only-windows，不宣称原生代码安全沙箱。

入库采用canonical文字→真实SectionSplit/PositionMap/build_documents→既有PDF远程LangExtract→原生grounding/KG构建及文档登记。保留原企业抽取提示、合成few-shot、3000字符分段/200上下文/一遍抽取；SDK输出4096、无重试、超时30，两层并发设1。不是重新运行MinerU上传解析，也不是无本地模型的DOCX/XLSX Ollama路线，不偷换后者供应商。索引及查询分别记账。

|来源|桥接Documents|KG节点|边|原生grounded标签|标签与原文切片严格相等|
|---|---:|---:|---:|---:|---:|
|LCNC-HOME|22|131|253|121|92|
|NIST-8091|7|152|755|134|80|

合计283节点，其中255为原生grounded标签，172条抽取标签与source slice精确相等。两项定义不同，均不证明属性/关系事实有据。原生lookup_range可best-effort映射起点；保存全部AnnotatedDocument、offset、alignment、原文interval/slice和节点映射，不能把grounded自报当证据支持率。

P0明确为**P0_NATIVE_SCOPED_KG**：真实rag_query(document_id)→authorized_graph→KG-only RetrievalPipeline/RAGGenerator→真实QueryResponse，保留原提示、检索、repair及4000字符API限制。没有把管理员多路入口、BM25夹具或人工top-k冒充P0。研究ASGI管理员身份fixture验证了路由函数和授权分支，不证明JWT、中间件或完整HTTP服务验收。六题均实际进入原生生成，每题1预处理+1回答，共12次；API答案与原生最终answer[:4000]一致，本轮答案均未达到字符截断线。

A从原件结构sidecar自动解析范围；HTML标题来自h标签，代码#注释不参与标题，Note布局表与数据表区分；PDF使用bold/font/节点顺序及完整页集合，不按异常y坐标聚类。缺字体、无法拼接标题、缺/重复页、重复章节、缺中间节或歧义时弃权。六题均RESOLVED/COMPLETE_SCOPE；NIST读取完整第3节含3.1，不借Gold裁清单。该状态只证明按规则可解析/组装，不等于范围语义正确。

A采用前轮S冻结的system/map/reduce指令，每8000字符顺序无重叠切块，全部map后一次reduce。五个LinuxCNC题各1map+1reduce，NIST3map+1reduce，共14请求；逐map原文切片和最终归并输入链均保留。

## 实际预算

|阶段|请求|输入tokens|输出tokens|合计tokens|HTTP调用耗时和/秒|
|---|---:|---:|---:|---:|---:|
|一次索引构建|40|101870|17371|119241|94.074|
|P0六题查询|12|6836|1325|8161|21.444|
|A六题查询|14|18689|6218|24907|42.820|
|总计|66|127395|24914|152309|158.338|

父进程整轮约212.594秒，包含各独立子进程启动、本地解析/索引及收尾，不与纯HTTP耗时混称。P0查询冷启动较多，A在一个进程运行，供应商缓存状态不受控，不将时延当公平性能比较。

|开发题|P0调用|P0累计tokens|A调用|A累计tokens|
|---|---:|---:|---:|---:|
|DEV-L01|2|1350|2|2369|
|DEV-L02|2|1149|2|2625|
|DEV-L03|2|1516|2|3019|
|DEV-L04|2|1486|2|4669|
|DEV-L05|2|1284|2|2425|
|DEV-N01|2|1376|4|9800|

P0单调用峰值输入1068/输出243 tokens；A峰值输入2307/输出879，索引峰值2941/1257。P0逐题累计最高1516 tokens，A最高9800。以上是本轮观察负载，不是未来保证或自动冻结的公共预算。P0全链含预处理，不沿用原API仅主回答的usage字段。

缓存命中输入62848（索引57216/P0 384/A 5248）已包含在127395输入总数中，不扣除或再相加。实际完整request JSON559506字节，含messages及请求参数。未核算货币账单，不把token数当实付费用。

首真实调用前按全源离线规划修订额度：72=index40+P0最多18+A14，声明输出上限229376，JSON输入1.2M字节、请求窗口1800秒。旧24索引/64总设计不足，在真实请求前修订并独立复核；未看生成答案后抬预算。实际66次均finish stop且usage完整，未触发闭锁；未知成本尝试0。本地截止只限制本地等待，不等于远端取消。

## 验证与证据

- 模型迁移先红后绿，作者157专项；独立锁匹配环境验证实际provider/SDK MockTransport参数，旧模型兼容意见关闭。
- 结构陌生文档及旧scope回归：最终82通过；独立复跑82通过，六题非Gold结构/范围重新计算一致。修复缺字体、分片标题及XML缺页漏边界，不用实际六题通路掩盖泛化缺陷。
- transport/隔离最终30离线测试及独立30复跑通过。实际SDK为OpenAI3.14.1/httpx2，动态捕获requests/httpx/httpx2同步异步；错误/密钥回显/损坏类型/空内容/截断/usage缺失均闭锁，进程锁后重读累计状态。
- 最初预检猜测httpx漏接新版SDK，使用临时假key时被沙箱10013拒绝连接；保留失败副本，不称离线成功。修后真实SDK本地MockTransport加socket拒绝，正式r2预检40次/443857字节通过，无真实provider usage；有效模块位于独占副本。
- 实际66份request/response原始UTF8 wire、SHA、bytes、usage、逐轨/逐题累计及A源slice→map→reduce、P0最终API输出均已本地复算。执行145源码及公开输入hash保持一致。
- 原生产数据保护范围3306文件/47969302字节前后hash一致（kg/runtime/vectordb/embedding_cache/lineage/conversations/docs_store/rewrite-cache）；不推论未检查的其他目录。真实key在新预算产物扫描命中0，未保存Authorization或.env，未发送企业材料。

产物入口：[机器汇总](development-budget-20261014/resource-summary.json)、[原始用量账本](development-budget-20261014/calls/ledger.json)、[执行登记](development-budget-20261014/registration.json)、[执行状态](development-budget-20261014/execution-status.json)、[独立执行放行](2026-10-15-development-execution-review.md)、[独立资源审查](2026-10-15-development-resource-review.md)。原生索引、全部grounding证据、源码文本快照及分析源码已归档至development-budget-20261014/executed-isolation，不依赖.tmp长期保留。

## 当前结论与下一步

已完成两臂可运行资源profile，之前P0共同入库和A结构格式的工程阻塞在本次隔离文字开发轨关闭。**未评价范围语义正确、条目/属性完整性或claim输入支持，也未执行三次重复。** 五题同一HTML页、只有两来源单元，不能作稳定失败率、总体推断或创新证明。

历史S为27请求/71900 tokens，但请求别名、结构输入版本、索引条件和P0入口设定与本轮不同；即使响应model/fingerprint一致，也不能拼成受控三臂排名。三臂共同预算及质量比较尚未冻结，不把P0较低成本当更优、不把KG对齐问题包装成新方法。

下一步：统一三臂的执行版本、结构输入和可验证生成设置后冻结共同预算，再分别裁决范围选择、条目完整性与证据支持。H1/H2仍空、M2_OPEN；本任务没有重启生产服务、安装、提交/推送或部署，专项证据不替代修改后全量覆盖与安全门槛。
