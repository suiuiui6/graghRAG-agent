# 三臂共同配置、预算与分面评价 v1

状态：执行前设计；需独立复核与机器登记冻结。仅开发诊断，M2_OPEN；H1/H2仍为空。继承2026-10-12留出协议，不将本轮开发结果当留出结论。

## 配置与输入

三臂复用已核验的两来源、六题、规范文本及20261014 inputs.json结构。P0复用executed-isolation中冻结283节点/1008边KG与docs_store，不重新抽取。记录每个输入、KG文件、提示、执行源码及依赖身份SHA256。不得修改历史冻结包。

共同请求模型deepseek-flash、temperature=0.0、thinking disabled、非流式、生成max_tokens=2048。P0原生预处理仍max_tokens=300；原生提示、检索、后处理、API4000字符截断保留，按最终API答案评分并另存完整生成。A/S用同一system/map/reduce文字、同一heading结构元数据、8000 Unicode字符块；A按现有自动范围映射切块，S全指定文档切块。禁止Gold参与生成、选范围、补上下文或失败重试。

每题每臂3次新进程，54单元。顺序按题序、重复序，三臂用(P0,A,S)、(A,S,P0)、(S,P0,A)循环且题序轮转平衡；完整schedule执行前冻结。每个P0单元使用新的独立rewrite-cache，不带上次查询缓存；供应商缓存不能强制清空，记录cached usage。单元前后验证冻结KG与执行源码无漂移。只允许公开两源；不读生产KG或企业材料。

结构解析与建库为共用、固定输入预处理，成本沿用前轮记录单列，不混入在线回答墙钟。A每个fresh单元仍重新调用同一resolver/assemble_scope，并核范围与分块等于登记值，其耗时计入120秒；不能把已预计算范围冒称每次自动解析。S使用同一冻结结构导航元数据，不额外加入人工清单。

## 共同预算与停机

每单元预发送限制：最多8次HTTP尝试；单次完整JSON UTF8 <=24000字节，累计<=192000字节；声明max_tokens<=2048（P0预处理300）；本地墙钟120秒，含进程启动、范围/检索、缓存准备与全部调用。响应后检查actual usage：单次input<=8192、单元累计input<=65536/output<=16384。字节不等于token，无供应商本地精确tokenizer，不能声称发前硬token保证。

已知usage超额保留费用，单元RESOURCE_CAP并拒绝后续调用；可继续其他预登记单元。缺usage、传输中断、SENT_PENDING、超时且远端费用未知、非法响应/泄密，停止整个profile。不得自动重跑或增额。已完成前序调用保留但失败单元不算成功答案。全局5400秒从首单元启动前计时，耗尽未运行项记NOT_RUN，54分母保留。

离线精确调用计划：A每轮14，S当前全源块为LinuxCNC3+reduce、NIST6+reduce，即每轮27；P0最多预处理1尝试+主回答2尝试=3/题（默认max_retries=1）。54单元全局路径上限177尝试；这是路径限制，区别于54×8=432共同理论额度。全局声明输出上限177×2048=362496 token，实际用量单列；index费用不计本轮但单列历史建库成本。冻结前须从当前chunks及原生重试配置证明177，无法证明则不执行。

## 范围选择与访问分开

1. A selected_scope按resolver原样登记，对照问题范围条件独立裁决。Gold scope是target evidence region，scope_semantics允许支持上下文；其字符交并比仅称target-region access precision/recall诊断，不能把访问支持上下文判选择错误。问题指定整个第3节时读取整个第3节（含3.1）可选择正确，即使Gold目标列表仅一页。仅在问题范围本身有可靠闭合边界时评价selection span P/R，另报题目要求证据绑定覆盖率。
2. S deliberate全源visited_source_intervals，不把低访问precision记选择错误。其map相关/无关判断和最终条目范围归属单列，无法从map可靠复原selection时记UNASSESSABLE，禁止从最终正确答案反推范围选择成功。
3. P0隐式KG检索没有完整属性/边源span映射，selected_scope/span P/R为UNASSESSABLE；节点标签exact projection仅可独立诊断，不代表所有KG证据。登记实际模型可见KG输入与最终越界条目。
4. visited_source_intervals、actual_model_input_intervals、selected_scope分别保存；A/S输入必须是exact canonical slices，reduce只见map摘要，不能拿未传入原文直接证明reduce支持。

