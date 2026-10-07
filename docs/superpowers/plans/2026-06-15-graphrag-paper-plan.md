# GraphRAG Paper Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the current `graghRAG-agent` project into a submission-ready paper package, prioritizing SCI Q4 acceptance or major-revision viability, with Peking University Core / stronger general journals as the safer fallback.

**Architecture:** Treat the paper as a research-style system and evaluation manuscript centered on Chinese complex long-document QA with Agentic GraphRAG. Use the current repository's strongest evidence surface first, unify evaluation protocol on one frozen commit, then add the minimum baseline/ablation/stress-test package required for reviewer confidence.

**Update principle:** This revision does not overturn the original plan. It adds an evidence-governance layer and reorders execution priorities so the roadmap upgrades from a reasonable internal plan to a defensible submission package.

**Tech Stack:** Python, FastAPI, LangGraph/LangChain, NetworkX, BM25, Chroma/vector retrieval, DeepSeek-compatible generation, pytest-based verification, deterministic evaluation scripts.

---

## 1. Executive Positioning

### 1.1 Primary paper identity

The most defensible paper identity for the current project is:

**A Chinese complex long-document Agentic GraphRAG system paper focused on reliability, groundedness, robustness, and quality-cost trade-offs.**

This is better supported than:

- a pure algorithmic novelty paper
- a generic "enterprise AI platform" paper
- a broad "multimodal universal GraphRAG" paper

### 1.2 Submission strategy

#### Route A: Main route

- **Target:** SCI Q4 acceptance or major revision
- **Paper type:** system / engineering-evaluation paper
- **Decision rule:** use this route if the unified rerun, baseline ladder, and ablation package support a clear reliability-robustness-cost story under one governed evidence surface
- **Winning angle:** grounded hybrid retrieval + evidence governance + bounded quality-cost trade-off analysis

#### Route B: Parallel fallback route

- **Target:** Peking University Core or stronger general journal
- **Paper type:** Chinese long-document QA system design and evaluation
- **Decision rule:** use this route if system value is clear but novelty, baseline breadth, or external-validity expectations remain too high for the current SCI Q4 cycle
- **Winning angle:** coherent Chinese task focus + complete architecture + reproducible experiments + case-based application value

### 1.3 Explicit non-goals

Do **not** position this paper as:

- the first-ever GraphRAG method
- a universal low-cost real-time QA framework
- a clear SOTA algorithmic breakthrough
- a fully validated enterprise-report production paper

---

## 2. One-Sentence Argument

> For Chinese complex long-document question answering, we show that an Agentic GraphRAG framework built around knowledge-graph evidence, multi-path retrieval, and citation-verified generation can deliver high recall, strong groundedness, and reliable refusal behavior, while also exposing a non-trivial precision and long-tail cost trade-off that must be controlled through budget-aware retrieval.

This sentence is the paper's control center. Every section must serve it.

---

## 3. Repository Facts to Reuse as Paper Evidence

### 3.1 Strongest existing evidence

- [`iteration-2/eval-2-existing-components/rag_eval/REPORT_FINAL.md`](</D:/graghRAG-agent/iteration-2/eval-2-existing-components/rag_eval/REPORT_FINAL.md>)
  - 50 questions
  - 7 task types
  - A1-A5 metric structure
  - success/failure analysis
  - latency/token/cost analysis
- [`iteration-2/eval-2-existing-components/rag_eval/release_gate_report.md`](</D:/graghRAG-agent/iteration-2/eval-2-existing-components/rag_eval/release_gate_report.md>)
  - release-gate thresholds
  - final-context metrics
  - latency guardrails
  - provenance and SHA linkage
- [`iteration-2/eval-2-existing-components/rag_eval/raw_runs.jsonl`](</D:/graghRAG-agent/iteration-2/eval-2-existing-components/rag_eval/raw_runs.jsonl>)
  - runtime traces for tool usage
  - activity types and tool-call counts
  - evidence for the `Agentic` title gate
- [`backend/retrieval.py`](</D:/graghRAG-agent/backend/retrieval.py>)
  - 5-step retrieval pipeline
  - query preprocessing
  - multi-path recall
  - rerank and budget controls
  - global/local mode logic
