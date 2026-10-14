# 开发预算 profile：远程授权补充与执行计划

项目 graphrag-paper-001，M2_OPEN。仅预算探索，不执行留出验证或方法优劣裁决。

2026-10-13 用户明确说明没有本地模型，随后授权“可以用远程调用APIkey的形式吧”。本次授权覆盖SCI零API技能默认限制以及既有协议的本地主线限制，仅用于已公开的LinuxCNC/NIST开发原文和无Gold题目；不上传企业材料，不索取/保存/打印密钥。使用现有backend/.env中的配置，限定官方HTTPS地址。旧协议不回写历史执行状态。

## 核定结果与测量边界

- backend/server.py以override=True加载backend/.env；当前文件白名单模型deepseek-chat、temperature0、官方api.deepseek.com。未核运行中服务身份。生产回答实际generator.GenerationConfig默认max_tokens2048、timeout30、max_retries1，与config.py同名类不同。
- 正常新会话P0最多1次查询预处理+2次回答HTTP尝试。预处理默认deepseek-chat/300输出；最终回答2048输出。共指、多查询为条件分支；SelfCorrection未接入。生产usage不覆盖全链。Requests等待timeout不能推导整链硬截止。
- P0_NATIVE：新2源未进入可核验生产共同索引，CORPUS_UNAVAILABLE/NOT_RUN，预算未测。不得以人工top-k或旧材料冒充。
- A_AUTO_READ：既有scope_v2在6个无Gold输入上均UNRESOLVED；只记录本地路由结果与耗时，不修解析器，不将0生成调用视为完成答案的0成本预算。
- S_SCAN_ALL：完整canonical文字按8000 Unicode字符、无重叠、源内顺序切块，LCNC3块/NIST6块。每题全部map后单级reduce。源级结构索引由原HTML h标签/原PDF文本行构建，非Gold范围。每块带字符坐标及引用ID。map保留原文支持内容及限定，reduce逐条去重保留属性/引用；中间结果不假设无损。
- 两次P0_PROMPT_ONLY_DIAGNOSTIC：每源首8000字符，提取实际生产build_prompt的模板与枚举指令形成消息。替换context组装为一个已给定文本片段，仅测生成配置/模板请求成本，绝非P0_NATIVE。

## 有界执行

先两次模板诊断验证响应及usage，再按DEV-L01..L05、DEV-N01顺序执行S；不看Gold，不按答案选择参数。S=5×(3+1)+1×(6+1)=27请求，加2诊断共29。temperature0、max_tokens2048、不重试。最大声明输出59392 tokens；累计完整JSON messages UTF8上限600000 bytes（独立资源保护，非token预算）；全局本地单调时钟900秒，每worker最多45秒且不超过剩余时间。调用前检查动态reduce完整消息与累计上限。网络失败/usage缺失/截断立即停止全组，不重新提交未知结果请求。

900秒约束本地请求窗口，启动worker紧前重算剩余额度；最后收尾写盘另计，不能称整进程严格900秒。发送状态区分HTTP_RESPONSE_RECEIVED、REQUEST_ATTEMPTED_DELIVERY_UNKNOWN、UNKNOWN与NOT_ATTEMPTED。本地终止不证明供应商取消；失败/超时且无usage记UNKNOWN成本，不记0。只统计收到的有效供应商usage作为known subtotal，有未知调用则总成本不完整。记录response model/id/fingerprint（如有）、完整消息、原输出、finish_reason、token usage、耗时、request SHA及源码/原文SHA。deepseek-chat别名不是固定权重版本；响应也不能证明权重快照。

## 验证与完成条件

根代理仅拥有本目录预算脚本/收据/报告及memory追加；其他产品修改保留。预算专家独立只读复核设计与结果。准备模式不联网、不读密钥；执行子进程才读取现有密钥，错误正文不落盘、不打印。所有输入只能来自sources.json/questions.input.json/结构映射/源码模板，不加载questions-gold或answers。原文hash、输入无Gold字段、连续块覆盖、自动调用上限、输出上限和字节guard先离线核验。

执行后按调用和题累计input/output tokens、实际调用数、耗时、截断及未知usage，独立于字符代理统计。以实际可用数据建议后续预算，不因P0/A缺可运行条件而冻结虚假的三臂共同预算。更新memory，无commit/push/安装/生产服务启动/索引写入。
