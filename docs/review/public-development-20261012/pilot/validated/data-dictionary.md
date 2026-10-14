# 当前开发Gold数据字典与评分规则

身份：graphrag-paper-001 / M / M2 / PUBLIC-DEV-GOLD-20261012。只用于本地开发；AI原文/视觉核对及独立AI复核通过，人工Gold未执行。

|字段/文件|定义|
|---|---|
|questions-gold.v1.json|协调者接受的开发答案，保留被评审候选hash，不能输入被评测模型|
|questions.input.json|模型可见题号/来源ID/问题/范围条件，不包含答案、答案数或Gold范围偏移|
|source_sha256|原PDF/HTML字节身份，原始文件不改动|
|canonical_sha256|对应本地解析文本字节身份，与原件hash不同|
|canonical_char_half_open|Python Unicode码点索引、LF、[start,end)，不是UTF-8字节数；PDF保留换页符|
|quote|必须严格等于canonical文本[start:end]|
|xpaths|原XHTML元素的局部名称XPath（忽略命名空间），块级坐标；ElementTree按DOM文档顺序生成|
|PDF页码|zero_based=7 / one_based=8 / printed_page_label=5；三种坐标分别存储，不混用|
|gold_items|范围内应答条目，6题共36个，按题计算精确率/召回率/全条目完整率|
|required_attributes|每项需要的属性；字段中可含复合语义，所有请求要点须满足|
|scoring_atoms|沿用候选字段名，实质为81个评分单元；并非每个都是最小语义原子|
|required_answer_qualifiers|另计1条“该列表非领域全集”的限定，不当第15类别|
|scope|应答条目目标范围；可读取支持上下文，不能添加范围外答案条目|
|range_condition|6题均scope_given；不证明自动范围选择难度|
|sources.json|完整HTML文字块与17页PDF提取；图示未OCR，完整多模态扫描不准入|
|draft_provenance / draft_evidence|原网页提取记录仅用于历史追踪，不作当前评分坐标|
|freeze-manifest.json|当前标准答案、语料、原件、图像、脚本、许可等字节快照；修改后需新版本和适用复核|

数值/参数值精确比对；同步成员按集合精确比对（空集合表示无最终移动同步）；中文解释接受语义等价，由评分者检查每个复合字段的全部要点，部分满足不能给该字段满分。脚本未执行语义自动评分器。

先按题锁定内容评分，再审核实际模型输入证据支持。Gold有来源证据不等于模型当次看到该证据。保留范围选择、条目完整性、属性完整性、范围外多答与输入支持各项记录，不能混成一个正确率掩盖不同失效。

81评分单元与36条目不当作81或36个独立样本；五道LinuxCNC题同源且相关。H1/H2目前为空，不能报告留出已冻结或泛化结果。开发题全为可回答正例，尚未覆盖无答案/干扰等鲁棒场景。

LinuxCNC原件页脚2026-10-11 09:59:50 UTC，2.9网址分支不是不可变发行标识，以本地sha256固定版本。复制署名/许可须保留../raw/gpld-copyright.html。NIST注明Michael Shneier (2015), Predicting Robot System Performance by Measuring and Composing Subsystem Attributes, NISTIR 8091, DOI10.6028/NIST.IR.8091；Republished courtesy of the National Institute of Standards and Technology。未对外发布原文/标注包。
