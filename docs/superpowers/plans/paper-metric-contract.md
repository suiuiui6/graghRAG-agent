# Paper Metric Contract

## 1. Purpose and Scope

This document defines which metric surfaces may support manuscript claims, where each metric may appear in the paper, and how retrieval, answer-support, and engineering metrics must be separated.

Its purpose is to stop metric drift between:

- the manuscript text
- the release-gate layer
- the metric JSON outputs
- the legacy evaluation specification

## 2. Evidence Sources

This contract is grounded in the current repository evidence:

- [RAG-EVAL-SPECIFICATION.md](/D:/graghRAG-agent/iteration-2/eval-2-existing-components/rag_eval/RAG-EVAL-SPECIFICATION.md)
- [REPORT_FINAL.md](/D:/graghRAG-agent/iteration-2/eval-2-existing-components/rag_eval/REPORT_FINAL.md)
- [release_gate_report.md](/D:/graghRAG-agent/iteration-2/eval-2-existing-components/rag_eval/release_gate_report.md)
- [raw_runs.jsonl](/D:/graghRAG-agent/iteration-2/eval-2-existing-components/rag_eval/raw_runs.jsonl)
- [metrics_a1_retrieval.json](/D:/graghRAG-agent/iteration-2/eval-2-existing-components/rag_eval/metrics_a1_retrieval.json)
- [metrics_a2_faithfulness.json](/D:/graghRAG-agent/iteration-2/eval-2-existing-components/rag_eval/metrics_a2_faithfulness.json)
- [metrics_a5_performance.json](/D:/graghRAG-agent/iteration-2/eval-2-existing-components/rag_eval/metrics_a5_performance.json)
- [release_gate_report.json](/D:/graghRAG-agent/iteration-2/eval-2-existing-components/rag_eval/release_gate_report.json)

## 3. Why This Contract Is Needed

The current repository already shows visible specification drift.

The older specification still centers on:

- `relevant_doc_ids`
- `retrieved_doc_ids`
- document-level `Recall@k`
- `LLM-as-judge` faithfulness

The live evaluation evidence has shifted toward:

- surface-based retrieval evaluation
- `path_hits`, `pre_rerank`, and `final_context`
- rules-based answer-support checks
- release-gate thresholds that explicitly privilege `final-context`

Without a metric contract, the paper could easily mix outdated schema language, diagnostic surfaces, and answer-support metrics into one headline result claim.

## 4. Metric Surface Taxonomy

The manuscript uses three layers:

1. retrieval headline surface
2. retrieval diagnostic surfaces
3. answer-side support surfaces

The default rule is simple:

- any manuscript-level retrieval claim defaults to `final-context`
- `path_hits` and `pre-rerank` are analysis-only unless the paper explicitly studies retrieval-stage degradation

## 5. Headline Surface

The manuscript headline retrieval surface is:

- `final-context`

Reason:

- it is the evidence actually delivered to generation
- it matches the current release-gate logic
- it is the most defensible retrieval surface for abstract-level claims

Primary headline metrics:

- `recall_macro`
- `hit_rate_macro`
- `strict_hit_macro`
- optionally `mrr_macro` if regenerated and clearly tied to the same frozen bundle

Current repository note:

- [release_gate_report.json](/D:/graghRAG-agent/iteration-2/eval-2-existing-components/rag_eval/release_gate_report.json) already treats `a1_final_context_recall_min` as the enterprise-critical retrieval threshold

## 6. Diagnostic Retrieval Surfaces

The diagnostic retrieval surfaces are:

- `path_hits`
- `pre-rerank`

Their job is to explain where recall is gained or lost, not to replace the headline retrieval claim.

Allowed uses:

- failure analysis
- ablation interpretation
- retrieval-stage degradation analysis
- appendix diagnostic tables

Prohibited use:

- they may not be used as the main retrieval numbers in the abstract, introduction, or headline result table

## 7. Answer-Side Support Surfaces

The answer-side support surfaces include:

- `cited_in_retrieved_rate`
- `node_id_validity`
- claim-level support labels
- citation precision / citation recall
- `keyword_coverage`
- grounding / citation-verification summaries where supported by the frozen bundle

The current implementation name `node_id_validity` is retained only for file compatibility. In manuscript prose it must be described as **citation-ID validity**: whether a cited identifier exists and belongs to the allowed evidence set. The legacy `hallucination_rate` derived from this check is also an identifier-error proxy, not a semantic hallucination rate.

Only claim-level adjudication may support statements about whether an answer proposition is fully supported, partially supported, unsupported, or contradicted by the cited evidence.

Together these metrics test different parts of whether retrieved evidence is used in a traceable and defensible way.

They do not replace retrieval quality metrics.

Interpretation rule:

- answer-support metrics may strengthen trust claims
- answer-support metrics may not be presented as retrieval performance

