# Paper Evidence Freeze Note

## 1. Purpose and Submission Context

This note defines the evidence-governance boundary for the current GraphRAG paper package. It is intended to support both the main SCI Q4 route and the parallel Peking University Core / stronger general journal route described in [2026-06-15-graphrag-paper-plan.md](/D:/graghRAG-agent/docs/superpowers/plans/2026-06-15-graphrag-paper-plan.md).

Its purpose is not to repeat every experimental result. Its purpose is to lock which evidence assets may enter the manuscript, under what conditions they may be cited, and which current files remain historical snapshots rather than final paper evidence.

## 2. Scope of This Note

This note covers only the `rag_eval` evidence layer and its manuscript-use boundary.

It does not replace:

- the paper plan
- the future baseline table
- the future ablation package
- the manuscript text itself

It applies to the current evaluation directory:

- [rag_eval](/D:/graghRAG-agent/iteration-2/eval-2-existing-components/rag_eval)

## 3. Frozen Evidence Policy

Only results generated from one frozen paper commit, one aligned evaluation specification, one recorded command chain, and one immutable artifact bundle may be used as final manuscript evidence.

For the current repository state, this note records the pre-freeze situation and establishes the operating rule for the next unified rerun:

- paper headline claims must cite only `current frozen evidence`
- manuscript tables and figures must cite only artifacts listed as `accepted_for_manuscript`
- historical outputs may be used for risk discovery, motivation, and evolution notes, but not as the manuscript headline result surface

## 4. Historical vs Current Evidence Classification

The repository evidence is divided into two classes: `historical evidence` and `current frozen evidence`.

`historical evidence` refers to earlier exploratory runs, intermediate reports, and snapshot-style outputs that document what the system observed at a particular time. These assets may explain system evolution and known risks, but they do not define the final quantitative claims of the paper.

`current frozen evidence` refers to the evidence bundle regenerated under one frozen commit, one aligned specification, one command chain, and one locked metric contract. Unless explicitly labeled otherwise, manuscript-level quantitative statements, tables, figures, and abstract numbers must come only from `current frozen evidence`.

Operational rule:

- [REPORT_FINAL.md](/D:/graghRAG-agent/iteration-2/eval-2-existing-components/rag_eval/REPORT_FINAL.md) and [release_gate_report.md](/D:/graghRAG-agent/iteration-2/eval-2-existing-components/rag_eval/release_gate_report.md) may be cited today only as repository-status references
- they must not jointly define the final paper headline surface before the next unified frozen rerun

## 5. Frozen Artifact Manifest

### 5.1 Manifest fields

Each accepted paper artifact should be tracked with the following fields:

| Field | Meaning |
|---|---|
| `artifact_id` | Human-readable unique identifier |
| `artifact_role` | `ground_truth`, `raw_runs`, `metric_output`, `summary_report`, `release_gate`, `log`, or related role |
| `file_name` | File name |
| `relative_path` | Repository-relative path |
| `source_class` | `historical` or `current_frozen` |
| `frozen_commit` | Git commit tied to the artifact |
| `generated_at_utc` | UTC generation time |
| `generator_command` | Exact command used to generate the file |
| `upstream_inputs` | Files consumed to produce the artifact |
| `metric_surface` | `final-context`, `path_hits`, `pre-rerank`, `answer-support`, `performance`, or related label |
| `question_set` | Question-set identity |
| `sha256` | File checksum |
| `status` | `accepted_for_manuscript`, `historical_only`, `diagnostic_only`, or `pending_rerun` |
| `manuscript_use` | `headline_table`, `diagnostic_table`, `appendix_only`, `repro_note`, or `not_citable_yet` |
| `notes` | Short interpretation boundary |

Optional but recommended fields:

- `model_config`
- `retrieval_budget_config`
- `generation_config`
- `spec_version`

### 5.2 Current repository snapshot manifest

The table below records the current pre-freeze state at commit `727c00967c42fa856c3483835cd4202a3e40cfe2`.