- [`backend/generator.py`](</D:/graghRAG-agent/backend/generator.py>)
  - citation verification
  - bounded retries
  - refusal-related generation behavior
- [`integration/rag-engineering-blueprint-v1.0.md`](</D:/graghRAG-agent/integration/rag-engineering-blueprint-v1.0.md>)
  - system architecture and intended engineering scope

### 3.2 Immediate reviewer risk already visible in the repo

The paper must not mix evaluation surfaces casually.

The largest immediate risk is:

- `REPORT_FINAL` uses the 2026-05-28 50-question evaluation surface and reports very high latency/cost tails.
- `release_gate_report` uses a later 2026-06-14 gated surface and reports much lower latency.

If these surfaces are not frozen, classified, and reconciled under one metric contract, reviewers will question artifact integrity and reproducibility before they assess contribution.

### 3.3 Historical evidence vs current gated evidence

Treat the current repository evidence as two separate classes:

- historical evidence: older reruns, exploratory reports, and snapshot-style artifacts
- current gated evidence: frozen-commit outputs that are allowed to enter the manuscript

Historical evidence can explain how the system evolved, but it must be labeled explicitly. Final paper figures, tables, and headline claims should cite only the frozen artifact bundle.

### 3.4 Headline metric surface

The plan must define one manuscript headline metric surface before drafting the paper.

Recommended contract:

- headline surface: `final-context` retrieval quality, because this is the evidence actually delivered to generation
- diagnostic surfaces: `path_hits` and `pre-rerank`, because they explain where recall is gained or lost
- answer-side support surface: grounding / citation verification, because it tests whether retrieved evidence is actually used faithfully

If these surfaces are mixed without labels, reviewers will not know whether the paper is proving raw recall, usable evidence quality, or grounded answer quality.

---

## 4. Final Paper Scope Decision

### 4.1 Main story to lock now

Use this as the main paper scope:

**Chinese complex long-document QA**

### 4.2 What to downgrade to supporting material

Keep "enterprise project report" as:

- future work
- system extension potential
- discussion on applicability

Do not make it the main title or central claim unless a real enterprise document benchmark and matched experiments are added later.

Manuscript scope is defined by the current evidence surface, not by the full product vision of the repository.

### 4.3 Why this decision is optimal

- Current hardest evidence is already on Chinese long-document QA.
- Current paper can be made coherent without collecting entirely new datasets.
- This preserves a fast path to submission while keeping an upgrade path to an enterprise-focused second paper.

The overall paper direction remains correct: the project is best positioned as a Chinese long-document QA system/evaluation paper rather than as a pure algorithmic novelty claim. However, the bottleneck is now evidence governance. The next-stage manuscript must tie its headline claims to one frozen experimental surface, one metric ledger, one baseline ladder, and one bounded interpretation policy.

---

## 5. Recommended Titles

### 5.1 Primary title candidates

1. **Agentic GraphRAG for Chinese Long-Document Question Answering: Reliability, Robustness, and Cost Trade-offs**
2. **A Citation-Verified Hybrid Retrieval RAG System for Chinese Complex Long-Document QA**
3. **Grounded Agentic GraphRAG for Chinese Long-Document QA: Architecture and Empirical Analysis**

Title ranking rule: default to a non-agentic-leading title unless the ablation results clearly isolate the value of agentic control.

### 5.2 Fallback Chinese-style positioning titles

1. **面向中文长文档问答的 Agentic GraphRAG 系统设计与评测**
2. **融合知识图谱与多路检索的中文长文档可溯源问答方法**
3. **面向复杂结构化文档的知识图谱增强问答系统及实验分析**

### 5.3 Agentic title gate

Do not remove `Agentic` yet. Decide after the frozen-commit reruns whether the runtime evidence still looks agentic or more like a bounded pipeline.

Keep `Agentic` only if the frozen bundle still shows meaningful decision logic such as multi-path strategy control, global/local mode selection, KG rescue, and non-trivial runtime traces. If not, downgrade the final title to `hybrid retrieval`, `KG-enhanced`, or `citation-verified` wording before submission.

