"""
Tenant management endpoints — §7.1 of enterprise-evolution-blueprint.

Organization and Project CRUD with member management (12 endpoints).
Admin-only: create org. org_admin: manage members, create projects.
"""

from fastapi import APIRouter, HTTPException, Request

from services.tenant_service import TenantService, get_tenant_service
from models import OrganizationCreate, ProjectCreate, MemberInvite, RoleUpdate

router = APIRouter()


def _get_svc() -> TenantService:
    return get_tenant_service()


def _require_admin(request: Request):
    user = getattr(request.state, "user", None)
    if not user or "admin" not in user.get("roles", []):
        raise HTTPException(status_code=403, detail="Admin only")


def _require_org_admin(request: Request, org_id: str):
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if "admin" in user.get("roles", []):
        return  # Global admin always passes
    try:
        svc = _get_svc()
        member = svc.get_member(org_id, user.get("user_id", ""))
        if not member or member.role != "org_admin":
            raise HTTPException(status_code=403, detail="Organization admin only")
    except HTTPException:
        raise
    except Exception:  # noqa: BLE001  # 成员权限校验失败统一按无权限处理（异常本身不泄露内部细节）
        raise HTTPException(status_code=403, detail="Organization admin only")


# ── Organizations ────────────────────────────────────────────────────────

@router.post("/orgs")
async def create_org(body: OrganizationCreate, request: Request):
    """Create an organization (global admin only)."""
    _require_admin(request)
    svc = _get_svc()
    org = svc.create_org(body)
    return {"org": org.model_dump()}


@router.get("/orgs")
async def list_orgs(request: Request):
    """List organizations visible to current user."""
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    svc = _get_svc()
    if "admin" in user.get("roles", []):
        orgs = svc.list_orgs()
    else:
        user_orgs = svc.get_user_orgs(user.get("user_id", ""))
        orgs = [svc.get_org(o["org_id"]) for o in user_orgs if svc.get_org(o["org_id"])]
    return {"orgs": [o.model_dump() for o in orgs if o]}


@router.get("/orgs/{org_id}")
async def get_org(org_id: str, request: Request):
    svc = _get_svc()
    org = svc.get_org(org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return {"org": org.model_dump()}


@router.put("/orgs/{org_id}")
async def update_org(org_id: str, body: dict, request: Request):
    """Update organization settings (org_admin or global admin)."""
    _require_org_admin(request, org_id)
    svc = _get_svc()
    org = svc.update_org(org_id, body)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return {"org": org.model_dump()}


# ── Projects ──────────────────────────────────────────────────────────

@router.post("/orgs/{org_id}/projects")
async def create_project(org_id: str, body: ProjectCreate, request: Request):
    _require_org_admin(request, org_id)
    user = getattr(request.state, "user", {})
    svc = _get_svc()
    proj = svc.create_project(org_id, body, created_by=user.get("user_id", "system"))
    if not proj:
        raise HTTPException(status_code=404, detail="Organization not found")
    return {"project": proj.model_dump()}


@router.get("/orgs/{org_id}/projects")
async def list_projects(org_id: str):
    svc = _get_svc()
    projects = svc.list_projects(org_id)
    return {"projects": [p.model_dump() for p in projects]}


@router.put("/orgs/{org_id}/projects/{project_id}")
async def update_project(org_id: str, project_id: str, body: dict, request: Request):
    _require_org_admin(request, org_id)
    svc = _get_svc()
    proj = svc.get_project(project_id)
    if not proj or proj.org_id != org_id:
        raise HTTPException(status_code=404, detail="Project not found")
    proj = svc.update_project(project_id, body)
    return {"project": proj.model_dump()}


@router.post("/orgs/{org_id}/projects/{project_id}/archive")
async def archive_project(org_id: str, project_id: str, request: Request):
    _require_org_admin(request, org_id)
    svc = _get_svc()
    proj = svc.get_project(project_id)
    if not proj or proj.org_id != org_id:
        raise HTTPException(status_code=404, detail="Project not found")
    proj = svc.archive_project(project_id)
    return {"project": proj.model_dump(), "status": "archived"}


# ── Members ─────────────────────────────────────────────────────────────

@router.post("/orgs/{org_id}/members")
async def invite_member(org_id: str, body: MemberInvite, request: Request):
    _require_org_admin(request, org_id)
    user = getattr(request.state, "user", {})
    svc = _get_svc()
    member = svc.add_member(org_id, body, invited_by=user.get("user_id", ""))
    if not member:
        raise HTTPException(status_code=404, detail="Organization not found")
    return {"member": member.model_dump()}


@router.get("/orgs/{org_id}/members")
async def list_members(org_id: str, request: Request):
    svc = _get_svc()
    members = svc.list_members(org_id)
    return {"members": [m.model_dump() for m in members]}


@router.put("/orgs/{org_id}/members/{user_id}/role")
async def update_member_role(org_id: str, user_id: str, body: RoleUpdate, request: Request):
    _require_org_admin(request, org_id)
    svc = _get_svc()
    member = svc.update_member_role(org_id, user_id, body.role)
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    return {"member": member.model_dump()}


@router.delete("/orgs/{org_id}/members/{user_id}")
async def remove_member(org_id: str, user_id: str, request: Request):
    _require_org_admin(request, org_id)
    svc = _get_svc()
    ok = svc.remove_member(org_id, user_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Member not found")
    return {"status": "removed", "org_id": org_id, "user_id": user_id}