| artifact_id | artifact_role | file_name | relative_path | source_class | frozen_commit | metric_surface | sha256 | status | manuscript_use | notes |
|---|---|---|---|---|---|---|---|---|---|---|
| `pre_freeze_gt` | `ground_truth` | `ground_truth.json` | `iteration-2/eval-2-existing-components/rag_eval/ground_truth.json` | `historical` | `727c00967c42fa856c3483835cd4202a3e40cfe2` | `question-set-definition` | `95F2FD33AF49772C6E5369D8E7AD06B6...` | `pending_rerun` | `not_citable_yet` | Current GT file; should be reconfirmed or rehashed in the frozen bundle. |
| `pre_freeze_raw_runs` | `raw_runs` | `raw_runs.jsonl` | `iteration-2/eval-2-existing-components/rag_eval/raw_runs.jsonl` | `historical` | `727c00967c42fa856c3483835cd4202a3e40cfe2` | `path_hits/pre_rerank/final-context/runtime` | `15DE8EB0A69BB1203EFDE6F29747F2014B473BB25EB7C678DF842F331921750E` | `historical_only` | `appendix_only` | Matches current release-gate provenance; must be regenerated for final paper use. |
| `pre_freeze_a1` | `metric_output` | `metrics_a1_retrieval.json` | `iteration-2/eval-2-existing-components/rag_eval/metrics_a1_retrieval.json` | `historical` | `727c00967c42fa856c3483835cd4202a3e40cfe2` | `path_hits/pre_rerank/final-context` | `809D16866B0D5037DA2FE31C...` | `diagnostic_only` | `diagnostic_table` | Current A1 file is valuable for surface taxonomy and release-gate linkage. |
| `pre_freeze_a2` | `metric_output` | `metrics_a2_faithfulness.json` | `iteration-2/eval-2-existing-components/rag_eval/metrics_a2_faithfulness.json` | `historical` | `727c00967c42fa856c3483835cd4202a3e40cfe2` | `answer-support` | `88E5890F37E5E5BDA8598...` | `diagnostic_only` | `appendix_only` | Useful for grounding support, but should be frozen with the next unified rerun. |
| `pre_freeze_a3` | `metric_output` | `metrics_a3_robustness.json` | `iteration-2/eval-2-existing-components/rag_eval/metrics_a3_robustness.json` | `historical` | `727c00967c42fa856c3483835cd4202a3e40cfe2` | `robustness` | `FB28F896EB77CC6EFC1A710...` | `historical_only` | `appendix_only` | Current file is not yet a stable paper headline source because its refusal counts differ from the earlier report surface. |
| `pre_freeze_a4` | `metric_output` | `metrics_a4_multihop.json` | `iteration-2/eval-2-existing-components/rag_eval/metrics_a4_multihop.json` | `historical` | `727c00967c42fa856c3483835cd4202a3e40cfe2` | `multihop/efficiency` | `CABAC73837AF8F2DAC4D600E3...` | `historical_only` | `appendix_only` | Treat as analysis support until the frozen rerun confirms wording and scope. |
| `pre_freeze_a5` | `metric_output` | `metrics_a5_performance.json` | `iteration-2/eval-2-existing-components/rag_eval/metrics_a5_performance.json` | `historical` | `727c00967c42fa856c3483835cd4202a3e40cfe2` | `performance` | `84AFB48887ACF13D7486DC...` | `diagnostic_only` | `appendix_only` | Current file reflects the later fast bounded pipeline surface and should not be mixed directly with older tail-cost claims. |
| `pre_freeze_report_final` | `summary_report` | `REPORT_FINAL.md` | `iteration-2/eval-2-existing-components/rag_eval/REPORT_FINAL.md` | `historical` | `727c00967c42fa856c3483835cd4202a3e40cfe2` | `mixed historical snapshot` | `142B3E080A8546078CE8C8F75EAAA7D836...` | `historical_only` | `not_citable_yet` | Strong narrative evidence, but not yet aligned with the later gated surface. |
| `pre_freeze_release_gate_md` | `release_gate` | `release_gate_report.md` | `iteration-2/eval-2-existing-components/rag_eval/release_gate_report.md` | `historical` | `727c00967c42fa856c3483835cd4202a3e40cfe2` | `final-context/performance gate` | `D0901955EC98C2674BC01FA5619...` | `diagnostic_only` | `repro_note` | Useful because it enforces the current `final-context` gate, but it is still not the whole paper result surface. |
| `pre_freeze_release_gate_json` | `release_gate` | `release_gate_report.json` | `iteration-2/eval-2-existing-components/rag_eval/release_gate_report.json` | `historical` | `727c00967c42fa856c3483835cd4202a3e40cfe2` | `final-context/performance gate` | `B1C77F2ABF3FC2A9E3D0C66A0...` | `diagnostic_only` | `repro_note` | Contains explicit thresholds and provenance; should be regenerated in the frozen bundle. |
| `pre_freeze_run_log` | `log` | `run.log` | `iteration-2/eval-2-existing-components/rag_eval/run.log` | `historical` | `727c00967c42fa856c3483835cd4202a3e40cfe2` | `execution-log` | `B8B19200674E9C9451E4DF69A86FD05B22C7446FBE...` | `historical_only` | `appendix_only` | Execution trace for current runs; use as provenance support, not as primary scientific evidence. |

