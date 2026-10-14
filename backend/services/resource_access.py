"""Fail-closed document and tenant authorization shared by routes."""
from __future__ import annotations
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from auth import PUBLIC_PATHS


def require_principal(request: Request) -> dict:
    user = getattr(request.state, "user", None)
    if not isinstance(user, dict) or not user.get("user_id"):
        raise HTTPException(401, "需要有效认证")
    return user


def is_admin(principal: dict) -> bool:
    return "admin" in principal.get("roles", []) and principal.get("auth_type") != "api_key"


def project_membership(principal: dict, project_id: str, write: bool = False):
    from services.tenant_service import get_tenant_service
    svc = get_tenant_service()
    project = svc.get_project(project_id)
    if not project or project.is_archived or not svc.get_org(project.org_id):
        raise HTTPException(404, "资源不存在")
    member = svc.get_member(project.org_id, principal["user_id"])
    if not member or (write and member.role not in {"owner", "org_editor", "org_admin"}):
        raise HTTPException(404, "资源不存在")
    return project, member


def authorize_resource(request: Request, resource: dict, write: bool = False) -> dict:
    user = require_principal(request)
    selected = request.headers.get("X-Project-Id")
    if selected:
        project_membership(user, selected)
        if resource.get("project_id") != selected:
            raise HTTPException(404, "资源不存在")
    if is_admin(user):
        return resource
    owner = resource.get("owner_id") == user["user_id"]
    org_id, project_id = resource.get("org_id"), resource.get("project_id")
    if org_id or project_id:
        if not org_id or not project_id:
            raise HTTPException(404, "资源不存在")
        project, member = project_membership(user, project_id)
        if project.org_id != org_id or (write and not owner and member.role not in {"owner", "org_editor", "org_admin"}):
            raise HTTPException(404, "资源不存在")
        return resource
    if owner:
        return resource
    raise HTTPException(404, "资源不存在")


def authorized_documents(request: Request, document_id: str | None = None, write: bool = False) -> list[dict]:
    require_principal(request)
    selected = request.headers.get("X-Project-Id")
    if selected:
        project_membership(require_principal(request), selected)
    from routes import get_docs_snapshot
    results = []
    for doc in get_docs_snapshot():
        if document_id is not None and doc.get("document_id") != document_id:
            continue
        try:
            results.append(authorize_resource(request, doc, write))
        except HTTPException as exc:
            if exc.status_code != 404:
                raise
    if document_id is not None and not results:
        raise HTTPException(404, "资源不存在")
    return results


def ingest_identity(request: Request) -> dict:
    user = require_principal(request)
    selected = request.headers.get("X-Project-Id")
    if selected:
        project, _ = project_membership(user, selected, write=True)
        return {"owner_id":user["user_id"], "org_id":project.org_id, "project_id":selected}
    return {"owner_id":user["user_id"], "org_id":None, "project_id":None}


def create_resource_guard_middleware():
    allowed = ("/api/v1/documents", "/api/v1/files", "/api/v1/graph", "/api/v1/query", "/api/v1/rag/query", "/api/v1/rag/summarize", "/api/v1/ingest", "/api/v1/status")
    async def guard(request: Request, call_next):
        path = request.url.path
        if path in PUBLIC_PATHS:
            return await call_next(request)
        try:
            user = require_principal(request)
            safe_path = path in {"/api/v1/auth/me", "/api/v1/auth/logout"} or any(path == prefix or path.startswith(prefix + "/") for prefix in allowed)
            if not is_admin(user) and not safe_path:
                raise HTTPException(403, "此接口仅限管理员")
        except HTTPException as exc:
            return JSONResponse(status_code=exc.status_code, content={"detail":exc.detail})
        return await call_next(request)
    return guard
