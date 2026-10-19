# 共同三臂执行器独立代码审查

2026-10-15；审查common_three_arm.py及专项测试与离线预登记。只读代码、公开源结构/非Gold问题与旧资源身份；未读Gold、新生成答案、密钥，未联网或发API。

## 审查总结

**PASS_FOR_AUTHORIZED_BOUNDED_DEVELOPMENT_EXECUTION；未关闭问题0**。C1/C2最终修复已独立复核，专项25 passed，正式最终登记、六题fresh A解析、旧145源码+新runner、四KG、54平衡单元与177路径上界已核实。仅放行用户已授权的公开开发预算/诊断生成；未执行语义裁决，不能据此证明方法缺口或推进M2。

## 问题清单

### 🟠 High C1：A复用预计算范围而未执行单元自动解析

- 位置：`backend/research/common_three_arm.py` 的 `run_worker` A/S分支及 `map_reduce`。
- 问题：当前A直接用旧inputs.work的resolution/chunks，fresh session只重跑模型，未执行resolver；范围计算时间不在登记的单元120秒内。已有预计算为合法无Gold结构结果，但不能据此报告每次新单元执行自动选择及其完整耗时。
- 建议：每个A单元使用冻结Source/StructureIndex重新执行现有resolver和assemble_scope，断言源/范围/chunks与登记一致；结构原件解析可作为共享预处理成本单列。Before：`chunks=work['chunks']`直接执行；After：`resolved=resolve(...); assert resolved==registered; chunks=assemble(resolved)`。
- 主审已接受，等待修后陌生输入测试与最终正式快照核验。
- 最终关闭：`resolve_a_work`每A单元重建冻结Source/StructureIndex，调用resolver与assemble_scope，核COMPLETE_SCOPE、resolution/chunks逐项等于登记，记录local_resolution_seconds；该调用发生在父进程绝对120秒deadline内。陌生第4/5节合成测试核正常输入及登记漂移拒绝。正式六题逐一独立fresh重算全部MATCH。

### 🟢 Low C2：实际输入区间字段未包含heading元数据

- 位置：`map_reduce` 返回的actual_model_input_intervals。
- map消息除body chunks还含全源heading结构index。现字段只列body区间，不能称全部模型输入源映射。建议分别记body_source_intervals和structure_metadata_input；实际证据裁决以完整wire messages为准。不能因body不含某heading便断言模型没看到该标题。
- Before：单一actual_model_input_intervals。After：注明body scope并独立记录结构标题内容/坐标。此项不阻断保留完整wire的运行，但必须在指标解释中披露。
- 最终关闭：新增body_source_intervals、structure_metadata_input与actual_model_input_intervals_scope=body_only标记；离线测试核full source body及heading单列一致。

## 独立验证与契约闭合

1. 既有锁环境执行：PYTHONPATH=`backend;langextract`，TEMP/TMP指向workspace，`.tmp/backend-quality-venv-20261012/Scripts/python.exe -B -X utf8 -m pytest backend/tests/test_common_three_arm.py -q -p no:cacheprovider --basetemp .tmp/common-three-arm-review-20261015`：**22 passed in 3.46s，exit0**。全部离线MockTransport与假密钥，未使用真实env-file。
2. 独立读取离线registration并复算146源码、docs_store、四KG哈希；四KG分别与永久receipt-freeze `executed-isolation/kg`比对一致。54单元unique、每臂18、每题3重复各位置含三臂，planned_attempts总177，S每源3/6块。第一次审计误用archive key前缀产生KeyError，查实际归档key并更正路径后验证通过，未改材料。
3. 静态核P0固定scoped KG调用图：preprocess一次POST，generator默认max_retries1最多两回答尝试，无query_optimizer/domain_dict注入；原生prompt/repair/API输出沿用冻结代码。原生失败重试可能被闭锁guard阻断，最大计划3是保守源码上界。
4. 共同guard实际requests/httpx1/SDKhttpx2同步/异步均继承已核守卫；temperature必须0、flash/thinking/max_tokens由双层守卫校验，单次24000/累计192000bytes、8attempts、计划路径上界均发前核；8192单次/65536累计输入与16384累计输出实际usage响应后核，已知超额RESOURCE_CAP、未知费用/异常停全组，原费用保留。
5. 父进程在构造子进程command之前生成deadline，子进程全部verify/cache准备/激活/模型均在120秒父timeout内；guard phase继承绝对deadline。全局5400秒在首单元前计，后续NOT_RUN写全54单元。新rewritecache仅删新runtime内固定SQLite四文件，拒绝外根/目录，不碰冻结旧缓存。
6. 源码来自旧有效snapshot而非当前产品；只复制公开两源KG与重定位docs_store。无生成阶段Gold读取；模型messages完整、失败raw日志不落盘，安全父进程只在真实run打开env-file。Windows仅audit-only-windows，不宣称机械沙箱。正式登记仍应绑定contract/hash、全部共同额度与最终runner，防代码/契约漂移。
7. 新契约D1 target evidence region与允许support context的细化已读认可：NIST问题指定整个第3节时读含3.1可范围正确；Gold目标列表区域char P/R只作访问诊断。不得将target-region precision当selection正确性的充分判据。

## 优化建议汇总

### 最终准入证据

正式候选锁环境独立复跑 `test_common_three_arm.py`，同PYTHONPATH与workspace TEMP，basetemp `.tmp/common-three-arm-final-review-20261015`：**25 passed in 3.28s，exit0**。实际 `verify_registration('.tmp/common-three-arm-final-20261015')` 验证全部源码/KG/规范文本/契约计划/历史KG归档/依赖身份，复核完整共同caps字典与54/177；六A问题使用正式冻结文本重新执行`resolve_a_work`全部MATCH，exit0。全程socket.connect/connect_ex/create_connection拒绝网络，未读Gold或密钥。

最终runner SHA256 `d5cbf52cb9dc5ff30bdd13fe7de9c050751cec6413f4e69f31f49f2abc998d9e`；正式registration SHA256 `0bc8fe290a67d3b3c047372e2685eb33cd5fed7c681ddd95da76df40233228ec`。最终新代码补了子进程环境白名单、独占HOME/cache/TEMP、contract/plan与历史KG归档hash、共同model/caps机器登记，原先继承全部env的边界亦关闭。本审未以主审80专项自报代替自身25项与实际冻结核验。

1. 按已冻结54单元/共同caps执行授权公共开发生成，任何未知费用停组，已知资源超额保留并标RESOURCE_CAP，不自动增额/补跑。
2. 输出冻结后才启动独立内容/证据裁决，保持AI_REVIEW_ONLY、SINGLE_OPERATOR_UNBLINDED、M2开放。
