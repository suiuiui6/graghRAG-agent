"""Authentication gate; identities must be established by trusted middleware."""
from __future__ import annotations

import hashlib
import hmac
import os
from fastapi import Request
from fastapi.responses import JSONResponse

PUBLIC_PATHS = {"/", "/health", "/metrics", "/docs", "/redoc", "/openapi.json", "/api/v1/health", "/api/v1/auth/login", "/api/v1/auth/callback", "/api/v1/auth/refresh", "/static/chat-widget.js"}


def is_production() -> bool:
    return any(os.getenv(name, "").lower() in {"production", "prod"} for name in ("APP_ENV", "ENVIRONMENT", "ENV", "NODE_ENV"))


def allow_anonymous() -> bool:
    return not is_production() and os.getenv("AUTH_ALLOW_ANONYMOUS", "").lower() == "true"


def _hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def get_admin_key_hash() -> str:
    key = os.getenv("ADMIN_API_KEY", "")
    return _hash_key(key) if key else ""


def _is_whitelisted(path: str) -> bool:
    return path in PUBLIC_PATHS


def create_auth_middleware():
    async def auth_middleware(request: Request, call_next):
        if _is_whitelisted(request.url.path):
            return await call_next(request)
        principal = getattr(request.state, "user", None)
        if principal and principal.get("user_id"):
            return await call_next(request)
        header = request.headers.get("Authorization", "")
        configured = get_admin_key_hash()
        if configured and header.startswith("Bearer ") and hmac.compare_digest(_hash_key(header[7:].strip()), configured):
            request.state.user = {"user_id":"admin-api-key", "username":"管理员", "roles":["admin"], "auth_type":"admin_key"}
            return await call_next(request)
        if not header and allow_anonymous():
            request.state.user = {"user_id":"anonymous", "username":"匿名开发用户", "roles":["viewer"], "auth_type":"anonymous"}
            return await call_next(request)
        return JSONResponse(status_code=401, content={"detail":"需要有效认证"})
    return auth_middleware
