"""Document list, download & delete endpoints."""

import json, os, shutil
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from models import DocumentListResponse, DocumentItem, DeleteResponse
from routes import remove_doc, get_docs_snapshot

router = APIRouter()


def _parse_iso(ts: str) -> datetime:
    """Parse ISO 8601 timestamp, handling 'Z' suffix for older Python versions."""
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


@router.get("/documents", response_model=DocumentListResponse)
async def list_documents():
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
        for d in get_docs_snapshot()
    ]


    return DocumentListResponse(documents=items, total=len(items))


UPLOADS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")


@router.get("/documents/{doc_id}/download")
async def download_document(doc_id: str):
    """Download the original uploaded document."""
    doc = next((d for d in get_docs_snapshot() if d["document_id"] == doc_id), None)
    if not doc:
        raise HTTPException(404, detail="Document not found")
    filepath = doc.get("filepath")
    if not filepath or not os.path.exists(filepath):
        raise HTTPException(404, detail="Original file not available for download")
    # Path traversal protection: ensure filepath is within UPLOADS_DIR
    if not os.path.realpath(filepath).startswith(os.path.realpath(UPLOADS_DIR) + os.sep):
        raise HTTPException(403, detail="Access denied")
    return FileResponse(filepath, filename=doc["filename"], media_type="application/octet-stream")


@router.delete("/documents/{doc_id}", response_model=DeleteResponse)
async def delete_document(doc_id: str):
    _base = os.path.dirname(os.path.dirname(__file__))
    kg_root = os.path.realpath(os.path.join(_base, "output", "kg"))

    # 1. Clean KG directories
    for prefix in ["", "doc_"]:
        kg_path = os.path.realpath(os.path.join(kg_root, prefix + doc_id))
        try:
            if not kg_path.startswith(kg_root + os.sep):
                continue
            if os.path.isdir(kg_path):
                shutil.rmtree(kg_path)
        except Exception:
            pass

    # 2. Clean uploaded source file (try matching by doc_id as task_id prefix)
    uploads_dir = os.path.join(_base, "uploads")
    try:
        if os.path.isdir(uploads_dir):
            for fname in os.listdir(uploads_dir):
                if fname.startswith(doc_id.replace("doc_", "")) or fname.startswith(doc_id):
                    os.remove(os.path.join(uploads_dir, fname))
    except Exception:
        pass

    remove_doc(doc_id)
    return DeleteResponse(
        document_id=doc_id,
        status="deleted",
        deleted_at=datetime.now(timezone.utc),
    )


@router.get("/files/{filename:path}")
async def serve_uploaded_file(filename: str, request: Request):
    """Serve an uploaded file directly — use with ngrok tunnel to get public URL for MinerU.

    Requires ?token= parameter for non-localhost access."""
    from security import verify_file_token
    verify_file_token(request)
    UPLOADS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
    real_path = os.path.realpath(os.path.join(UPLOADS_DIR, filename))
    if not real_path.startswith(os.path.realpath(UPLOADS_DIR) + os.sep):
        raise HTTPException(403, detail="Access denied")
    if not os.path.exists(real_path):
        raise HTTPException(404, detail="File not found")
    return FileResponse(real_path, media_type="application/octet-stream")