---

## 6. Contribution Template

Keep the paper to **three** contributions.

### Contribution 1

We present a Chinese complex long-document QA framework that integrates knowledge-graph evidence, multi-path retrieval, budget-aware control, and citation-verified generation into a single auditable pipeline for answerability, refusal, correction, and traceability.

### Contribution 2

We build a reproducible evaluation protocol that measures not only retrieval quality and answer grounding, but also refusal reliability, robustness to noisy or false-premise queries, tool efficiency, latency, and cost.

### Contribution 3

We empirically reveal a core trade-off of this class of systems: high recall, strong groundedness, and strong safety behavior can coexist with poor precision and severe long-tail inference cost, motivating explicit budget-aware retrieval controls.

The contribution is not that each module is individually novel, but that the paper makes their interaction auditable and empirically bounded under a unified reliability-robustness-cost evaluation surface.

---

## 7. Full Manuscript Structure

## 7.1 Abstract

Write last. Structure:

1. task and challenge
2. gap in existing RAG/GraphRAG evidence
3. proposed framework
4. key quantitative findings
5. bounded conclusion

### Abstract rules

- no "first"
- no "SOTA"
- no "production-ready enterprise deployment"
- no "real-time low-cost"

## 7.2 Introduction

Use a five-part arc:

1. Chinese long-document QA matters and is harder than standard semantic retrieval
2. Existing RAG/GraphRAG setups under-report grounding, refusal, and long-tail cost issues
3. This paper targets reliability rather than answer-only headline accuracy
4. Introduce the Agentic GraphRAG architecture and why it should help
5. Summarize contributions and experimental findings

## 7.3 Related Work

Four blocks:

1. long-document RAG
2. GraphRAG / KG-RAG / agentic retrieval
3. grounded generation / hallucination control / refusal
4. RAG evaluation and reliability-cost analysis

End with the gap:

**Current literature lacks a unified evidence surface for Chinese complex QA that jointly evaluates grounding, refusal, robustness, and cost.**

## 7.4 Method

Write around module motivation, not around code inventory.

Recommended order:

1. task formulation and design goals
2. system overview figure
3. query preprocessing
4. multi-path recall
5. reranking and redundancy/source-budget control
6. citation-verified generation and refusal behavior
7. implementation details and reproducibility boundaries

## 7.5 Experiments

Recommended research questions:

- **RQ1:** Can the system retrieve correct evidence for factual, aggregative, numeric, and multi-hop questions?
- **RQ2:** Are generated answers genuinely grounded in retrieved evidence?
- **RQ3:** Is the system robust on OOD, noisy, and false-premise queries?
- **RQ4:** What quality-cost trade-offs emerge under agentic retrieval?
- **RQ5:** Which components actually matter?

## 7.6 Discussion

Required themes:

1. why recall and groundedness are strong
2. why precision is weak
3. why long-tail cost appears
4. which controls matter most
5. what remains limited in current external validity

## 7.7 Conclusion

Bound the claim:

This paper should conclude that Agentic GraphRAG is promising for high-reliability Chinese long-document QA, but only becomes deployment-practical when precision and tail cost are explicitly managed.

---

## 8. Experimental Plan

## 8.1 P0 — mandatory for credible SCI Q4 attempt

### P0-0 Evidence Freeze and Artifact Governance

**Reviewer question answered:** Are the reported numbers tied to one immutable evidence bundle and one stable metric contract?

Required output:

- one frozen paper commit
- one immutable artifact bundle or frozen artifact directory
- one manifest with commands, environment, model and budget settings, and sha256 checksums
- one aligned `RAG-EVAL-SPECIFICATION.md`
- one metric contract that locks the headline, diagnostic, and answer-side surfaces
- one explicit label separating historical evidence from current gated evidence

Minimum manifest contents:

- commit hash
- `ground_truth.json` sha256 if used by the rerun
- `raw_runs.jsonl` sha256
- main metrics file sha256 values
- `REPORT_FINAL.md` sha256 if regenerated
- `release_gate_report.md` sha256 if regenerated
- exact evaluation commands
- model configuration and key retrieval budgets
- generation timestamp

