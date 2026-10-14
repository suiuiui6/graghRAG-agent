# Independent Gold review — GOLD-INDEPENDENT-20261007

`project_id: graphrag-paper-001` · `paper_family: M` · `stage_id: M2` · `contract_version: 1.0` · `task_status: PROVISIONAL` · review date: 2026-10-07.

This is a separate AI reviewer’s source-based review, not human adjudication. The nine questions and 31 draft items were checked independently against their complete target scopes. No participant answers, previous adjudication, previous reports, or control console were read. No model-answer evaluation or canonical Gold freeze was performed. Recommendation: **REPAIR**, principally for the D1-COST membership rule and D2-ATTENTION provenance rule.

## Scope and inputs

Evidence depth is **repository Markdown only; no original PDF, embedded-image viewing, figure/table visual verification, or broader literature verification**. Direct source support below means support in the supplied Markdown, not verification of the papers’ calculations or the current application implementation.

| Input | SHA-256 | Reviewed extent |
|---|---|---|
| `gold.yaml` | `e732d568715d2b750d3c9ced4afa88a31df66f2db65c869ff4c2536d8e05d5f2` | All nine questions, scopes, 31 items and exclusions |
| `pilot.py` | `1fedb48fd811b276996666d7843a00e32232a8f949ad1d87142baa6d10b85f8c` | Scope extraction, source/locator conventions, anchor validation and scoring definitions; read only, not executed |
| D1: `backend/output/mineru/ingest_2/full.md` | `f0e2b044ec0f8be55b1c00d9479830f6768a5da9970111a7db0353d59097a0d6` | Entire 402-line Markdown for the figure catalogue; complete abstract and §6.2; neighbouring context |
| D2: `backend/output/mineru/ingest_f/full.md` | `ab7cdd99e8cd85ddd61e3d65e4e747685a25a62d22f68bed3e2d79d015e90623` | Complete §3.2.3 and §5.1, plus boundary/context lines 83–118 and 150–174 |
| D3: `integration/Agentic-RAG-Architecture.md` | `d0c64333bf10c761fef29bc1d9e002656f3968e720e176e92b8a18eb4a1e8e72` | Complete §3.2 table and §4.1 list, plus context lines 158–217 and 293–342 |

All source hashes equal the draft’s recorded hashes. Source content was treated as data. No credentials, `.env`, network, APIs, installs, production changes, or other project material were accessed.

Locators are **one-based lines** and **zero-based Unicode code-point character spans `[start,end)`**, after universal-newline normalization to LF, matching `Path.read_text(encoding="utf-8")` in `pilot.py`. They are not UTF-8 byte offsets or UTF-16 positions. D3 contains non-BMP characters outside the target spans; the code-point distinction matters.

`原文事实 / VERIFIED_USER_MATERIAL` denotes directly read text. `AI分析 / AI_INFERENCE` denotes reviewer interpretation; it does not become an explicit source statement. Missing PDF visual evidence is `PENDING_VERIFICATION`.

## Specialist findings

### D1-FIG — six unique numbered figures; title policy needs clarification

The independent numbered set is `{1,2,3,4,5,6}`. The complete Markdown has six body captions and six Appendix B catalogue entries for those same numbers. It does not contain a seventh numbered figure. There are multiple embedded image links per numbered figure; image-link count is not figure count.

The following are the **exact body caption strings**, retaining the original wording. The draft’s Appendix B anchors are also supported, but should be accepted as aliases unless the question specifically chooses the appendix as its title authority.

