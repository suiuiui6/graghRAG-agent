# 开发生成器、提示与资源 profile（2026-10-13）

**结论：远程公开开发 profile 已实际执行；三基线共同预算仍未冻结。** 6道开发题的S_SCAN_ALL完成27次请求，消耗71,900 tokens；另2次生产模板诊断消耗4,446 tokens。P0_NATIVE缺可核验共同入库，既有A规则6题均未解析，不能宣称三臂预算已测齐。保持M2_OPEN，不据此进入新方法设计。

## 授权与生成器身份

用户确认没有已有本地模型，随后明确授权远程API形式。本次只发送已公开LinuxCNC/NIST开发文字和无Gold问题，使用已有配置；不上传企业材料。该授权作为[执行补充计划](development-budget-20261013/plan.md)，覆盖技能零API默认限制及旧协议本地主线限制，未授权未来留出实验。未索取、输出或写入密钥，未修改.env。

生产server.py以override=True加载backend/.env；白名单核对文件配置LANGEXTRACT_MODEL_ID=deepseek-chat、官方HTTPS地址、temperature0。生产增强RAG入口实际采用generator.GenerationConfig，默认2048输出、timeout30、max_retries1；config.py另一个同名类的timeout120不是该入口的配置。当前运行服务身份未验证。

本次全部29次请求model字段为deepseek-chat；**29份供应商回执的model均为deepseek-flash**，system_fingerprint均为`aeb56401ca74e127821c4f9126dcb669`。登记请求别名与响应模型两列，不再将请求名当作固定模型版本。temperature0、max_tokens2048，未显式设置thinking。相同fingerprint是回执一致性证据，不证明可复现权重快照。

