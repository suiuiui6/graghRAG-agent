# 生产基线验证前只读核查

2026-10-07。源代码审计，不是生产回放；没有访问模型、初始化服务、读取凭据、重建索引或修改业务代码。指纹与纯谓词检查见`production-readiness-audit.json`。部署进程版本、索引内容/映射/指纹、运行时模型与缓存状态仍待核验。

## 已核实的代码事实

1. `backend/routes/rag_query.py:224`的查询路径构建RetrievalConfig并调用RAGGenerator。现有多路检索、条件rescue、rerank跳过、prompt枚举约束和答案repair/complete/supplement都必须保留在真实B0中，不能以离线B1替换。`include_evidence_trace=true`能取得序列化模型上下文、原始模型回答与变换阶段（`generator.py:1398`、`:1581`、`:1605`；`evidence_trace.py:152`）。
2. `QueryRequest.document_id`存在于`models.py:83`，但当前`rag_query.py`只将它写入返回metadata；`generator.generate`与`retrieve`调用没有传它。不能把这个参数当成已生效的文档过滤。必须确认现存索引中D1/D2/D3的实际身份和混合语料范围；若新增隔离数据副本或导入缺失文档，另行审批并标明不是原生产实例。
3. `config.py:57`起默认候选上限5、context上限4000、cross-encoder开启、multi-query/global关闭，source caps为2/2/1/1/1。这些是代码默认，不是现运行实例的实际配置。`prompt_builder.py:55`和`:125`使用4字符≈1token估计；真实usage必须另外记录，不能称4000是精确token预算。
4. 生产生成器`generator.py:189`把v4 thinking设置放入原始HTTP JSON的`extra_body`字段；首轮独立适配器则用顶层thinking。生产原生回放必须如实保留并记录，不能默默修正再称生产B0；任何统一请求设置后的对照必须另命名为受控adapter。生产GenerationConfig默认max_retries=1；`_post_with_bounded_retries`最多2次尝试。运行成本/授权应按实际provider调用计数，不能认为1个问答请求必然只调用模型1次。
5. `retrieval.py:279`查询预处理可能额外调用模型，并写rewrite cache；默认model_name为deepseek-chat，缓存是否命中改变调用数。会话、lineage、缓存也可能写入本项目存储。只查health不证明语料、运行身份或调用行为；本轮不触发这些路径。
6. `rag_query.py:367`和`:375`对API回答执行4000字符限制。必须分别裁决原始模型输出、后处理后全文、API可见答案，不能把API截断后的遗漏都归于模型或检索。
7. `vector_store.py:285`保存section_path及char_start/end，但`doc_processor.py:194`起的PDF节构建用重新累积的char_offset，而不是直接将桥接节的原始char_start传出。生产metadata的数字不能未经核对就当成full.md原始跨度；协议必须要求实际文本逐字比对，不能核对时标LOCATION_UNVERIFIED。Embedding源代码采用本地SentenceTransformer；首次初始化仍须确认模型已在本地，禁止为本次验证静默下载。

## 真实本地执行的纯谓词检查

从AST仅提取两个无I/O谓词，对旧9题运行，不导入生产模块：D1-COST不触发`_is_summary_metric_query`；D1-FIG触发`_is_figure_inventory_query`；D3-TOOLS也因“表格＋所有”触发后者。这里只证明检测条件，不证明后续候选、路由或答案失败。新自动范围方案应区分图目录/普通工具表格，不能直接将这个检测器冒称通用scope resolver。

## 必须先解决的证据门禁

- 独立Gold复核及版本化，明确旧题敏感性解释与新题前瞻验证不混算。
- 精确语料映射/索引快照和代码、依赖、prompt、运行进程身份；D3现有入库状态UNKNOWN，不自动补导入。
- 区分真实B0原生系统比较与同模型/同prompt/同预算的范围干预；避免把请求参数修正、后处理或更大上下文的收益混归scope routing。
- 执行前制定provider总调用上限、额外预处理/重试计数、数据传输范围、无隐式恢复和日志脱敏。用户本轮授权的是复核与设计，不是新一轮API实验。

下一步：等待盲法Gold复核返回，按其条目/范围边界完成B0及自动路由协议；当前未执行新模型实验。