| Draft ID | Value / unit / role | Body caption; original line and character span | Appendix B alias; original line and character span |
|---|---|---|---|
| F1 | `1` / 图号 / figure | `图 1 问题一园区功率曲线（上：源荷对比；下：购售电功率）`; L114 `[7650,7679)` | `图 1— 问题一园区功率曲线（上：源荷对比；下：购售电功率）`; L374 `[21775,21805)` |
| F2 | `2` / 图号 / figure | `图 2 问题二(1) 最优方案调度图（产量36吨/日，蓝色底色为设备运行时段）`; L163 `[10776,10815)` | `图 2— 问题二离散制氨最优调度（产量 36吨/日，蓝色为设备运行时段）`; L376 `[21807,21843)` |
| F3 | `3` / 图号 / figure | `图 3 问题二(2) 全年吨氨成本分布（左：各产量箱线图；右：排序分布曲线）`; L179 `[11873,11911)` | `图 3— 问题二全年吨氨成本分布（左：各产量箱线图；右：排序分布曲线）`; L378 `[21845,21880)` |
| F4 | `4` / 图号 / figure | `图 4 离散 vs连续制氨对比（左：全年成本分布；右：绿电指标雷达图）`; L222 `[14725,14760)` | `图 4— 问题三离散 vs连续对比（左：全年成本分布曲线；右：绿电指标雷达图）`; L380 `[21882,21921)` |
| F5 | `5` / 图号 / figure | `图 5 问题四分析结果（左：三种模式经济性对比；右：储能充放电调度曲线）`; L254 `[16321,16357)` | `图 5— 问题四离网与储能分析（左：三种模式经济性对比；右：储能充放电调度）`; L382 `[21923,21961)` |
| F6 | `6` / 图号 / figure | `图 6 全问题综合汇总（左上：各方案吨氨成本对比；右上：绿电指标雷达演进；左下：各产量成本对比；右下：离网vs联网产量对比）`; L298 `[19169,19231)` | `图 6— 全问题综合汇总图（四合一：成本对比/指标雷达/成本分布/产量对比）`; L384 `[21963,22001)` |

Conditions are the parenthetical panel descriptions in the table. F2’s production condition is **36吨/日 in both captions**. Adjacent discussion of a 54吨/日 economically balanced solution does not change this figure’s caption binding. F6 has four panels; those are not four additional figure numbers. `final\_comprehensive.png — 综合汇总图（四合一）`, L386 `[22003,22040)`, is an unnumbered file entry, not a supported figure 7. Its precise binary identity with an embedded image was not verified.

All F1–F6 exist and have the appropriate role. The draft’s shortened labels are not all verbatim body titles. The broad question asks for all figures in the paper, while `pilot.py`’s `figure_catalogue` regex `^图\s*\d+\s*[—－-].+$` selects only the six appendix entries in this source and excludes the six body captions because they lack that dash. The projection provides a useful catalogue, but is not itself a full-document completeness audit.

**GIR-C03, scope/title-policy ambiguity:** retain the old question for sensitivity analysis with body-caption and appendix-alias answers accepted, while keeping the same six-number set. For a new version, choose either “仅根据提供的 Markdown 文档，汇总所有显式编号的图，按图号去重；以正文题注为主，附录 B 名称作为别名注明” or “仅按附录 B‘支撑材料文件说明’中的编号图目录，列出图号及标题，不计未编号文件名”. Record that choice and a new question version; do not silently substitute the appendix-only interpretation.

### D1-COST — five direct cost levels are supported; the original membership rule is ambiguous

Full abstract scope: L7–22, `[55,1097)`; `关键词：` begins at L23 and is excluded. Independently reconstructed direct cost levels:

| ID | Exact support | Value | Unit | Condition / role | Locator |
|---|---|---|---|---|---|
| C1 | `吨氨成本3554元/吨` | `3554` | 元/吨 | 问题一满负荷连续运行基准，摘要称典型日；result | L11 `[260,271)`; full condition context L11 `[173,350)` |
| C2 | `全年吨氨成本 5820元/吨` | `5820` | 元/吨 | 问题二全开/全关离散调节，五种产量×24场景的全年结果；result | L13 `[449,463)`; condition context `[352,573)` |
| C3 | `72吨/日，18/24场景全满足，7111元/吨` | `7111` | 元/吨 | 问题二高产量72吨/日档，18/24场景全满足；result | L13 `[495,519)` |
| C4 | `36吨/日，0/24场景全满足，3669元/吨` | `3669` | 元/吨 | 问题二低产量36吨/日档，0/24场景全满足；result | L13 `[528,551)` |
| C5 | `全年吨氨成本降至 5652元/吨（降低2.9%）` | `5652` | 元/吨 | 问题三10%–100%连续调节，相对问题二离散调节的全年结果；result | L15 `[640,664)`; condition context `[575,766)` |