[官方当前调用说明](https://api-docs.deepseek.com/quick_start/pricing-details-cny/)使用deepseek-flash，[更新日志](https://api-docs.deepseek.com/updates/?release=deepseek-coder)将该名称对应至V4.1 Flash；但[历史公告](https://api-docs.deepseek.com/news/news260424/)称deepseek-chat将于7月退役，与本次10月仍获成功回执不一致。保留这一文档/实测差异，不自行推断兼容映射或权重版本，也未修改生产模型配置。

## 实际提示与生产调用链

生产prompt_builder以system/user两消息构建：仅依据context、逐事实引用、证据不足说明、同语言回答；命中枚举关键词时追加完整列项、保留distinct items和跨chunk合并指令。本次模板诊断通过AST只提取实际常量、纯消息构建函数和枚举判定，给定一个文本片段替代检索context组装。它没有执行原生检索、预处理和后处理，严格标签P0_PROMPT_ONLY_DIAGNOSTIC。

生产“tokens”主要按字符÷4估算；默认context4000约等于16000字符，文本chunk先截8000字符、KG先截4000字符。build_prompt的total_tokens未计完整模板和枚举附加指令。模板字典output_reserve4000不覆盖实际请求max_tokens2048。诊断LCNC原生字符报告2255对API输入2246，NIST2251对1895，不能将其当真实生成token计数。

新会话、常规可运行RAG且multi-query关闭时，P0源码条件最多1次预处理（输出300）加2次回答尝试（每次输出2048）。历史共指、多查询另有条件调用；SelfCorrection未接入。已有token_usage只保留最后成功主回答，遗漏预处理/其他调用及失败重试，确定性拒答的零值也不是全链零成本。旧KG agent的输出及SDK重试未机械闭合，不能并入统一有限预算。独立核查及定位见[专家审查](development-budget-20261013/expert-review.yaml)与执行计划。

## 三臂当前状态

|臂|实际执行状态|预算解释|
|---|---|---|
|P0_NATIVE|CORPUS_UNAVAILABLE / NOT_RUN|91条本地文档登记未发现新两源标签；运行索引身份未知，未建立共同语料可用性，预算未测|
|A_AUTO_READ|6/6 UNRESOLVED|既有scope_v2对冻结canonical及无Gold问题的实际本地路由结果；0生成请求不等于完成答案的零成本预算|
|S_SCAN_ALL|27/27调用SUCCESS，六题均完成map与reduce|完整文字输入遍历通过；仅单次资源profile，未判条目正确或语义完整|

P0的[可用性盘点](development-budget-20261013/p0-availability.json)是有界登记标签检查，不是全索引内容不存在的证明。未用BM25或人工挑片段替代生产P0。A未解析与canonical结构格式/既有规则适配有关，应先走工程排查；未修规则或借Gold指定范围。

S按Unicode字符8000无重叠顺序切块，每题读完整指定来源文字（由questions.input给定来源），LCNC3块、NIST6块，全部map后单次reduce。附带源级结构元数据，不使用Gold目标范围。HTML结构来自h标签，PDF编号行只标候选标题，未把模式匹配当可靠章节边界。源码与prompt全文见[manifest](development-budget-20261013/manifest.json)及逐请求收据。跨块切断、抽取遗漏或归并丢失仍可能存在，当前未做语义裁决。

## 实测资源

|S题目|调用数|累计输入tokens|累计输出tokens|合计tokens|调用耗时和/秒|
|---|---:|---:|---:|---:|---:|
|DEV-L01|4|8439|1083|9522|11.515|
|DEV-L02|4|8257|1039|9296|11.047|
|DEV-L03|4|9006|2004|11010|15.563|
|DEV-L04|4|9397|3016|12413|18.390|
|DEV-L05|4|8460|1344|9804|13.156|
|DEV-N01|7|17425|2430|19855|22.031|
|S合计|27|60984|10916|71900|91.702|

两次模板诊断另计：输入4141、输出305、合计4446 tokens，调用耗时和4.688秒。总输入65125、输出11221、合计76346 tokens；整个本地profile约96.406秒。均有完整供应商usage，finish_reason全为stop，无重试/失败/截断，未知成本调用0。未核算货币账单。

S单次最大输入3001 tokens、单次最大输出1358；逐题累计最大输入17425、最大输出3016、最多7调用，最大题耗时22.031秒。这些是已观察的开发负载，**不是未来保证或三臂共同上限**。若后续预算要覆盖本轮所有S请求，须至少容纳这些已观察峰值，并另计P0预处理/重试及A可执行路径；后两臂未测齐前不能冻结主比较额度。

S输入中13440 tokens为供应商缓存命中，已包含在60984输入总数中，不扣除或二次加计。调用顺序固定且缓存逐步变热，时间/费用不作臂间公平比较。6题只有2来源单元，5题同一HTML页，单次profile不估计稳定失败率、总体置信区间或性能显著性。

## 验证与剩余事项

执行上限29请求、单次2048声明输出、累计messages JSON UTF8≤600000字节、请求窗口900秒、每worker≤45秒，无重试。实际完整messages为268279字节。失败或usage缺失即全组停止；本地超时不等于远端取消，未知费用不能写0。本次未触发这些停止条件。

离线8项边界检查通过（端点/模型拒绝、错误正文与异常保密、usage一致性及截断识别），无网络/真实凭据读取。prepare自动核算29请求、21map/6reduce、连续分块覆盖。summarize实际核验全部请求/响应SHA、完整messages SHA/字节、每次usage与累计值、六题完整文字输入遍历，以及源码/原文前后hash一致。Gold原件验收复跑35冻结文件、12专家hash、145证据绑定通过；不加载Gold参与模型输入或语义评分。

关键产物：[机器资源汇总](development-budget-20261013/resource-summary.json)、[逐调用账本](development-budget-20261013/run-01/ledger.json)、[运行摘要](development-budget-20261013/run-01/summary.json)、[离线边界核验](development-budget-20261013/offline-verification.json)。本次未启动生产服务、改索引、改产品代码、安装依赖或提交推送。

下一步：在隔离开发环境中先补齐可核验共同入库与A结构输入适配，再测P0/A全链预算；保留本轮S收据后完成三臂共同额度登记。当前资源profile不能证明简单强基线的可重复语义缺口，H1/H2仍空，M2保持开放。
