import time

import jwt
import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from auth import create_auth_middleware
from middleware import jwt_middleware as jm
from middleware.tenant_middleware import create_tenant_middleware
from models import ApiKeyCreate, OrganizationCreate, ProjectCreate, MemberInvite, User
from services import api_key_manager as keys, tenant_service as tenants

TEST_SECRET = "p0-auth-test-only-secret-0123456789abcdef"


@pytest.fixture
def setup(monkeypatch, sandbox_tmp_path):
    monkeypatch.chdir(sandbox_tmp_path)
    monkeypatch.delenv("ADMIN_API_KEY", raising=False)
    monkeypatch.delenv("AUTH_ALLOW_ANONYMOUS", raising=False)
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("JWT_SECRET_KEY", TEST_SECRET)
    from services import auth_service
    monkeypatch.setattr(auth_service, "USERS_DIR", sandbox_tmp_path / "users")
    monkeypatch.setattr(auth_service, "OAUTH_STATES_DIR", sandbox_tmp_path / "oauth")
    service = auth_service.AuthService()
    monkeypatch.setattr(auth_service, "_service", service)
    for user_id in ("alice", "bob", "stranger"):
        service._save_user(User(user_id=user_id, username=user_id, roles=["viewer"],
                               email="", display_name=user_id, created_at=service._now()))
    for name, sub in [("ORGS_DIR", "orgs"), ("PROJECTS_DIR", "projects"), ("MEMBERS_DIR", "members")]:
        monkeypatch.setattr(tenants, name, sandbox_tmp_path / sub)
    svc = tenants.TenantService(sandbox_tmp_path)
    monkeypatch.setattr(tenants, "_service", svc)
    mgr = keys.ApiKeyManager(sandbox_tmp_path / "keys")
    monkeypatch.setattr(keys, "_manager", mgr)
    app = FastAPI()
    @app.api_route("/api/v1/documents", methods=["GET", "DELETE"])
    async def endpoint(request: Request):
        return getattr(request.state, "user", {})
    app.middleware("http")(create_tenant_middleware())
    app.middleware("http")(create_auth_middleware())
    app.middleware("http")(jm.create_jwt_middleware())
    return TestClient(app), svc, mgr


def test_missing_identity_denied(setup):
    client, _, _ = setup
    assert client.get("/api/v1/documents").status_code == 401


def test_managed_key_validated_method_scoped_and_bound_to_owner(setup):
    client, _, mgr = setup
    key = mgr.create(ApiKeyCreate(name="读", scopes=["read:catalog"]), created_by="alice")
    headers = {"Authorization": f"Bearer {key.full_key}"}
    response = client.get("/api/v1/documents", headers=headers)
    assert response.status_code == 200
    assert response.json()["user_id"] == "alice"
    assert response.json()["roles"] == ["viewer"]
    assert client.delete("/api/v1/documents", headers=headers).status_code == 403
    mgr.revoke(key.key_id)
    assert client.get("/api/v1/documents", headers=headers).status_code == 401


@pytest.mark.parametrize("payload", [{"sub":"alice"}, {"exp":time.time()+600}, {"sub":"alice","exp":time.time()+600,"type":"refresh"}])
def test_incomplete_or_refresh_jwt_rejected(setup, payload):
    client, _, _ = setup
    token = jwt.encode(payload, TEST_SECRET, algorithm=jm.JWT_ALGORITHM)
    assert client.get("/api/v1/documents", headers={"Authorization":f"Bearer {token}"}).status_code == 401


def test_verified_jwt_coexists_with_admin_key(setup, monkeypatch):
    client, _, _ = setup
    monkeypatch.setenv("ADMIN_API_KEY", "test-admin-credential")
    token = jm.create_access_token("alice", "Alice")
    assert client.get("/api/v1/documents", headers={"Authorization":f"Bearer {token}"}).status_code == 200


def test_forged_project_and_fake_default_membership_denied(setup):
    client, svc, _ = setup
    assert svc.get_member("default", "stranger") is None
    token = jm.create_access_token("stranger", "陌生用户")
    response = client.get("/api/v1/documents", headers={"Authorization":f"Bearer {token}", "X-Project-Id":"forged"})
    assert response.status_code == 404


