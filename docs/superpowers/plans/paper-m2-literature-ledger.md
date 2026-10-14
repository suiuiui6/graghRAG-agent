# GraphRAG 论文 M2 文献证据台账

> 最新复审（2026-10-07）：文献记录保留，原新颖性判断及后续候选以 `paper-recent-journal-limitations-review.md`、`paper-conflict-calibration-competitor-review.md` 和控制台第11节为准；宽泛冲突校准贡献已否决，M2仍部分通过，不能据旧台账批准后续学术推进。

> 检索与核验日期：2026-10-07  
> 范围：代表性发现、直接竞品发现与官方全文核验；不是系统综述。  
> 证据规则：网页摘要只用于发现，纳入核心表的条目均核验官方论文页与官方全文。候选研究空白统一标为 `AI_INFERENCE`。

## 1. 检索设计

### 1.1 概念与同义词

| 概念块 | 检索词 |
|---|---|
| 图结构 RAG | GraphRAG, graph-based RAG, KG-RAG, knowledge graph guided, graph retrieval, community summary, Personalized PageRank |
| 长文档 | long-document RAG, long-context QA, LCQA, hierarchical retrieval, source paragraph mapping |
| 中文复杂文档 | Chinese long context, Chinese document QA, annual report QA, PDF, table, numerical reasoning |
| 引用与溯源 | grounded generation, attribution, provenance, citation recall, citation precision, claim support, faithfulness |
| 拒答 | unanswerable, abstention, selective refusal, missing evidence, contradiction, false premise |
| 自适应与成本 | adaptive RAG, query complexity, routing, retrieval steps, token cost, latency |
| RAG 评测 | claim recall, context precision, answer faithfulness, component diagnosis, confidence interval, production parity |

### 1.2 代表性检索式

```text
("GraphRAG" OR "graph-based RAG" OR "knowledge graph retrieval augmented generation")
AND ("long document" OR "long-context QA")
AND (grounded OR citation OR provenance OR faithfulness)

("retrieval-augmented generation" OR RAG)
AND (unanswerable OR abstention OR "selective refusal")
AND (benchmark OR evaluation)

("adaptive RAG" OR "retrieval routing")
AND (cost OR latency OR token OR "retrieval steps")

("RAG evaluation")
AND ("context relevance" OR faithfulness OR "claim recall" OR citation)
AND ("confidence interval" OR diagnostic)

("Chinese" OR 中文)
AND ("long document question answering" OR "long-context")
AND (RAG OR "retrieval-augmented generation")
```

检索来源包括 ACL Anthology、NeurIPS Proceedings、ICLR Proceedings、arXiv 和 Microsoft Research 官方页面。未使用 Scopus、Web of Science、CNKI 或机构登录数据库，也未调用第三方文献 API；因此本台账不能支持“首次提出”或“文献中不存在”的穷尽性断言。

## 2. 核心文献

