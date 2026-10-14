# v2验证前本地只读核查

任务记录日期：2026-10-08（工具UTC实测）；项目 `graphrag-paper-001`，M2仍开放。数值及指纹见同名JSON。使用已存在的backend Python与标准库/本地PyYAML；未导入生产模块、读凭据、调用模型、联网、启动服务、导入语料、修生产代码或安装软件。

## 已核实的本地观察

- 上轮生产审计15个文件及3份原文SHA256与本轮一致；工作目录HEAD为`46b202c3e400741fd569f024412c0745f224a538`。这不是运行进程身份认证，也不表明dirty tree为空。
- Chroma数据库以`mode=ro`加`PRAGMA query_only=ON`打开；`rag_docs`为512维，1440条。数据库及两份缓存检查前后SHA256一致，未建立镜像或恢复/重建索引。
- 用整段非空文本（去首尾空白，至少20字符）逐字匹配冻结Markdown：D1有31段匹配，metadata source_file均为`test.pdf`；仅1段的原存储[start,end)切片逐字匹配文本，30段未匹配，不能直接当原文坐标。D1这些source_file未在docs_store完成映射。示例c00002存储起点57，源文找到起点58；不能简单假定全篇统一加1，需逐段重定位/歧义检查。
- D2/D3该逐字方法的匹配数均0。不能据此说文档没入库：转写、规范化、其他KG路径或其他索引均未穷尽核验；目前仅记`CORPUS_MAPPING_UNVERIFIED`。
- 本地BM25持久化artifact仅3段、table artifact仅2行，均标`paper.pdf`，与D1候选`test.pdf`不同。进程究竟加载哪些artifact或重建结果未验证。`docs_store.json`83条也不能证明向量/KG内容、版本或可查性。
- `netstat -ano`退出0，本次未观察到8001监听。没有启动服务或以问答请求代替健康检查。其他端口或部署未知。
- 默认本地HuggingFace缓存有bge-small和bge-reranker各1个snapshot，config/tokenizer/weights存在；没有加载模型，运行实际缓存路径、可离线载入性未确认。不因文件存在就开启下载/模型执行。

## 54次提案的必要条件

AST只读枚举当前路线四处直接requests发送：生成重试helper（generator296）、preprocess（retrieval343）、multi-query变体（retrieval1802）、会话指代消解（conversation425）。调用计数不能只看答案生成。

在新会话无历史、include_evidence_trace=true禁止legacy fallback、multi-query关闭、运行pipeline和所审代码一致且未注入optimizer、每题preprocess最多1次/生成最多2次、transport无额外尝试、受控三臂各1次复用已捕获预处理的条件下，`9×(1+2+3)=54`才是候选发送上界。代码route初始化未传query_optimizer，但无法据此认证运行中的单例。

原生生成模型需运行时核验；拟用deepseek-v4-pro，preprocess函数当前默认deepseek-chat，不能把全路径冒称只用一个模型。gpt-6.1-sol是本轮原生独立专家，不是新增实验臂。新批次授权须包含辅助调用的真实模型/端点/片段/有限次数；无新金额cap要求。没有发送计数拦截、运行配置与隐含调用核验，不能宣称54已强制保证。

## 当前可交付与不可下的结论

Gold按新问法版本化并保留旧31项crosswalk；严格记录属性、范围和显式/推断边界。原文核查不等于人工Gold认证。FIG新范围是整篇Markdown，旧8192字节上限下不得照搬六附录行就声称整篇可见。通用caption扫描/范围projection如需采用，应冻结扫描覆盖与逐项映射，区分本地全篇扫描证据和模型实际输入；未实现时记`PARTIAL_SCOPE/NOT_VERIFIED`，不伪造完整性。

本地观察支持“执行前来源身份/坐标门禁尚未过”，不支持现生产端到端失败、新scope方法有效或跨文档研究问题已成立。禁止因D2/D3匹配不到就计失败，禁止为凑齐九题自动导入。

## 下一步

先实现/核验不触网的v2加载、通用范围组装及来源映射工具，受控AUTO禁读Gold；真实B0回放仍须运行/语料身份门禁和独立有限批次授权。若需要创建隔离索引或导入D2/D3，先明确请求许可，仅写新评估目录，不能动现存生产库。本记录不是新批次授权或论文阶段通过。