def test_resource_owner_and_membership_authorization(setup):
    _, svc, _ = setup
    from services.resource_access import authorize_resource, ingest_identity
    from fastapi import HTTPException
    org = svc.create_org(OrganizationCreate(name="甲", slug="a"))
    project = svc.create_project(org.org_id, ProjectCreate(name="项目"), "alice")
    request = Request({"type":"http", "headers":[]})
    request.state.user = {"user_id":"alice", "roles":["viewer"]}
    document = {"document_id":"doc-a", "owner_id":"alice", "org_id":org.org_id, "project_id":project.project_id}
    with pytest.raises(HTTPException) as exc:
        authorize_resource(request, document)
    assert exc.value.status_code == 404
    svc.add_member(org.org_id, MemberInvite(user_id="alice", role="org_viewer"))
    assert authorize_resource(request, document, write=True) == document
    request.state.user = {"user_id":"bob", "roles":["viewer"]}
    svc.add_member(org.org_id, MemberInvite(user_id="bob", role="org_viewer"))
    assert authorize_resource(request, document) == document
    with pytest.raises(HTTPException):
        authorize_resource(request, document, write=True)
    assert ingest_identity(request) == {"owner_id":"bob", "org_id":None, "project_id":None}


def test_production_disallows_dev_login(setup, monkeypatch):
    from services.auth_service import AuthService
    monkeypatch.setenv("APP_ENV", "production")
    assert AuthService().login_local("admin", "anything") is None


def test_admin_key_principal_and_unknown_tokens(setup, monkeypatch):
    client, _, _ = setup
    monkeypatch.setenv("ADMIN_API_KEY", "test-admin-credential")
    assert client.get("/api/v1/documents", headers={"Authorization":"Bearer test-admin-credential"}).json()["roles"] == ["admin"]
    assert client.get("/api/v1/documents", headers={"Authorization":"Bearer sk-forged"}).status_code == 401


def test_anonymous_opt_in_never_applies_in_production(setup, monkeypatch):
    client, _, _ = setup
    monkeypatch.setenv("AUTH_ALLOW_ANONYMOUS", "true")
    assert client.get("/api/v1/documents").json()["auth_type"] == "anonymous"
    monkeypatch.setenv("APP_ENV", "production")
    assert client.get("/api/v1/documents").status_code == 401
    token = jwt.encode({"sub":"admin", "roles":["admin"], "exp":time.time()+600}, jm.JWT_SECRET, algorithm=jm.JWT_ALGORITHM)
    assert client.get("/api/v1/documents", headers={"Authorization":f"Bearer {token}"}).status_code == 401


def test_guard_denies_global_and_prefix_lookalike_paths(setup):
    from services.resource_access import create_resource_guard_middleware
    app = FastAPI()
    @app.get("/{path:path}")
    async def endpoint(path: str):
        return {"ok":True}
    app.middleware("http")(create_resource_guard_middleware())
    app.middleware("http")(create_auth_middleware())
    app.middleware("http")(jm.create_jwt_middleware())
    client = TestClient(app)
    headers={"Authorization":f"Bearer {jm.create_access_token('alice', 'Alice')}"}
    for path in ["/api/v1/catalog", "/api/v1/export", "/api/v1/lineage", "/api/v1/documents-admin", "/api/v1/system"]:
        assert client.get(path, headers=headers).status_code == 403
    assert client.get("/api/v1/documents/doc-a", headers=headers).status_code == 200
    assert client.get("/healthz").status_code == 401


def test_ingest_project_requires_editor_and_resource_legacy_requires_admin(setup):
    from fastapi import HTTPException
    from services.resource_access import authorize_resource, ingest_identity
    _, svc, _ = setup
    org = svc.create_org(OrganizationCreate(name="乙", slug="b"))
    project = svc.create_project(org.org_id, ProjectCreate(name="项目乙"), "alice")
    svc.add_member(org.org_id, MemberInvite(user_id="alice", role="org_viewer"))
    request = Request({"type":"http", "headers":[(b"x-project-id", project.project_id.encode())]})
    request.state.user = {"user_id":"alice", "roles":["viewer"]}
    with pytest.raises(HTTPException) as exc:
        ingest_identity(request)
    assert exc.value.status_code == 404
    svc.update_member_role(org.org_id, "alice", "org_editor")
    assert ingest_identity(request)["org_id"] == org.org_id
    request = Request({"type":"http", "headers":[]})
    request.state.user = {"user_id":"alice", "roles":["viewer"]}
    with pytest.raises(HTTPException):
        authorize_resource(request, {"document_id":"legacy"})
    request.state.user = {"user_id":"root", "roles":["admin"]}
    assert authorize_resource(request, {"document_id":"legacy"})["document_id"] == "legacy"


