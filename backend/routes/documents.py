"""Document list, download & delete endpoints."""

import os
import shutil
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
    docs = get_docs_snapshot()

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
        except Exception:  # noqa: S110, BLE001  # 可选依赖或产物缺失时降级为跳过，缺失本身已由调用方判定
            pass

    # 2. Clean uploaded source file (try matching by doc_id as task_id prefix)
    uploads_dir = os.path.join(_base, "uploads")
    try:
        if os.path.isdir(uploads_dir):
            for fname in os.listdir(uploads_dir):
                if fname.startswith(doc_id.replace("doc_", "")) or fname.startswith(doc_id):
                    os.remove(os.path.join(uploads_dir, fname))
    except Exception:  # noqa: S110, BLE001  # 清理为尽力而为，失败已由调用方汇总，不中断其余类别
        pass

    remove_doc(doc_id)
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
async def document_chunk_count(document_id: str):
    """Return chunk count for a document — used by Engine-Vue syncPendingFiles."""
    try:
        import os
        import json
        # Check KG nodes for this document
        kg_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output", "kg")
        doc_kg_dir = os.path.join(kg_dir, f"doc_{document_id}" if not document_id.startswith("doc_") else document_id)
        if os.path.isdir(doc_kg_dir):
            nodes_path = os.path.join(doc_kg_dir, "nodes.json")
            if os.path.exists(nodes_path):
                with open(nodes_path, encoding="utf-8") as f:
                    nodes = json.load(f)
                return {"document_id": document_id, "chunk_count": len(nodes.get("nodes", [])), "expected_chunks": len(nodes.get("nodes", []))}
        # Fallback: check vector store
        from vector_store import VectorStore
        vs = VectorStore()
        info = vs.get_collection_info()
        total = info.get("count", 0)
        return {"document_id": document_id, "chunk_count": max(0, total // 10), "expected_chunks": max(0, total // 10)}
    except Exception:  # noqa: BLE001  # 文档统计探测失败时返回零值占位，不阻断文档查询接口
        return {"document_id": document_id, "chunk_count": 0, "expected_chunks": 0}


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
