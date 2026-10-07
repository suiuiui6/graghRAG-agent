"""
API Key authentication — §3.3 of enterprise-evolution-blueprint.

Bearer Token verification via FastAPI HTTP middleware.
Whitelisted paths: /health, /metrics, /docs, /redoc, /, /openapi.json
"""

from __future__ import annotations

import hashlib
import os

from fastapi import Request
from fastapi.responses import JSONResponse

WHITELIST_PREFIXES = (
    "/health",
    "/metrics",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/api/v1/health",
    "/api/v1/files/",
)


def _hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def get_admin_key_hash() -> str:
    key = os.getenv("ADMIN_API_KEY", "")
    return _hash_key(key) if key else ""


def _is_whitelisted(path: str) -> bool:
    for prefix in WHITELIST_PREFIXES:
        if path == prefix or path.startswith(prefix):
            return True
    # Root path
    if path == "/":
        return True
    return False


def create_auth_middleware():
    """Return an ASGI middleware function for API Key verification."""

    async def auth_middleware(request: Request, call_next):
        path = request.url.path

        # Whitelist
        if _is_whitelisted(path):
            return await call_next(request)

        # Read key from env (supports runtime config change)
        key_hash = get_admin_key_hash()

        # No key configured → allow all (development mode)
        if not key_hash:
            return await call_next(request)

        # Verify Bearer token
        auth_header = request.headers.get("Authorization", "")
        if not auth_header:
            return JSONResponse(
                status_code=401,
                content={"detail": "Missing Authorization header"},
            )

        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=403,
                content={"detail": "Invalid Authorization format. Use: Bearer <key>"},
            )

        token = auth_header[7:].strip()
        if not token:
            return JSONResponse(
                status_code=401,
                content={"detail": "Empty API Key"},
            )

        if _hash_key(token) != key_hash:
            return JSONResponse(
                status_code=403,
                content={"detail": "Invalid API Key"},
            )

        return await call_next(request)

    return auth_middleware
