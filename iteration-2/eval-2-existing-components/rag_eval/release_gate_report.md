# Enterprise Release Gate Report

- Generated at (UTC): `2026-07-04T12:54:16.509008+00:00`
- Final verdict: `NO-GO`

## Enterprise Release Gate Summary

- Retrieval measurement surface: `PASS`
- Multi-turn rewrite stability: `PASS`
- Tail latency target: `PASS`

## Broader Backend Validation

- Result: `FAIL`
- Evidence: `.\.venv\Scripts\python -m pytest tests -q` -> `1 failed, 191 passed, 3 warnings, 65 errors in 131.64s (0:02:11)`.

## Conversation Rewrite Validation

- Result: `PASS`
- Evidence: `.\.venv\Scripts\python -m pytest tests/test_conversation_rewrite.py -q -s --capture=no` -> `5 passed, 1 warning in 24.75s`.

## Conversation Rewrite Supplemental Metrics

- Ground truth: `D:\graghRAG-agent\iteration-2\eval-2-existing-components\rag_eval\ground_truth_multiturn_smoke.json`
- Raw runs: `D:\graghRAG-agent\iteration-2\eval-2-existing-components\rag_eval\raw_runs_multiturn_smoke.jsonl`
- followup_questions: `3`
- rewrite_success_rate_macro: `1.0000`
- session_id_match_rate_macro: `1.0000`
- keyword_coverage_macro: `1.0000`
- corpus_drift_cases: `2`
- invalid_eval_cases: `0`
- valid_questions_for_scoring: `1`
- Final enterprise verdict: `NO-GO`

## Checks

| Check | Actual | Target | Result |
| --- | ---: | ---: | --- |
| `a1_final_context_surface_ready` | 50 | `> 0` | PASS |
| `a1_final_context_recall_min` | 0.5765 | `>= 0.35` | PASS |
| `a2_keyword_coverage_min` | 0.6893 | `>= 0.75` | FAIL |
| `a2_cited_in_retrieved_min` | 1.0000 | `>= 0.98` | PASS |
| `a5_p95_latency_ms_max` | 3272 | `<= 6000` | PASS |
| `a5_p99_latency_ms_max` | 4440 | `<= 15000` | PASS |
| `backend_validation_passed` | 1 | `== 0` | FAIL |
| `conversation_rewrite_validation_passed` | 0 | `== 0` | PASS |

## Provenance

- Raw runs: `D:\graghRAG-agent\iteration-2\eval-2-existing-components\rag_eval\raw_runs.jsonl`
- Raw runs sha256: `e403cb0fc111338376059b0de466928d825689c2e22457638df072da6bd03be0`
- Inference log: `D:\graghRAG-agent\iteration-2\eval-2-existing-components\rag_eval\run.log`

## Decision Notes

- `a1_final_context_surface_ready` blocks release when final-context retrieval evidence is absent; this avoids treating stale eval runs as production-ready proof.
- `a1_final_context_recall_min` is the enterprise-critical retrieval threshold because it measures what actually reached generation.
- `a2` checks protect answer grounding while retrieval tuning evolves.
- `a5` checks bound both typical tail latency (`p95`) and extreme outliers (`p99`).

## Known Non-Gated Notes

- Conversation rewrite supplemental eval reports possible corpus drift / invalid eval cases; review per-question alias evidence before treating multiturn smoke misses as retrieval regressions.

## Waivers Required

- `a2_keyword_coverage_min` failed: actual=0.6893, target=`>= 0.75`
- `backend_validation_passed` failed: actual=1, target=`== 0`