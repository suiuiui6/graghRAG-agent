# 公共开发实际资源收据独立复核

2026-10-15；SCI统计报告专家，项目graphrag-paper-001 / M / M2 / DEV-P0-A-BUDGET-20261015。审计既有本地实验材料，无新远程调用、密钥/Gold读取或语义评分。

## 审查总结

66份实际HTTP请求与回执、145个隔离源码文件及源输入哈希闭合，费用未知0、失败0、所有finish为stop。**PASS_CANDIDATE：资源事实复核通过，未关闭问题0**；初审1项Medium登记温度问题已通过追加说明关闭：索引40请求未带temperature，不能把登记0.0扩展至索引阶段。M2保持开放，旧S与本轮P0/A不能构成受控三臂比较。

|轨道|实际调用|输入tokens|输出tokens|合计tokens|请求JSON bytes|缓存命中输入tokens|
|---|---:|---:|---:|---:|---:|---:|
|索引构建|40|101870|17371|119241|443857|57216|
|P0_NATIVE_SCOPED_KG|12|6836|1325|8161|32963|384|
|A_AUTO_READ|14|18689|6218|24907|82686|5248|
|总计|66|127395|24914|152309|559506|62848|

索引成本独立登记，不隐藏在查询预算中。全组本地elapsed约212.594秒；各调用耗时之和不能替代全组墙钟，缓存为供应商实际usage字段，不宣称关闭缓存。所有请求/回执model均deepseek-flash、thinking显式disabled；别名/fingerprint不能证明固定权重。索引温度40/40 OMITTED，P0 12/12及A14/14为0.0；P0预处理6次max_tokens300、主回答6次2048，A14次2048，索引40次4096。

|开发题|P0总tokens|A总tokens|
|---|---:|---:|
|DEV-L01|1350|2369|
|DEV-L02|1149|2625|
|DEV-L03|1516|3019|
|DEV-L04|1486|4669|
|DEV-L05|1284|2425|
|DEV-N01|1376|9800|

## 问题与更正

🟡 Medium T1，`registration.json` 的全局 `temperature: 0.0`：40份索引wire均省略temperature，只有查询轨道明确0.0。建议保留原登记作为历史，追加执行偏差说明与分轨temperature字段；不得回写原HTTP收据或假定服务端默认值。Before：笼统“所有调用温度0”；After：“索引未传、有效值未知；P0/A显式0”。这是报告准确性问题，不否定实测usage。

定点复核关闭：主审新增 `registration-clarification.json`，独立复算原登记SHA与说明完全一致，分轨温度值匹配实际wire。随后再次执行66收据独立审计exit0。原登记/原HTTP材料未回写；T1为 RESOLVED_BY_ORCHESTRATOR。

## 独立验证范围

- 实际执行 `.tmp/backend-quality-venv-20261012/Scripts/python.exe -B -X utf8 .tmp/resume_resource_audit_20261015.py`，exit0，输出INDEPENDENT_RECEIPTS_PASS。首次执行对全局温度假设触发KeyError，检查实际wire后撤去错误假设并独立分轨统计，未修改任何收据。
- 逐条复算66request/response原UTF8 SHA、request bytes与解析JSON、usage算术、实际model/thinking/outputcaps、finish stop、cost KNOWN；核总数66≤72、索引40≤40、P012≤18、A14≤14，559506≤1200000bytes。
- 登记绑定snapshot和inputs哈希，145源码文件及全部源input_hashes逐一匹配；8个执行步骤exit0、all_steps_completed真实。
- 六题A每段输入为canonical Unicode区间exact slice，map原输出进入reduce完整列表，最终answer对应最后回执；范围结构版本记录保留，未借Gold裁剪。
- 六题P0各2次模型调用，native serialized_model_context messages与主回答wire完全相等；executed_sources仅kg、document_id身份一致，API answer严格等于native answer前4000字符。原生repair/提示可能改变模型原文，不能只拿原始completion当API答案；没有将4000字符契约等同模型token截断。
- 索引29个bridge documents及offset原源slice一致；283个抽取标签证据interval/source slice/hash和exact标记逐一复算，native grounded255，exact label source match172。两个数衡量不同事项，均不证明属性/关系或生成答案有据。

## 解释边界与下一步

仅2个开发来源、6题、每题单次，其中5题来自同一LinuxCNC文档；66调用不是66独立研究样本。没有置信区间、显著性检验、效应量或“方法更好”结论。旧S27调用71900tokens属于历史开发profile，输入结构与请求别名变化，不能直接算三臂胜负或冻结公平共同预算。H1/H2空、M2开放。

下一步由主审归档最终资源profile并制定后续受控比较计划。
