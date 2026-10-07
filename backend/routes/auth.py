"""
Authentication endpoints — §6.1 of enterprise-evolution-blueprint.

OAuth2 login, callback, JWT refresh, user profile, logout.
Local login for development.
"""

import os
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from services.auth_service import AuthService, get_auth_service
from models import LoginRequest

router = APIRouter()

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")


def _get_service() -> AuthService:
    return get_auth_service()


class RefreshRequest(BaseModel):
    refresh_token: str


@router.get("/auth/login")
async def login(provider: str = "local"):
    """OAuth2 login redirect or local login info."""
    svc = _get_service()
    if svc.provider == "local":
        return {"provider": "local", "message": "Use POST /api/v1/auth/login with username"}
    url = svc.get_login_url()
    return {"provider": svc.provider, "login_url": url}


@router.post("/auth/login")
async def login_local(body: LoginRequest):
    """Local login (development only)."""
    svc = _get_service()
    if body.provider == "local" and body.username:
        tokens = svc.login_local(body.username, body.password or "")
        if tokens:
            return tokens.model_dump()
    raise HTTPException(status_code=401, detail="Login failed")


@router.get("/auth/callback")
async def auth_callback(code: str, state: str):
    """OAuth2 callback — exchange code for JWT pair, redirect to frontend."""
    svc = _get_service()
    tokens = svc.handle_callback(code, state)
    if not tokens:
        raise HTTPException(status_code=401, detail="OAuth callback failed")
    # Redirect to frontend with tokens in query params
    params = urlencode({
        "access_token": tokens.access_token,
        "refresh_token": tokens.refresh_token,
        "expires_in": tokens.expires_in,
        "token_type": tokens.token_type,
    })
    return RedirectResponse(url=f"{FRONTEND_URL}/auth/callback?{params}", status_code=302)


@router.post("/auth/refresh")
async def refresh_token(body: RefreshRequest):
    """Refresh JWT access token."""
    svc = _get_service()
    tokens = svc.refresh_tokens(body.refresh_token)
    if not tokens:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    return tokens.model_dump()


@router.get("/auth/me")
async def get_current_user(request: Request):
    """Get current user from JWT token."""
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


@router.post("/auth/logout")
async def logout(request: Request):
    """Logout (client should discard tokens)."""
    user = getattr(request.state, "user", None)
    if user:
        try:
            from services.audit_logger import get_audit_logger
            get_audit_logger().auth_logout(user.get("user_id", ""))
        except Exception:  # noqa: S110, BLE001  # 审计写入失败不阻断业务主流程
            pass
    return {"status": "logged_out"}


# ── User Management (admin only) ────────────────────────────────────────

@router.get("/users")
async def list_users(request: Request):
    """List all users (admin only)."""
    user = getattr(request.state, "user", None)
    if not user or "admin" not in user.get("roles", []):
        raise HTTPException(status_code=403, detail="Admin only")
    svc = _get_service()
    return {"users": [u.model_dump() for u in svc.list_users()]}


@router.put("/users/{user_id}/roles")
async def update_user_roles(user_id: str, body: dict, request: Request):
    """Update user roles (admin only)."""
    user = getattr(request.state, "user", None)
    if not user or "admin" not in user.get("roles", []):
        raise HTTPException(status_code=403, detail="Admin only")
    svc = _get_service()
    updated = svc.update_roles(user_id, body.get("roles", []))
    if not updated:
        raise HTTPException(status_code=404, detail="User not found")
    return {"status": "updated", "user": updated.model_dump()}


@router.delete("/users/{user_id}")
async def disable_user(user_id: str, request: Request):
    """Disable user (admin only)."""
    user = getattr(request.state, "user", None)
    if not user or "admin" not in user.get("roles", []):
        raise HTTPException(status_code=403, detail="Admin only")
    svc = _get_service()
    ok = svc.disable_user(user_id)
    if not ok:
        raise HTTPException(status_code=404, detail="User not found")
    return {"status": "disabled", "user_id": user_id}
