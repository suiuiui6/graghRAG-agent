# Portfolio open-source productization execution record

## Scope

This record covers the GraphRAG Agent flagship work from the approved
`2026-09-09-graphrag-star-growth` plan. The objective is a clear 30-second explanation,
a reproducible five-minute offline path, and evidence that contributors can rerun locally.
Goal and Harness Engineering remain optional delivery/provenance dependencies; they are not
runtime dependencies of GraphRAG Agent.

## Delivered work

- Added a deterministic offline document/entity/relation fixture and `GET /api/v1/demo/sample`.
- Added explicit 503 error handling for missing or malformed fixtures and a process smoke command.
- Added typed frontend demo payload validation and loading/empty/success/error states.
- Added the public README entry point, walkthrough, architecture/evaluation docs, and a real local
  screenshot captured from the offline UI.
- Added CI, contributor/security guidance, issue forms, and pull-request evidence requirements.
- Added this release checklist with command-level evidence and rollback preparation.

## Verification snapshot (2026-09-10)

| Evidence | Result |
|---|---|
| `python -B tools/check_public_surface.py` | exit 0, PASS |
| `python -B tools/run_offline_demo.py` | exit 0, PASS |
| backend pytest (`backend/tests`) | 7 passed, exit 0; warnings are dependency deprecations |
| `git diff --check` | exit 0 |
| tracked-file secret scan | zero matches, exit 0 |
| `npm audit --package-lock-only --json` | zero current advisories, exit 0 |
| frontend `npm ci` | Windows EPERM while unlinking `node_modules/.package-lock.json`; exit -4048 |
| frontend `npm run build` | Windows EPERM writing `tsconfig.tsbuildinfo`; exit 1 |
| frontend `node --test tests/demo-state.test.mjs` | Windows EPERM spawning child process; exit 1 |

The frontend failures are environment/file-lock failures in the Windows workspace, not
relaxed assertions or changed test expectations. A prior clean frontend build passed; rerun
the exact CI sequence on Ubuntu and retain its Actions URL before release.

## Evidence classification

The passing checks are contract and offline-fixture evidence. Provider integrations, browser E2E,
production deployment, and observed Agent+Skill event replay are explicitly `not-run`. The checked-in
PNG is a genuine local UI capture but is not browser-E2E or provider-quality evidence.

## Risks and follow-up

- React Router remains on the 6.x dependency line. A prior review noted moderate advisory noise;
  the current package-lock-only audit is clean, but dependency status should be reconfirmed in CI.
- Windows EPERM prevents a complete local frontend matrix in this shell; do not represent it as green.
- No production hosting, credentials, or external services were used.

## Rollback

Rollback is limited to reverting the affected task commit(s), beginning with this documentation
commit if the evidence record itself is incorrect. Preserve the fixture, prior main history, and
legacy branches for investigation. Do not force-push or alter Goal/Harness contracts.
