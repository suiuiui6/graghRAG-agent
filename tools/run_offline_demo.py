"""Process-level smoke check for the provider-free offline demo."""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
BACKEND_ROOT_STR = str(BACKEND_ROOT)
sys.path[:] = [entry for entry in sys.path if entry != BACKEND_ROOT_STR]
sys.path.insert(0, BACKEND_ROOT_STR)

from fastapi.testclient import TestClient
from server import app


def main() -> int:
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/demo/sample")
        if response.status_code != 200:
            raise RuntimeError(f"unexpected status: {response.status_code}")
        payload = response.json()
        if payload.get("mode") != "offline":
            raise RuntimeError("demo response is not offline mode")
        if payload.get("document_id") != "sample-handbook":
            raise RuntimeError("demo response has the wrong document")
        if not payload.get("sources"):
            raise RuntimeError("demo response has no source references")
    except Exception as exc:
        print(f"offline demo: FAIL ({exc})", file=sys.stderr)
        return 1

    print("offline demo: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
