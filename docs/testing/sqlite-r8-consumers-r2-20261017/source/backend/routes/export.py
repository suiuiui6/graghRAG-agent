"""
Data export endpoints — §5.3 of enterprise-evolution-blueprint.
"""

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from services.kg_exporter import get_exporter
from services.lineage_store import get_lineage_store

router = APIRouter()


@router.get("/export/kg")
async def export_kg(
    format: str = Query("json", pattern="^(json|csv|rdf|neo4j|zip)$"),
):
    """Export knowledge graph in various formats."""
    exporter = get_exporter()
    try:
        return exporter.export_kg(format)
    except ValueError as e:
        # 导出器的 ValueError 只描述用户提交的 format 参数，消息可安全外露
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/export/domain-dict")
async def export_domain_dict(
    format: str = Query("yaml", pattern="^(yaml|csv|json)$"),
):
    """Export domain dictionary in YAML/CSV/JSON."""
    exporter = get_exporter()
    try:
        return exporter.export_domain_dict(format)
    except ValueError as e:
        # 导出器的 ValueError 只描述用户提交的 format 参数，消息可安全外露
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/export/feedback")
async def export_feedback(
    format: str = Query("csv", pattern="^(csv|json)$"),
    status: str | None = Query(None, pattern="^(open|acknowledged|resolved)$"),
):
    """Export feedback data (filterable by status)."""
    exporter = get_exporter()
    return exporter.export_feedback(format, status=status)


@router.get("/export/conversations")
async def export_conversations():
    """Export all conversations as Markdown ZIP."""
    exporter = get_exporter()
    return exporter.export_conversations()


@router.get("/export/lineage/{entity_id}")
async def export_lineage_dot(entity_id: str):
    """Export entity lineage as Graphviz DOT graph."""
    store = get_lineage_store()
    dot = store.export_dot(entity_id)
    if dot is None:
        raise HTTPException(status_code=404, detail="Entity lineage not found")
    return StreamingResponse(
        iter([dot]),
        media_type="text/plain",
        headers={"Content-Disposition": f"attachment; filename=lineage_{entity_id}.dot"},
    )
