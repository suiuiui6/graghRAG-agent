"""
API Key management endpoints — §6.6 of enterprise-evolution-blueprint.

Create, list, revoke, rotate API keys for external integrations.
"""

from fastapi import APIRouter, HTTPException, Request

from models import ApiKeyCreate
from services.api_key_manager import get_api_key_manager

router = APIRouter()


@router.post("/api-keys")
async def create_api_key(body: ApiKeyCreate, request: Request):
    """Create a new API key. The full key is returned ONLY ONCE."""
    user = getattr(request.state, "user", {})
    created_by = user.get("user_id", "admin")
    mgr = get_api_key_manager()
    result = mgr.create(body, created_by=created_by)
    return result.model_dump()


@router.get("/api-keys")
async def list_api_keys():
    """List all API keys (without the full key)."""
    mgr = get_api_key_manager()
    keys = []
    for rec in mgr.list_all():
        keys.append({
            "key_id": rec.key_id,
            "name": rec.name,
            "key_prefix": rec.key_prefix,
            "created_by": rec.created_by,
            "created_at": rec.created_at,
            "expires_at": rec.expires_at,
            "last_used_at": rec.last_used_at,
            "revoked": rec.revoked,
            "scopes": rec.scopes,
            "rate_limit_per_minute": rec.rate_limit_per_minute,
        })
    return {"api_keys": keys}


@router.get("/api-keys/{key_id}")
async def get_api_key(key_id: str):
    """Get API key metadata (without the full key)."""
    mgr = get_api_key_manager()
    rec = mgr.get(key_id)
    if not rec:
        raise HTTPException(status_code=404, detail="API key not found")
    return {
        "key_id": rec.key_id,
        "name": rec.name,
        "key_prefix": rec.key_prefix,
        "created_by": rec.created_by,
        "created_at": rec.created_at,
        "expires_at": rec.expires_at,
        "last_used_at": rec.last_used_at,
        "revoked": rec.revoked,
        "scopes": rec.scopes,
        "rate_limit_per_minute": rec.rate_limit_per_minute,
    }


@router.post("/api-keys/{key_id}/revoke")
async def revoke_api_key(key_id: str, request: Request):
    """Revoke an API key. Immediately invalid."""
    user = getattr(request.state, "user", {})
    revoked_by = user.get("user_id", "admin")
    mgr = get_api_key_manager()
    ok = mgr.revoke(key_id, revoked_by=revoked_by)
    if not ok:
        raise HTTPException(status_code=404, detail="API key not found")
    return {"status": "revoked", "key_id": key_id}


@router.post("/api-keys/{key_id}/rotate")
async def rotate_api_key(key_id: str, request: Request):
    """Rotate an API key — revoke old, create new. Full key returned ONCE."""
    user = getattr(request.state, "user", {})
    rotated_by = user.get("user_id", "admin")
    mgr = get_api_key_manager()
    result = mgr.rotate(key_id, rotated_by=rotated_by)
    if not result:
        raise HTTPException(status_code=404, detail="API key not found")
    return result.model_dump()
