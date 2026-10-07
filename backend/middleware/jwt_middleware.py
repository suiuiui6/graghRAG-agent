"""
JWT Authentication Middleware — §6.1 of enterprise-evolution-blueprint.

Coexists with existing API Key auth (auth.py). Priority:
1. Cookie/Session (OAuth2)
2. Authorization: Bearer <JWT>
3. Authorization: Bearer <API Key> (delegates to auth.py)
4. Whitelist paths
"""

from __future__ import annotations

import os
import time

import jwt
from fastapi import Request
from fastapi.responses import JSONResponse

JWT_SECRET = os.getenv("JWT_SECRET_KEY", "graphrag-dev-secret-change-in-production")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))

WHITELIST_PATHS = {
    "/", "/docs", "/redoc", "/openapi.json", "/metrics", "/health",
    "/api/v1/health", "/api/v1/auth/login", "/api/v1/auth/callback",
    "/api/v1/bot/feishu", "/api/v1/bot/feishu/alert",
}

# Scope → allowed path prefixes
SCOPE_PATH_MAP = {
    "read:query": ["/api/v1/query", "/api/v1/rag/query", "/api/v1/status"],
    "read:catalog": ["/api/v1/catalog", "/api/v1/lineage", "/api/v1/graph", "/api/v1/documents"],
    "read:export": ["/api/v1/export"],
    "write:ingest": ["/api/v1/ingest"],
    "write:feedback": ["/api/v1/feedback"],
    "write:dict": ["/api/v1/domain-dict"],
    "admin:system": ["/api/v1/system", "/api/v1/users"],
    "admin:keys": ["/api/v1/api-keys"],
}

# Per-key rate limit tracking (in-memory, resets on restart)
_rate_limit_state: dict[str, list[float]] = {}


def _check_scope(scopes: list[str], path: str) -> bool:
    """Check if any of the scopes allow access to this path."""
    for scope in scopes:
        for prefix in SCOPE_PATH_MAP.get(scope, []):
            if path.startswith(prefix):
                return True
    return False


def _check_rate_limit(key_id: str, limit_per_minute: int) -> bool:
    """Simple sliding-window per-key rate limiter."""
    now = time.time()
    if key_id not in _rate_limit_state:
        _rate_limit_state[key_id] = []
    window = [t for t in _rate_limit_state[key_id] if now - t < 60]
    _rate_limit_state[key_id] = window
    if len(window) >= limit_per_minute:
        return False
    window.append(now)
    return True


# Periodic cleanup of rate limit state
_last_cleanup = time.time()


def _cleanup_rate_state():
    global _last_cleanup
    now = time.time()
    if now - _last_cleanup > 300:  # Every 5 minutes
        for key in list(_rate_limit_state.keys()):
            _rate_limit_state[key] = [t for t in _rate_limit_state[key] if now - t < 60]
            if not _rate_limit_state[key]:
                del _rate_limit_state[key]
        _last_cleanup = now


def _is_whitelisted(path: str) -> bool:
    for wp in WHITELIST_PATHS:
        if path == wp:
            return True
        if wp != "/" and path.startswith(wp):
            return True
    return False


def create_jwt_middleware():
    """Create function-based JWT middleware for FastAPI."""

    async def jwt_middleware(request: Request, call_next):
        path = request.url.path

        if _is_whitelisted(path):
            return await call_next(request)

        # Try JWT from Authorization header
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()

            # If looks like API Key (sk- prefix), skip JWT — let auth.py handle it
            if token.startswith("sk-"):
                return await call_next(request)

            # Try JWT decode
            try:
                payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
                # Check expiration
                if payload.get("exp") and payload["exp"] < time.time():
                    return JSONResponse(status_code=401, content={"detail": "Token expired"})
                request.state.user = {
                    "user_id": payload.get("sub", ""),
                    "username": payload.get("preferred_username", ""),
                    "email": payload.get("email", ""),
                    "roles": payload.get("roles", ["viewer"]),
                }
                return await call_next(request)
            except jwt.ExpiredSignatureError:
                return JSONResponse(status_code=401, content={"detail": "Token expired"})
            except jwt.InvalidTokenError:
                pass  # Invalid JWT, fall through to API Key auth

            # Check API keys from api_key_manager
            try:
                from services.api_key_manager import get_api_key_manager
                mgr = get_api_key_manager()
                rec = mgr.validate(token)
                if rec:
                    # Enforce scope
                    scopes = rec.scopes
                    if not _check_scope(scopes, path):
                        return JSONResponse(
                            status_code=403,
                            content={"detail": f"Insufficient scope for {path}. Key scopes: {scopes}"},
                        )
                    # Enforce rate limit
                    if not _check_rate_limit(rec.key_id, rec.rate_limit_per_minute):
                        return JSONResponse(
                            status_code=429,
                            content={"detail": "API Key rate limit exceeded"},
                        )
                    _cleanup_rate_state()

                    request.state.user = {
                        "user_id": f"apikey:{rec.key_id}",
                        "username": rec.name,
                        "email": "",
                        "roles": ["viewer"],
                        "scopes": rec.scopes,
                    }
                    return await call_next(request)
            except Exception:  # noqa: S110, BLE001  # 审计写入失败不阻断业务主流程
                pass

        return await call_next(request)

    return jwt_middleware


def create_access_token(user_id: str, username: str, email: str = "",
                        roles: list[str] | None = None,
                        expires_minutes: int | None = None) -> str:
    """Create a JWT access token."""
    exp_min = expires_minutes or JWT_EXPIRE_MINUTES
    now = int(time.time())
    payload = {
        "sub": user_id,
        "preferred_username": username,
        "email": email,
        "roles": roles or ["viewer"],
        "iat": now,
        "exp": now + exp_min * 60,
        "iss": "graphrag-backend",
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    """Create a long-lived refresh token."""
    now = int(time.time())
    refresh_days = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))
    payload = {
        "sub": user_id,
        "type": "refresh",
        "iat": now,
        "exp": now + refresh_days * 86400,
        "iss": "graphrag-backend",
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict | None:
    """Decode a JWT token, returns payload or None."""
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except Exception:  # noqa: BLE001  # JWT 解码失败统一返回 None 由调用方按未认证处理（含过期/篡改/格式错）
        return None
