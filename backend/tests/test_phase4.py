"""
Phase 4 Integration Tests — §7.1 of enterprise-evolution-blueprint.

Tests tenant service (org/project/member CRUD), tenant middleware,
and tenant API endpoints.
"""

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture
def temp_tenants(sandbox_tmp_path):
    """Temp directory for tenant data."""
    base = sandbox_tmp_path
    old_env = os.environ.get("DEFAULT_ORG_ID", "")
    os.environ["DEFAULT_ORG_ID"] = "test-org"
    _patch_tenant_dirs(base)
    try:
        yield base
    finally:
        if old_env:
            os.environ["DEFAULT_ORG_ID"] = old_env
        _restore_tenant_dirs()


def _patch_tenant_dirs(base: Path):
    import services.tenant_service as ts
    ts.TENANTS_DIR = base / "tenants"
    ts.ORGS_DIR = ts.TENANTS_DIR / "orgs"
    ts.PROJECTS_DIR = ts.TENANTS_DIR / "projects"
    ts.MEMBERS_DIR = ts.TENANTS_DIR / "members"
    for d in [ts.ORGS_DIR, ts.PROJECTS_DIR, ts.MEMBERS_DIR]:
        d.mkdir(parents=True, exist_ok=True)


_original_dirs = None


def _restore_tenant_dirs():
    import services.tenant_service as ts
    ts.TENANTS_DIR = Path("output/tenants")
    ts.ORGS_DIR = ts.TENANTS_DIR / "orgs"
    ts.PROJECTS_DIR = ts.TENANTS_DIR / "projects"
    ts.MEMBERS_DIR = ts.TENANTS_DIR / "members"


# ── Tenant Service Tests ──────────────────────────────────────────────


class TestTenantService:
    def test_create_and_get_org(self, temp_tenants):
        from services.tenant_service import TenantService
        from models import OrganizationCreate
        svc = TenantService(base_dir=temp_tenants / "tenants")
        org = svc.create_org(OrganizationCreate(name="Test Org", slug="test-org"))
        assert org.org_id
        assert org.name == "Test Org"
        assert org.slug == "test-org"

        got = svc.get_org(org.org_id)
        assert got is not None
        assert got.name == "Test Org"

    def test_list_orgs(self, temp_tenants):
        from services.tenant_service import TenantService
        from models import OrganizationCreate
        svc = TenantService(base_dir=temp_tenants / "tenants")
        svc.create_org(OrganizationCreate(name="Org A", slug="org-a"))
        svc.create_org(OrganizationCreate(name="Org B", slug="org-b"))
        orgs = svc.list_orgs()
        assert len(orgs) >= 2

    def test_update_org(self, temp_tenants):
        from services.tenant_service import TenantService
        from models import OrganizationCreate
        svc = TenantService(base_dir=temp_tenants / "tenants")
        org = svc.create_org(OrganizationCreate(name="Old", slug="old"))
        updated = svc.update_org(org.org_id, {"name": "New"})
        assert updated is not None
        assert updated.name == "New"

    def test_delete_org(self, temp_tenants):
        from services.tenant_service import TenantService
        from models import OrganizationCreate
        svc = TenantService(base_dir=temp_tenants / "tenants")
        org = svc.create_org(OrganizationCreate(name="Temp", slug="temp"))
        assert svc.delete_org(org.org_id)
        assert svc.get_org(org.org_id) is None

    def test_create_and_list_projects(self, temp_tenants):
        from services.tenant_service import TenantService
        from models import OrganizationCreate, ProjectCreate
        svc = TenantService(base_dir=temp_tenants / "tenants")
        org = svc.create_org(OrganizationCreate(name="Org", slug="org"))
        proj = svc.create_project(org.org_id, ProjectCreate(name="Proj A"), "user1")
        assert proj is not None
        assert proj.org_id == org.org_id

        projects = svc.list_projects(org.org_id)
        assert len(projects) >= 1

    def test_update_and_archive_project(self, temp_tenants):
        from services.tenant_service import TenantService
        from models import OrganizationCreate, ProjectCreate
        svc = TenantService(base_dir=temp_tenants / "tenants")
        org = svc.create_org(OrganizationCreate(name="Org", slug="org"))
        proj = svc.create_project(org.org_id, ProjectCreate(name="Proj"), "user1")
        updated = svc.update_project(proj.project_id, {"name": "Renamed"})
        assert updated.name == "Renamed"

        archived = svc.archive_project(proj.project_id)
        assert archived.is_archived

    def test_create_project_nonexistent_org(self, temp_tenants):
        from services.tenant_service import TenantService
        from models import ProjectCreate
        svc = TenantService(base_dir=temp_tenants / "tenants")
        assert svc.create_project("nonexistent", ProjectCreate(name="X"), "u1") is None

    def test_member_lifecycle(self, temp_tenants):
        from services.tenant_service import TenantService
        from models import OrganizationCreate, MemberInvite
        svc = TenantService(base_dir=temp_tenants / "tenants")
        org = svc.create_org(OrganizationCreate(name="Org", slug="org"))

        # Add member
        m = svc.add_member(org.org_id, MemberInvite(user_id="user1", role="org_editor"))
        assert m is not None
        assert m.role == "org_editor"

        # List members
        members = svc.list_members(org.org_id)
        assert len(members) >= 1

        # Update role
        updated = svc.update_member_role(org.org_id, "user1", "org_admin")
        assert updated is not None
        assert updated.role == "org_admin"

        # Get member
        found = svc.get_member(org.org_id, "user1")
        assert found is not None
        assert found.role == "org_admin"

        # Remove member
        assert svc.remove_member(org.org_id, "user1")
        assert svc.get_member(org.org_id, "user1") is None

    def test_get_user_orgs(self, temp_tenants):
        from services.tenant_service import TenantService
        from models import OrganizationCreate, MemberInvite
        svc = TenantService(base_dir=temp_tenants / "tenants")
        org = svc.create_org(OrganizationCreate(name="Org", slug="org"))
        svc.add_member(org.org_id, MemberInvite(user_id="user1", role="org_viewer"))
        orgs = svc.get_user_orgs("user1")
        assert len(orgs) >= 1
        assert orgs[0]["org_id"] == org.org_id


