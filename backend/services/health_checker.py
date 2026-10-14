"""
Health Checker — §6.7 of enterprise-evolution-blueprint.

Periodic dependency health probes (apscheduler, every 5 min).
DeepSeek, MinerU, ChromaDB, OAuth2 Provider, Feishu Bot.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

from logging_config import get_logger

logger = get_logger(__name__)

CHROMADB_PATH = Path("output/vectordb")


class HealthChecker:
    """Periodic external dependency health probes."""

    def __init__(self):
        self._status: dict[str, dict] = {}

    def probe_all(self) -> dict[str, dict]:
        results = {}
        results["deepseek_api"] = self._probe_deepseek()
        results["mineru_api"] = self._probe_mineru()
        results["chromadb"] = self._probe_chromadb()
        results["oauth2_provider"] = self._probe_oauth2()
        results["feishu_bot"] = self._probe_feishu()
        self._status = results

        degraded = sum(1 for v in results.values() if v["status"] == "degraded")
        down = sum(1 for v in results.values() if v["status"] == "down")
        logger.info("health_probe_completed", healthy=len(results) - degraded - down,
                    degraded=degraded, down=down)
        return results

    def get_status(self) -> dict[str, dict]:
        return self._status

    # ── probes ────────────────────────────────────────────────────────

    def _probe_deepseek(self) -> dict:
        t0 = time.time()
        try:
            import requests
            api_key = os.getenv("LANGEXTRACT_API_KEY", "")
            base_url = os.getenv("LANGEXTRACT_BASE_URL", "https://api.deepseek.com")
            if not api_key:
                return {"status": "degraded", "message": "API key not configured"}
            # Simple models list as health check
            resp = requests.get(
                f"{base_url.rstrip('/')}/v1/models",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=10,
            )
            latency = int((time.time() - t0) * 1000)
            if resp.status_code == 200:
                return {"status": "ok", "latency_ms": latency}
            return {"status": "degraded", "latency_ms": latency,
                    "message": f"HTTP {resp.status_code}"}
        except Exception as e:  # noqa: BLE001  # 探活失败即视为该依赖 down，不抛给调用方
            return {"status": "down", "latency_ms": int((time.time() - t0) * 1000),
                    "message": str(e)[:200]}

    def _probe_mineru(self) -> dict:
        t0 = time.time()
        try:
            import requests
            mineru_url = os.getenv("MINERU_API_URL", "")
            mineru_key = os.getenv("MINERU_API_KEY", "")
            if not mineru_url:
                return {"status": "degraded", "message": "MinerU URL not configured"}
            resp = requests.get(
                f"{mineru_url.rstrip('/')}/health",
                headers={"Authorization": f"Bearer {mineru_key}"} if mineru_key else {},
                timeout=10,
            )
            latency = int((time.time() - t0) * 1000)
            if resp.status_code < 500:
                return {"status": "ok", "latency_ms": latency}
            return {"status": "degraded", "latency_ms": latency,
                    "message": f"HTTP {resp.status_code}"}
        except Exception as e:  # noqa: BLE001  # 探活失败即视为该依赖 down，不抛给调用方
            return {"status": "down", "latency_ms": int((time.time() - t0) * 1000),
                    "message": str(e)[:200]}

    def _probe_chromadb(self) -> dict:
        t0 = time.time()
        try:
            db = CHROMADB_PATH / "chroma.sqlite3"
            if not db.exists():
                return {"status": "degraded", "message": "ChromaDB not found"}
            import sqlite3
            conn = sqlite3.connect(str(db))
            cur = conn.execute("SELECT COUNT(*) FROM embedding_metadata")
            count = cur.fetchone()[0]
            conn.close()
            return {"status": "ok", "latency_ms": int((time.time() - t0) * 1000),
                    "documents": count}
        except Exception as e:  # noqa: BLE001  # 探活失败即视为该依赖 down，不抛给调用方
            return {"status": "down", "latency_ms": int((time.time() - t0) * 1000),
                    "message": str(e)[:200]}

    def _probe_oauth2(self) -> dict:
        t0 = time.time()
        provider = os.getenv("AUTH_PROVIDER", "local")
        if provider == "local":
            return {"status": "ok", "message": "local auth (no OAuth2)"}
        try:
            import requests
            issuer = os.getenv("OIDC_ISSUER", "")
            if not issuer:
                return {"status": "degraded", "message": "OIDC_ISSUER not configured"}
            resp = requests.get(f"{issuer.rstrip('/')}/.well-known/openid-configuration",
                              timeout=10)
            latency = int((time.time() - t0) * 1000)
            if resp.status_code == 200:
                return {"status": "ok", "latency_ms": latency, "connected": True}
            return {"status": "degraded", "latency_ms": latency, "connected": False}
        except Exception as e:  # noqa: BLE001  # 探活失败即视为该依赖 down，不抛给调用方
            return {"status": "down", "latency_ms": int((time.time() - t0) * 1000),
                    "message": str(e)[:200]}

    def _probe_feishu(self) -> dict:
        t0 = time.time()
        app_id = os.getenv("FEISHU_APP_ID", "")
        if not app_id:
            return {"status": "ok", "message": "Feishu bot not configured"}
        try:
            import requests
            app_secret = os.getenv("FEISHU_APP_SECRET", "")
            resp = requests.post(
                "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
                json={"app_id": app_id, "app_secret": app_secret},
                timeout=10,
            )
            latency = int((time.time() - t0) * 1000)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("tenant_access_token"):
                    return {"status": "ok", "latency_ms": latency, "webhook_registered": True}
            return {"status": "degraded", "latency_ms": latency,
                    "message": f"token fetch failed: {resp.status_code}"}
        except Exception as e:  # noqa: BLE001  # 探活失败即视为该依赖 down，不抛给调用方
            return {"status": "down", "latency_ms": int((time.time() - t0) * 1000),
                    "message": str(e)[:200]}


# ── singleton ─────────────────────────────────────────────────────────────

_checker: HealthChecker | None = None


def get_health_checker() -> HealthChecker:
    global _checker
    if _checker is None:
        _checker = HealthChecker()
    return _checker
