from tests.request_helpers import authenticated_client
"""任务终态语义：全失败 → failed；部分失败 → done + partial；零实体 → done + warning。

不跑真实 MinerU/Ollama —— 直接把 worker.run_real_pipeline 换成受控实现，
只验证 routes/ingest.py 的终态映射逻辑（这正是本次改造的核心）。
"""
import sys
import os
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from errors import (
    ErrorCode, ErrorContext, PipelineStage, StageExtractionError,
)


@pytest.fixture
def client(monkeypatch, sandbox_tmp_path):
    from server import app
    import routes
    import routes.ingest as ing
    import routes.query as query

    store_dir = sandbox_tmp_path / "output"
    store_dir.mkdir()
    monkeypatch.setattr(routes, "DOCS_JSON_PATH", str(store_dir / "docs_store.json"))
    monkeypatch.setattr(routes, "_docs_store", [])
    monkeypatch.setattr(ing, "TASKS_STORE_PATH", str(store_dir / "tasks_store.json"))
    monkeypatch.setattr(ing, "_tasks", {})
    routes._save_docs([])
    ing._save_tasks({})
    uploads_dir = store_dir / "uploads"
    uploads_dir.mkdir()
    (uploads_dir / "t.docx").write_bytes(b"test-only-ingest-input")
    kg_dir = store_dir / "kg"
    kg_dir.mkdir()
    monkeypatch.setattr(query, "KG_DIR", str(kg_dir))
    monkeypatch.setattr(query, "G_grounded", None)
    monkeypatch.setattr(query, "_agent", None)
    # Keep reload and temporary KG reads real; substitute only model construction.
    monkeypatch.setattr(query, "_build_agent", lambda graph: object())
    return authenticated_client(app, monkeypatch, sandbox_tmp_path, raise_server_exceptions=False)


def _run_ingest(client, monkeypatch, task_id, pipeline_impl):
    """把 task_id 注册进 routes.ingest._tasks 后直接调 _run_indexing。"""
    import routes.ingest as ing

    ing._tasks[task_id] = {
        "task_id": task_id,
        "status": ing.TaskStatus.PENDING,
        "filename": "t.docx",
        "file_size_bytes": 10,
        "created_at": ing.datetime.now(ing.timezone.utc),
        "updated_at": ing.datetime.now(ing.timezone.utc),
        "stage": None, "progress": None, "result": None, "error": None,
    }

    import worker
    monkeypatch.setattr(worker, "run_real_pipeline",
                        lambda *a, **k: pipeline_impl(*a, **k))

    filepath = Path(ing.TASKS_STORE_PATH).parent / "uploads" / "t.docx"
    ing._run_indexing(task_id, str(filepath), "t.docx", 10, {"identity": {"owner_id": "compat-admin"}})
    task = ing._tasks[task_id]
    persisted_tasks = json.loads(Path(ing.TASKS_STORE_PATH).read_text(encoding="utf-8"))
    assert persisted_tasks[task_id]["status"] == task["status"]
    import routes
    persisted_docs = json.loads(Path(routes.DOCS_JSON_PATH).read_text(encoding="utf-8"))
    if task["status"] == "done":
        assert len(persisted_docs) == 1
        assert persisted_docs[0]["filepath"] == str(filepath)
        assert persisted_docs[0]["owner_id"] == "compat-admin"
    else:
        assert persisted_docs == []
    return task


def _all_batches_failed(task_id, filepath, filename, progress, opts):
    exc = StageExtractionError(
        "实体抽取全部批次失败", code=ErrorCode.PIPELINE_EXTRACTION_EMPTY,
        context=ErrorContext(provider="ollama", stage=PipelineStage.EXTRACTION,
                             task_id=task_id),
    )
    raise exc


def _partial(task_id, filepath, filename, progress, opts):
    return {
        "document_id": "doc_partial", "kg_nodes": 3, "kg_edges": 2,
        "grounded_entities": 3, "entity_types": 1, "pages_parsed": 1,
        "kg_path": "", "partial": True, "warnings": ["1/2 批次抽取失败"],
    }


