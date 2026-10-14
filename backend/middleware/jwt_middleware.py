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
    "read:query": ["/api/v1/query", "/api/v1/rag/query", "/api/v1/rag/summarize", "/api/v1/status"],
    "read:catalog": ["/api/v1/catalog", "/api/v1/lineage", "/api/v1/graph", "/api/v1/documents", "/api/v1/files"],
    "read:export": ["/api/v1/export"],
    "write:ingest": ["/api/v1/ingest"],
    "write:documents": ["/api/v1/documents"],
    "write:feedback": ["/api/v1/feedback"],
    "write:dict": ["/api/v1/domain-dict"],
    "admin:system": ["/api/v1/system", "/api/v1/users"],
    "admin:keys": ["/api/v1/api-keys"],
}

# Per-key rate limit tracking (in-memory, resets on restart)
_rate_limit_state: dict[str, list[float]] = {}


def _check_scope(scopes: list[str], path: str, method: str = "GET") -> bool:
    for scope in scopes:
        if scope.startswith("read:") and method not in {"GET", "HEAD"}:
            # Query is a read operation delivered using POST.
            if not (method == "POST" and scope == "read:query" and path in {"/api/v1/query", "/api/v1/rag/query", "/api/v1/rag/summarize"}):
                continue
        for prefix in SCOPE_PATH_MAP.get(scope, []):
            if path == prefix or path.startswith(prefix + "/"):
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
    from auth import PUBLIC_PATHS
    return path in PUBLIC_PATHS


def _secret() -> str | None:
    from auth import allow_anonymous
    secret = os.getenv("JWT_SECRET_KEY", "")
    if len(secret) >= 32 and secret != "graphrag-dev-secret-change-in-production":
        return secret
    if allow_anonymous():
        return "graphrag-dev-secret-change-in-production"
    return None


def create_jwt_middleware():
    async def jwt_middleware(request: Request, call_next):
        if _is_whitelisted(request.url.path):
            return await call_next(request)
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return await call_next(request)
        token = header[7:].strip()
        from auth import get_admin_key_hash, _hash_key
        import hmac
        admin_hash = get_admin_key_hash()
        if admin_hash and hmac.compare_digest(_hash_key(token), admin_hash):
            request.state.user = {"user_id":"admin-api-key", "username":"管理员", "roles":["admin"], "auth_type":"admin_key"}
            return await call_next(request)
        payload = decode_token(token)
        if payload and payload.get("type") == "access":
            from services.auth_service import get_auth_service
            user = get_auth_service().get_user(payload["sub"])
            if user is None:
                return JSONResponse(status_code=401, content={"detail":"无效身份"})
            request.state.user = {"user_id":user.user_id, "username":user.username, "email":user.email, "roles":user.roles, "auth_type":"jwt"}
            return await call_next(request)
        from services.api_key_manager import get_api_key_manager
        rec = get_api_key_manager().validate(token)
        if not rec or not rec.created_by:
            return JSONResponse(status_code=401, content={"detail":"需要有效认证"})
        from services.auth_service import get_auth_service
        if get_auth_service().get_user(rec.created_by) is None:
            return JSONResponse(status_code=401, content={"detail":"无效身份"})
        if not _check_scope(rec.scopes, request.url.path, request.method):
            return JSONResponse(status_code=403, content={"detail":"API 密钥权限不足"})
        if not _check_rate_limit(rec.key_id, rec.rate_limit_per_minute):
            return JSONResponse(status_code=429, content={"detail":"API 密钥请求过于频繁"})
        _cleanup_rate_state()
        request.state.user = {"user_id":rec.created_by, "username":rec.name, "roles":["viewer"], "scopes":rec.scopes, "auth_type":"api_key", "key_id":rec.key_id}
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
        "type": "access",
        "preferred_username": username,
        "email": email,
        "roles": roles or ["viewer"],
        "iat": now,
        "exp": now + exp_min * 60,
        "iss": "graphrag-backend",
    }
    secret = _secret()
    if not secret:
        raise ValueError("必须配置安全 JWT 密钥，或显式开启非生产开发模式")
    return jwt.encode(payload, secret, algorithm=JWT_ALGORITHM)


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
    secret = _secret()
    if not secret:
        raise ValueError("必须配置安全 JWT 密钥，或显式开启非生产开发模式")
    return jwt.encode(payload, secret, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict | None:
    secret = _secret()
    if not secret:
        return None
    try:
        payload = jwt.decode(token, secret, algorithms=[JWT_ALGORITHM], issuer="graphrag-backend", options={"require":["sub", "exp", "iss", "type"]})
        if not isinstance(payload.get("sub"), str) or not payload["sub"].strip():
            return None
        if type(payload.get("exp")) not in (int, float):
            return None
        return payload
    except jwt.InvalidTokenError:
        return None
