"""Resolve explicit project headers only through real memberships."""
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from auth import PUBLIC_PATHS


def create_tenant_middleware():
    async def tenant_middleware(request: Request, call_next):
        user = getattr(request.state, "user", None) or {}
        tenant = {"org_id":None, "project_id":None, "user_id":user.get("user_id", ""), "org_role":"", "permissions":user.get("roles", [])}
        selected = request.headers.get("X-Project-Id")
        if selected and request.url.path not in PUBLIC_PATHS:
            from services.resource_access import require_principal, project_membership
            try:
                project, member = project_membership(require_principal(request), selected)
                tenant.update(org_id=project.org_id, project_id=project.project_id, org_role=member.role)
            except HTTPException as exc:
                return JSONResponse(status_code=exc.status_code, content={"detail":exc.detail})
        request.state.tenant = tenant
        return await call_next(request)
    return tenant_middleware
