# 原件版面、解析与开发标准答案v1核验

项目graphrag-paper-001，M2_OPEN，2026-10-12。协调者接受本轮**6道scope_given开发题、36个条目、81个属性评分单元及1条非穷尽限定**，仅用于本地开发校准。原件绑定、目标区域视觉、解析及独立AI复核均通过；未执行独立人工标注、模型实验或论文阶段验收。

2026-10-13最终冻结验收通过：35文件hash、12项独立复核输入hash、145处证据绑定均一致；候选到v1答案内容未变，模型输入题目不含Gold。见[最终验收机器记录](public-development-20261012/pilot/validated/final-verification.json)。最终脚本首次报告路径少一层已修，随后实际执行退出0；没有改冻结答案或放宽断言。

可读交付：[标准答案v1](public-development-20261012/pilot/validated/answers.v1.md)。机器交付：[Gold及逐项原件证据](public-development-20261012/pilot/validated/questions-gold.v1.json)、[不含Gold的模型输入题目](public-development-20261012/pilot/validated/questions.input.json)、[数据字典与评分规则](public-development-20261012/pilot/validated/data-dictionary.md)。冻结证据：[35文件字节清单](public-development-20261012/pilot/validated/freeze-manifest.json)、[独立专家完整返回及被评审hash](public-development-20261012/pilot/validated/expert-result.yaml)。

## 原件与版面核验

- 三份下载原件（NISTPDF、LinuxCNC HTML、完整许可页）hash与下载清单一致，未改动。LinuxCNC的2.9网址是分支，页脚更新时间2026-10-11 09:59:50 UTC；本轮以原文件SHA256识别快照，不冒称固定发行版本。CSS来自原页显式引用的两个官方静态文件，单独保留hash。
- 本地Poppler渲染NIST封面及列表所在PDF第8页；实际页底为**印刷页5**，此前平台文本中的6错误。14个列表条目都在这页，原文非穷尽声明可见；以原PDF重建当前证据，不沿用网页页码。
- 用已有Edge155.0.4283.45无界面渲染本地原HTML，JavaScript关闭、页面远程请求全部阻断。查看表格、6.1–6.3、6.10、6.11、6.14共7张截图；表头四列、4种回零行、3个编码器枚举及2个Note、5个序列示例和5个立即回零配置项对应关系正确。
- 主代理和独立专家都实际查看全部9张图。Poppler报告Symbol字体警告，已查看任务页中项目符号和正文均清楚；不把警告吞掉或推定全17页视觉无误。HTML图示资源未保存/核验，不纳入当前文字题；原文页脚与目标区域截图不替代发行号认证。

## 解析核验与修复

XHTML以Python标准库ElementTree完整解析为127个可回溯XPath文字块：表格按行及列序保留，代码块保留换行/符号，Note保留独立块。NIST使用本地pdftotext25.07.0的-layout模式，保留17页映射、LF及换页符。原件hash、解析hash、块XPath/PDF页码、Unicode半开字符范围及quote同时记录。

对比默认pdftotext发现真实结构差异：默认模式将14个项目符号集中到条目之前；-layout将符号与对应条目保持在一起。两个模式去除空白及项目符号位置后正文一致，未发现该页正文遗漏。该失败由解析模式解决，属于工具配置问题，**不作为新方法剩余缺口或模型性能证据**。证据见[解析模式对照](public-development-20261012/pilot/validated/parser-comparison.json)。

6题范围、36条目证据和81评分单元的quote与偏移逐项相等，并在各自目标范围内。L01补表头证据；L02只要求枚举代码及Note，避免将段首其他行为错计漏项；L03题干补充明确请求搜索零值行为，避免答案多要求未问属性；L04同步指最终移动；L05 HOME不是第六个配置项；N01将非穷尽限定单列，示例/问题按27个语义组件分别检查。

“81评分单元”不称81个最小语义原子：例如编码器behavior包含多个语义要点，同步成员集合作为一个单元。每单元全部要点满足才得满分，条目名不替代属性；可接受中文语义等价表达，需要评分者裁决，未运行自动语义评分器。36条目与81单元不充当独立样本量。

## 独立复核与接受范围

独立SCI数据专家只读复核原件/候选/9图，实际校验127 XPath、17页映射、全部scope及证据偏移、主要枚举/参数与语义支持；结论PASS_CANDIDATE，无阻断错误。协调者再次核对12项专家hash一致，最终版本只调整状态/接受元数据与说明，不改被评审答案或证据内容，保留被评审候选SHA256。

用户已明确授权材料用于本地开发并要求核验确认开发标准答案，因此协调者直接登记开发v1。该授权及AI复核不当作作者逐项人工标注，也不替代未来独立人工Gold。下载清单及先前pilot的PENDING是历史状态；当前效力以本报告和v1冻结清单为准，不回写原下载收据。

适用边界：2个来源单元，五题同属LinuxCNC同页，问题互相关；全部scope_given正向题。当前可用于文字开发校准；未来scope_hidden、不可回答与干扰题另建并分组报告。完整文本可供S_SCAN_ALL读取，但图示语义未OCR，不能宣称完整多模态解析或生产MinerU链路已验证。范围/条目/属性与实际输入支持仍分开评价，Gold原件支持不能替代运行时输入收据。

## 实际执行与验收

|执行|结果|
|---|---|
|pdftoppm -f 8 -l 8 -r 120 -png -singlefile 原PDF 输出前缀；封面另-r90|退出0，两图生成；Symbol字体警告已披露并核任务页可读|
|已有node运行validated/render_original.cjs|受限首试Edge启动失败；获准本地无界面执行后退出0，7图及DOM对照生成|
|backend/.venv/Scripts/python.exe -B -X utf8 .../validated/build_validated_gold.py|首次脚本括号错误已修；最终退出0，6题36项81单元1限定、17页/14项目与表格矩阵核验通过|
|pdftotext 原PDF validated/NIST-8091.default.txt；本地compare_parsers.py|退出0；确认默认模式符号集中问题，-layout任务页内容核验通过|
|专家只读复核+协调者hash比对|12项被评审hash一致；9图及全部题目范围/属性支持通过AI复核|
|最终冻结验收|见validated/final-verification.json：字节hash、证据quote/范围、模型题目无Gold、候选到v1答案不变|

没有触发产品服务或MinerU/API/模型，没读未来留出材料，未改生产索引/配置，无安装/commit/push。生成器预算继续未冻结，H1/H2仍空，M2保持开放。

下一步：确定实际生成器及其提示/计数口径，在当前开发语料测定三基线预算；预算冻结前不启动比较实验。
