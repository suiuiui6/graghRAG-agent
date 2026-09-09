# GraphRAG Agent Star-Growth Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make GraphRAG Agent understandable in 30 seconds, runnable offline in 5 minutes, and verifiable through reproducible CI.

**Architecture:** Add an additive offline fixture path beside the existing FastAPI provider pipeline. Keep React/Vite as the UI and keep Goal/Harness as delivery-verification dependencies, not application runtime dependencies.

**Tech Stack:** Python 3.12+, FastAPI, pytest, React 18, TypeScript, Vite, npm lockfile, GitHub Actions, Markdown.

---

## File map

- Create `fixtures/offline/sample.json`: public deterministic graph and answer fixture.
- Create `backend/routes/demo.py`: read-only offline demo endpoint.
- Create `backend/tests/test_demo.py`: endpoint and error-contract tests.
- Modify `backend/server.py`: mount demo routes.
- Create `tools/run_offline_demo.py`: process-level smoke check.
- Modify `frontend/src/lib/api.ts`, `frontend/src/pages/QueryPage.tsx`, and `frontend/src/pages/GraphPage.tsx`: typed demo client and four UI states.
- Create `frontend/src/components/DemoState.tsx`: reusable loading/empty/success/error rendering.
- Create `.github/workflows/ci.yml`: public surface, backend offline tests, smoke, and frontend build.
- Create `docs/getting-started.md`, `docs/demo-walkthrough.md`, `docs/architecture.md`, and `docs/evaluation.md`.
- Modify `README.md`, `CONTRIBUTING.md`, `SECURITY.md`, issue forms, and pull-request template.
- Create `docs/release-checklist.md` and update the execution record.

## Task 1: Offline fixture and endpoint

**Files:** `fixtures/offline/sample.json`, `backend/routes/demo.py`, `backend/tests/test_demo.py`, `backend/server.py`

- [ ] Write `test_demo_fixture_contains_grounded_answer(client)` asserting GET `/api/v1/demo/sample` returns 200, `mode == "offline"`, `document_id == "sample-handbook"`, a non-empty answer, and non-empty sources.
- [ ] Run `python -B -m pytest --rootdir backend -p no:cacheprovider -q backend/tests/test_demo.py::test_demo_fixture_contains_grounded_answer`; expect RED because the route is absent.
- [ ] Add a JSON fixture with one document, two entities, one relation, one question, one answer, and one source span. Implement a loader using `Path(__file__).resolve()` and mount a GET route under `/api/v1`.
- [ ] Rerun the focused test; expect `1 passed`.
- [ ] Commit with `git add -- fixtures/offline/sample.json backend/routes/demo.py backend/tests/test_demo.py backend/server.py` and `git commit -m "feat: add deterministic offline demo fixture"`.

## Task 2: Error contract and smoke check

**Files:** `backend/routes/demo.py`, `backend/tests/test_demo.py`, `tools/run_offline_demo.py`

- [ ] Add `test_demo_missing_fixture_returns_actionable_error(client, monkeypatch)` that replaces `FIXTURE_PATH`, requests the endpoint, and asserts status 503 with `{"detail": "Offline demo fixture is unavailable."}`.
- [ ] Run the focused test and verify RED because missing-fixture handling is undefined.
- [ ] Catch only missing/malformed fixture errors, return the exact 503 detail, and avoid logging file contents. Add `tools/run_offline_demo.py` that imports the backend path explicitly, uses `TestClient`, validates mode/document/source fields, prints `offline demo: PASS`, and exits 1 on failure.
- [ ] Run `python -B tools/run_offline_demo.py` and `python -B -m pytest --rootdir backend -p no:cacheprovider -q backend/tests/test_demo.py`; expect exit 0.
- [ ] Commit with `git add -- backend/routes/demo.py backend/tests/test_demo.py tools/run_offline_demo.py` and `git commit -m "test: add offline demo error and smoke contracts"`.

## Task 3: Frontend demo states

