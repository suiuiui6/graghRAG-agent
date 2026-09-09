## Summary

Describe the user-visible change and link the issue.

## Reproduction and behavior

- Reproduction or usage steps:
- Expected behavior:
- Actual behavior before this PR:
- Environment (OS, Python/Node, commit):

## Evidence and verification

Evidence level: `contract` / `offline-fixture` / `observed-event` / `provider-integration` / `browser-e2e` / `production`

- [ ] `python -B tools/check_public_surface.py`
- [ ] `python -B tools/run_offline_demo.py` (or explain `not-run`)
- [ ] Backend tests/build run (command and result below)
- [ ] Frontend `npm ci` and `npm run build` run (command and result below)
- [ ] Secret scan run; no credentials, private documents, logs, or caches included
- [ ] Live providers and production claims are explicitly marked `not-run` unless observed

Commands and results:

## Risk and rollback

Describe affected components, compatibility concerns, and the smallest rollback.
