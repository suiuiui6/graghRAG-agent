"""Ingest + status endpoints — §3.2.1, §3.2.2 — REAL pipeline."""

import json
import os
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, BackgroundTasks, Request
from models import (
    IngestResponse, StatusResponse, TaskStatus, StageProgress, TaskResult, TaskError, SUPPORTED_EXTENSIONS, MAX_FILE_SIZE,
)
from routes import add_doc

from errors import ErrorCode, PipelineError, user_message
from logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter()
UPLOADS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
os.makedirs(UPLOADS_DIR, exist_ok=True)

# In-memory task store (persisted to JSON for crash recovery)
TASKS_STORE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output", "tasks_store.json")


def _load_tasks() -> dict[str, dict]:
    """Load tasks from JSON file. Returns empty dict on first run or corruption."""
    if os.path.exists(TASKS_STORE_PATH):
        try:
            with open(TASKS_STORE_PATH, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def _save_tasks(tasks: dict[str, dict]):
    """Persist tasks to JSON file."""
    import datetime as _dt
    def _json_serial(obj):
        if isinstance(obj, (_dt.datetime, _dt.date)):
            return obj.isoformat()
        if hasattr(obj, 'model_dump'):
            return obj.model_dump()
        if hasattr(obj, 'value'):
            return obj.value
        return str(obj)
    os.makedirs(os.path.dirname(TASKS_STORE_PATH), exist_ok=True)
    with open(TASKS_STORE_PATH, "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2, default=_json_serial)


_tasks: dict[str, dict] = _load_tasks()


def _run_indexing(task_id: str, filepath: str, filename: str, file_size: int, ingest_options: dict):
    """Background indexing — REAL MinerU → LangExtract → KG pipeline."""

    _tasks[task_id]["status"] = TaskStatus.RUNNING
    _tasks[task_id]["updated_at"] = datetime.now(timezone.utc)
    _save_tasks(_tasks)

    def progress(stage_key, stage_name, step, details, error=None,
                 error_code=None, degraded=False):
        _tasks[task_id]["stage"] = stage_key
        _tasks[task_id]["progress"] = StageProgress(
            stage_name=stage_name,
            current_step=step, total_steps=5,
            details=details,
        ).model_dump()
        _tasks[task_id]["updated_at"] = datetime.now(timezone.utc)
        if error:
            if degraded:
                # 任务**确实完成**，只是结果不完整 —— 骑在 result 上，
                # 不改 TaskStatus（那是 wire 契约，DEGRADED 是质量维度）。
                existing = _tasks[task_id].get("result") or {}
                _tasks[task_id]["result"] = {
                    **existing,
                    "partial": True,
                    "warnings": [*(existing.get("warnings") or []), error],
                }
                logger.warning("ingest_degraded", task_id=task_id, stage=stage_key,
                               error_code=error_code, detail=error)
            else:
                _tasks[task_id]["status"] = TaskStatus.FAILED
                _tasks[task_id]["error"] = TaskError(
                    code=error_code or ErrorCode.INTERNAL_ERROR.value,
                    message=error,
                ).model_dump()
                logger.error("ingest_failed", task_id=task_id, stage=stage_key,
                             error_code=error_code, detail=error)
        _save_tasks(_tasks)

    try:
        from worker import run_real_pipeline
        result = run_real_pipeline(task_id, filepath, filename, progress, ingest_options)
    except PipelineError as exc:
        progress(exc.stage.value if exc.stage else "mineru", "Pipeline Error", 0, {},
                 error=exc.message, error_code=exc.code.value)
        return
    except Exception:
        logger.error("ingest_unexpected", task_id=task_id, exc_info=True)
        progress("mineru", "Pipeline Error", 0, {},
                 error=user_message(ErrorCode.INTERNAL_ERROR),
                 error_code=ErrorCode.INTERNAL_ERROR.value)
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
            partial=result.get("partial", False),
            warnings=result.get("warnings", []),
        ).model_dump(),
        "updated_at": datetime.now(timezone.utc),
    })
    _save_tasks(_tasks)
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
        # Non-fatal: KG will load on next query
        logger.error("kg_reload_failed", task_id=task_id, exc_info=True)


