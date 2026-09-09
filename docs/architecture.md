# Architecture

## Runtime flow

```text
React/Vite UI
    │  HTTP JSON
    ▼
FastAPI server ── optional provider adapters ── MinerU / DeepSeek / OSS / Neo4j
    │
    └── /api/v1/demo/sample → checked-in JSON fixture (offline, read-only)
```

The offline route is additive. It does not replace upload, extraction, graph,
or query routes and does not call provider adapters.

## Evidence boundaries

- `fixtures/offline/sample.json` is deterministic synthetic input.
- `tools/run_offline_demo.py` is a process smoke check for route wiring.
- Backend tests validate response and error contracts.
- Frontend tests validate state mapping and evidence preservation.
- Provider quality, browser behavior, and production operations require separate
  observed runs and are not implied by this fixture.

Goal and Harness Engineering artifacts document delivery provenance and remain
optional to application runtime.