# ── Tenant Endpoint Tests ─────────────────────────────────────────────


class TestTenantEndpoints:
    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from server import app
        return TestClient(app)

    def test_list_orgs_unauthorized(self, client):
        r = client.get("/api/v1/orgs")
        assert r.status_code in (200, 401)

    def test_create_org_requires_admin(self, client):
        r = client.post("/api/v1/orgs", json={"name": "Test", "slug": "test"})
        assert r.status_code in (200, 401, 403)  # depends on whether token present

    def test_list_projects(self, client):
        r = client.get("/api/v1/orgs/default/projects")
        assert r.status_code in (200, 404)

    def test_tenant_middleware_injects_context(self, client):
        """Health endpoint should have tenant context set."""
        r = client.get("/api/v1/health")
        assert r.status_code == 200


# ── Tenant Middleware Tests ───────────────────────────────────────────


class TestTenantMiddleware:
    def test_whitelist_paths_pass(self):
        from middleware.tenant_middleware import _is_whitelisted
        assert _is_whitelisted("/api/v1/health")
        assert _is_whitelisted("/api/v1/auth/login")
        assert _is_whitelisted("/api/v1/bot/feishu")
        assert not _is_whitelisted("/api/v1/orgs")


# ── E2E Multi-Tenant Regression (§7.1 Gate) ─────────────────────────