These are five different atomic **condition–cost** bindings, not five occurrences of an undifferentiated cost concept. Do not bind C1 to 问题二36吨/日; do not bind 7111 or 3669 to 问题一; do not omit the annual/scenario context of C2–C5. The abstract alone does not explicitly say C1 is the 36吨/日 capacity baseline, so that additional condition should not be made a mandatory abstract-only field.

Two further in-scope economic facts are material to the phrase “吨氨成本类经济指标”:

| Candidate only; not a canonical Gold addition | Exact support | Value / unit / role | Condition and boundary | Locator |
|---|---|---|---|---|
| C6-proposed | `电网支撑价值为1970元/吨` | `1970` / 元/吨 / economic_comparison | 问题四电网功率支撑的吨氨经济价值。摘要没有给出其减法公式或组成成本，不能从正文补入摘要答案 | L17 `[927,941)`; context `[768,967)` |
| C7-proposed | `降低2.9%` | `2.9` / % / relative_cost_reduction | 问题三连续调节全年吨氨成本相对离散制氨的降幅；不是另一个元/吨成本水平 | L15 `[657,663)`; full binding `[640,664)` |

**GIR-C01, ontology conflict:** a “direct cost-level” ontology gives C1–C5; a “per-ton economic-value” ontology also admits C6; a “cost-related economic indicator” ontology also admits the C7 relative reduction. The source resolves their values, not the intended membership policy. Under the original broad wording, 1970元/吨 is a defensible required item; 2.9% is a defensible cost-related fact, potentially an attribute of C5 rather than a separate counted item. Treating either as an unsupported hallucination would be unjustified.

Specific correction: freeze the ontology before answer adjudication. A revised narrow question can read “仅根据摘要，列出直接报告的吨氨成本水平（单位元/吨）及对应问题、运行模式和产量/全年条件；不单独计入相对降幅或电网支撑价值”. This supports five level items and may retain C5’s 2.9% as optional context. A revised broad question should explicitly request “成本水平、成本相对降幅和电网支撑价值”, then specify whether C7 is a separate comparison item or an attribute. For the unchanged old question, report the five/six/seven membership sensitivities separately; do not silently alter the historical task or denominator.

Other abstract numbers concern energy, ammonia output, renewable utilization, compliance, or storage configuration and are not automatically economic-cost items. 168元/吨 is outside the abstract; 3682 and 3749元/吨 are outside it. The existing exclusions of those values remain appropriate.

### D1-LIMITS — four numbered limitations, with explanatory subconditions

Full §6.2 scope: L314–323, `[19694,20159)`. The independent set of **numbered limitation categories** is `{L1,L2,L3,L4}`; `value` and `unit` are null and `role=limitation` throughout.

| ID | Exact limitation heading / locator | Required explanatory binding when a substantive description is requested | Complete item context |
|---|---|---|---|
| L1 | `(1) 忽略储能寿命衰减。`; L316 `[19711,19724)` | 当前储能被简化为无限循环能量池；未考虑充放电深度、循环次数对电池寿命的影响 | L316 `[19711,19829)` |
| L2 | `(2) 场景覆盖度有限。`; L318 `[19831,19843)` | 24种风光组合未考虑季节性常规负荷变化和电价政策的季节性调整 | L318 `[19831,19950)` |
| L3 | `(3) 未纳入碳交易收益。`; L320 `[19952,19965)` | 当前吨氨成本未考虑绿氨替代灰氨的碳减排经济价值 | L320 `[19952,20057)` |
| L4 | `(4) 确定性模型未处理预测不确定性。`; L322 `[20059,20078)` | 当前依赖确定的日前风光场景，未量化预测误差带来的运行风险 | L322 `[20059,20157)` |