## 8. Metric Publication Rules

### 8.1 What may appear in the abstract and introduction

Only the following quantitative claims may appear in the abstract or introduction:

- `final-context` headline retrieval numbers
- claim-level support and citation precision/recall numbers, but only after a frozen annotation/adjudication protocol is executed

### 8.2 What must stay out of the abstract and introduction

The following should not appear in the abstract or introduction unless the frozen rerun redefines the contract explicitly:

- `path_hits` numbers
- `pre-rerank` numbers
- `node_id_validity` or its legacy derived `hallucination_rate` as evidence of semantic faithfulness
- per-category `T1-T7` breakdowns
- per-question examples
- failure-bucket counts
- long-tail outlier decomposition
- outdated document-level metric wording inherited from the old specification

### 8.3 What belongs in analysis, ablation, or appendix

The following belong in Results analysis, ablation sections, or appendix:

- full `path_hits` and `pre-rerank` panels
- category-level splits
- latency and cost tail analysis
- per-question examples from [raw_runs.jsonl](/D:/graghRAG-agent/iteration-2/eval-2-existing-components/rag_eval/raw_runs.jsonl)
- lexical mismatch analysis, such as low `keyword_coverage` despite semantically adequate support

## 9. Reporting Template

| Layer | Surface | Role in paper | Canonical metrics | Allowed locations | Primary evidence |
|---|---|---|---|---|---|
| Retrieval headline | `final-context` | Main performance claim | `recall_macro`, `hit_rate_macro`, `strict_hit_macro`, optional `mrr_macro` | Abstract, Introduction, Results, Main tables | `metrics_a1_retrieval.json`, `release_gate_report.*` |
| Retrieval diagnostic | `path_hits` | Early-path recall diagnosis | Same metric family as headline | Analysis, Ablation, Appendix | `metrics_a1_retrieval.json` |
| Retrieval diagnostic | `pre-rerank` | Candidate-pool diagnosis | Same metric family as headline | Analysis, Ablation, Appendix | `metrics_a1_retrieval.json` |
| Answer support | `cited_in_retrieved_rate` | Evidence-use validity | `cited_in_retrieved_rate_macro` | Results, Analysis, Appendix | `metrics_a2_faithfulness.json`, `release_gate_report.*` |
| Identifier validity | legacy `node_id_validity` | Citation-ID existence / allowed-set membership only | `node_id_validity_macro`, legacy identifier-error rate | Diagnostic analysis, Appendix | `metrics_a2_faithfulness.json`, `REPORT_FINAL.md` |
| Answer support | claim adjudication | Proposition-level semantic support | supported / partial / unsupported / contradicted rates; citation precision / recall | Results, Analysis, Appendix; Abstract only after frozen validation | Future frozen claim annotations and adjudication output |
| Answer support | grounding / citation verification | Provenance support | Frozen-bundle grounding summaries | Analysis, System description, Appendix | Frozen rerun + implementation evidence |
| Answer quality secondary | `keyword_coverage` | Surface-form answer completeness | `keyword_coverage_macro` | Results, Analysis | `metrics_a2_faithfulness.json` |
| Engineering gate | latency / gate checks | Submission hardening, not scientific headline | `p95`, `p99`, gate pass/fail | Reproducibility note, Appendix, Threats | `metrics_a5_performance.json`, `release_gate_report.*` |

## 10. Change Control

The following items must move together:

- manuscript wording
- metric JSON definitions
- release-gate thresholds where cited
- evaluation specification text

If a later rerun changes:

- metric names
- allowed locations
- surface priority
- interpretation boundaries

then this contract must be updated before the manuscript is revised.

No manuscript section should silently promote:

- `path_hits` into a headline surface
- answer-support metrics into retrieval metrics
- engineering gate thresholds into scientific contribution claims

## 11. M3 Design Addendum (2026-10-07)

The prospective definitions in `paper-m3-evaluation-contract.md` and the seven variants in `paper-m3-variant-plan.yaml` govern the next implementation and frozen experiment. They do not retroactively change historical JSON outputs or validate historical numbers.

Before comparing heterogeneous path, KG, table and final-context objects, map them to canonical evidence groups. Equivalent source locations are alternatives, not additional mandatory hits. Evaluate the visible serialized generation context after truncation, rather than assuming the response source list exactly matches the prompt.

Strict claim support counts only fully supported claims. Partial support, missing citations, contradictions, answer completeness and refusal behavior remain separate. A response with no evidence-requiring claims is not assigned perfect support. Preserve and report all scheduled questions, errors, invalid runs and the coverage of paired valid comparisons.

The main implementation comparison expands to B01–B07 so that KG and conditional Table increments are isolated. The earlier five-row ladder can describe only their combined increment. All new metric definitions, annotations and manifests must be frozen before M5 execution and propagated to the evaluation specification before manuscript results are written.
