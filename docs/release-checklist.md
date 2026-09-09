# GraphRAG Agent release-candidate checklist

Date: 2026-09-10  
Candidate: `main` at `31bd23b2edc017fc93a06bd4f810241993d96c3f` (plus this evidence commit)

This checklist records a local release-candidate review. It is not a hosted-production
approval and does not claim that provider integrations or browser behavior were observed.

## P0 local verification

Commands were run from the repository root unless noted otherwise.

| Check | Command | Result |
|---|---|---|
| Public surface | `python -B tools/check_public_surface.py` | PASS, exit 0 |
| Offline process smoke | `python -B tools/run_offline_demo.py` | PASS, exit 0; fixture-only, no external provider |
| Backend tests | `python -B -m pytest --rootdir backend -p no:cacheprovider -q backend/tests` | PASS, 7 passed, 33 warnings, exit 0 |
| Frontend state tests | `Set-Location frontend; node --test tests/demo-state.test.mjs` | NOT-RUN/FAILED in this Windows shell: Node child-process spawn returned EPERM, exit 1 |
| Frontend dependency install | `Set-Location frontend; npm ci` | NOT-RUN/FAILED in this Windows workspace: unlink of `node_modules/.package-lock.json` returned EPERM, exit -4048 |
| Frontend build | `Set-Location frontend; npm run build` | NOT-RUN/FAILED in this Windows workspace: TypeScript could not write tracked `tsconfig.tsbuildinfo` (EPERM), exit 1 |
| Diff hygiene | `git diff --check` | PASS, exit 0 |
| Secret scan | `git grep -n -I -E '(sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|BEGIN (RSA|OPENSSH|EC) PRIVATE KEY)' -- ':!*.example' ':!docs/assets/*'` | PASS, no matches, exit 0 |

The frontend build had passed independently before this Windows file-lock failure; the
failure above is retained rather than hidden. `frontend/tsconfig.tsbuildinfo` was restored
and is not part of this evidence change.

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