Checksum formatting note:

- the full `raw_runs.jsonl` sha256 is already confirmed by [release_gate_report.json](/D:/graghRAG-agent/iteration-2/eval-2-existing-components/rag_eval/release_gate_report.json)
- abbreviated hashes above should be expanded to full-length values in the frozen bundle manifest

## 6. Metric Surface Contract

This note follows the current plan-level metric taxonomy:

- headline surface: `final-context`
- diagnostic retrieval surfaces: `path_hits` and `pre-rerank`
- answer-side support surfaces: grounding, citation verification, `cited_in_retrieved_rate`, `node_id_validity`, and related trust metrics

No manuscript retrieval headline claim may be supported primarily by `path_hits` or `pre-rerank`.

## 7. Allowed Manuscript Uses

The following uses are allowed after the next unified freeze:

- one headline retrieval table based on the frozen `final-context` surface
- one answer-support table based on frozen grounding / citation evidence
- one reproducibility or provenance paragraph citing the frozen manifest
- one appendix note explaining how historical outputs differed from the final frozen bundle

The following uses are conditionally allowed now, only as repository-status context:

- cite [REPORT_FINAL.md](/D:/graghRAG-agent/iteration-2/eval-2-existing-components/rag_eval/REPORT_FINAL.md) as a historical snapshot
- cite [release_gate_report.md](/D:/graghRAG-agent/iteration-2/eval-2-existing-components/rag_eval/release_gate_report.md) as the current gated engineering surface

## 8. Prohibited Uses and Interpretation Boundaries

The following are prohibited in the paper package before the unified frozen rerun:

- mixing [REPORT_FINAL.md](/D:/graghRAG-agent/iteration-2/eval-2-existing-components/rag_eval/REPORT_FINAL.md) and [release_gate_report.md](/D:/graghRAG-agent/iteration-2/eval-2-existing-components/rag_eval/release_gate_report.md) into one manuscript headline result
- quoting older tail-cost or older refusal numbers as if they belonged to the current fast bounded surface
- using release-gate engineering thresholds as the sole academic headline result
- citing mutable working files without manifest identity, checksum, and command provenance

Interpretation boundary:

- current repository evidence is sufficient to design the manuscript and define the governance layer
- current repository evidence is not yet sufficient to support final abstract-level numbers without the next unified freeze

## 9. Current Repository Evidence Snapshot

At the current repository state:

- the evaluation directory already contains GT, raw runs, metric JSON files, reports, and logs
- the current release gate uses `final-context` as the critical retrieval surface
- the older comprehensive report still carries strong scientific narrative value
- the specification file remains outdated relative to the live surface-based implementation

This means the repository is already strong enough to support a submission plan, but not yet clean enough to support a final governed manuscript bundle.

## 10. Placeholders Pending the Next Frozen Rerun

The following fields should remain explicit placeholders until the next unified rerun:

- `freeze_bundle_id = <TO_BE_FILLED>`
- `freeze_generated_at_utc = <TO_BE_FILLED>`
- `headline_metric_surface = <TO_BE_LOCKED>`
- `diagnostic_metric_surfaces = <TO_BE_LOCKED>`
- `accepted_manuscript_artifacts = <TO_BE_LOCKED>`
- `exact_eval_command = <TO_BE_RECORDED>`
- `model_configuration = <TO_BE_RECORDED>`
- `retrieval_budget_configuration = <TO_BE_RECORDED>`
- `generation_configuration = <TO_BE_RECORDED>`
- `question_set_version = <TO_BE_LOCKED>`
- `spec_alignment_status = <TO_BE_CONFIRMED_AFTER_RERUN>`
- `historical_snapshot_reference_note = <TO_BE_FILLED_IF_OLD_REPORTS_ARE_CITED>`

Recommended rerun-time checksum fields to refresh in full length:

- `ground_truth_sha256`
- `raw_runs_sha256`
- `metrics_a1_retrieval_sha256`
- `metrics_a2_faithfulness_sha256`
- `metrics_a3_robustness_sha256`
- `metrics_a4_multihop_sha256`
- `metrics_a5_performance_sha256`
- `release_gate_report_md_sha256`
- `release_gate_report_json_sha256`
- `run_log_sha256`

## 11. Update Rule

This note must be updated only by appending a new freeze record or replacing placeholder fields after a documented unified rerun.

It must not be updated by silently overwriting:

- commit identity
- artifact checksums
- surface definitions
- manuscript-use classification

If a later rerun changes any headline number, the note must record whether the change is caused by:

- specification alignment
- command-chain change
- model or budget change
- question-set change
- bug fix or implementation change
