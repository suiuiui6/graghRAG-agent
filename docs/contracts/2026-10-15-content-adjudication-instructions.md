# 匿名开发答案内容裁决操作口径

供两个彼此隔离的AI评审使用；仅内容判断，不判断未提供的模型输入支持。资料为匿名content-packet、此口径、冻结Gold紧凑字段及内嵌原文证据。禁止读取operator-only-mapping、运行回执、输入链、资源、另一评分者或历史臂答案。不猜测臂名，风格可能泄漏方法，不能称人工双盲。

每份答案必须产生以下JSON结构（所有54份都保留，失败运行所有内容判定null，不将失败当语义错误）：

```json
{"reviewer_id":"assigned-id","review_mode":"AI_REVIEW_ONLY","answers":[{"answer_id":"B001","question_id":"DEV-L01","items":[{"item_id":"I01","present":true,"quote":"答案原文子串","atoms":[{"atom_id":"HOME_SEARCH_VEL","correct":true,"quote":"答案原文子串","reason":"值与Gold一致"}]}],"extra_items":[],"qualifiers":[],"completeness_claims":[]}]}
```

必须遍历题目每一Gold item与每一atom，字段correct/present只能true/false/null。中文或英文同义表达、等价数值可通过；有矛盾不通过。present仅判断正确条目身份是否出现，不能以全部属性正确为条件；属性逐atom独立。true必须有实际答案子串quote；漏项或漏属性为false，可quote空串并说明。无法裁定才null，不因写法不熟直接判错。列表组件和条件独立，不擅自降低标准。

extra_items列所有非Gold新增条目，以及可能影响正确性的主动新增事实，字段text/in_scope/correct/reason（三值规则同上）。解释性复述无需重复列；即使原文某处正确，问题限定范围外的列表项仍in_scope=false。Gold targetregion允许支持上下文，不能用“句子出现在目标片段外”直接判越界，按问题请求对象及限定范围裁定。对无源证据的额外事实correct=null，并交后续证据审计。

每答案另填predicted_item_count：实际回答的、问题要求对象类型的去重条目数（不是句子数/属性数；重复同义项计一次）。空答案填0，无法可靠切分填null并加precision_reason。item precision按正确Gold身份数/该分母计算，错误属性由atom/strict tuple另计。

qualifiers逐内嵌required限定填{id,correct,quote,reason}。列举完成性陈述填{text,status,reason}：显式“全部/仅这些”等承诺若Gold已证遗漏，status=["FALSE_COMPLETENESS"]；内容已齐但输入链尚未知，status=["INPUT_AUDIT_PENDING"]；没有承诺则空列表。用户问题要求全部不等于答案自己声称穷尽；普通列举形式本身也不自动记承诺。最终supported/unsupported在输入链审计后按主契约裁决，不在匿名内容阶段臆测。

同题、同run_status、字节完全相同答案可复用同一内容裁决（exact_content_groups），展开成每answer_id一条，不能把不同输入的证据支持也一并复用。语义类似但非完全相同必须另读。可用本地脚本生成JSON骨架和复用，但不得用字符串包含自动替代语义判断。输出文件须结构校验，保留所有原判，写完后锁hash再进入仲裁。

统计限制：仅两源六开发题，81scoring_atoms含例子/条件，不均是独立测量；三次重复不增加独立文档数。此操作不认定方法创新、不推进论文阶段。