def _zero_entities(task_id, filepath, filename, progress, opts):
    return {
        "document_id": "doc_empty", "kg_nodes": 0, "kg_edges": 0,
        "grounded_entities": 0, "entity_types": 0, "pages_parsed": 1,
        "kg_path": "", "partial": False, "warnings": ["未抽取到实体"],
    }


def test_all_extraction_failed_marks_task_failed(client, monkeypatch):
    task = _run_ingest(client, monkeypatch, "t-fail", _all_batches_failed)
    assert task["status"] == "failed", f"实得 {task['status']}"
    assert task["error"]["code"] == "PIPELINE_EXTRACTION_EMPTY"
    # 用户可见文案不得是内部异常原文的裸拼接
    assert task["error"]["message"]


def test_partial_extraction_marks_partial(client, monkeypatch):
    task = _run_ingest(client, monkeypatch, "t-partial", _partial)
    assert task["status"] == "done"
    assert task["result"]["partial"] is True
    assert task["result"]["warnings"]


def test_zero_entities_is_done_with_warning(client, monkeypatch):
    task = _run_ingest(client, monkeypatch, "t-empty", _zero_entities)
    assert task["status"] == "done"
    assert task["result"]["partial"] is False
    assert task["result"]["warnings"]


def test_pipeline_error_literal_is_gone():
    """PIPELINE_ERROR 字面量必须全仓消失（backend + frontend）。"""
    repo = BACKEND.parent
    hits = []
    paths = []
    for root, pattern in [(BACKEND, "*.py"), (repo / "frontend" / "src", "*.ts*")]:
        for directory, dirs, files in os.walk(root):
            dirs[:] = [name for name in dirs if name not in {".venv", "tests", "__pycache__", "node_modules", "output", "uploads"}]
            paths.extend(Path(directory) / name for name in files if Path(name).match(pattern))
    for p in paths:
        rel = str(p).replace("\\", "/")
        if ".venv" in rel or "/tests/" in rel or p.name == "test_ingest_degraded_status.py":
            continue
        if "PIPELINE_ERROR" in p.read_text(encoding="utf-8", errors="replace"):
            hits.append(rel)
    assert not hits, f"仍存在 PIPELINE_ERROR 字面量：{hits}"


def test_non_degraded_error_sites_terminate_control_flow():
    """worker.py 的不变式：每个 `progress_callback(error=...)` 必须二选一 ——

      ① 带 degraded=True  → progress() 记降级，函数继续执行并返回成功；
      ② 不带 degraded     → progress() 标 FAILED，该分支必须随即 return/raise 终止。

    反例（本测试要抓住的缺陷）：`error=` 不带 degraded、之后**继续执行** ——
    函数最终返回成功 dict，把 status 由 FAILED 翻回 DONE，却把 error 字段留在
    task 上，产生「status=done 但挂着 error」的脏任务。实测该缺陷在向量化、
    BM25/Table 索引两条降级分支上都存在过。
    """
    import ast

    tree = ast.parse((BACKEND / "worker.py").read_text(encoding="utf-8"))
    offenders = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler):
            continue
        for call in ast.walk(node):
            if not isinstance(call, ast.Call):
                continue
            if getattr(call.func, "id", "") != "progress_callback":
                continue
            kw = {k.arg for k in call.keywords if k.arg}
            if "error" not in kw or "degraded" in kw:
                continue
            terminates = any(isinstance(s, (ast.Return, ast.Raise)) for s in node.body)
            if not terminates:
                offenders.append(
                    f"line {call.lineno} (except at line {node.lineno})"
                )
    assert not offenders, (
        "progress_callback(error=...) 既未标 degraded、又未终止控制流，"
        f"会留下 status=DONE + 残留 error 的脏任务：{offenders}"
    )
