"""
Conversation management endpoints — §10.2 of enterprise-evolution-blueprint.
"""

from fastapi import APIRouter, HTTPException, Query

from conversation import get_conversation_manager

router = APIRouter()


@router.get("/conversations")
async def list_conversations(limit: int = Query(50, le=100)):
    mgr = get_conversation_manager()
    return {"conversations": mgr.list_all(limit=limit)}


@router.get("/conversations/{session_id}")
async def get_conversation(session_id: str):
    mgr = get_conversation_manager()
    conv = mgr.load(session_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv.to_dict()


@router.delete("/conversations/{session_id}")
async def delete_conversation(session_id: str):
    mgr = get_conversation_manager()
    ok = mgr.delete(session_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"status": "deleted"}


@router.get("/conversations/{session_id}/export")
async def export_conversation(session_id: str):
    mgr = get_conversation_manager()
    md = mgr.export_markdown(session_id)
    if md is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"markdown": md}
