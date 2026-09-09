# GraphRAG Agent release-candidate checklist

Date: 2026-09-10  
Candidate: `main` at `d9e0cf07d29ce047327816d4334297e8db6a2b9e`

This checklist records a local release-candidate review. It is not a hosted-production
approval and does not claim that provider integrations or browser behavior were observed.

## P0 local verification

Commands were run from the repository root unless noted otherwise.

| Check | Command | Result |
|---|---|---|
| Public surface | `python -B tools/check_public_surface.py` | PASS, exit 0 |
| Offline process smoke | `python -B tools/run_offline_demo.py` | PASS, exit 0; fixture-only, no external provider |
| Backend tests | `python -B -m pytest --rootdir backend -p no:cacheprovider -q backend/tests` | PASS, 7 passed, 33 warnings, exit 0 |
| Frontend state tests | `Set-Location <isolated-temp>/frontend; node --test tests/demo-state.test.mjs` | PASS, 4 passed, exit 0; clean-shell fixture copy |
| Frontend dependency install | `Set-Location <isolated-temp>/frontend; npm ci` | PASS, 241 packages installed, exit 0; clean-shell fixture copy |
| Frontend build | `Set-Location <isolated-temp>/frontend; npm run build` | PASS, 302 modules transformed, exit 0; clean-shell fixture copy |
| Diff hygiene | `git diff --check` | PASS, exit 0 |
| Secret scan | `git grep -n -I -E '(sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|BEGIN (RSA|OPENSSH|EC) PRIVATE KEY)' -- ':!*.example' ':!docs/assets/*'` | PASS, no matches, exit 0 |

The repository workspace also reproduced Windows file-lock failures for these frontend
commands. Those environment failures remain in the execution record; the isolated copy
demonstrates the commands themselves succeed. `frontend/tsconfig.tsbuildinfo` was restored.

## Evidence boundaries

- **Contract evidence:** public-surface checks, typed frontend state tests, and backend test assertions.
- **Offline fixture evidence:** `fixtures/offline/sample.json`, `/api/v1/demo/sample`, and the process smoke script.
- **Observed Agent+Skill event replay:** `not-run`.
- **Live Provider integrations (MinerU, DeepSeek, OSS, Neo4j):** `not-run`; no credentials were used.
- **Browser E2E:** `not-run`; the checked-in screenshot is a local UI capture, not a browser test claim.
- **Hosted production/deployment:** `not-run`; no production endpoint or service was contacted.
- **Synthetic records:** are labeled as fixtures and must not be read as provider-quality measurements.

## Dependency and CI notes

- CI workflow: [`.github/workflows/ci.yml`](../.github/workflows/ci.yml), intended GitHub URL:
  <https://github.com/suiuiui6/graghRAG-agent/actions/workflows/ci.yml>.
- The workflow runs on `main` pushes and pull requests and does not require Provider credentials.
- `npm audit --package-lock-only --json` returned zero current advisories locally (exit 0).
  React Router remains on the 6.x line (`react-router-dom` resolves to 6.30.6); earlier
  dependency review recorded moderate advisory noise. Revisit with a dedicated Node 20 or
  dependency-upgrade change and verify on Ubuntu CI before calling the issue closed.
- No hosted-production readiness, uptime, security review, or provider SLA is implied.

## Rollback preparation

If this candidate regresses the offline route, an existing Provider route, frontend build,
or public-surface contract, revert only the release-candidate documentation commit and then
the smallest affected task commit. Keep the deterministic fixture and prior history available
for diagnosis. Do not force-push, delete legacy branches, rotate unrelated credentials, or
change Goal/Harness contracts as part of rollback.

## Explicit not-run gates before a real release

1. Run the full CI workflow on GitHub and retain the run URL and commit SHA.
2. Run browser E2E against a clean local stack, recording browser and OS versions.
3. Execute provider integrations only with separately authorized test credentials and isolated data.
4. Perform production deployment and rollback rehearsal under an operations/security review.
5. If Agent+Skill behavior is evaluated, retain observed event traces separately from fixture evidence.