SCI Q4 note:

- treat a short annotation protocol note as near-mandatory for the SCI Q4 route, especially if GT boundary criticism remains visible

Rule:

- only the frozen artifact bundle may feed manuscript figures, tables, and abstract-level numbers
- historical outputs may be mentioned only as labeled snapshots or evolution notes

### P0-1 Unified evaluation rerun on one frozen commit

**Reviewer question answered:** Are all reported numbers from the same system version and metric surface?

The paper must declare one headline metric surface, with diagnostic surfaces separated clearly from headline claims.

Required output:

- one frozen commit hash
- one unified 50-question rerun
- one unified metrics ledger that distinguishes historical evidence from current gated evidence
- one merged table covering:
  - raw/path retrieval
  - pre-rerank
  - final-context
  - answer grounding/citation

### P0-2 Budget-matched baseline ladder

**Reviewer question answered:** Why do we need the full GraphRAG system rather than simpler alternatives?

Minimum baseline table:

- Vector-only
- Vector + BM25
- KG-only
- Full Agentic GraphRAG

Hard rule:

- all baselines must be budget-matched on retrieval budget, context budget, generation settings, and stopping rules

Minimum common report columns:

- headline quality metrics
- final-context retrieval metrics
- latency
- input tokens
- total tokens
- estimated cost

### P0-3 Key ablation package

**Reviewer question answered:** Which components actually drive the gain, and which are just engineering complexity?

Minimum ablations:

- remove priority KG rescue
- remove rerank guard / budget logic
- remove redundancy or source-budget filtering
- remove cross-encoder rerank
- remove citation verification if evaluation can support it

### P0-4 Failure-bucket challenge set

**Reviewer question answered:** Did the system really fix its known blind spots?

Required tracked failures:

- Q10
- Q11
- Q15
- Q16
- Q31

Bucket them as:

- figure description
- list aggregation
- extrema / comparison
- multi-hop exploration tail

## 8.2 P1 — strong acceptance boosters

### P1-1 Annotation protocol and GT boundary note

Document:

- how `expected_node_ids` are built
- how keywords, refusal labels, and hop counts are assigned
- how equivalent nodes, equivalent expressions, and list-boundary ambiguity are handled
- which parts remain subjective and how that subjectivity is bounded

For the SCI Q4 route, this should be treated as close to mandatory even if it remains a short companion note.

### P1-2 Robustness confidence intervals

Add Wilson or exact binomial intervals for small-sample refusal, noise, and false-premise results, especially T5, T6, and T7.

### P1-3 Light cross-document transfer slice

Add a small cross-document transfer slice to strengthen external validity without waiting for a full second benchmark.

Recommended scope:

- one structurally different document
- 10 to 20 manually constructed questions
- the same metric contract as the main paper where feasible

### P1-4 Global mode benchmark

Compare local vs global mode on summary/overview-style queries.

### P1-5 Strict vs lenient scoring audit

Useful for figure/list questions where node-level strictness may understate answer usefulness.

### P1-6 Cost-quality Pareto analysis

Scan:

- `rerank_budget_ms`
- `rerank_max_candidates`
- `rerank_max_chars`
- `max_total_candidates`

Plot quality vs latency/tokens.

## 8.3 P2 — optional, high-cost, ceiling-raising

### P2-1 Full second benchmark

Add a second document or second KG benchmark if time allows.

### P2-2 Human usefulness audit

Add small human evaluation if feasible.

These are not first-priority within a 6-week sprint.

---

## 9. Minimum Submission Package

The smallest package that still looks like a real paper submission must include an evidence-governed artifact surface:

1. one frozen artifact bundle with manifest
2. one aligned evaluation specification
3. one metric contract note for headline and diagnostic surfaces
4. one short annotation protocol note for GT, refusal, and hop labeling
5. one 50-question rerun generated into the frozen artifact bundle on the paper experiment commit
6. one budget-matched baseline comparison table
7. one ablation table
8. one quality-efficiency Pareto figure
9. one failure-mode table focused on known hard cases
10. one light cross-document transfer slice or one explicit deferment note
11. two positive and two negative case studies
12. one system overview figure
13. one threat-to-validity subsection

