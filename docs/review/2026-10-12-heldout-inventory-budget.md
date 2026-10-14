# 留出候选盘点与开发集预算测量

项目graphrag-paper-001；日期2026-10-12；M2_OPEN。
依据：[留出协议](../contracts/2026-10-12-heldout-scope-qa-validation.md)。
本轮完成本地只读盘点、开发材料计数和旧usage核验；实际留出与生成预算均未达到冻结条件，不是模型实验。

## 1. 结论与用户确认

用户明确确认这批企业安全管理规定、隐患标准等上传资料具有本地论文研究使用授权。用户同时确认“此前是否用于论文QA/标准答案/规则调试”不确定，需要保留曝光待核实。公开原文、再分发和第三方传输不由本次本地授权推出。

限定资产目录中有62个原始/解析文件、27个完全相同hash组。安全研究候选33副本去重后为8份，不是33独立文档，也不是8个已确认独立家族。8组均已有索引元数据；入库不等同论文实验曝光，查无引用也不证明未曝光。

**实际准入留出H1=[]、H2=[]；8组均保留隔离候选。** 这不是“现有材料不能研究”，而是不能以未知曝光材料支持留出泛化主张。即使曝光全部核实，现有8份也比协议12份设计目标少4份；该目标本身不是功效保证，不事后降门槛冒称确认性通过。

## 2. 候选清单

完整路径、所有副本及SHA256见[机器清单](scope-holdout-20261012/run-01/inventory-budget.json)。以下名称仅为文件标签，不核验其法律效力或现行性。

| 候选ID/hash前缀 | 文件标签 | 副本 | 准入 |
|---|---|---:|---|
| C-1163f36560f3 | 吉林化建零容忍规定，含test/test-kg改名副本 | 7 | QUARANTINE |
| C-b5e9ae1fdbf9 | 隐患判定标准通用部分 | 4 | QUARANTINE |
| C-0000e756b3ec | 隐患判定标准工程建设企业部分 | 4 | QUARANTINE |
| C-4c5ea4fb6dd1 | 工程股份“五个零容忍”通知 | 4 | QUARANTINE |
| C-7ce1735d7f94 | 寰球附件2停工条款 | 4 | QUARANTINE |
| C-3c8382414415 | 危险化学品安全法命名文件 | 3 | QUARANTINE |
| C-c03d4a040075 | 寰球附件1高压线 | 4 | QUARANTINE |
| C-67e5e6baf375 | GBT50484-2019命名文件 | 3 | QUARANTINE |

两份隐患标准可能为同一系列，两份寰球附件可能同族；这是由标签推断的待核关系，不将文件hash当独立家族身份。近重复核验及标注角色分工尚未进行。本轮未抽取/阅读这些候选正文，不将候选送入开发token计数或模型。

旧D1、D2、D3及D2的MinerU MVP副本保持development。8份同hash申报书未扩大研究授权，排除；sample及demo/test伪文件排除。产品tests临时夹具、隔离副本、论文排版产物和项目评估PDF不计新原始资料。首次宽目录探索的782条混有大量临时测试文件，已弃作样本口径；最终限定资产目录范围可复现，不能将782写成文档样本数。

独立数据专家读取时docs_store有91记录，包含8企业条目及大量doc_partial/doc_empty等夹具；不能当91独立实际文档。registry文件hash和本轮变化检查见机器清单。分组依赖完整内容hash，文档标签关联仅为元数据join，不声称索引内容身份已验证。

## 3. 开发集实测：原文规模

既有本地`BAAI/bge-m3`缓存tokenizer，tokenizers 0.22.2；从本地tokenizer.json直接编码，不加载权重、不推理、不联网，关闭padding/truncation与special tokens。**这是检索tokenizer代理计数，不是生成模型token数。** 可复核输入规模，不可据此给生成窗口或FIT/OVER定类。

| 已暴露开发原文 | Unicode字符 | UTF-8字节 | 本地代理tokens |
|---|---:|---:|---:|
| D1制氨论文 | 22,366 | 38,228 | 14,167 |
| D2 Attention论文 | 42,551 | 42,636 | 13,236 |
| D3架构规范 | 17,729 | 22,650 | 6,051 |

| v2目标范围 | 代理tokens |
|---|---:|
| D1-FIG全文目标 | 14,167 |
| D1-COST摘要 | 735 |
| D1-LIMITS | 310 |
| D1-FUTURE第4项语义目标 | 62 |
| D2-ATTENTION与D2-NONE各自完整3.2.3 | 各306 |
| D2-DATA 5.1 | 153 |
| D3-TOOLS | 233 |
| D3-SUPERVISOR | 68 |

FIG全文审查范围与题注投影输入不是同一个分母；不能把14,167直接当模型必需输入。其他8题目标都很短，仅靠这些短目标不足以校准跨块全扫描聚合。开发题新版比旧问法有更多必需属性，旧completion长度不能证明新版所需输出额度。

