"""
Tenant Middleware — §7.1 of enterprise-evolution-blueprint.

Injects tenant context (org_id, project_id, user role) into
request.state.tenant. Runs after JWT middleware.
"""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse

from logging_config import get_logger

logger = get_logger(__name__)

TENANT_WHITELIST = {
    "/", "/docs", "/redoc", "/openapi.json", "/metrics", "/health",
    "/api/v1/health", "/api/v1/auth/login", "/api/v1/auth/callback",
    "/api/v1/auth/refresh", "/api/v1/bot/feishu", "/api/v1/bot/feishu/alert",
}


def _is_whitelisted(path: str) -> bool:
    for wp in TENANT_WHITELIST:
        if path == wp:
            return True
        if wp != "/" and path.startswith(wp):
            return True
    return False


def create_tenant_middleware():
    """FastAPI middleware — inject request.state.tenant from X-Project-Id
    and JWT user info. Must run AFTER jwt_middleware."""

    async def tenant_middleware(request: Request, call_next):
        path = request.url.path

        if _is_whitelisted(path):
            request.state.tenant = {"org_id": "default", "project_id": None,
                                    "user_id": "", "org_role": "viewer", "permissions": []}
            return await call_next(request)

        user = getattr(request.state, "user", None)
        if not user:
            # No authenticated user — tenant defaults with empty permissions
            request.state.tenant = {"org_id": "default", "project_id": None,
                                    "user_id": "", "org_role": "", "permissions": []}
            return await call_next(request)

        user_id = user.get("user_id", "")
        roles = user.get("roles", [])

        # Determine org_id from user or default
        org_id = user.get("org_id", "default")

        # Determine project_id from X-Project-Id header
        project_id = request.headers.get("X-Project-Id")

        # Non-admin without project_id → try default project
        if not project_id and "admin" not in roles:
            try:
                from services.tenant_service import get_tenant_service
                svc = get_tenant_service()
                orgs = svc.get_user_orgs(user_id)
                if orgs:
                    # Pick first org's first project
                    first_org = orgs[0]
                    org_id = first_org["org_id"]
                    projects = svc.list_projects(org_id)
                    if projects:
                        project_id = projects[0].project_id
                    else:
                        return JSONResponse(
                            status_code=400,
                            content={"detail": "No project available. Create a project first."},
                        )
                else:
                    return JSONResponse(
                        status_code=400,
                        content={"detail": "No organization found. Create an org first."},
                    )
            except Exception as e:  # noqa: BLE001  # 租户上下文解析失败仅记录告警并回退默认作用域，不拒绝请求
                logger.warning("tenant_context_failed", error=str(e))

        # Determine org_role from membership or user roles
        org_role = "org_viewer"
        if "admin" in roles:
            org_role = "org_admin"
        elif project_id:
            try:
                from services.tenant_service import get_tenant_service
                svc = get_tenant_service()
                member = svc.get_member(org_id, user_id)
                if member:
                    org_role = member.role
            except Exception:  # noqa: S110, BLE001  # 可选依赖或产物缺失时降级为跳过，缺失本身已由调用方判定
                pass

        request.state.tenant = {
            "org_id": org_id,
            "project_id": project_id,
            "user_id": user_id,
            "org_role": org_role,
            "permissions": roles,
        }
        return await call_next(request)

    return tenant_middleware
