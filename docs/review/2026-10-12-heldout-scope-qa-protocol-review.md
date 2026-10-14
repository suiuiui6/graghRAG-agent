# 留出范围问答协议：独立评审与验证记录

项目：graphrag-paper-001；stage：M2。任务：HOLDOUT-PROTOCOL-20261012-REVIEW。
对象：[协议 v0.1](../contracts/2026-10-12-heldout-scope-qa-validation.md)。日期：2026-10-12。
权限：独立只读设计/统计评审，不运行模型、网络、生产链或实验。

## 首轮意见与处理

独立chatbot-reviewer依据sci-skills-statistical-reporting审查，返回2项主要问题、0项严重问题，建议REPAIR：

1. UNSUPPORTED_COMPLETENESS判据不够可重复，可能改变严格主终点及G1/G2。已接受：§7.3增加六行裁决表和四职责边界例，分别记录闭合Gold内容完整、claim支持与穷尽承诺证据；未闭合Gold为UNASSESSABLE，不进入语义失败门禁。
2. 方法作者的盲化不等于评分者盲化。已接受：§3规定匿名随机答案→锁定内容属性→输入证据审计→仲裁→揭盲；角色无法分离时保留先前锁定记录，暴露标ASSESSOR_UNBLINDED且按探索性报告。

首轮合同paper_family=null，与任务文件M不一致；未作为有效验收合并。已要求修正为M并重新读取两处修改作定点复核。

## 文档验证

既有环境执行PowerShell here-string传给`backend/.venv/Scripts/python.exe -B -X utf8 -`，读取协议、contracts索引、专家任务合同及研究状态YAML。

- 首轮协议检查：10节、3本地链接、9必需状态标签、无尾部空格，退出0。
- 专家任务合同：字段覆盖SCI-Skills expert-task schema，3输入文件存在，身份为M2/contract1.0，退出0。
- 修订后检查：2文档、5本地链接、10节、11必需状态标签、研究状态YAML可解析且实验NOT_EXECUTED，退出0。
- 修订后协议SHA256：daf0756b47ef41b42e9b8d2ee0e372f4bf3e3d04fb6a2392ea90c2b6a5f0163f。

这些检查只证明格式、链接与登记一致性；不证明研究效果、统计功效、模型执行或生产测试通过。没有Git提交/推送，未运行产品覆盖率。

## 定点复核

当前状态：DESIGN_REVIEW_CLOSED_NOT_EXECUTION_FROZEN。

原reviewer定点复核派发后保持pending_init，已停止其待启动任务；另由独立chatbot-reviewer按任务HOLDOUT-PROTOCOL-20261012-RECHECK读取§3及§7.3，确认两项问题均CLOSED、限定范围无新增阻断。复核结果见[合同](2026-10-12-heldout-scope-qa-recheck-result.yaml)；主协调者核对project/family/stage/task/version全部匹配，接受该定点结论。其范围不是全协议重新审查，也不证明实际双人评分/盲化已执行。

首轮全协议审查与本次定点复核共同形成设计评审闭环。协议仍为待执行登记的设计版本；样本、预算、模型与Gold执行门禁未满足，不冻结或启动实验。研究M2保持开放。文档及索引最终链接/schema检查见日期记录。
