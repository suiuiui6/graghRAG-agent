# Offline demo walkthrough

The demo is a deterministic vertical slice for reviewers and contributors.
It proves wiring and source display, not provider model quality.

## 1. Start the services

Run the backend and frontend commands in [Getting started](getting-started.md).
No API key or database is needed.

## 2. Call the endpoint

```powershell
Invoke-RestMethod http://localhost:8000/api/v1/demo/sample | ConvertTo-Json -Depth 6
```

The response has `mode: "offline"`, document `sample-handbook`, a grounded
answer, two entities, one relation, and a source span pointing to page 1.

## 3. Inspect the UI

Open the Vite URL and visit the query or graph view. The Offline demo card
shows loading, empty, success, and error states. In the success state it keeps
the answer, entity/relation counts, and source document identifier visible.

## 4. Reproduce from a clean shell

```powershell
python -B tools/run_offline_demo.py
```

The command uses an explicit local backend import path and exits non-zero if
the fixture, response mode, document, or source list is missing.
