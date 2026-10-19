# 实际输入支持与范围裁决口径

必须在两位匿名内容评审各自锁hash后才揭示调用链；角色独立于两内容评审。使用evidence-DEV-*.json的实际请求messages仓库及逐调用输出、resource-audit的exact-slice/归并验证、冻结原文与Gold。不能以整库/未输入页面支持某答案。

每答案输出answer_id、scope_selection（CORRECT/INCORRECT/UNASSESSABLE）、scope_reason、claims、completeness_claims。所有54答案保留；失败单元scope不可评、claims空，不能造事实判断。

claims逐可独立证伪事实拆分，字段claim_id/text/content_correct/in_scope/input_supported/citation_entails/map_call_ids/final_call_id/locators/reason。四判断为true/false/null。定位包含实际call_id、消息/quote、上游chunk_id及Unicode范围（可核时）；不能只给原文整页。表格每参数取值/单位/条件/例子单独一claim；语义重复只计一次，有矛盾保留两条。条目身份可在属性claim中体现；只列名称则每名称一claim；缺失的Gold属性不是“输出事实”，不要拿遗漏当无支持claim填分母。结构标题可作为实际可见文本核其存在，但不是模型提示允许的事实来源替代，另述限制。免责声明/完整性承诺独立记录，不混入普通事实支持分母。

A/S逐claim检查原文实际map输入→map输出→实际reduce输入→最终事实；必须每跳不改变该命题。最终碰巧原文正确但map已漏或错时input_supported=false。P0检查最后生成实际KG上下文→原生最终API答案，并用Gold/原文另核content_correct；KG中有某属性不等于该属性真实。原文无法支持额外KG事实时内容正确性可null。未能核验的支持记null而非false；明知输入缺命题记false。引用标记不存在/无映射/不蕴含该命题为citation_entails=false，不能因为另一个chunk有据而替该引用背书。

范围：A对照问题显式范围与实际resolver结果；不是对照Gold targetregion的最小字符区间。S的全源访问是既定策略，其隐式map范围选择无法唯一定位则UNASSESSABLE，另核最终所有claims的in_scope及map错误收取。P0无完整KG属性边源映射则UNASSESSABLE，不把标签位置当范围精度。支持上下文不自动越界；新增非请求清单条目或从别节引入问题限定属性时独立判定。

completeness_claims沿用主契约，每条{text,status:[...],reason}。内容已漏却说全为FALSE_COMPLETENESS；未证明全目标检查仍承诺全为UNSUPPORTED_COMPLETENESS；两者可并存。闭合Gold、全部必要内容正确、逐事实支持且全目标范围遍历/已验证完备清单满足时SUPPORTED_COMPLETENESS。未作承诺为空列表，内容不全仍不能strict成功。不把问句中“全部”自动当答句承诺。

输出evidence-final.json为{"review_mode":"AI_REVIEW_ONLY","answers":[...]}，另写简短审计记录，说明所有原文/输入链可核验与尚存unknown，不宣称人工验证或独立文档扩增。局部判断不能以批量默认true代替逐事实阅读；完全相同答案的内容可复用，但支持需分别核实际调用链。