## 4. 旧调用实际usage复核

读取既有27份响应与对应plan；不是新执行。每臂9题、每题1次，B2/B3预先给定正确范围；B1不是生产基线。旧输入上限为8192 UTF-8字节，不是8192 tokens，不能转成新协议token上限。以下prompt包括供应商记录的完整请求开销，不等于原文token计数。

| 旧臂 | prompt最小/中位/最大 | completion最大 | 全9题总tokens |
|---|---|---:|---:|
| B1 | 2357 / 2906 / 3754 | 507 | 27,769 |
| B2 | 243 / 461 / 876 | 316 | 5,830 |
| B3 | 194 / 390 / 818 | 356 | 5,134 |

合计38,733 tokens，与逐响应usage求和一致，27份finish_reason均stop。旧request max_tokens=2048是请求上限，507是观察峰值；两者都不是新任务最优输出额度，不能据此削减预算或证明所有长范围输出可容纳。

## 5. 预算登记裁决

已测：三份开发原文、九个v2目标范围及旧27调用usage。
尚未测：实际生成tokenizer、v2完整prompt/chat-template开销、S全扫描map/reduce输出长度与累计tokens、P0原生完整调用图、三臂各阶段运行耗时及重试。当前检查的缓存仅识别到检索/重排tokenizer，未识别生成器tokenizer；不推断整台电脑不存在其他模型。

因此registration保持：

- generator/model/tokenizer身份：PENDING；FIT/OVER：UNKNOWN。
- per-call input/output、累计input/output、调用数、wall-clock：PENDING，未冻结。
- 所有三臂预算要在同一真实生成tokenizer下计算完整prompt与输出预留；现有代理仅可辅助估计文件规模。
- 开发profile下一阶段先只做tokenizer-only序列化计数；真实map/reduce输出与延迟必须通过单独登记的本地开发执行才能测量，不把计划标成测得。
- 未识别合法可用的本地生成路径前不下载安装、配置外部API或重跑历史远程请求。

可执行profile计算规则：输入上限需满足模型上下文窗减去输出预留，完整prompt必须包括模板/工具schema/元数据；累计额含每次map/reduce、路由、补证与重试，不只算最终调用。主轨额由开发测量与明确资源约束共同决定，不从留出答案挑阈值。完整扫描更高资源诊断单列，不用偏小上限制造失败。

## 6. 复现与只读验证

分析源码：[audit_inventory_budget.py](scope-holdout-20261012/audit_inventory_budget.py)。实际命令（项目根，既有backend环境）：

```powershell
backend/.venv/Scripts/python.exe -B -X utf8 docs/review/scope-holdout-20261012/audit_inventory_budget.py --root D:/graghRAG-agent --tokenizer C:/Users/14156/.cache/huggingface/hub/models--BAAI--bge-m3/snapshots/5617a9f61b028005a4858fdac845db406aefb181/tokenizer.json --output D:/graghRAG-agent/docs/review/scope-holdout-20261012/run-01
```

本次退出0。重跑须使用新的run目录，拒绝覆盖旧输出。脚本只写报告目录，不导入生产模块、不读取.env、模型权重或候选正文。tokenizer路径/hash、开发源hash、旧响应hash与脚本hash写入机器清单。

后续独立只读验证对62个源文件全部重新hash，大小及内容均一致；输入Gold/plan/registry/tokenizer/开发源/响应前后无变化。检查8候选/33副本、27响应及38733总tokens通过，退出0，详见[验证记录](scope-holdout-20261012/run-01/verification.json)。在本轮观察窗口内未检测到源修改，不推断整个并行工作区不变。

实际split决定：[split-decision.json](scope-holdout-20261012/run-01/split-decision.json)。独立数据专家合同：[inventory-expert-result.yaml](scope-holdout-20261012/inventory-expert-result.yaml)。独立统计专家复核确认逐条usage、三臂合计、代理计数边界与未冻结结论，见[专家结果](scope-holdout-20261012/budget-expert-result.yaml)。

独立复跑使用同一命令，仅将输出目录改为`run-02`，退出0；两次JSON仅`created_utc`不同，其余所有字段一致，62个原始/解析文件再次hash通过，见[复跑验证](scope-holdout-20261012/run-02/verification.json)。专家曾看到原时间为本地+08:00格式；协调者直接读取原JSON实际为`2026-10-12T10:13:56.650543+00:00`，符合脚本UTC输出，原记录未修改。原时间渲染差异的来源未确定，数字结果已独立复现。

## 唯一下一步

保留8组隔离候选和空H1/H2；曝光无法核实时改用尚未用于开发、许可可核验的新来源。同步确认实际本地生成模型/tokenizer后，完成完整prompt与全扫描预算profile，再冻结样本/预算。当前数据对病例与盘点SUFFICIENT，对本协议留出验证INSUFFICIENT，M2保持开放。
