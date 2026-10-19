"""
System management endpoints — §5.4/§5.6 of enterprise-evolution-blueprint.

Backup, restore, cleanup, and storage management APIs.
"""

from fastapi import APIRouter, HTTPException, Query

from services.backup import get_backup_manager
from services.lifecycle import get_lifecycle_manager
from services.quality import get_quality_monitor

router = APIRouter()


# ── Backup (§5.4) ──────────────────────────────────────────────────────

@router.post("/system/backup")
async def create_backup():
    """Trigger an immediate full backup."""
    mgr = get_backup_manager()
    result = mgr.create_backup(backup_type="manual")
    if result.status == "failed":
        raise HTTPException(status_code=500, detail=result.error)
    return result.model_dump()


@router.get("/system/backups")
async def list_backups():
    """List all available backups."""
    mgr = get_backup_manager()
    return {"backups": mgr.list_backups()}


@router.get("/system/backup/{backup_id}/manifest")
async def get_backup_manifest(backup_id: str):
    """Get backup content manifest."""
    mgr = get_backup_manager()
    manifest = mgr.get_manifest(backup_id)
    if manifest is None:
        raise HTTPException(status_code=404, detail="Backup not found")
    return manifest


@router.post("/system/backup/verify/{backup_id}")
async def verify_backup(backup_id: str):
    """Verify backup integrity."""
    mgr = get_backup_manager()
    result = mgr.verify(backup_id)
    return result


@router.post("/system/restore")
async def restore_backup(backup_id: str = Query(..., min_length=1)):
    """Restore from a backup (creates pre-restore snapshot first)."""
    mgr = get_backup_manager()
    result = mgr.restore(backup_id)
    if result.status == "failed":
        raise HTTPException(status_code=400, detail=result.error or "Restore failed")
    return result.model_dump()


# ── Lifecycle (§5.6) ──────────────────────────────────────────────────

@router.post("/system/cleanup")
async def run_cleanup():
    """Manually trigger global data cleanup per retention policies."""
    lm = get_lifecycle_manager()
    report = lm.run_cleanup()
    return report.model_dump()


@router.get("/system/cleanup/preview")
async def preview_cleanup():
    """Preview what data would be cleaned (dry-run)."""
    lm = get_lifecycle_manager()
    previews = lm.preview_cleanup()
    return {"previews": [p.model_dump() for p in previews]}


@router.get("/system/storage")
async def storage_report():
    """Get disk usage statistics for all data directories."""
    lm = get_lifecycle_manager()
    return lm.storage_report().model_dump()


# ── Quality (§5.5) ────────────────────────────────────────────────────

@router.get("/system/quality")
async def quality_report():
    """Compute and return current data quality report."""
    qm = get_quality_monitor()
    report = qm.compute()
    return report.model_dump()