def test_unconfigured_environment_rejects_public_default_admin_token(setup, monkeypatch):
    client, _, _ = setup
    for name in ("APP_ENV", "ENVIRONMENT", "ENV", "NODE_ENV", "JWT_SECRET_KEY", "AUTH_ALLOW_ANONYMOUS"):
        monkeypatch.delenv(name, raising=False)
    token = jwt.encode({"sub":"attacker", "exp":time.time()+600, "iss":"graphrag-backend", "roles":["admin"]}, "graphrag-dev-secret-change-in-production", algorithm="HS256")
    assert client.get("/api/v1/documents", headers={"Authorization":f"Bearer {token}"}).status_code == 401
    with pytest.raises(ValueError):
        jm.create_access_token("attacker", "攻击者", roles=["admin"])


@pytest.mark.parametrize("claims", [
    {"sub":"alice", "exp":str(int(time.time()+600)), "iss":"graphrag-backend"},
    {"sub":123, "exp":time.time()+600, "iss":"graphrag-backend"},
    {"sub":"alice", "exp":time.time()+600, "iss":"other-service"},
    {"sub":"alice", "exp":time.time()+600},
    {"sub":"alice", "exp":True, "iss":"graphrag-backend"},
])
def test_claim_types_and_issuer_are_strict(setup, claims):
    client, _, _ = setup
    token = jwt.encode({"type":"access", **claims}, TEST_SECRET, algorithm="HS256")
    assert client.get("/api/v1/documents", headers={"Authorization":f"Bearer {token}"}).status_code == 401


def test_public_secret_only_allowed_for_explicit_dev_mode(setup, monkeypatch):
    client, _, _ = setup
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
    monkeypatch.setenv("AUTH_ALLOW_ANONYMOUS", "true")
    token = jm.create_access_token("alice", "Alice")
    assert client.get("/api/v1/documents", headers={"Authorization":f"Bearer {token}"}).status_code == 200
    monkeypatch.setenv("APP_ENV", "production")
    assert client.get("/api/v1/documents", headers={"Authorization":f"Bearer {token}"}).status_code == 401


def test_current_user_roles_and_disable_revoke_existing_access(setup):
    from services.auth_service import get_auth_service
    client, _, mgr = setup
    service = get_auth_service()
    service.update_roles("alice", ["admin"])
    headers = {"Authorization":f"Bearer {jm.create_access_token('alice', 'Alice', roles=['admin'])}"}
    assert client.get("/api/v1/documents", headers=headers).json()["roles"] == ["admin"]
    service.update_roles("alice", ["viewer"])
    assert client.get("/api/v1/documents", headers=headers).json()["roles"] == ["viewer"]
    key = mgr.create(ApiKeyCreate(name="读", scopes=["read:catalog"]), created_by="alice")
    key_headers = {"Authorization":f"Bearer {key.full_key}"}
    assert client.get("/api/v1/documents", headers=key_headers).status_code == 200
    assert service.disable_user("alice")
    assert client.get("/api/v1/documents", headers=headers).status_code == 401
    assert client.get("/api/v1/documents", headers=key_headers).status_code == 401


def test_missing_access_type_rejected(setup):
    client, _, _ = setup
    token = jwt.encode({"sub":"alice", "exp":time.time()+600, "iss":"graphrag-backend"}, TEST_SECRET, algorithm="HS256")
    assert client.get("/api/v1/documents", headers={"Authorization":f"Bearer {token}"}).status_code == 401


def test_valid_refresh_token_cannot_access_documents(setup):
    client, _, _ = setup
    refresh = jm.create_refresh_token("alice")
    assert jm.decode_token(refresh)["type"] == "refresh"
    assert client.get("/api/v1/documents", headers={"Authorization":f"Bearer {refresh}"}).status_code == 401
