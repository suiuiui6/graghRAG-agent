"""Ingest + status endpoints — §3.2.1, §3.2.2 — REAL pipeline."""

import os
import uuid
import traceback
from datetime import datetime, timezone

from fastapi import APIRouter, UploadFile, File, Form, BackgroundTasks
from models import (
    IngestResponse, StatusResponse, TaskStatus, PipelineStage,
    StageProgress, TaskResult, TaskError, SUPPORTED_EXTENSIONS, MAX_FILE_SIZE,
)
from routes import add_doc

router = APIRouter()
UPLOADS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
os.makedirs(UPLOADS_DIR, exist_ok=True)

# In-memory task store
_tasks: dict[str, dict] = {}


def _run_indexing(task_id: str, filepath: str, filename: str, file_size: int):
    """Background indexing — REAL MinerU → LangExtract → KG pipeline."""

    def progress(stage_key: str, stage_name: str, step: int, details: dict, error: str | None = None):
        _tasks[task_id]["stage"] = stage_key
        _tasks[task_id]["progress"] = StageProgress(
            stage_name=stage_name,
            current_step=step, total_steps=5,
            details=details,
        ).model_dump()
        _tasks[task_id]["updated_at"] = datetime.now(timezone.utc)
        if error:
            _tasks[task_id]["status"] = TaskStatus.FAILED
            _tasks[task_id]["error"] = TaskError(code="PIPELINE_ERROR", message=error).model_dump()

    try:
        from worker import run_real_pipeline
        result = run_real_pipeline(task_id, filepath, filename, progress)
    except Exception as e:
        progress("mineru", "Pipeline Error", 0, {}, error=str(e))
        return

    if result is None:
        return  # Already marked as failed in progress callback

    doc_id = result["document_id"]
    _tasks[task_id].update({
        "status": TaskStatus.DONE,
        "stage": "completed",
        "progress": StageProgress(
            stage_name="Complete", current_step=5, total_steps=5,
            details={"mineru": "done", "bridge": "done", "extraction": "done", "grounding": "done", "kg_build": "done"},
        ).model_dump(),
        "result": TaskResult(
            document_id=doc_id,
            kg_nodes=result["kg_nodes"],
            kg_edges=result["kg_edges"],
            grounded_entities=result["grounded_entities"],
            entity_types=result["entity_types"],
            pages_parsed=result["pages_parsed"],
            kg_path=result.get("kg_path", ""),
        ).model_dump(),
        "updated_at": datetime.now(timezone.utc),
    })
    add_doc({
        "document_id": doc_id,
        "filename": filename,
        "status": "indexed",
        "kg_nodes": result["kg_nodes"],
        "kg_edges": result["kg_edges"],
        "pages": result["pages_parsed"],
        "indexed_at": datetime.now(timezone.utc).isoformat(),
        "file_size_bytes": file_size,
        "filepath": filepath,
    })

    # Hot-reload KG so query endpoint picks up new data
    try:
        from routes.query import reload_kg
        reload_kg()
    except Exception:
        traceback.print_exc()  # Non-fatal: KG will load on next query


@router.post("/ingest", response_model=IngestResponse)
async def ingest(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(default=None),
    url: str = Form(default=""),
    language: str = Form(default="ch"),
    enable_ocr: bool = Form(default=False),
    enable_formula: bool = Form(default=True),
    enable_table: bool = Form(default=True),
    model_version: str = Form(default="pipeline"),
):
    from fastapi import HTTPException

    # ── URL mode: skip file upload, pass URL directly to worker ──
    url = url.strip()
    if url:
        if not (url.startswith("http://") or url.startswith("https://")):
            raise HTTPException(400, detail="URL must start with http:// or https://")
        task_id = f"ingest_{uuid.uuid4().hex[:8]}"
        filename = url.split("/")[-1] or "document.pdf"
        now = datetime.now(timezone.utc)
        _tasks[task_id] = {
            "task_id": task_id, "status": TaskStatus.PENDING, "stage": "upload",
            "filename": filename, "file_size_bytes": 0,
            "created_at": now, "updated_at": now, "progress": None, "result": None, "error": None,
        }
        background_tasks.add_task(_run_indexing, task_id, url, filename, 0)
        return IngestResponse(task_id=task_id, status=TaskStatus.PENDING, filename=filename,
                              file_size_bytes=0, created_at=now, estimated_duration_seconds=60,
                              links={"status": f"/api/v1/status/{task_id}"})

    # ── File upload mode ──
    if file is None:
        raise HTTPException(400, detail="Either file or url parameter is required")

    ext = os.path.splitext(file.filename or "x")[1].lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(400, detail=f"Unsupported format: {ext}. Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}")

    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(413, detail=f"File too large: {len(contents)} bytes (max {MAX_FILE_SIZE})")

    task_id = f"ingest_{uuid.uuid4().hex[:8]}"
    filepath = os.path.join(UPLOADS_DIR, f"{task_id}_{file.filename}")
    with open(filepath, "wb") as f:
        f.write(contents)

    now = datetime.now(timezone.utc)
    _tasks[task_id] = {
        "task_id": task_id, "status": TaskStatus.PENDING, "stage": "upload",
        "filename": file.filename, "file_size_bytes": len(contents),
        "created_at": now, "updated_at": now, "progress": None, "result": None, "error": None,
    }

    env_file_url = os.getenv("FILE_URL", "").strip()
    if env_file_url:
        filepath = env_file_url
    background_tasks.add_task(_run_indexing, task_id, filepath, file.filename or "unknown", len(contents))

    return IngestResponse(task_id=task_id, status=TaskStatus.PENDING,
        filename=file.filename or "unknown", file_size_bytes=len(contents),
        created_at=now, estimated_duration_seconds=60,
        links={"status": f"/api/v1/status/{task_id}"})


@router.get("/status/{task_id}", response_model=StatusResponse)
async def get_status(task_id: str):
    task = _tasks.get(task_id)
    if not task:
        from fastapi import HTTPException
        raise HTTPException(404, detail=f"Task not found: {task_id}")

    return StatusResponse(
        task_id=task["task_id"],
        status=task["status"],
        stage=task.get("stage"),
        progress=StageProgress(**task["progress"]) if task.get("progress") else None,
        result=TaskResult(**task["result"]) if task.get("result") else None,
        error=TaskError(**task["error"]) if task.get("error") else None,
        created_at=task["created_at"],
        updated_at=task["updated_at"],
        duration_seconds=int((task["updated_at"] - task["created_at"]).total_seconds()) if task.get("updated_at") else None,
    )