This package is enough to support a system/evaluation manuscript.

Companion governance notes to create and maintain:

- [paper-evidence-freeze-note.md](/D:/graghRAG-agent/docs/superpowers/plans/paper-evidence-freeze-note.md)
- [paper-metric-contract.md](/D:/graghRAG-agent/docs/superpowers/plans/paper-metric-contract.md)
- [paper-annotation-protocol.md](/D:/graghRAG-agent/docs/superpowers/plans/paper-annotation-protocol.md)

---

## 10. Six-Week Execution Schedule

## Week 1: 2026-06-15 to 2026-06-21

**Objective:** lock paper scope, freeze evidence assets, and align the metric/specification layer

- [ ] Freeze the commit to be used for paper experiments
- [ ] Create the immutable artifact bundle and manifest
- [ ] Classify current evidence into historical evidence and current gated evidence
- [ ] Align `RAG-EVAL-SPECIFICATION.md` with the implemented metrics
- [ ] Write a short metric contract and annotation protocol note
- [ ] Decide final main scope: Chinese long-document QA
- [ ] Decide the manuscript headline metric surface
- [ ] Re-run 50-question evaluation on frozen commit
- [ ] Re-run release gate on the same commit
- [ ] Create unified metrics ledger
- [ ] Record exact commands and artifact paths

**Exit criteria**

- one frozen commit
- one immutable artifact bundle
- one aligned evaluation spec
- one unified metrics ledger
- one short metric-contract / annotation note

## Week 2: 2026-06-22 to 2026-06-28

**Objective:** build the fair main baseline table

- [ ] Lock comparable retrieval, context, and generation budgets across baselines
- [ ] Implement or wire Vector-only baseline
- [ ] Implement or wire Vector+BM25 baseline
- [ ] Implement or wire KG-only baseline
- [ ] Run Full GraphRAG under the same evaluation setup
- [ ] Produce the main comparison table with quality, latency, tokens, and cost
- [ ] Write short interpretation notes

**Exit criteria**

- baseline comparison table ready for manuscript

## Week 3: 2026-06-29 to 2026-07-05

**Objective:** identify which modules matter

- [ ] Run key ablations
- [ ] Run parameter scans for budget controls
- [ ] Compute confidence intervals for small-sample robustness buckets
- [ ] Produce quality-latency-cost Pareto plot
- [ ] Summarize module impact deltas

**Exit criteria**

- ablation table
- Pareto figure
- robustness interval note

## Week 4: 2026-07-06 to 2026-07-12

**Objective:** make failure analysis publication-grade

- [ ] Run the challenge subset around Q10/Q11/Q15/Q16/Q31
- [ ] Bucket failures by type
- [ ] Produce one failure-mode table
- [ ] Select 2 good and 2 bad case studies
- [ ] Run a light cross-document transfer slice
- [ ] If time allows, add local vs global benchmark

**Exit criteria**

- failure taxonomy
- transfer slice note
- case-study material

## Week 5: 2026-07-13 to 2026-07-19

**Objective:** draft the manuscript in evidence-first order

- [ ] Draft Experiments / Results
- [ ] Draft Introduction
- [ ] Draft Method
- [ ] Draft Discussion
- [ ] Draft Conclusion
- [ ] Draft Title and Abstract last

**Exit criteria**

- manuscript v1 complete

## Week 6: 2026-07-20 to 2026-07-26

**Objective:** submission hardening

- [ ] Add Threats to Validity
- [ ] Add reproducibility / implementation notes
- [ ] Polish figures and captions
- [ ] Run full final rerun for consistency check
- [ ] Apply the `Agentic` title gate and choose the final title family
- [ ] Produce SCI-Q4-oriented title/abstract version
- [ ] Produce PKU-Core-oriented title/abstract version

**Exit criteria**

- submission-ready v2
- main-route version
- fallback-route version

---

## 11. Writing Order Rules

Follow research-paper evidence-first drafting order:

1. Results / Experiments
2. Introduction
3. Method
4. Discussion
5. Conclusion
6. Title
7. Abstract

Do **not** start with the Introduction.

