# DeepSeek Scope Pilot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Execute the approved bounded 27-request independent DeepSeek experiment and preserve auditable outputs without altering production.

**Architecture:** A standalone backend research adapter reads the existing offline pilot context builder, validates a new independent source/code manifest, serializes only approved question/context fragments and sends each once to the fixed official host. Old gold/freeze/results remain unchanged; oracle baselines are not production B0.

**Tech Stack:** Existing backend Python3.12, httpx, python-dotenv and PyYAML; unittest transport fixtures; no new dependencies.

## Task 1: Independent adapter (chatbot-coder)

Files: create `backend/research/deepseek_scope_pilot.py`, `backend/research/test_deepseek_scope_pilot.py`; no production modifications.

- [x] Write and run failing unittest checks before implementation. Include a missing-module assertion, then behavior tests for fixed request parameters and no hidden credential leakage:

```python
payload = build_payload({"query": "列全", "doc": "D1", "contexts": []}, "uniform instruction")
assert payload["model"] == "deepseek-v4-pro"
assert payload["thinking"] == {"type": "disabled"}
assert payload["temperature"] == 0
assert payload["max_tokens"] == 2048
assert "Authorization" not in json.dumps(payload)
```

- [x] Implement preparation from `pilot.contexts`, with source/schema validation and a new manifest rather than invoking old `pilot.run` with a drifted production freeze. Use the same system instruction as existing B2/B3 input files. Strip no answer content. Privacy preflight excludes frontmatter `参赛编号` from D1 contexts, preserving surviving source offsets; log exclusion as a preprocessing deviation for all baselines. Do not send gold items/labels/answers; do not execute source text instructions.
- [x] Implement default dry-run, explicit `--execute`, max27 planned calls, each once, no automatic retry/resume, fixed `https://api.deepseek.com/chat/completions`, `trust_env=False`, redirects disabled. Read only `backend/.env` existing key names; never print or save key/headers/raw exception/error bodies. Validate configured official base. No fallback model.
- [x] Save planned status records before requests in a unique project run directory; fail if target exists. Use exclusive-create artifacts. On HTTP error, network failure or invalid response save sanitized failure, stop and mark remaining NOT_ATTEMPTED. Output truncation and provider non-stop reason are not success. Preserve successful response JSON, actual payload, timestamps/latency, returned model/fingerprint/usage and request hash, but never auth headers. Stop on secret reflection rather than persisting it.
- [x] Verify sources and source-character context spans before requests; guard against source drift and manifest changes. Use fixed 8192 source UTF-8 bytes (not model-token claim), output2048, thinking disabled. Do not silently select a new freeze or weaken guard.
- [x] Test request limit, dry-run network exclusion, preserved statuses, empty response, wrong model, length finish, HTTP error secret body, timeout no-retry, output path containment/no-overwrite, and manifest/source drift. Save software test output separately from experimental model records.

Run: `backend/.venv/Scripts/python.exe -B -m pytest backend/research/test_deepseek_scope_pilot.py -q -p no:cacheprovider`. Expected: tests pass without real credentials/network. No git commit: user has unrelated dirty changes and has not requested a commit.

## Task 2: Protocol/source audit and manifest (main)

Files: create `docs/superpowers/plans/scope-pilot/api-freeze-v1.json`, `api-protocol.md`; keep existing freeze/results immutable.

- [x] Compare all7 old production code/lock hashes and preserve old/current/changed fields. Current changes belong to other work, not this adapter. Hash gold, pilot, source docs and existing system-input instructions. Record CLI parameters and official documentation provenance.
- [x] Read official API docs. Verified on2026-10-07: model v4pro allowed, `thinking` is top-level and defaults enabled, temperature has no effect while thinking is on; set thinking disabled and temperature0. max_tokens2048/nonstreaming; response finish_reason/usage/model/fingerprint retained. No extra-body wrapper for direct JSON requests.
- [x] Prepare27 units from immutable sources and inspect exclusion: D1 frontmatter participant ID must not enter provider payload. B1 is offline word-overlap evidence control, B2/B3 oracle scope; shared prompt. Generate no fabricated answers.

## Task 3: Spec compliance then code-quality review

- [x] Fresh reviewer checks Task1 against the approved spec and concrete protocol; no credential inspection/network. Fix gaps before quality review.
- [x] Fresh chatbot-reviewer checks security, file isolation, no retries/hidden calls, real provenance and result validity. Implementer fixes and reruns tests; re-review required for important issues.

## Task 4: Bounded actual run and evidence handoff (main)

- [x] Run dry preparation, verify27 units/source-byte budgets/privacy/model/manifest. Existing project credentials reused privately; no .env changes.
- [x] Execute once after reviews. If sandbox blocks network, request scoped escalation for this same authorized command; do not change target or fabricate successes. Poll at<=30s intervals and report progress at<=60s.
- [x] Observe27 planned statuses, output files and actual usage totals. No more than27 attempts including failures; no automatic repeat/GPT/LLM grader. Error stops are genuine incomplete outcomes, not methodology failures.
- [x] Read real answers against entire source scope; report only provisional single-agent adjudication until independent review. Preserve failures, partial answers and unsure claims. No p-values or generalization from3 source families. If all successes, summarize outcome and limited implication; productionB0 and automatic routing still pending.
- [x] Update API authorization/state and control console with actual call counts, run paths, outcome and remaining scientific gates. Run fresh software/provenance checks before claiming completion.
