# 公开开发材料筛选

2026-10-12；graphrag-paper-001；M2_OPEN。完成官方来源筛选与网页结构检查，未下载数据包、未清洗/标注、未运行模型，未新增确认留出。

## 选择结果

**主开发材料选择“既有8份中文安全文件＋LinuxCNC固定版本文档＋NIST制造技术报告”。** 这是待构建的开发语料组合，不是现成命名数据集。开发用来校准三条简单基线与预算，不能用其调试后的表现证明未见文档泛化。

8份不是一个必然过小的统计门槛：它们可以启动本地开发，缺口在于现有来源集中于安全规章、公开复现实证权利未核实，尚无一套已冻结的公开制造技术手册开发材料。新增题目或清洗不能补足来源类型。未读取这8份正文来断言它们缺少某类表格或章节。

| 优先级 | 来源 | 使用决策 |
|---|---|---|
| 主线 | [LinuxCNC官方文档](https://linuxcnc.org/docs/2.9/html/) | 机床控制、配置、参数与报错条件的完整技术正文；适合范围和集合属性任务 |
| 主线补充 | [NIST技术系列](https://www.nist.gov/nist-research-library/nist-series-publications) | 制造部署、机器人性能、维护与数据模型报告；补充不同结构 |
| 辅助 | [TechManualQA-700](https://zenodo.org/records/17410809) | 现成手册QA与审计参考；不能直接充当全范围穷尽Gold |
| 有条件辅助 | [Industrial-Instruction](https://huggingface.co/datasets/Parssky/industrial-instruction-dataset) | 工业检索干扰/证据整合参考；当前公开QA schema不直接支持完整手册全扫描评价 |

该排序是对本项目任务的适配判断，非所有制造QA数据集的全面排名。单靠文档问答不能声称验证机器人操作、具身控制或真实制造决策能力。

## 主线实际候选

[机器清单](public-development-20261012/source-shortlist.json)登记以下6份报告和1个手册家族。它们是7项来源候选，尚不是7份已经落盘并通过准入的文档。

| ID | 标题/版本 | 本轮读取深度 |
|---|---|---|
| LCNC | [LinuxCNC 2.9文档](https://linuxcnc.org/docs/2.9/html/) | 官方目录、许可；G-code、INI配置、回零、运动学页面正文 |
| N1 | [Guide to Industrial Wireless Systems Deployments, AMS300-4](https://nvlpubs.nist.gov/nistpubs/ams/NIST.AMS.300-4.pdf) | PDF可读，62页；目录及附录清单定位 |
| N2 | [Measuring and Representing the Performance of Manufacturing Assembly Robots, IR8091](https://nvlpubs.nist.gov/nistpubs/ir/2015/NIST.IR.8091.pdf) | PDF可读，17页；性能与装配过程正文 |
| N3 | [Enabling FAIR Data in Additive Manufacturing to Accelerate Industrialization, AMS500-1](https://nvlpubs.nist.gov/nistpubs/ams/NIST.AMS.500-1.pdf) | PDF可读，20页；目录、模块/属性正文 |
| N4 | [PHM for Smart Manufacturing路线图, AMS100-2](https://www.nist.gov/publications/measurement-science-roadmap-prognostics-and-health-management-smart-manufacturing) | 官方记录/DOI；未打开PDF |
| N5 | [Metrics and Key Performance Indicators for Robotic Cybersecurity Performance Analysis, IR8177](https://csrc.nist.gov/pubs/ir/8177/final) | 官方记录/作者/下载入口；未打开PDF |
| N6 | [Guide to Operational Technology Security, SP800-82r3](https://csrc.nist.gov/pubs/sp/800/82/r3/final) | 官方记录/下载入口；未打开PDF；固定r3，不能混入r4初稿 |

LinuxCNC HTML目录显示2.9.10，而本轮打开的PDF标识为2.9.7-9-gd435482ad1，不能把“2.9”当相同字节版本。正式使用先选定一种固定快照。合订本包含的章节、单独HTML页、PDF和中英译本不能分别当独立文档扩充样本数。[官方PDF目录](https://linuxcnc.org/docs/2.9/pdf/)

LinuxCNC文档许可明确为GNU FDL 1.1或以后版本、无不变章节及封面文本；应保留许可与署名。[官方许可](https://linuxcnc.org/docs/2.9/html/common/gpld-copyright.html) NIST政策允许其员工著作按规定引用、重印与衍生，同时明确第三方著作例外；不能把所有NIST托管PDF或其中第三方图表统一标“公共领域”。逐报告权利与内容例外仍需核实。[NIST版权政策](https://www.nist.gov/open/copyright-fair-use-and-licensing-statements-srd-data-software-and-technical-series-publications)

本轮打开的正文登记为开发曝光。其近重复版本不得事后用作“未参与开发”的确认材料；只看目录/元数据的候选也单独保留访问级别，不一概声称正文已曝光。

## 现成基准为何不作主开发语料

TechManualQA官方记录声称700对、20手册、数据CC BY4.0。公开包以QA/审计材料为主，原PDF须另下且遵守厂家条款；短答案及页号不是范围穷尽标注。专家另发现README链接身份和脚本手册数不一致，尚未解决，不能按20份已核实原文导入。[作者仓库](https://github.com/tduricic/techmanualqa)、[打包脚本](https://github.com/tduricic/techmanualqa/blob/main/src/techmanualqa/create_zenodo_archive.py)

Industrial-Instruction的论文报告906份Panasonic来源文件，基准按场景抽QA，未证明按文档隔离。官方QA预览有question、answer、documents字段，但缺可直接冻结的完整文档定位；CC BY-NC许可仍要求遵守源条款。未能读取pana_v0_0目录，不能断言该项目完全没有完整原文。[论文](https://arxiv.org/html/2608.22817v1)、[发布卡片](https://huggingface.co/datasets/Parssky/industrial-instruction-dataset)

[QASPER](https://huggingface.co/datasets/allenai/qasper)的论文正文/证据与[Doc2Dial](https://doc2dial.github.io/README.html)的正文/章节span可辅助检验定位，但其领域和标注目标不能替代本研究的制造集合问答Gold。

## 研究到数据的映射及试采边界

| 评价面 | 需要字段 | 开发材料适配例 |
|---|---|---|
| 范围选择 | source/version、章节路径、边界、歧义处理 | LinuxCNC重复报错小节及配置节 |
| 条目和必需属性 | 全部匹配项、条件/单位/排除、条目关系 | 参数配置；制造部署清单与模块属性 |
| 证据支持 | 原文区间、页/锚点、实际模型输入、逐断言绑定 | 同一原文支撑三臂独立评估 |

网页结构探查已确认G-code/INI章节和NIST附录清单可定位；这只是适配证据，没有验证本地解析质量、原字节hash或Gold。IR8091部分列表明确不穷尽，题目须限定“文中明确列出的条目”，不能问现实世界所有指标。

[采集计划](public-development-20261012/collection-plan.yaml)先安排3个官方页面或少量PDF页试采；原始来源、版本、hash、许可、家族、访问角色及文档边界核实后，再进行3份完整来源、每份4–6题的开发试标（12–18题仅是起步目标）。不把这些章节算3个独立家族。语言/格式分层报告；英文扩展不等于中文制造适用性验证。

用户已授权既有8份进入本地论文开发，当前用途改为DEVELOPMENT_AUTHORIZED；旧历史曝光结论保留，但不再为开发使用继续追认“未曝光”。H1/H2仍空，新开发来源不补入留出。先用开发材料测A_AUTO_READ、S_SCAN_ALL、P0_NATIVE，未证明强基线重复缺口前不进入新方法设计。

## 核查与交付状态

协调者用平台原生搜索及官方网页核查LinuxCNC/NIST；独立web-data-acquisition专家核查现成基准、schema/包目录/作者代码，见[专家结果](public-development-20261012/expert-result.yaml)。这是有界筛选，不称系统综述。

本地仅写本报告、来源清单、专家合同、采集计划及状态/记忆。未下载PDF/JSONL/ZIP原文件，未安装依赖、运行模型、调用外部接口、修改生产索引或提交Git。计划验证器首次因YAML列表缩进兼容失败，调整序列化缩进后退出0；`pilot-ready`仅说明计划字段符合检查，不代表试采/解析/许可全部通过。

## 唯一下一步

按已选LinuxCNC/NIST路线做小规模原文冻结与解析试采，先验证版本、权利、来源边界，再建立开发Gold与预算；保留未来留出来源不参与规则调试。