---

## 12. Figure and Table Package

Minimum figure/table set:

1. **Figure 1:** system overview
2. **Figure 2:** retrieval/generation pipeline detail
3. **Table 1:** main baseline comparison
4. **Table 2:** ablation study
5. **Figure 3:** quality-latency-cost Pareto
6. **Table 3:** failure-bucket analysis
7. **Figure 4:** case study visualization

Caption policy:

- captions explain setup and message
- discussion belongs in text, not in giant captions

---

## 13. Reviewer Risk Register

### Risk 1: novelty feels like engineering aggregation

**Mitigation**

- avoid "new algorithm" framing
- emphasize unified reliability-cost evidence and release-grade controllability

### Risk 2: evaluation surfaces look inconsistent

**Mitigation**

- freeze one commit
- rerun all key numbers
- explicitly explain old vs final gated results if historical numbers are mentioned

### Risk 3: specification drift undermines credibility

**Mitigation**

- align the live evaluation spec with the actual scripts before drafting
- cite only frozen artifact outputs in manuscript tables and figures

### Risk 4: benchmark credibility is weakened by subjective GT boundaries

**Mitigation**

- document the annotation protocol
- report confidence intervals for small-sample buckets
- add a light external transfer slice if feasible

### Risk 5: no strong or fair baseline

**Mitigation**

- prioritize baseline ladder in week 2 before more polishing work
- require budget-matched baselines and joint reporting of quality, latency, tokens, and cost

### Risk 6: tail cost looks too ugly

**Mitigation**

- turn it into a scientific finding
- add budget-control Pareto analysis

### Risk 7: title overstates agentic behavior

**Mitigation**

- decide the final title only after the frozen-commit reruns
- downgrade to `hybrid retrieval` or `KG-enhanced` wording if runtime traces look bounded

### Risk 8: manuscript reads like project docs

**Mitigation**

- write every section as claim → evidence → boundary
- keep module descriptions tied to motivation and ablation hooks

---

## 14. Route-Specific Packaging

## 14.1 SCI Q4 package

Emphasize:

- hybrid retrieval architecture
- grounded answer generation
- refusal and robustness behavior
- evidence governance and claim-to-metric traceability
- frozen-artifact reproducible evaluation
- cost/reliability trade-off

De-emphasize:

- `Agentic` branding if the title gate is not clearly passed
- enterprise platform branding
- broad universality claims
- unrealistic efficiency marketing

## 14.2 PKU Core / stronger general journal package

Emphasize:

- Chinese long-document QA
- KG-enhanced architecture
- complete system implementation
- traceable answers
- case analysis and application value
- disciplined scope control rather than inflated novelty claims
- conservative title framing is acceptable if it improves defensibility

De-emphasize:

- aggressive top-tier benchmark rhetoric
- claims that require large multi-domain external validation

---

## 15. Immediate Action List

### Highest-priority next actions

- [ ] Create the `P0-0` evidence freeze package
- [ ] Decide the manuscript headline metric surface
- [ ] Align the evaluation specification with implemented metrics
- [ ] Lock the paper's main scope to Chinese complex long-document QA
- [ ] Record the frozen experiment commit
- [ ] Write the short metric contract and annotation protocol note
- [ ] Create a unified metrics ledger that reconciles `REPORT_FINAL`-style historical metrics with current gated metrics without mixing them into one headline result surface
- [ ] Enumerate the exact budget-matched baseline implementations to run
- [ ] Enumerate the exact ablations to run
- [ ] Draft the light cross-document transfer slice
- [ ] Convert current markdown metrics into manuscript tables
- [ ] Draft the system overview figure
- [ ] Draft the failure taxonomy table
- [ ] Draft the one-sentence argument and three contributions in manuscript-ready English
- [ ] Start the Experiments section skeleton

---

## 16. Completion Standard for This Paper Plan

This planning document is successful only if it enables the next session to:

1. execute experiments without re-deciding the paper identity
2. write the manuscript without re-deciding the main claim
3. choose between SCI Q4 and PKU Core packaging late in the process, not early

The plan should therefore be treated as the paper roadmap, not as a brainstorming note.
