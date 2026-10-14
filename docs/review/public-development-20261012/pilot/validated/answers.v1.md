# 开发题标准答案v1：原件及独立AI复核版

仅用于开发校准。6题36项、81评分单元及1个非穷尽限定；原文核对及独立AI复核通过，已登记本地开发版。没有人工Gold认证，非未来留出。

题目均为scope_given，不能据此宣称自动范围选择难度或新颖性。模型只接收questions.input.json与相应全文文本，不接收Gold。

## DEV-L01

按第6节 Configuration 开头的表格，列出全部回零类型，并分别给出 HOME_SEARCH_VEL、HOME_LATCH_VEL、HOME_USE_INDEX 的取值。

|条目|必需属性|
|---|---|
|Immediate|HOME_SEARCH_VEL：0；HOME_LATCH_VEL：0；HOME_USE_INDEX：NO|
|Index-only|HOME_SEARCH_VEL：0；HOME_LATCH_VEL：nonzero；HOME_USE_INDEX：YES|
|Switch-only|HOME_SEARCH_VEL：nonzero；HOME_LATCH_VEL：nonzero；HOME_USE_INDEX：NO|
|Switch and Index|HOME_SEARCH_VEL：nonzero；HOME_LATCH_VEL：nonzero；HOME_USE_INDEX：YES|

证据定位：原HTML章节/元素XPath及原件绑定文本偏移。

评分：条目命中与属性评分单元分别计分；语义等价可接受，不能用条目名称代替属性。缺项与范围外多答分别记录；实际输入证据支持另审。

## DEV-L02

在6.10 HOME_ABSOLUTE_ENCODER 中，列出枚举代码中的设置值及其行为，并列出该节Note说明的静默忽略行为。

|条目|必需属性|
|---|---|
|0|default：是；behavior：不使用绝对编码器|
|1|behavior：使用绝对编码器，并最终移动到 [JOINT_n]HOME|
|2|behavior：使用绝对编码器，不执行最终到 [JOINT_n]HOME 的移动|
|HOME_IS_SHARED|behavior：设置被静默忽略|
|rehome request|behavior：重新回零请求被静默忽略|

证据定位：原HTML章节/元素XPath及原件绑定文本偏移。

评分：条目命中与属性评分单元分别计分；语义等价可接受，不能用条目名称代替属性。缺项与范围外多答分别记录；实际输入证据支持另审。

## DEV-L03

仅依据6.1–6.3，列出三个速度参数的单位和数值默认值；若没有给出数值默认值，写出未设置时的行为。对 HOME_FINAL_VEL 补充允许的取值条件。对 HOME_SEARCH_VEL，另说明零值对搜索阶段的影响。

|条目|必需属性|
|---|---|
|HOME_SEARCH_VEL|units：machine-units per second；default：0；behavior：假定没有回零开关，跳过搜索阶段|
|HOME_LATCH_VEL|units：machine-units per second；default：0|
|HOME_FINAL_VEL|units：machine-units per second；missing_behavior：使用关节最大速度；value_constraint：必须为正数|

证据定位：原HTML章节/元素XPath及原件绑定文本偏移。

评分：条目命中与属性评分单元分别计分；语义等价可接受，不能用条目名称代替属性。缺项与范围外多答分别记录；实际输入证据支持另审。

## DEV-L04

列出6.11为三关节系统给出的全部示例，按顺序给出三个 HOME_SEQUENCE 值，并说明哪些关节同步最终移动。

|条目|必需属性|
|---|---|
|示例1|values：0；1；1；synchronized_joints：无同步关节|
|示例2|values：0；-1；-1；synchronized_joints：1；2|
|示例3|values：0；-1；1；synchronized_joints：1；2|
|示例4|values：0；0；0；synchronized_joints：无同步关节|
|示例5|values：-1；-1；-1；synchronized_joints：0；1；2|

证据定位：原HTML章节/元素XPath及原件绑定文本偏移。

评分：条目命中与属性评分单元分别计分；语义等价可接受，不能用条目名称代替属性。缺项与范围外多答分别记录；实际输入证据支持另审。

## DEV-L05

列出6.14 Immediate Homing 代码块中的全部配置及其给定值或允许替代值，并说明省略 HOME_SEQUENCE 对 HOME ALL 的影响。

|条目|必需属性|
|---|---|
|HOME_SEARCH_VEL|value：0|
|HOME_LATCH_VEL|value：0|
|HOME_USE_INDEX|value：NO|
|HOME_OFFSET|value：0；alternative：home position offset (HOME)|
|HOME_SEQUENCE|value：0；alternative：other valid sequence number；omission_effect：该关节不参与 HOME ALL|

证据定位：原HTML章节/元素XPath及原件绑定文本偏移。

评分：条目命中与属性评分单元分别计分；语义等价可接受，不能用条目名称代替属性。缺项与范围外多答分别记录；实际输入证据支持另审。

## DEV-N01

在NISTIR 8091第3节中，引出子系统所需度量的列表列出了哪些类别？为每类保留括号中全部示例或判定要点，并说明该列表是否声称穷尽全部度量。

|条目|必需属性|
|---|---|
|Tolerances|example_or_meaning_components：机械臂到达指令位置的变化；传感器输出的不确定性|
|Time needed for execution|example_or_meaning_components：机械臂抓取零件所需时间；传感器定位零件所需时间|
|Variability|example_or_meaning_components：时间的变化；位置的变化|
|Weight|example_or_meaning_components：机械臂负载能力；可达体积不同部位的负载能力约束|
|Size|example_or_meaning_components：设备占地；传感器视场；机器人可抓取物体的最大尺寸|
|Reachability of equipment|example_or_meaning_components：机械臂工作体积|
|Accuracy of equipment|example_or_meaning_components：机器人能否足够精确地配合零件以完成装配；传感器能否以取件所需精度测量|
|Speed of equipment|example_or_meaning_components：子系统能否在分配时间内执行|
|Part feeding|example_or_meaning_components：设备是否需要精确供料；是否需增加传感器定位零件|
|Required system capacity|example_or_meaning_components：当前配置系统能否达到必要吞吐量|
|Uptime of equipment|example_or_meaning_components：设备可靠性是否足以保证所需产能；子系统失效对整体系统的影响|
|Tool changes required|example_or_meaning_components：是否需要换刀；若需要，能否调整操作顺序以减少换刀|
|Testing and inspection|example_or_meaning_components：测试与检查能否并入其他步骤；是否需要独立子系统；若需要，独立子系统的数量|
|Constraints|example_or_meaning_components：新增子系统是否限制其他子系统的使用；例如机械臂要求传感器在特定容差内定位零件|

必须说明：列表不完整；只穷尽文中当前列表，不代表所有可能度量。

证据定位：原PDF第8页（索引7），印刷页5；14条列表均在同一页。

评分：条目命中与属性评分单元分别计分；语义等价可接受，不能用条目名称代替属性。缺项与范围外多答分别记录；实际输入证据支持另审。

机器证据、SHA256、逐项quote与偏移见 questions-gold.v1.json；canonical字符坐标按Unicode码点、LF、半开区间。
