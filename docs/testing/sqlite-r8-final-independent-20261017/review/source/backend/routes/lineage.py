"""
Data lineage query endpoints — §5.1 of enterprise-evolution-blueprint.
"""

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse

from services.lineage_store import get_lineage_store

router = APIRouter()


@router.get("/lineage/entity/{entity_id}")
async def trace_entity(entity_id: str):
    """Get full lineage for an entity (document → entity → answers → feedback)."""
    store = get_lineage_store()
    trace = store.trace_entity(entity_id)
    if trace is None:
        raise HTTPException(status_code=404, detail="Entity lineage not found")
    return trace.model_dump()


@router.get("/lineage/answer/{query_id}")
async def trace_answer(query_id: str):
    """Get full lineage for a query/answer (retrieval → generation → entity → doc)."""
    store = get_lineage_store()
    trace = store.trace_answer(query_id)
    if trace is None:
        raise HTTPException(status_code=404, detail="Answer lineage not found")
    return trace.model_dump()


@router.get("/lineage/document/{doc_id}")
async def trace_document(doc_id: str):
    """List all entities derived from a document."""
    store = get_lineage_store()
    return store.trace_document(doc_id)


@router.get("/lineage/feedback/{feedback_id}")
async def trace_feedback(feedback_id: str):
    """Trace from feedback back through answer → entity → document."""
    store = get_lineage_store()
    trace = store.trace_feedback(feedback_id)
    if trace is None:
        raise HTTPException(status_code=404, detail="Feedback lineage not found")
    return trace.model_dump()


@router.get("/lineage/conversation/{session_id}")
async def trace_conversation(session_id: str):
    """Get all lineage nodes for a conversation session."""
    store = get_lineage_store()
    return store.trace_conversation(session_id)


@router.get("/lineage/term/{term}")
async def trace_term(term: str):
    """Find queries where a domain term was used for expansion."""
    store = get_lineage_store()
    return store.trace_term(term)


@router.get("/lineage/export")
async def export_lineage_dot(entity_id: str = Query(..., min_length=1)):
    """Export entity lineage as Graphviz DOT format."""
    store = get_lineage_store()
    dot = store.export_dot(entity_id)
    if dot is None:
        raise HTTPException(status_code=404, detail="Entity lineage not found")
    return PlainTextResponse(content=dot, media_type="text/plain")
