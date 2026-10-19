# Research report behavior tests — 2026-10-17

Added only `backend/tests/test_research_report_behaviors.py`; production, coverage scope and thresholds were unchanged. Inputs are synthetic JSON/HTML generated inside pytest temporary directories. No frozen research materials, private sources, historical Gold, real `.env` or provider are read. Module-scoped autouse fixture blocks socket connection and restores it after each test.

## Actual verification

Interpreter: `.tmp/backend-quality-venv-20261012/Scripts/python.exe`.

Environment: `PYTHONPATH=D:/graghRAG-agent/langextract;D:/graghRAG-agent/backend`, `PYTHON_DOTENV_DISABLED=1`, `PYTHONDONTWRITEBYTECODE=1`.

Command: `python -X utf8 -m pytest backend/tests/test_research_report_behaviors.py -q --tb=short -p no:cacheprovider --basetemp .tmp/publish-retry-report-tests-20261017/run4-temp`.

Run 4: **exit 0, 36 passed in 5.00s**. Actual output, receipt and post-run source hashes are stored in `.tmp/publish-retry-report-tests-20261017/run4.log`, `receipt.json`, `source-manifest.json`. Hashes were captured after the successful run, not before it; this is an explicit limitation, not proof of whole-suite acceptance. Root will bind its final full-scope run to the final source snapshot.

Earlier attempts remain preserved: missing pytest basetemp parent (32 setup errors), sandbox ACL failure, and run 3 (31 passed, 1 failed). Run 3 showed the real source-chain check rejecting mutation within an actually selected slice. The drift-only fixture was corrected to append outside the selected slice, preserving exact source/wire agreement while verifying `source_inputs_unchanged=False`. No production fix was needed or made.

## Behaviors covered

- Common resource audit: full synthetic 54-unit P0/A/S schedules; exact UTF-8 request/response hashes; map-to-reduce chain; usage/cost reconciliation; unknown costs and failed units with no ledger; registration, wire, map, reduce, token totals, identity, active status and total-attempt tampering fail before report publication.
- Content summary: 54 anonymous units, six questions and three repeats per arm; necessary content versus source-adjudicated extra facts; original blind reasons remain immutable; unknown atom/support judgments; incorrect or unknown source metadata; noncompleted units remain unassessable; unsupported completeness; 18 question/arm groups; malformed/missing adjudications rejected. Scientific stage remains M2_OPEN and no inference or human-Gold verification is claimed.
- Development summary: verified snapshot/input manifest hashes and request/response wire; map/reduce/P0 4000-character chain; missing optional outputs; known versus unknown cost; source/code drift flags; malformed hashes or generation-chain outputs rejected. The main statistic and report algorithms execute directly without mocks.
- Development preparation: real HTML structure parsing, source-map verification, explicit section scope resolution, exact source chunks and one unresolved question. Canonical source tampering is rejected.
- Authorized supervisor: eight-step success, nonzero child exit, child timeout, and exhausted local window. Only the process boundary is intercepted. `dotenv_values` is wrapped to assert its sole read is the explicit synthetic repository's temporary `.env`; a real provider is never invoked. Child environment strips unrelated keys, offline flags are verified, arbitrary logs and credential-echoing JSON are omitted from persisted/emitted status.

These are meaningful component behavior tests, **not the project's full dual-90 acceptance or permission to commit/push**. No production integration, migration, deployment, paid model call, commit or push occurred in this subtask.
