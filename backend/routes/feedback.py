"""
Feedback collection endpoints — §4.1 of enterprise-evolution-blueprint.
"""

from fastapi import APIRouter, HTTPException, Query

from models import FeedbackCreate, FeedbackUpdate
from services.feedback_store import get_feedback_store

router = APIRouter()


@router.post("/feedback")
async def submit_feedback(body: FeedbackCreate):
    """Submit answer feedback (thumbs up/down + optional comment)."""
    store = get_feedback_store()
    rec = store.submit(body)
    return {"status": "received", "feedback_id": rec.feedback_id}


@router.get("/feedback")
async def list_feedback(
    status: str | None = Query(None, pattern="^(open|acknowledged|resolved)$"),
    limit: int = Query(50, le=200),
):
    store = get_feedback_store()
    items = [r.model_dump() for r in store.list_all(status=status, limit=limit)]
    return {"feedback": items, "total": len(items)}


@router.get("/feedback/stats")
async def feedback_stats():
    store = get_feedback_store()
    return store.stats()


@router.get("/feedback/{feedback_id}")
async def get_feedback(feedback_id: str):
    store = get_feedback_store()
    rec = store.get(feedback_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="Feedback not found")
    return rec.model_dump()


@router.patch("/feedback/{feedback_id}")
async def update_feedback(feedback_id: str, body: FeedbackUpdate):
    store = get_feedback_store()
    rec = store.update(feedback_id, body)
    if rec is None:
        raise HTTPException(status_code=404, detail="Feedback not found")
    return {"status": "updated", "feedback": rec.model_dump()}


@router.delete("/feedback/{feedback_id}")
async def delete_feedback(feedback_id: str):
    store = get_feedback_store()
    ok = store.delete(feedback_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Feedback not found")
    return {"status": "deleted"}
