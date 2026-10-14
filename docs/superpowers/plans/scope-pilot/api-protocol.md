# 独立DeepSeek对照协议 v1

2026-10-07作者确认设计。本轮27个计划请求：9题×B1/B2/B3各1次，唯一模型`deepseek-v4-pro`；不新增GPT/重复轮/模型判分。独立API流程不宣称遵循SCI-Skills零API执行规则，但仍保留学术证据和阶段门禁。

## 已核验接口

DeepSeek官方 `https://api-docs.deepseek.com/api/create-chat-completion/`，2026-10-07通过平台浏览器实际读取。请求`/chat/completions`支持v4pro；thinking为顶层字段，默认enabled；thinking开启时temperature不生效。本轮固定顶层`thinking: {type: disabled}`、temperature0、max_tokens2048、stream false，不使用额外body包装、不指定未经核验seed。保留返回model/system_fingerprint/usage及finish_reason。URL仅作协议来源，不是本轮传输输出。

## 来源与版本

原离线Gold/冻结/结果不覆盖。`api-freeze-v1.json`重新记录本次实际源文件与代码指纹及旧/新生产指纹差异，不能视作历史可恢复快照或生产回放。当前manifest记录6个生产文件与旧离线freeze不同；本实验不调用它们，也不修改/回滚别的工作。执行前与每次调用前核验manifest guard。

统一question/system prompt，context来自原pilot函数，不由gold条目拼接。B1离线词项检索只是证据控制；B2/B3依赖已知范围，不冒称自动范围识别。8192 UTF-8源文本字节限制不冒称模型token限制；真实API用量按返回记录，模型输入还包括统一指令、题目、字符定位封装。

## 隐私排除

离线B1的D1-FIG上下文含参赛编号。API准备阶段对全部基线统一排除含`参赛编号`的源文本行，保留剩余片段的原始字符位置，日志记录排除事件。此为新增的隐私预处理，原离线结果与API输入不能宣称逐字节一致；不影响图条目真值。拒绝发送真实凭据；不读取其他项目，不上传完整仓库。

## 运行纪律

默认dry-run无网络/无凭据读取。执行时仅程序私下从本项目backend/.env读取既有凭据，固定官方host，禁重定向/环境代理/重试。每个计划单元最多一次请求；调用意图先记日志，防止断电后误认未调用。失败立即停止，剩余单元NOT_ATTEMPTED；不把错误或截断当正确答案。

唯一输出目录位于本项目`scope-pilot/api-runs/`；新建且不覆盖历史目录/文件。真实payload不含headers/Gold答案，成功原响应保留；失败只记状态与安全类别，不记反射密钥的错误body或完整异常。只要实际凭据出现在返回文本，就停止并不落盘该敏感文本。

模型名不代表不可变快照，记录request/returned model与fingerprint，不静默换模型。usage汇总属于实测，费用若无官方单价/账单证据则不填写具体人民币金额。

## 解释边界

全部回答只由本agent对源范围作暂定裁决，不新增LLM grader。Gold和裁决均待独立复核。无检验功效/显著性/总体失败率结论；一题的不同模型输出或不同基线不增加独立文档数。生产B0、自动范围路由、新颖性和新方法优势仍独立待验证。
