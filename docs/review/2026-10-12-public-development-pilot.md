# 公开开发来源小样本核验与开发题草案

项目：graphrag-paper-001；阶段：M2_OPEN；日期：2026-10-12。

## 后续更新：原文件已直接下载

用户追问能否直接下载后，改用系统已有curl.exe下载官方普通静态文件。受限环境首试DNS失败；获准网络执行后3个文件均退出0：NIST原PDF（467253字节）、LinuxCNC回零原HTML（33689字节）和完整许可HTML（22447字节）。准确字节数、SHA256、URL、保存时间见[下载清单](public-development-20261012/pilot/raw/download-manifest.json)，不再需要用户手动下载。

本地pdftotext -layout成功输出17页，封面题名、作者页与November 2015吻合；原HTML标题与4类回零表格文本标识通过。此为文件身份和基本可解析性检查；版面核验、完整解析比对、原件坐标重绑定与最终Gold评审仍待做，原有draft不自动升级。本页下文保留下载前记录。前轮浏览器故障并不意味着所有普通下载路径均不可用。

## 裁决

**未通过原文件冻结和解析准入。** 已保存两来源的平台文本提取记录，并形成6道开发题、36个条目及必需属性的证据绑定草案；不能称为正式标准答案或执行基准。用户已授权本轮解析和开发标注，无需再次征求清洗许可。未来留出H1/H2仍空，未采集或参与调试。

## 实际核验与发现

|来源|已核实|缺失与处理|
|---|---|---|
|LinuxCNC Homing Configuration|官方2.9路径；文本表格4行、绝对编码器3值与2注意事项、5个序列代码示例均有可定位文本|没有原HTML字节；确切release未冻结；图示未核，不出运动轨迹/图布局题|
|NISTIR 8091|原文标题为 Predicting Robot System Performance by Measuring and Composing Subsystem Attributes，Michael Shneier，November 2015，DOI 10.6028/NIST.IR.8091；印刷页6/PDF索引7列表有14个一级条目|旧候选标题有误，已更正；平台标题NIST Special Publication XXX也不可靠。PDF字节与版面未核，不把文本提取正确等同视觉核验通过|

NIST列表明确称“incomplete”，Gold只要求该自然范围内的全部列举项，不声称行业度量全集。提取行241存在页尾页码拼接，部分文本行跨页；保留原提取记录，不将其冒作原PDF。网页图像只留下链接/占位，未提取图中事实。LinuxCNC同一手册的单元不计独立文档扩样；目前是2个来源单元，0个原文件冻结。

LinuxCNC许可依据为[官方Legal Section](https://linuxcnc.org/docs/2.9/html/common/gpld-copyright.html)，GNU FDL 1.1或更新；后续原文副本须保留署名与完整许可。NIST依据[官方技术系列员工著作政策](https://www.nist.gov/open/copyright-fair-use-and-licensing-statements-srd-data-software-and-technical-series-publications)：作者机构见原文前页，本次只取本报告叙述列表，不取引用第三方分类图；保留署名及“Republished courtesy of the National Institute of Standards and Technology.”；不外推所有NIST候选均已准入。本轮仅本地研究，未发布语料。

## 开发题草案

|题号|范围|条目数|必需属性/难点|
|---|---|---:|---|
|DEV-L01|6节开头表格|4|每类3个配置值，避免错行|
|DEV-L02|6.10|5|3个设置值的行为+2个静默忽略注意事项|
|DEV-L03|6.1–6.3|3|单位、默认值或未设置行为、正值条件|
|DEV-L04|6.11的五个示例|5|三个关节值及最终移动同步成员|
|DEV-L05|6.14|5|代码块值与替代值、HOME_SEQUENCE省略影响|
|DEV-N01|第3节印刷页6列表|14|逐类示例/判定含义；列表非穷尽声明|

机器草案：[questions-gold.draft.json](public-development-20261012/pilot/questions-gold.draft.json)。所有题保留范围、每项证据及属性；中文问题/解释与英文证据的语义翻译为AI草案，尚无人工逐项确认。条目、属性、范围选择、运行时实际输入支持须分开计分；Gold本身的证据绑定不能替代模型输入收据。不得用这些有题号锚点的范围直接喂给A_AUTO_READ作为提示，否则变成oracle。

这6题是`scope_given`范围明确的校准题，不能据此证明自动范围选择能力或剩余方法缺口；后续另建隐藏范围提示的题组并分开报告。题干已移除答案数量提示；N01的非穷尽判断单独结构化并绑定行213，示例含义拆分后逐分量计分。L01保留表头证据，L02限定枚举代码与Note避免把整节额外行为误作漏标。独立AI评审见[专家记录](public-development-20261012/pilot/expert-review.yaml)，原件/视觉/人工与完整扫描不足仍未关闭。五道LinuxCNC题并非五个独立样本；未来留出为空并不意味着已完成留出冻结。

范围和证据坐标只针对平台文本快照：原网页行号为闭区间；本地LF文本为Unicode码点半开区间；快照SHA256与原文件SHA256分别登记，后者均null。NIST快照只是观察到的一段文本，不称完整文档。正式原文件获得后必须重新解析并重建坐标，不能直接沿用网页行号。

## 执行证据与阻塞

- 原生浏览器`cua_repl`创建官方文档tab失败；备用`node_repl`初始化也失败：`failed to write kernel assets: 系统找不到指定的路径。 (os error 3)`。
- 平台web可提取官方文本；PDF截图按URL失败，按返回ref重试仍Cache miss。0个成功版面核验。
- 保存web-open/web-rights-find/web-visual-rights/web-screenshot-retry四份工具响应，明确为平台输出，不伪装原文件。没有用网络脚本绕过SCI零外部API限制。
- 本地执行：`backend/.venv/Scripts/python.exe -B -X utf8 docs/review/public-development-20261012/pilot/build_pilot.py`退出0，6题36项所有证据行连续、偏移在范围内、快照哈希已生成。仅结构通过，不是生产解析器验证。
- 未测生产MinerU/分块/检索/生成器；无模型调用、token预算测定或方法缺口结论；未扩采余下候选；M2不推进。

## 下一步唯一动作

按[原文件下载操作卡](public-development-20261012/pilot/manual-download.md)补齐这两个已曝光开发来源的原文件，再本地逐项核版面与解析、关闭独立复核意见后冻结开发题；其余未来留出另行保留。