@router.post("/ingest", response_model=IngestResponse)
async def ingest(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(default=None),
    url: str = Form(default=""),
    language: str = Form(default="ch"),
    enable_ocr: bool = Form(default=False),
    enable_formula: bool = Form(default=True),
    enable_table: bool = Form(default=True),
    model_version: str = Form(default="pipeline"),
    # 允许复用 output/mineru/ 下的**既有**产物作为最后兜底（默认关闭）。
    # 为何默认关闭：缓存目录是按**目录名字典序**挑的、与本次文件无关，开启会在
    # MinerU/OSS 都失败时静默把**别的文档**的产物当成这次的入库。仅在明确要复用
    # 同一份产物（重复入库 / 离线演示）时显式打开，并自行确认缓存内容与文件一致。
    allow_cached_mineru_output: bool = Form(default=False),
):
    filename_override = None
    # ── JSON body mode (from Engine-Vue Java backend) ──
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            json_body = await request.json()
            json_url = json_body.get("url", "")
            if json_url:
                url = json_url
            json_filename = json_body.get("filename", "")
            if json_filename:
                filename_override = json_filename
        except Exception:  # noqa: S110, BLE001  # 可选依赖或产物缺失时降级为跳过，缺失本身已由调用方判定
            pass

    # ── URL mode: skip file upload, pass path directly to worker ──
    url = url.strip()
    if url:
        if not (url.startswith("http://") or url.startswith("https://")):
            # Allow local file paths (e.g., D:/Engine/uploadPath/xxx.docx)
            if not os.path.exists(url):
                raise HTTPException(400, detail=f"File not found: {url}")
            task_id = f"ingest_{uuid.uuid4().hex[:8]}"
            filename = filename_override or os.path.basename(url) or "document.docx"
            now = datetime.now(timezone.utc)
            _tasks[task_id] = {
                "task_id": task_id, "status": TaskStatus.PENDING, "stage": "upload",
                "filename": filename, "file_size_bytes": os.path.getsize(url) if os.path.exists(url) else 0,
                "created_at": now, "updated_at": now, "progress": None, "result": None, "error": None,
            }
            _save_tasks(_tasks)
            ingest_options = {
                "language": language,
                "enable_ocr": enable_ocr,
                "enable_formula": enable_formula,
                "enable_table": enable_table,
                "model_version": model_version,
            }
            background_tasks.add_task(_run_indexing, task_id, url, filename, os.path.getsize(url), ingest_options)
            return IngestResponse(task_id=task_id, status=TaskStatus.PENDING, filename=filename,
                                  file_size_bytes=os.path.getsize(url), created_at=now, estimated_duration_seconds=60,
                                  links={"status": f"/api/v1/status/{task_id}"})

        task_id = f"ingest_{uuid.uuid4().hex[:8]}"
        filename = url.split("/")[-1] or "document.pdf"
        now = datetime.now(timezone.utc)
        _tasks[task_id] = {
            "task_id": task_id, "status": TaskStatus.PENDING, "stage": "upload",
            "filename": filename, "file_size_bytes": 0,
            "created_at": now, "updated_at": now, "progress": None, "result": None, "error": None,
        }
        _save_tasks(_tasks)
        ingest_options = {
            "language": language,
            "enable_ocr": enable_ocr,
            "enable_formula": enable_formula,
            "enable_table": enable_table,
            "model_version": model_version,
        }
        background_tasks.add_task(_run_indexing, task_id, url, filename, 0, ingest_options)
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
    _save_tasks(_tasks)

    ingest_options = {
        "language": language,
        "enable_ocr": enable_ocr,
        "enable_formula": enable_formula,
        "enable_table": enable_table,
        "model_version": model_version,
        "allow_cached_mineru_output": allow_cached_mineru_output,
    }
    background_tasks.add_task(_run_indexing, task_id, filepath, file.filename or "unknown", len(contents), ingest_options)

    return IngestResponse(task_id=task_id, status=TaskStatus.PENDING,
        filename=file.filename or "unknown", file_size_bytes=len(contents),
        created_at=now, estimated_duration_seconds=60,
        links={"status": f"/api/v1/status/{task_id}"})


@router.get("/status/{task_id}", response_model=StatusResponse)
async def get_status(task_id: str):
    task = _tasks.get(task_id)
    if not task:
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
