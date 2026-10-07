"""
Auth Service — §6.1 of enterprise-evolution-blueprint.

OAuth2/OIDC integration + local JWT management. Handles login, callback,
token refresh, and user profile lookup.
"""

from __future__ import annotations

import json
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path

from models import User, TokenPair, UserRole
from logging_config import get_logger

logger = get_logger(__name__)

USERS_DIR = Path("output/users")
OAUTH_STATES_DIR = Path("output/oauth_states")


class AuthService:
    """OAuth2/OIDC authentication and user management."""

    def __init__(self):
        USERS_DIR.mkdir(parents=True, exist_ok=True)
        OAUTH_STATES_DIR.mkdir(parents=True, exist_ok=True)

    @property
    def provider(self) -> str:
        return os.getenv("AUTH_PROVIDER", "local")

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    # ── OAuth2 Login ──────────────────────────────────────────────────

    def get_login_url(self) -> str:
        """Generate OAuth2 authorization URL."""
        if self.provider == "local":
            return "/login"  # local login page
        client_id = os.getenv("OIDC_CLIENT_ID", "")
        redirect_uri = os.getenv("OIDC_REDIRECT_URI", "http://localhost:8000/api/v1/auth/callback")
        issuer = os.getenv("OIDC_ISSUER", "")

        state = secrets.token_hex(16)
        (OAUTH_STATES_DIR / f"{state}.json").write_text(
            json.dumps({"created_at": self._now()}), encoding="utf-8")

        scopes = os.getenv("OIDC_SCOPES", "openid profile email")
        return (
            f"{issuer.rstrip('/')}/protocol/openid-connect/auth"
            f"?client_id={client_id}"
            f"&redirect_uri={redirect_uri}"
            f"&response_type=code"
            f"&scope={scopes}"
            f"&state={state}"
        )

    def handle_callback(self, code: str, state: str) -> TokenPair | None:
        """Exchange authorization code for tokens."""
        # Validate state
        state_file = OAUTH_STATES_DIR / f"{state}.json"
        if not state_file.exists():
            logger.warning("oauth_invalid_state")
            return None
        state_file.unlink()

        # Exchange code for token
        try:
            import requests
            issuer = os.getenv("OIDC_ISSUER", "")
            client_id = os.getenv("OIDC_CLIENT_ID", "")
            client_secret = os.getenv("OIDC_CLIENT_SECRET", "")
            redirect_uri = os.getenv("OIDC_REDIRECT_URI", "")

            resp = requests.post(
                f"{issuer.rstrip('/')}/protocol/openid-connect/token",
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "redirect_uri": redirect_uri,
                },
                timeout=30,
            )
            resp.raise_for_status()
            token_data = resp.json()

            # Get userinfo
            userinfo_resp = requests.get(
                f"{issuer.rstrip('/')}/protocol/openid-connect/userinfo",
                headers={"Authorization": f"Bearer {token_data['access_token']}"},
                timeout=30,
            )
            userinfo_resp.raise_for_status()
            userinfo = userinfo_resp.json()

            # Create or update local user
            user = self._upsert_oauth_user(userinfo)

            # Issue our own JWT pair
            from middleware.jwt_middleware import create_access_token, create_refresh_token
            access = create_access_token(
                user.user_id, user.username, user.email, user.roles)
            refresh = create_refresh_token(user.user_id)

            return TokenPair(access_token=access, refresh_token=refresh,
                           expires_in=3600, token_type="Bearer")

        except Exception as e:  # noqa: BLE001  # SSO 回调失败仅记录错误并返回 None，由路由转换为认证失败响应
            logger.error("oauth_callback_failed", error=str(e))
            return None

    # ── Local Login ────────────────────────────────────────────────────

    def login_local(self, username: str, password: str) -> TokenPair | None:
        """Simple local login (development only)."""
        if self.provider != "local":
            return None
        # Accept any user for local dev; create on first login
        user = self._get_or_create_local_user(username)
        from middleware.jwt_middleware import create_access_token, create_refresh_token
        access = create_access_token(user.user_id, user.username, user.email, user.roles)
        refresh = create_refresh_token(user.user_id)

        user.last_login = self._now()
        self._save_user(user)

        logger.info("user_login_local", user_id=user.user_id)
        return TokenPair(access_token=access, refresh_token=refresh,
                       expires_in=3600, token_type="Bearer")

    # ── Token Refresh ─────────────────────────────────────────────────

    def refresh_tokens(self, refresh_token: str) -> TokenPair | None:
        """Validate refresh token and issue new token pair."""
        from middleware.jwt_middleware import decode_token, create_access_token, create_refresh_token
        payload = decode_token(refresh_token)
        if not payload or payload.get("type") != "refresh":
            return None

        user_id = payload.get("sub", "")
        user = self.get_user(user_id)
        if not user:
            return None

        access = create_access_token(user.user_id, user.username, user.email, user.roles)
        new_refresh = create_refresh_token(user.user_id)
        return TokenPair(access_token=access, refresh_token=new_refresh,
                       expires_in=3600, token_type="Bearer")

    # ── User CRUD ──────────────────────────────────────────────────────

    def get_user(self, user_id: str) -> User | None:
        p = USERS_DIR / f"{user_id}.json"
        if not p.exists():
            return None
        try:
            return User(**json.loads(p.read_text(encoding="utf-8")))
        except Exception:  # noqa: BLE001  # 旧版本产物或脏数据反序列化失败时跳过该条，不影响其余记录
            return None

    def list_users(self) -> list[User]:
        results = []
        for f in sorted(USERS_DIR.glob("*.json")):
            try:
                results.append(User(**json.loads(f.read_text(encoding="utf-8"))))
            except Exception:  # noqa: S110, BLE001  # 旧版本产物或脏数据反序列化失败时跳过该条，不影响其余记录
                pass
        return results

    def update_roles(self, user_id: str, roles: list[str]) -> User | None:
        user = self.get_user(user_id)
        if not user:
            return None
        # Validate roles
        valid_roles = {r.value for r in UserRole}
        user.roles = [r for r in roles if r in valid_roles]
        self._save_user(user)

        try:
            from services.audit_logger import get_audit_logger
            get_audit_logger().log("user.role_changed", "admin",
                                   target_user_id=user_id, new_roles=roles)
        except Exception:  # noqa: S110, BLE001  # 审计写入失败不阻断业务主流程
            pass
        return user

    def disable_user(self, user_id: str) -> bool:
        p = USERS_DIR / f"{user_id}.json"
        if p.exists():
            p.unlink()
            return True
        return False

    # ── Internal ───────────────────────────────────────────────────────

    def _upsert_oauth_user(self, userinfo: dict) -> User:
        user_id = userinfo.get("sub", secrets.token_hex(8))
        existing = self.get_user(user_id)
        user = User(
            user_id=user_id,
            username=userinfo.get("preferred_username", user_id),
            email=userinfo.get("email", ""),
            display_name=userinfo.get("name", userinfo.get("preferred_username", "")),
            roles=existing.roles if existing else ["viewer"],
            department=userinfo.get("department"),
            created_at=existing.created_at if existing else self._now(),
            last_login=self._now(),
            auth_provider=self.provider,
        )
        self._save_user(user)
        return user

    def _get_or_create_local_user(self, username: str) -> User:
        # Check if user exists with this username
        for f in USERS_DIR.glob("*.json"):
            try:
                u = User(**json.loads(f.read_text(encoding="utf-8")))
                if u.username == username:
                    return u
            except Exception:  # noqa: S110, BLE001  # 旧版本产物或脏数据反序列化失败时跳过该条，不影响其余记录
                pass
        # Create new local user
        user = User(
            user_id=f"local-{secrets.token_hex(4)}",
            username=username,
            email=f"{username}@local",
            display_name=username,
            roles=["admin" if username == "admin" else "viewer"],
            created_at=self._now(),
            last_login=self._now(),
            auth_provider="local",
        )
        self._save_user(user)
        return user

    def _save_user(self, user: User) -> None:
        (USERS_DIR / f"{user.user_id}.json").write_text(
            user.model_dump_json(indent=2), encoding="utf-8")


# ── singleton ─────────────────────────────────────────────────────────────

_service: AuthService | None = None


def get_auth_service() -> AuthService:
    global _service
    if _service is None:
        _service = AuthService()
    return _service
