# Evaluation and evidence

GraphRAG Agent separates structural checks from observed behavior:

| Level | Command or source | What it proves |
| --- | --- | --- |
| Structure | `python -B tools/check_public_surface.py` | Public files, README contract, and secret scan |
| Offline smoke | `python -B tools/run_offline_demo.py` | A local FastAPI process can serve the fixture contract |
| Backend | `python -B -m pytest --rootdir backend -p no:cacheprovider -q backend/tests` | Route and safe-error behavior |
| Frontend | `npm run build` and `node --test frontend/tests/demo-state.test.mjs` | Type-check/build and four UI state mapping |
| Observed provider | Explicit execution record | Real MinerU/DeepSeek/OSS/Neo4j behavior only |

The checked-in fixture is synthetic and intentionally small. It must not be
reported as production-agent evaluation, model benchmarking, or a hosted
service SLA. Any unexecuted provider, browser, or deployment scenario is marked
`not-run`.

## Reproducibility

Use `npm ci` rather than `npm install` for lockfile-resolved frontend builds.
Run commands from a clean shell and record exit codes, dependency versions,
and whether the result came from a fixture, smoke process, or observed system.
