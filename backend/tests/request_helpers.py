"""Trusted test requests and genuine JWT clients; no production auth bypass."""
from fastapi import Request
from fastapi.testclient import TestClient


def admin_request() -> Request:
    """Supply the principal normally produced by middleware in direct route unit tests."""
    request = Request({"type": "http", "method": "POST", "path": "/", "headers": []})
    request.state.user = {"user_id": "compat-admin", "roles": ["admin"], "auth_type": "jwt"}
    return request


def authenticated_client(app, monkeypatch, base_dir, **kwargs) -> TestClient:
    """Exercise the real server middleware with a signed, isolated test token."""
    monkeypatch.setenv("JWT_SECRET_KEY", "compat-test-only-signing-secret-at-least-32-characters")
    import services.auth_service as auth_service
    from models import User
    monkeypatch.setattr(auth_service, "USERS_DIR", base_dir / "users")
    monkeypatch.setattr(auth_service, "OAUTH_STATES_DIR", base_dir / "oauth_states")
    service = auth_service.AuthService()
    monkeypatch.setattr(auth_service, "_service", service)
    for user_id in ("compat-admin", "admin"):
        service._save_user(User(user_id=user_id, username=user_id, email=f"{user_id}@test.local",
                               display_name=user_id, roles=["admin"], created_at=service._now()))
    from middleware.jwt_middleware import create_access_token
    token = create_access_token("compat-admin", "compat-admin", roles=["admin"])
    return TestClient(app, headers={"Authorization": f"Bearer {token}"}, **kwargs)
