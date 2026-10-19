# 新文档探索性先导执行契约

依赖：简单输出约束提示已封存SHA32f5cb13cbe578e89df9375a80bb347fb4e69a4f3d99b095dd5afb85d916fedc，开发复验执行中。本文不修改提示、解析器、resolver、Gold或评分规则，不以新文档结果修补它们。

正式12文档H1/H2目标尚未准入。首批3长文全部超过共同S预算，保留而不算语义失败。追加最多3份短篇独立官方指南，作为NEW_DOCUMENT_EXPLORATORY_PILOT，不冒称12文档确认性完成、人工Gold或G2通过。原文选择/Gold由数据角色保管，方法角色只接触运行必需的来源manifest、结构和问法，不使用Gold。

## 执行适配

原runner固定六题两源，禁止改登记后伪称适用于任意新文档。另建backend/research/new_document_pilot.py及有效离线测试；不改旧runner及冻结归档。复用冻结原生145源码及预算transport/结构/resolver，新增编排文件写入新源码快照；每份新文档独占runtime/索引/账本。无生产索引、服务启动或企业材料。

输入为已核公开PDF一份、canonical逐页文本及源页半开映射、Poppler XML、来源manifest和自然问题。只从原始来源结构构建index，不能把Gold章节/条目插入。问题字段query本身可明确范围；不额外提供oracle heading。无法解析的A保留UNRESOLVED，无请求，不令全组停机，也不算语义失败。完整范围读取按旧resolver；歧义无人工修正。

先独立空输出MockTransport跑原生索引chunker/SDK最小I/O，记录真实SDK调用数/请求bytes；该值不是数据依赖的严格次数保证。索引上限首API前按2×预检请求数+4登记，4096每次声明输出，累计request bytes按2×预检bytes+24000登记，墙钟每源1800秒。原生索引temperature省略的历史行为如实记录默认未知，不冒称等同生成0.0；生成仍flash/temp0/thinking disabled。超过索引额度或未知费用保留失败并停止整pilot，不静默扩额重试。

索引补充共同可审计政策：单次JSON24000字节、响应后实际单次输入8192 token；累计实际输入8192×登记index_attempts，累计实际输出4096×登记index_attempts。声明max_tokens4096不代替实际usage检查；已知超额保留已消费费用并停止整pilot，未知费用同样停止，不重新登记补跑。累计bytes仍按上文预检公式，所有具体值首请求前写入registration，不称精确调用前token保障。

索引仅同一已核源，冻结KG/索引回执后才生成；无法入库记CORPUS_UNAVAILABLE，不能当模型语义错误。生成每题三臂三次fresh process、平衡次序；每单元仍8尝试/120秒/24k单次JSON/192k累计bytes/8192单次实际输入/65536累计输入/16384累计输出，map8000Unicode、无重叠。提示逐字复用封存版A/S；P0沿冻结原生KG入口。

每源实际N题登记9N单元；A计划calls=范围块数+1或0(UNRESOLVED)，S=全文块数+1，P0路径上界3，三次相加是本源总调用上限；不照搬177/54。全pilot来源清单、N、调用图、索引及生成累计预算、时间、共同可运行集、每source预算均须首网络前锁定。单源生成墙钟min(5400,120×9N)；当前已计划源文本长度≤56000字符，不因回答好坏替换文档。reduce实际字节/响应token在线核，预检不声称精确token保证。

全批首次网络前封sources、questions、raw/canonical/map/XML、结构、Gold(由评估角色hash封存)、方法代码/提示/环境/权利/曝光角色表及总预算。只有同一源码适配的离线行为测试与独立设计/代码审无阻断才能调用。无支持结构不得人工补造；需要改parser则新材料降工程开发，不能继续称原冻结留出。

## 评价

独立两角色先完整原文/解析及Gold审查，AI_REVIEW_ONLY。执行结束匿名内容先判必要条目/属性/限定/新增，再锁定，证据审计按实际输入链核支持与引用；范围适配/访问覆盖、条目完整性、输入支持、严格终点分报。未知不是错误、UNRESOLVED不是语义失败、资源失败不进入G1。方法作者若访问全Gold或H1语义则登记SINGLE_OPERATOR_UNBLINDED；本先导仅探索性。

后续正式H1/H2需要原协议全部准入，不拿本先导的不足样本放宽G0–G4。若开发版未解决残余，此先导也仅检验冻结版本，结果不用于本轮重新调提示。所有失败/费用与原文拒收保留。