| ID | 书目信息（已核验） | 本项目中的作用 | 不可越界的差异 |
|---|---|---|---|
| L01 | Darren Edge, Ha Trinh, Newman Cheng, Joshua Bradley, Alex Chao, Apurva Mody, Steven Truitt, Dasha Metropolitansky, Robert Osazuwa Ness, Jonathan Larson. 2024. [From Local to Global: A Graph RAG Approach to Query-Focused Summarization](https://arxiv.org/abs/2404.16130). arXiv:2404.16130 v2. | 社区摘要与全局问答直接参照 | 英文全局 sensemaking 为主；未审计 claim→边→原文坐标、拒答或生产链一致性 |
| L02 | Shilong Li, Yancheng He, Hangyu Guo, Xingyuan Bu, Ge Bai, Jie Liu, Jiaheng Liu, Xingwei Qu, Yangguang Li, Wanli Ouyang, Wenbo Su, Bo Zheng. 2024. [GraphReader](https://aclanthology.org/2024.findings-emnlp.746/). Findings of EMNLP. DOI: 10.18653/v1/2024.findings-emnlp.746. | “节点—原子事实—原文 chunk”可追溯结构基线 | 无最终 claim 级引用审计、中文实证或生产 API 一致性 |
| L03 | Bernal Jiménez Gutiérrez, Yiheng Shu, Yu Gu, Michihiro Yasunaga, Yu Su. 2024. [HippoRAG](https://proceedings.neurips.cc/paper_files/paper/2024/hash/6ddc001d07ca4f319af96a3024f6dbd1-Abstract-Conference.html). NeurIPS. DOI: 10.52202/079017-1902. | OpenIE + PPR 图检索与成本参照 | 未把 NER/OpenIE 误差贯通审计到最终回答和引用 |
| L04 | Xiangrong Zhu, Yuexiang Xie, Yi Liu, Yaliang Li, Wei Hu. 2025. [Knowledge Graph-Guided Retrieval Augmented Generation](https://aclanthology.org/2025.naacl-long.449/). NAACL. DOI: 10.18653/v1/2025.naacl-long.449. | 三元组关联 source chunk，是关系—来源谱系的直接竞品 | 无页码/字符坐标、claim grounding 或生产路径核验 |
| L05 | Qingfei Zhao, Ruobing Wang, Yukuo Cen, Daren Zha, Shicheng Tan, Yuxiao Dong, Jie Tang. 2024. [LongRAG: A Dual-Perspective Retrieval-Augmented Generation Paradigm for Long-Context Question Answering](https://aclanthology.org/2024.emnlp-main.1259/). EMNLP. DOI: 10.18653/v1/2024.emnlp-main.1259. | 跨块证据恢复、全局信息与事实细节分离参照 | 非 graph 方法；支持判断依赖 LLM/CoT，未验证引用 |
| L06 | Yushi Bai, Xin Lv, Jiajie Zhang, Hongchang Lyu, Jiankai Tang, Zhidian Huang, Zhengxiao Du, Xiao Liu, Aohan Zeng, Lei Hou, Yuxiao Dong, Jie Tang, Juanzi Li. 2024. [LongBench](https://aclanthology.org/2024.acl-long.172/). ACL. DOI: 10.18653/v1/2024.acl-long.172. | 中英双语长上下文、单/多文档 QA 的外部有效性参照 | 不覆盖 GraphRAG 谱系、引用或生产链路 |
| L07 | Tianning Zhu, Mo Liu, Murathan Kurfali. 2026. [CFQA: A Chinese Financial Question Answering Benchmark from Corporate Annual Reports](https://aclanthology.org/2026.fnp-1.3/). FNP @ LREC. DOI: 10.63317/4e6fhrncfrbu. | 中文年报 PDF、页码证据、表格/计算/推理失败分类参照 | 领域较窄且题型较模板化，不能代表一般长文档 |
| L08 | Tianyu Gao, Howard Yen, Jiatong Yu, Danqi Chen. 2023. [Enabling Large Language Models to Generate Text with Citations](https://aclanthology.org/2023.emnlp-main.398/). EMNLP. DOI: 10.18653/v1/2023.emnlp-main.398. | claim/citation recall 与 citation precision 的指标基线 | NLI 型自动评价对部分支持仍有限，需人工校准 |
| L09 | Cheng Niu, Yuanhao Wu, Juno Zhu, Siliang Xu, KaShun Shum, Randy Zhong, Juntong Song, Tong Zhang. 2024. [RAGTruth](https://aclanthology.org/2024.acl-long.585/). ACL. DOI: 10.18653/v1/2024.acl-long.585. | case/span 级人工幻觉标注协议参照 | 不检验图谱派生链或页码坐标 |
| L10 | Xiangyu Peng, Prafulla Kumar Choubey, Caiming Xiong, Chien-Sheng Wu. 2025. [Unanswerability Evaluation for Retrieval Augmented Generation](https://aclanthology.org/2025.acl-long.415/). ACL. DOI: 10.18653/v1/2025.acl-long.415. | 六类不可回答请求与 acceptable ratio，替代拒答关键词匹配 | 数据生成与评价含 LLM judge，仍需人工抽检 |
| L11 | Aashiq Muhamed, Leonardo F. R. Ribeiro, Markus Dreyer, Virginia Smith, Mona T. Diab. 2026. [RefusalBench](https://aclanthology.org/2026.eacl-long.321/). EACL. DOI: 10.18653/v1/2026.eacl-long.321. | 歧义、矛盾、缺失、错误前提等受控拒答测试参照 | 需中文化并适配真实知识库 |
| L12 | Soyeong Jeong, Jinheon Baek, Sukmin Cho, Sung Ju Hwang, Jong Park. 2024. [Adaptive-RAG](https://aclanthology.org/2024.naacl-long.389/). NAACL. DOI: 10.18653/v1/2024.naacl-long.389. | 按问题复杂度路由检索策略的质量—时间基线 | 不评价引用、图质量或证据治理 |
| L13 | Zhuowan Li, Cheng Li, Mingyang Zhang, Qiaozhu Mei, Michael Bendersky. 2024. [Retrieval Augmented Generation or Long-Context LLMs? A Comprehensive Study and Hybrid Approach](https://aclanthology.org/2024.emnlp-industry.66/). EMNLP Industry. DOI: 10.18653/v1/2024.emnlp-industry.66. | RAG、全文上下文与 SELF-ROUTE 的质量—成本基线 | 无 graph/provenance/refusal 联合评价 |
| L14 | Jon Saad-Falcon, Omar Khattab, Christopher Potts, Matei Zaharia. 2024. [ARES](https://aclanthology.org/2024.naacl-long.20/). NAACL. DOI: 10.18653/v1/2024.naacl-long.20. | 分离 context relevance、answer faithfulness、answer relevance，并支持置信区间 | 依赖训练型 judge，需报告校准证据 |
| L15 | Dongyu Ru, Lin Qiu, Xiangkun Hu, Tianhang Zhang, Peng Shi, Shuaichen Chang, Cheng Jiayang, Cunxiang Wang, Shichao Sun, Huanyu Li, Zizhao Zhang, Binjie Wang, Jiarong Jiang, Tong He, Zhiguo Wang, Pengfei Liu, Yue Zhang, Zheng Zhang. 2024. [RAGChecker](https://proceedings.neurips.cc/paper_files/paper/2024/hash/27245589131d17368cccdfa990cbf16e-Abstract.html). NeurIPS Datasets & Benchmarks. DOI: 10.52202/079017-0692. | 检索与生成模块的细粒度诊断和成本—噪声权衡参照 | 不检查离线评测与生产调用链是否一致 |

补充设计空间参照：Yukun Cao et al. 2025. [LEGO-GraphRAG](https://arxiv.org/abs/2411.05844), PVLDB, DOI: 10.14778/3748191.3748194。它已经系统讨论 GraphRAG 模块化设计与质量、运行时间、token/GPU 成本权衡，因此本项目不能把“模块化消融”或“质量—成本评测”本身宣称为首创。

## 3. 主张—文献映射

| 待写主张 | 支持文献 | 证据状态 | 写作边界 |
|---|---|---|---|
| 图结构可支持全局问答或关系扩展 | L01, L03, L04 | `VERIFIED_SOURCE` | 只说明已有方法能力，不推导本系统已具备相同性能 |
| 长文档需要层次化、回源或全文上下文对照 | L02, L05, L06, L13 | `VERIFIED_SOURCE` | 必须在相同上下文预算下比较 |
| 引用 ID 合法不等于 claim 得到支持 | L08, L09, L14, L15 | `VERIFIED_SOURCE` | 当前 node-ID validity 不得命名为事实一致性或零幻觉 |
| 拒答不能只靠关键词命中评价 | L10, L11 | `VERIFIED_SOURCE` | 需区分正确拒答、过拒答、澄清和错误纠正 |
| 自适应检索必须同时报告质量和真实成本 | L12, L13, L15 | `VERIFIED_SOURCE` | 成本需包含预处理、额外检索和最终生成 |
| 中文复杂文档具有独立的页码、表格、数值和推理问题 | L06, L07 | `VERIFIED_SOURCE` | 单一中文年报不能外推到所有中文长文档 |
| “生产一致 + claim 级谱系 + 拒答 + 成本”的组合可能存在研究空白 | L01–L15 的交叉比较 | `AI_INFERENCE` | 只能写成候选空白并由实验支持，不能写“首次” |

## 4. 排除与候补记录

| 条目 | 处理 | 原因 |
|---|---|---|
| RAPTOR | 候补 | 层次索引与派生摘要污染很有价值，但非 graph 方法；可在讨论中引用 |
| Jiang et al. 的 `LongRAG: Enhancing RAG with Long-context LLMs` | 候补 | 与 Zhao et al. 同名但不同方法；避免正文混淆 |
| LightRAG | 候补 | 高度相关，但核心表优先保留 source-chunk 谱系更明确的 KG²RAG |
| GRAG、G-Retriever | 排除为直接基线 | 假定输入已经是 textual graph/KG，不覆盖长文档解析到证据链 |
| RAGAS | 候补 | 本轮优先采用有人评校准/置信区间的 ARES 与细粒度 RAGChecker |
| DuReader_vis、CDQA | 非直接基线 | 可作中文或文档类型背景，不足以代表本研究任务 |
| Dissecting GraphRAG（TACL 2026） | 待核验 | 元数据页已发现，但本轮官方全文未成功核验，未纳入核心表 |

两个题名含 `LongRAG` 的条目不是同一论文，后续引用必须同时带作者与标识。GraphRAG L01 采用当前 arXiv v2/微软页面的 10 位作者记录。

## 5. M2 候选研究空白

以下全部为 `AI_INFERENCE`：

1. 本轮全文集合中，未发现同时测量“中文复杂 PDF → 图谱构建 → 检索 → 最终 claim 引用”的全链谱系并审计页码/字符坐标的研究。
2. GraphRAG 工作主要优化回答或检索；引用评测通常从已有 passage 出发，二者之间仍缺少“派生图事实是否忠于原文”的桥接评价。
3. 自适应 RAG 常优化正确率、时间或检索步数，尚未在同一 Pareto 面统一引用支持、适当拒答、图构建成本与生产 SLO。
4. ARES、RAGChecker 等诊断 RAG 模块，但“离线评测是否真正经过生产 API 与同一 source assembly”尚未成为常规效度指标。
5. 中文资源已有 LongBench、CFQA 等，但跨章节实体消歧、OCR/表格、关系方向、多重关系和坐标级来源仍需更具体验证。
6. 因而当前最稳妥的论文贡献不是“全新 GraphRAG 算法”，而是一个待实证的生产一致、claim 级可追溯、联合衡量正确性—拒答—成本的评价与证据治理框架。

## 6. 未完成的文献工作

- 投稿前按目标期刊要求补做 Web of Science/Scopus/CNKI 检索及可审计导出。
- 对候选主张做逐句引文回查，不能直接把本台账摘要复制成相关工作正文。
- 目标期刊确定后，检查引用年限、预印本政策和参考文献格式。