**Files:** `frontend/src/lib/api.ts`, `frontend/src/components/DemoState.tsx`, `frontend/src/pages/QueryPage.tsx`, `frontend/src/pages/GraphPage.tsx`

- [ ] Add a pure state-mapping test for exactly `loading`, `empty`, `success`, and `error`; assert error details and success source references are preserved.
- [ ] Run `Set-Location frontend; npm run build`; expect RED from the new typed state usage before implementation.
- [ ] Define `DemoResponse`, add `getDemoSample()`, and render all four states. Success shows answer, entity/relation counts, and source identifiers; error shows retry guidance. Do not alter provider endpoints.
- [ ] Run `npm run build`; expect exit 0.
- [ ] Commit with `git add -- frontend/src/lib/api.ts frontend/src/components/DemoState.tsx frontend/src/pages/QueryPage.tsx frontend/src/pages/GraphPage.tsx` and `git commit -m "feat: expose offline demo states in frontend"`.

## Task 4: Documentation and media

**Files:** `README.md`, `docs/getting-started.md`, `docs/demo-walkthrough.md`, `docs/architecture.md`, `docs/evaluation.md`, `docs/assets/graphrag-demo.png` or `.gif`

- [ ] Extend the public-surface test to require `Quick Start`, `Offline Demo`, `Screenshots`, `Limitations`, `Contributing`, `Security`, `License`, and the exact live-provider `not-run` boundary; run it and verify RED.
- [ ] Rewrite the first screen with value, Chinese summary, real screenshot/GIF, five-minute commands, result description, limitations, and links to the four docs. Explain Goal/Harness as optional provenance.
- [ ] Run `python -B tools/check_public_surface.py` and `git diff --check`; expect exit 0.
- [ ] Commit with `git add -- README.md docs .github` and `git commit -m "docs: create flagship offline demo entry point"`.

## Task 5: CI and community conversion

**Files:** `.github/workflows/ci.yml`, `CONTRIBUTING.md`, `SECURITY.md`, `.github/ISSUE_TEMPLATE/bug_report.yml`, `.github/ISSUE_TEMPLATE/feature_request.yml`, `.github/pull_request_template.md`

- [ ] Add workflow steps for public surface, `tools/run_offline_demo.py`, backend tests, `npm ci`, and `npm run build` on `main` and pull requests; do not reference Provider credentials.
- [ ] Require issue forms and PRs to record reproduction, expected/actual behavior, environment, evidence level, offline smoke, build, and secret scan status.
- [ ] Run the exact local CI sequence and verify every command exits 0.
- [ ] Commit with `git add -- .github CONTRIBUTING.md SECURITY.md` and `git commit -m "ci: verify offline demo and contributor path"`.

## Task 6: Release candidate and evidence

**Files:** `docs/release-checklist.md`, `docs/superpowers/reviews/2026-09-09-portfolio-open-source-productization-execution.md`, `README.md`

- [ ] List exact public-surface, smoke, backend, frontend, diff, and secret-scan commands. Mark Provider, browser, production, and observed Agent/Skill checks `not-run` unless evidence exists.
- [ ] Run `python -B tools/check_public_surface.py`, `python -B tools/run_offline_demo.py`, `python -B -m pytest --rootdir backend -p no:cacheprovider -q backend/tests`, `Set-Location frontend; npm ci; npm run build`, then return to the root and run the secret scan.
- [ ] Record exit codes, fixture boundaries, remaining React Router advisories, and CI URL. Do not claim hosted production readiness.
- [ ] Commit with `git add -- docs/release-checklist.md docs/superpowers/reviews README.md` and `git commit -m "docs: record GraphRAG release candidate evidence"`.
- [ ] Push only after all P0 checks are green using `git push origin main`; verify the resulting Actions run.

## Rollback

Revert only the affected task commit if the offline path, existing Provider route, frontend build, or public-surface check regresses. Do not force-push, delete legacy branches, or change Goal/Harness contracts.
