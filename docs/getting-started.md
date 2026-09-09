# Getting started

This guide runs the public, provider-free path. It does not require MinerU,
DeepSeek, OSS, or Neo4j.

## Prerequisites

- Python 3.12 or newer
- Node.js 18 or newer
- PowerShell (or equivalent shell commands)

## Install and run

```powershell
git clone https://github.com/suiuiui6/graghRAG-agent.git
Set-Location graghRAG-agent/backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn server:app --reload
```

In a second shell:

```powershell
Set-Location graghRAG-agent/frontend
npm ci
npm run dev
```

Copy `.env.example` to `.env` only when configuring a local integration. The
offline demo endpoint does not read credentials.

## Verify the install

From the repository root:

```powershell
python -B tools/check_public_surface.py
python -B tools/run_offline_demo.py
python -B -m pytest --rootdir backend -p no:cacheprovider -q backend/tests
Set-Location frontend
npm run build
```

## Troubleshooting

- If the frontend cannot reach the API, confirm the backend is listening on
  port 8000 and that `frontend/.env` points to it.
- If the demo returns 503, restore `fixtures/offline/sample.json`; the endpoint
  intentionally reports a safe, actionable error without exposing file data.
- Provider and production checks are outside this quick start.
