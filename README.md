# GraphRAG Agent

[![Public surface](https://github.com/suiuiui6/graghRAG-agent/actions/workflows/public-surface.yml/badge.svg)](https://github.com/suiuiui6/graghRAG-agent/actions/workflows/public-surface.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A multimodal GraphRAG application for document extraction, knowledge graphs, and
grounded question answering.

> 中文：GraphRAG Agent 面向 PDF、DOCX、PPTX 等文档解析、知识图谱构建和可追溯问答。
> 它是可本地运行的应用参考，不是托管平台，也不在仓库中提供云服务凭据。

## What it does

The application connects a React frontend to a FastAPI backend and optional
MinerU, DeepSeek, Neo4j, and OSS services. The intended flow is:

`upload → parse → extract entities → build graph → retrieve evidence → answer`

The repository also contains architecture and Harness Engineering records. Those
records explain how the project was developed; Harness is not a runtime
dependency for users who only want to inspect or run the application.

## Quick Start

### Prerequisites

- Python 3.12+
- Node.js 18+
- Optional: Neo4j and provider credentials for live document processing

### Backend (PowerShell)

```powershell
git clone https://github.com/suiuiui6/graghRAG-agent.git
Set-Location graghRAG-agent/backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn server:app --reload
```

### Frontend

```powershell
Set-Location ..\frontend
npm install
Copy-Item .env.example .env
npm run dev
```

POSIX shells can use `cp` and `source .venv/bin/activate` in the equivalent
commands. Put credentials only in ignored local `.env` files.

## Project map

| Path | Purpose |
| --- | --- |
| `backend/` | FastAPI service, workers, upload and query routes |
| `frontend/` | React/Vite application |
| `integration/` | Topology, architecture, and API blueprints |
| `langextract/` | Extraction experiments and bridge specifications |
| `iteration-2/` | Evaluation fixtures and reports |
| `docs/governance/` | Permissions and maintenance guidance |

## Validation and evidence

```powershell
python -B tools/check_public_surface.py
Set-Location frontend
npm run build
```

The public-surface workflow runs without provider credentials. Live MinerU,
DeepSeek, OSS, Neo4j, browser, and production deployment behavior is `not-run`
unless an execution record says otherwise. Synthetic evaluation fixtures are not
observed production-agent behavior.

## Status and limitations

This is an actively evolving application reference. It is not a hosted service,
does not promise production support, and should not be connected to production
credentials without an independent security and operations review.

## Contributing, security, and license

Read [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md), and
[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md). The project is released under the
[MIT License](LICENSE).