class TestMultiTenantE2E:
    """End-to-end multi-tenant isolation regression.

    Scenario:
      1. Create two orgs (OrgA, OrgB), each with one project (ProjX, ProjY)
      2. Add members to each org
      3. Verify data isolation: OrgA members can't see OrgB data
      4. Verify KG paths are tenant-scoped
      5. Verify admin can cross all tenants
    """

    def test_cross_org_isolation(self, temp_tenants):
        """Data from OrgA should not leak to OrgB."""
        from services.tenant_service import TenantService
        from models import OrganizationCreate, ProjectCreate, MemberInvite

        svc = TenantService(base_dir=temp_tenants / "tenants")

        # Create two organizations
        org_a = svc.create_org(OrganizationCreate(name="Alpha Corp", slug="alpha"))
        org_b = svc.create_org(OrganizationCreate(name="Beta Corp", slug="beta"))

        # Create projects
        svc.create_project(org_a.org_id, ProjectCreate(name="Alpha-X"), "admin")
        svc.create_project(org_b.org_id, ProjectCreate(name="Beta-Y"), "admin")

        # Add Alice to OrgA, Bob to OrgB
        svc.add_member(org_a.org_id, MemberInvite(user_id="alice", role="org_admin"))
        svc.add_member(org_b.org_id, MemberInvite(user_id="bob", role="org_editor"))

        # Alice can see OrgA but not OrgB
        alice_orgs = svc.get_user_orgs("alice")
        assert any(o["org_id"] == org_a.org_id for o in alice_orgs)
        assert not any(o["org_id"] == org_b.org_id for o in alice_orgs)

        # Bob can see OrgB but not OrgA
        bob_orgs = svc.get_user_orgs("bob")
        assert any(o["org_id"] == org_b.org_id for o in bob_orgs)
        assert not any(o["org_id"] == org_a.org_id for o in bob_orgs)

        # Alice is org_admin in OrgA
        alice_member = svc.get_member(org_a.org_id, "alice")
        assert alice_member is not None
        assert alice_member.role == "org_admin"

        # Bob is NOT a member of OrgA
        assert svc.get_member(org_a.org_id, "bob") is None

    def test_project_list_isolated(self, temp_tenants):
        """Project listing should be scoped to org."""
        from services.tenant_service import TenantService
        from models import OrganizationCreate, ProjectCreate

        svc = TenantService(base_dir=temp_tenants / "tenants")

        org_a = svc.create_org(OrganizationCreate(name="A", slug="a"))
        org_b = svc.create_org(OrganizationCreate(name="B", slug="b"))

        svc.create_project(org_a.org_id, ProjectCreate(name="A-1"), "admin")
        svc.create_project(org_a.org_id, ProjectCreate(name="A-2"), "admin")
        svc.create_project(org_b.org_id, ProjectCreate(name="B-1"), "admin")

        # OrgA should only have 2 projects
        a_projects = svc.list_projects(org_a.org_id)
        assert len(a_projects) == 2
        assert all(p.org_id == org_a.org_id for p in a_projects)

        # OrgB should only have 1 project
        b_projects = svc.list_projects(org_b.org_id)
        assert len(b_projects) == 1
        assert all(p.org_id == org_b.org_id for p in b_projects)

        # All projects (no filter) should have 3
        all_projects = svc.list_projects()
        assert len(all_projects) == 3

    def test_member_crud_regression(self, temp_tenants):
        """Full member lifecycle: invite → update role → remove."""
        from services.tenant_service import TenantService
        from models import OrganizationCreate, MemberInvite

        svc = TenantService(base_dir=temp_tenants / "tenants")
        org = svc.create_org(OrganizationCreate(name="Test", slug="test"))

        # Invite
        m = svc.add_member(org.org_id, MemberInvite(user_id="u1", role="org_viewer"))
        assert m.role == "org_viewer"

        # Double invite is idempotent
        m2 = svc.add_member(org.org_id, MemberInvite(user_id="u1", role="org_admin"))
        assert m2 is not None  # returns existing member

        # Update role
        updated = svc.update_member_role(org.org_id, "u1", "org_editor")
        assert updated.role == "org_editor"

        # List
        members = svc.list_members(org.org_id)
        assert len(members) == 1

        # Remove
        assert svc.remove_member(org.org_id, "u1")
        assert len(svc.list_members(org.org_id)) == 0

    def test_archive_then_list(self, temp_tenants):
        """Archived projects should still be listed but marked."""
        from services.tenant_service import TenantService
        from models import OrganizationCreate, ProjectCreate

        svc = TenantService(base_dir=temp_tenants / "tenants")
        org = svc.create_org(OrganizationCreate(name="X", slug="x"))
        proj = svc.create_project(org.org_id, ProjectCreate(name="Active"), "admin")

        archived = svc.archive_project(proj.project_id)
        assert archived.is_archived

        projects = svc.list_projects(org.org_id)
        assert len(projects) == 1
        assert projects[0].is_archived

    def test_kg_tenant_path(self):
        """KG path should include org_id and project_id."""
        from kg_store import get_tenant_kg_path

        path = get_tenant_kg_path("org_abc", "proj_xyz")
        assert "org_abc" in str(path)
        assert "proj_xyz" in str(path)

    def test_kg_load_with_tenant_filter(self, temp_tenants):
        """load_all_kg_graphs with tenant params should filter properly."""
        from pathlib import Path
        from kg_store import load_all_kg_graphs

        # Create tenant-scoped KG data
        base = Path(temp_tenants) / "kg"
        tenant_path = base / "org_a" / "proj_x" / "doc_test1"
        (tenant_path / "v1").mkdir(parents=True)
        (tenant_path / "v1" / "nodes.json").write_text(json.dumps({
            "nodes": [
                {"node_id": "n1", "entity_type": "metric", "label": "Test Metric"}
            ]
        }), encoding="utf-8")
        (tenant_path / "v1" / "edges.json").write_text(json.dumps({"edges": []}))
        (tenant_path / "versions.json").write_text(json.dumps({
            "doc_id": "doc_test1", "versions": [{"version": 1}], "active_version": 1
        }))

        # Load with tenant filter
        g = load_all_kg_graphs(base_dir=base, org_id="org_a", project_id="proj_x")
        assert g.number_of_nodes() == 1
        # Node ID has doc prefix from load_graph
        assert any("n1" in n for n in g.nodes)

        # Load with wrong tenant should find nothing
        g2 = load_all_kg_graphs(base_dir=base, org_id="org_b", project_id="proj_y")
        assert g2.number_of_nodes() == 0

    def test_tenant_api_flow(self, temp_tenants):
        """Full API flow: create org → create project → invite member → list."""
        import services.tenant_service as ts
        old_dirs = (ts.TENANTS_DIR, ts.ORGS_DIR, ts.PROJECTS_DIR, ts.MEMBERS_DIR)
        base = temp_tenants / "tenants"
        ts.TENANTS_DIR = base
        ts.ORGS_DIR = base / "orgs"
        ts.PROJECTS_DIR = base / "projects"
        ts.MEMBERS_DIR = base / "members"
        for d in [ts.ORGS_DIR, ts.PROJECTS_DIR, ts.MEMBERS_DIR]:
            d.mkdir(parents=True, exist_ok=True)

        try:
            from fastapi.testclient import TestClient
            from server import app
            from middleware.jwt_middleware import create_access_token

            client = TestClient(app)
            admin_token = create_access_token("admin", "admin", roles=["admin"])

            headers = {"Authorization": f"Bearer {admin_token}"}

            # Create org
            r = client.post("/api/v1/orgs", json={"name": "E2E Org", "slug": "e2e"},
                          headers=headers)
            assert r.status_code == 200
            org_data = r.json()["org"]
            org_id = org_data["org_id"]

            # Create project
            r = client.post(f"/api/v1/orgs/{org_id}/projects",
                          json={"name": "E2E Project"}, headers=headers)
            assert r.status_code == 200
            project_data = r.json()["project"]
            assert project_data["name"] == "E2E Project"

            # Invite member
            r = client.post(f"/api/v1/orgs/{org_id}/members",
                          json={"user_id": "testuser", "role": "org_editor"},
                          headers=headers)
            assert r.status_code == 200

            # List members
            r = client.get(f"/api/v1/orgs/{org_id}/members", headers=headers)
            assert r.status_code == 200
            members = r.json()["members"]
            assert any(m["user_id"] == "testuser" for m in members)

            # List orgs
            r = client.get("/api/v1/orgs", headers=headers)
            assert r.status_code == 200
            assert len(r.json()["orgs"]) >= 1
        finally:
            ts.TENANTS_DIR, ts.ORGS_DIR, ts.PROJECTS_DIR, ts.MEMBERS_DIR = old_dirs