The four draft headings are supported and complete at the numbered-category level. Their generic `condition: 当前模型` does not encode all explanatory detail, especially L2’s two omitted factors. The improvement clauses are proposals: rainflow cycle counting/equivalent-cycle lifetime modelling, annual simulation/Monte Carlo scenarios, multi-market coupling, and RO/SP must not be recast as methods already used.

**GIR-C04, granularity ambiguity:** preserve the original four-category scoring for sensitivity, with detailed subconditions audited separately. If finer atomic completeness is intended, revise the question to require the explanations, and define sub-bindings rather than silently increasing the item denominator. A stable revised question is “列出6.2的四个编号模型不足，并简述每项所忽略的因素或风险；改进建议另行标为建议”. No outside limitations from the assumptions section should be added to this bounded set.

### D1-FUTURE — two alternative proposed optimization families

The declared context is full §6.2, `[19694,20159)`, but the query’s semantic target is only item (4), L322 `[20059,20157)`. The independent requested method set is `{R1,R2}`.

| ID | Label / value / unit / condition / role | Support |
|---|---|---|
| R1 | 鲁棒优化 / `RO` / null / 日前风光预测误差不确定性与运行风险 / proposed | L322 `[20114,20157)`: `采用鲁棒优化（RO）或两阶段随机规划（SP）方法，在约束中加入预测误差的不确定性集合。` |
| R2 | 两阶段随机规划 / `SP` / null / 同上 / proposed | Same L322 support, including the explicit `两阶段` qualifier |

Both items are explicitly proposed, not implemented results. The source joins them with **或**; an answer should not claim both were adopted together. “在约束中加入预测误差的不确定性集合” is a proposed modelling measure, not a third separately named optimization family. Do not repair or expand the source’s technical wording using unstated textbook distinctions. MILP/LP elsewhere and Monte Carlo from item (2) are outside the requested method set. The draft two-item set is sound; add the alternative relation and support the `proposed` role using the complete `改进方向` sentence rather than a name-only anchor.

### D2-ATTENTION — three uses; explicit Q/K/V support is asymmetric

Full §3.2.3 scope: L97–106, `[12251,13474)`. L99 explicitly introduces three uses, `[12300,12366)`. The independent use set is `{A1,A2,A3}`; each has `value=null`, `unit=null`, `role=mechanism`. Q/K/V are separate provenance bindings, not units or numerical values.

| ID | Use | Independent binding / evidence level | Exact text and locator |
|---|---|---|---|
| A1 | encoder-decoder attention | Q: previous decoder layer; K: encoder output; V: encoder output. All explicit | L101 `[12370,12526)`: `In "encoder-decoder attention" layers, the queries come from the previous decoder layer, and the memory keys and values come from the output of the encoder.` |
| A2 | encoder self-attention | Q, K and V: output of the previous encoder layer. All explicit | L103 `[12780,12930)`: `In a self-attention layer all of the keys, values and queries come from the same place, in this case, the output of the previous layer in the encoder.` |
| A3 | decoder self-attention | Decoder position may attend only through and including its current position; masking of illegal softmax-input connections is explicit. Decoder-side self-attention Q/K/V origin is a permitted semantic inference from `Similarly` and `self-attention`, but **previous decoder layer is not explicitly restated in this scope** | L105 `[13029,13188)`: `Similarly, self-attention layers in the decoder allow each position in the decoder to attend to all positions in the decoder up to and including that position.` Full masking context L105 `[13027,13472)` |

The draft A1 is properly bound. The draft A2 has a correct condition but its anchor `The encoder contains self-attention layers.` alone does not support the previous-layer Q/K/V attribute; replace or supplement it with the complete provenance sentence. Full-scope source support exists, so this is an evidence-anchor issue, not proof that the source omits A2’s binding.

The draft A3 condition describes visibility/masking but omits the query’s requested Q/K/V provenance. A three-label answer with a mask description is not automatically a complete response to the original question. Equally, a requirement for an explicitly quoted previous-decoder-layer origin would be unsupported by this restricted text. The mask is applied to forbidden **inputs of softmax**, not directly to the V representation vectors merely because the source uses the word “values”. Do not use familiarity with the paper or another section to turn that inference into an explicit statement.

