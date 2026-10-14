"""Document list, download & delete endpoints."""

import os
import shutil
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from pathlib import Path
from services.resource_access import authorized_documents
from services.document_snapshot import contained_asset, graph_directory, document_graph
from models import DocumentListResponse, DocumentItem, DeleteResponse
from routes import remove_doc

router = APIRouter()


def _parse_iso(ts: str) -> datetime:
    """Parse ISO 8601 timestamp, handling 'Z' suffix for older Python versions."""
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


@router.get("/documents", response_model=DocumentListResponse)
async def list_documents(request: Request):
    docs = authorized_documents(request)

    items = [
        DocumentItem(
            document_id=d["document_id"],
            filename=d["filename"],
            status=d["status"],
            kg_nodes=d.get("kg_nodes"),
            kg_edges=d.get("kg_edges"),
            pages=d.get("pages"),
            indexed_at=_parse_iso(d["indexed_at"]) if d.get("indexed_at") else None,
            file_size_mb=round(d.get("file_size_bytes", 0) / 1048576, 1) if d.get("file_size_bytes") else None,
        )
        for d in docs
    ]


    return DocumentListResponse(documents=items, total=len(items))


UPLOADS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")


@router.get("/documents/{doc_id}/download")
async def download_document(doc_id: str, request: Request):
    """Download the original uploaded document."""
    doc = authorized_documents(request, doc_id)[0]
    if not doc:
        raise HTTPException(404, detail="Document not found")
    filepath = doc.get("filepath")
    if not filepath or not os.path.exists(filepath):
        raise HTTPException(404, detail="Original file not available for download")
    path = contained_asset(filepath, Path(UPLOADS_DIR))
    return FileResponse(path, filename=doc["filename"], media_type="application/octet-stream")


@router.delete("/documents/{doc_id}", response_model=DeleteResponse)
async def delete_document(doc_id: str, request: Request):
    doc = authorized_documents(request, doc_id, write=True)[0]
    base = Path(__file__).resolve().parent.parent
    kg_root = base / "output" / "kg"
    kg_path = graph_directory(doc, kg_root)
    original = contained_asset(doc["filepath"], Path(UPLOADS_DIR)) if doc.get("filepath") else None
    # Resolve every registered asset before mutating anything. Never infer prefixes.
    try:
        if original is not None and original.exists():
            original.unlink()
        if kg_path.exists():
            shutil.rmtree(kg_path)
    except OSError as exc:
        raise HTTPException(500, "Document cleanup failed") from exc
    remove_doc(doc_id)
    # Drop cached references without constructing a model during deletion.
    from routes import query as query_routes
    with query_routes._kg_swap_lock:
        query_routes.G_grounded = None
        query_routes._agent = None
    from routes.rag_query import invalidate_rag_runtime
    invalidate_rag_runtime()
    # Publish event + audit log
    try:
        from services.event_bus import get_event_bus
        get_event_bus().publish("doc.deleted", {"doc_id": doc_id})
    except Exception:  # noqa: S110, BLE001  # 事件发布为 fire-and-forget，投递失败不阻塞删除响应
        pass
    try:
        from services.audit_logger import get_audit_logger
        get_audit_logger().log("doc.deleted", doc_id=doc_id)
    except Exception:  # noqa: S110, BLE001  # 审计写入失败不阻断业务主流程
        pass
    return DeleteResponse(
        document_id=doc_id,
        status="deleted",
        deleted_at=datetime.now(timezone.utc),
    )


@router.get("/documents/{document_id}/chunk_count")
async def document_chunk_count(document_id: str, request: Request):
    doc = authorized_documents(request, document_id)[0]
    root = Path(__file__).resolve().parent.parent / "output" / "kg"
    count = document_graph(doc, root).number_of_nodes()
    return {"document_id": document_id, "chunk_count": count, "expected_chunks": count}


@router.get("/files/{filename:path}")
async def serve_uploaded_file(filename: str, request: Request):
    """Serve only registered files visible to the authenticated principal."""
    path = contained_asset(str(Path(UPLOADS_DIR) / filename), Path(UPLOADS_DIR))
    allowed = authorized_documents(request)
    if not any(doc.get("filepath") and Path(doc["filepath"]).resolve() == path for doc in allowed):
        raise HTTPException(404, detail="File not found")
    if not path.is_file():
        raise HTTPException(404, detail="File not found")
    return FileResponse(path, media_type="application/octet-stream")