## 内容与证据的独立裁决

冻结全部输出后，按确定性shuffle产生匿名编号，隐藏arm/重复/资源/输入链。两位独立AI内容评审只读问题、Gold及匿名最终答案，彼此隔离；先锁内容表再向证据审计揭示输入链。匿名措辞可能泄露臂，记录该限制，不称人工盲评或human-verified Gold。原始Gold为AI_REVIEWED，36项81属性与1非穷尽限定。

评分表每答案逐Gold item列presence(true/false/unknown)、逐scoring_atom列correct(true/false/unknown)、原句证据、理由；仅名称正确不能替代属性。item recall=出现的正确条目/Gold条目数；attribute accuracy=正确属性/固定81属性对应题分母；strict tuple要求该item全部所需属性正确。重复同义项只计一次；相互矛盾的重复不算正确属性。额外项逐条审查其范围/真实性，不能只看Gold召回。

原子claim按一个可独立证伪的item-attribute-value/条件/例子切分；表格每事实单元为一claim，合取拆分，重复语义只计一次，矛盾保留两条；标题/免责声明/引用标记本身不算事实。限定及完整性宣称单独列。分歧由第三位AI仲裁，保留两原判与最终理由；unknown不默认为支持或正确。

额外报item precision=正确范围内去重item数/所有所答去重item数；空答案precision=null、recall=0，unknown留在所答分母但不算正确。无法确定item切分时该precision=null并说明，不伪造数值。机器裁决schema固定answer_id、question_id、items[{item_id,present,quote,atoms[{atom_id,correct,quote,reason}]}]、extra_items[{text,in_scope,correct,reason}]、qualifiers[{id,correct,quote}]、completeness_claims[{text,status,reason}]；三值均为true/false/null。证据表claims[{claim_id,text,content_correct,in_scope,input_supported,citation_entails,map_call_ids,final_call_id,locators,reason}]。不得删减未答Gold项。

证据审计逐claim记录content_correct、in_scope、input_supported、citation_entails及定位。A/S必须核map实际源片段支持、reduce可见map支持两跳链；P0只用实际调用上下文，不把完整KG库当已检索证据。引用存在不等于蕴含；原文正确但输入没支持标input_supported=false，精确位置无法确认标unknown。未给引用记citation_entails=false；输入支持可独立为true。支持率true/全部事实claim，另列unknown率；空答案支持率null。

题级strict supported complete：Gold所有item/属性/限定正确、无错误或越界额外事实、所有事实claim实际输入支持；若完整性宣称则需完整证据，且不得有unknown。FALSE_COMPLETENESS（漏项却称全）和UNSUPPORTED_COMPLETENESS（范围覆盖不能推出语义穷尽）分别登记。不以引用格式替代支持判定。

完整性判据沿用旧协议§7.3：闭合Gold、完整范围访问或可核完备清单、逐claim支持及全部必要限定同时满足，可判SUPPORTED_COMPLETENESS。只证明机械扫描全部而有map遗漏、未证清单闭合或输入链不支持时才判UNSUPPORTED_COMPLETENESS；没有完整性宣称记NONE。FALSE与UNSUPPORTED可同时成立，保存标签数组。

## 报告

54单元状态全列；按题×重复×臂展示三个维度及资源，不将失败/NOT_RUN静默删掉。两来源聚类的描述汇总，六题和三次重复非独立文档，不作显著性、泛化、期刊创新或方法缺口结论。只能说明本轮开发中的可重复问题，进入新方法仍需未来独立留出门槛。