**GIR-C02, query/source mismatch:** retain the original question with three usage items, but audit provenance separately. Accept “decoder-side states, inferred from the self-attention description; §3.2.3 does not explicitly restate the layer of origin” and accept a source-conscious non-explicit statement. Do not treat omission of provenance as fully answered, and do not force an unsupported exact-layer assertion. For a revised scope-faithful question use: “List the three uses in section 3.2.3. Give Q/K/V sources where explicitly stated; for decoder self-attention describe the stated visibility and masking, and distinguish any inference about provenance.” If all three exact layer origins are required, first widen and version the source scope, then verify that added source rather than importing it post hoc.

**GIR-C05, anchor/attribute mismatch:** A2’s short draft anchor verifies existence only. A1’s longer anchor is sufficient for its Q/K/V sources; A3’s short visibility anchor does not independently verify the masking implementation or a Q/K/V source. Use attribute-specific supporting spans and an explicit/inference flag. Exact anchor presence is evidence availability, not semantic answer correctness.

### D2-DATA — two language pairs; preserve distinct source units

Full §5.1 scope: L156–159, `[20861,21487)`. The complete paragraph L158 `[20896,21485)` contains exactly two named translation language pairs with training-dataset sizes.

| ID | Pair / value / unit / condition / role | Exact support / locator |
|---|---|---|
| T1 | English–German / `about 4.5 million` / sentence pairs / WMT 2014 training data / training_data | `English-German dataset consisting of about 4.5 million sentence pairs`; L158 `[20932,21001)` |
| T2 | English–French / `36M` / sentences / WMT 2014 training data, as worded in this Markdown / training_data | `English-French dataset consisting of 36M sentences`; L158 `[21184,21234)` |

Both draft values/units are supported. Preserve T1’s approximation. Expanding `36M` to 36 million is a quantity-preserving normalization; replacing `sentences` with `sentence pairs` without explanation is not. No external reconstruction or PDF check was performed to resolve any familiarity-based objection to the source unit. “Sentence pairs were batched together” later in the paragraph does not silently change the earlier dataset-size unit. Add the explicitly stated WMT 2014 condition to T2 rather than using only the meta-condition “as worded in imported section 5.1”. The query asks language pairs, so do not require a translation direction not stated here. Vocabulary sizes of about 37000 tokens and 32000 word pieces, and approximately 25000 source/target tokens per batch, are not additional dataset-size entries.

### D2-NONE — valid scope-specific empty set

Full §3.2.3 `[12251,13474)` was read, including its introduction and all three bullets. **No optimizer name is stated in this section**. The expected optimizer-name set is empty, with affirmative `empty_scope_correct` behaviour. There is no positive item, numerical value, unit or optimizer role to fabricate.

The correct statement is “No optimizer names are stated in §3.2.3.” A global “the paper has no optimizer” is contradicted by the boundary context: §5.3 explicitly names Adam at L166 `[21935,22137)`. That out-of-scope fact is recorded here solely to verify the negative claim’s boundary; it must not become an answer item for this question. The draft empty set and exclusion of in-scope Adam are sound. Empty-set completeness must be reviewed independently; positive-anchor coverage has no denominator here. A simple absence of returned claims alone does not prove that the scoped negative answer was understood.

### D3-TOOLS — five table tools, specification roles

Full §3.2 scope: L188–197, `[6399,6809)`. The independent set is `{K1,K2,K3,K4,K5}`. All have `value=null`, `unit=null`, `role=specified_tool`. Their conditions are the table’s intended uses; they are not evidence of implementation.

| ID | Tool / exact use | Complete row locator |
|---|---|---|
| K1 | `search_kg` / 知识图谱结构化查询 | L192 `[6458,6527)` |
| K2 | `search_vector` / 语义相似度检索 | L193 `[6528,6602)` |
| K3 | `search_keyword` / BM25 关键词检索 | L194 `[6603,6672)` |
| K4 | `get_entity_detail` / 获取实体完整信息 | L195 `[6673,6734)` |
| K5 | `get_page_context` / 获取 PDF 页面上下文 | L196 `[6735,6807)` |

