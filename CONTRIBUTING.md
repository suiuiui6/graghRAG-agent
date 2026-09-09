# Contributing

Thanks for helping improve GraphRAG Agent. Start with a focused issue and keep changes reviewable.

## Local checks

From the repository root, run:

```text
python -B tools/check_public_surface.py
python -B tools/run_offline_demo.py
python -B -m pytest --rootdir backend -p no:cacheprovider -q backend/tests
cd frontend && npm ci && npm run build
```

Report exact commands and exit codes in pull requests. Use the evidence levels in the PR template and mark unrun checks `not-run`.

Never commit provider credentials, uploaded documents, generated logs, or build caches. Live providers and browser checks are opt-in and not required for offline CI. Goal/Harness are optional provenance dependencies, not runtime dependencies.
