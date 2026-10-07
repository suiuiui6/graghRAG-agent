"""
Audit log query endpoints — §6.5 of enterprise-evolution-blueprint.

Query and export security/compliance audit events.
"""

from fastapi import APIRouter, Query
from fastapi.responses import PlainTextResponse

from services.audit_logger import get_audit_logger

router = APIRouter()


@router.get("/audit")
async def query_audit(
    event: str | None = Query(None),
    user_id: str | None = Query(None),
    from_date: str | None = Query(None, description="YYYY-MM-DD"),
    to_date: str | None = Query(None, description="YYYY-MM-DD"),
    limit: int = Query(200, le=500),
):
    """Query audit events with optional filters."""
    audit = get_audit_logger()
    results = audit.query(event=event, user_id=user_id,
                         from_date=from_date, to_date=to_date, limit=limit)
    return {"audit_logs": results, "total": len(results)}


@router.get("/audit/export")
async def export_audit(
    from_date: str | None = Query(None),
    to_date: str | None = Query(None),
):
    """Export audit log as CSV."""
    audit = get_audit_logger()
    csv_data = audit.export_csv(from_date=from_date, to_date=to_date)
    return PlainTextResponse(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=audit_export.csv"},
    )