All five draft names and use bindings are correct and complete for the requested table. Inputs/outputs may be included as context but are not mandatory answer attributes under this question. `classify_query` in §3.3 and additional specialist-tool names in §4’s diagram are outside the table scope. A normative tool description is not an implementation claim; no current production code was examined by this reviewer. No question change is needed.

### D3-SUPERVISOR — four bounded responsibilities

Full §4.1 scope: L316–322, `[11015,11170)`. The independent set is `{S1,S2,S3,S4}`, with `value=null`, `unit=null`, `role=specified_responsibility`.

| ID | Exact source text; condition retained after the colon | Locator |
|---|---|---|
| S1 | `1. **解析用户 query**：识别需要哪些 Agent 参与` | L318 `[11039,11072)` |
| S2 | `2. **任务分发**：将子任务路由到对应的 Specialist Agent` | L319 `[11073,11112)` |
| S3 | `3. **结果整合**：合并各个 Agent 的返回结果` | L320 `[11113,11141)` |
| S4 | `4. **最终生成**：基于合并结果生成带引用的答案` | L321 `[11142,11168)` |

All four draft items are source-supported and complete at the numbered-responsibility level. Preserve S4’s “带引用” requirement and S2’s specialist routing; generic “generate an answer” or “dispatch a task” alone loses meaningful binding detail. Do not import offline index construction from §2, diagram tool lists, or communication-schema fields from §4.2. These remain specified responsibilities, not verified live-system behaviour. No question change is needed.

## Evidence and execution status

Local source reading, whole-file SHA-256 comparisons, and line/code-point locator computation were executed. `pilot.py` was only read. No generation, answer adjudication, retrieval-quality experiment, statistical analysis, rendering, upload, deployment, or human review was executed. No accuracy, novelty, significance, or production-readiness conclusion follows from this review.

There is a measurement limitation relevant to using this Gold: `pilot.py`’s anchor check tests exact text availability, while its item validity combines ID, condition, role, source support and scope. Neither a matching anchor nor a matched item ID alone establishes that all requested value/unit/provenance attributes were answered. This reviewer has not changed that code or evaluated any answer rows. Attribute-aware adjudication rules should be settled before scoring, particularly for D1-COST and D2-ATTENTION.

## Deliverables

Only `gold-review-v2/independent-sol-review.md` and `gold-review-v2/independent-sol-contract.yaml` were created. `gold.yaml`, production code, project/stage state, old review outputs and all answer artifacts were left untouched. Canonical merging remains **orchestrator_only**.

## Limitations and risks

The material supports completeness of the specified Markdown scopes. It cannot establish that OCR preserved every original figure or validate graph identities, table layouts, or numerical derivations in the PDFs. The architecture source supplies specifications, not present implementation facts. The broad old questions remain useful sensitivity cases but do not yet define an unambiguous canonical membership/provenance ontology. Revising a question after seeing answers would change the evaluation target; any adopted revision needs a recorded version and retained old-question results under their own policy.

## Quality checks

- All nine questions and 31 draft items reviewed; the empty question received an independent whole-scope check.
- Full target-source scopes read; D1’s entire Markdown read for catalogue completeness. All source hashes match the draft.
- Every reconstructed item has original text support and line/character locators; body/appendix aliases kept distinct.
- Values, source units, conditions, roles, scope limits, alternatives and negative-answer boundaries checked.
- Explicit facts separated from the decoder-provenance inference; candidate C6/C7 remain proposals.
- Five conflicts identified with competing readings and source locators; none silently resolved into canonical Gold.
- No private source frontmatter or participant identifiers copied into deliverables; no answer contamination or stage mutation.
- Local validation confirmed valid YAML, the exact 19-field result contract and task identity, nine question sections, and five complete conflict records.

## One next action

The orchestrator should adjudicate GIR-C01 through GIR-C05 and record a versioned Gold/question policy before canonical merging or subsequent answer scoring.
