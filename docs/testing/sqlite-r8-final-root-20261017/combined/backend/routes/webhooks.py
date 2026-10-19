"""
Webhook management endpoints — §6.3 of enterprise-evolution-blueprint.

CRUD for webhook subscriptions, delivery history, test ping.
"""

from fastapi import APIRouter, HTTPException, Query

from models import WebhookCreate
from services.webhook_manager import get_webhook_manager

router = APIRouter()


@router.post("/webhooks")
async def create_webhook(body: WebhookCreate):
    """Register a new webhook subscription."""
    mgr = get_webhook_manager()
    rec = mgr.create(body)
    return rec.model_dump()


@router.get("/webhooks")
async def list_webhooks():
    """List all webhook subscriptions."""
    mgr = get_webhook_manager()
    return {"webhooks": [wh.model_dump() for wh in mgr.list_all()]}


@router.get("/webhooks/{webhook_id}")
async def get_webhook(webhook_id: str):
    """Get webhook details."""
    mgr = get_webhook_manager()
    rec = mgr.get(webhook_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Webhook not found")
    return rec.model_dump()


@router.put("/webhooks/{webhook_id}")
async def update_webhook(webhook_id: str, body: WebhookCreate):
    """Update webhook configuration."""
    mgr = get_webhook_manager()
    rec = mgr.update(webhook_id, body)
    if not rec:
        raise HTTPException(status_code=404, detail="Webhook not found")
    return {"status": "updated", "webhook": rec.model_dump()}


@router.delete("/webhooks/{webhook_id}")
async def delete_webhook(webhook_id: str):
    """Delete webhook subscription."""
    mgr = get_webhook_manager()
    mgr.delete(webhook_id)
    return {"status": "deleted"}


@router.post("/webhooks/{webhook_id}/test")
async def test_webhook(webhook_id: str):
    """Send a test ping to the webhook URL."""
    mgr = get_webhook_manager()
    result = mgr.test_ping(webhook_id)
    return result


@router.get("/webhooks/{webhook_id}/deliveries")
async def get_deliveries(webhook_id: str, limit: int = Query(50, le=200)):
    """Get delivery history for a webhook."""
    mgr = get_webhook_manager()
    deliveries = mgr.get_deliveries(webhook_id, limit=limit)
    return {"webhook_id": webhook_id, "deliveries": [d.model_dump() for d in deliveries]}
