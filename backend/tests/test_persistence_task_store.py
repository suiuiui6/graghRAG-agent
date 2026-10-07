from datetime import datetime, timezone
import json
import sqlite3

import pytest

from persistence.context import AccessContext
from persistence.task_store import TaskStore


@pytest.fixture
def context() -> AccessContext:
    return AccessContext(
        owner_id="owner-a",
        tenant_id="tenant-a",
        org_id="org-a",
        project_id="project-a",
    )


def test_create_and_get_round_trips_scope_datetime_and_json(tmp_path, context) -> None:
    store = TaskStore(tmp_path / "state.sqlite3")
    created_at = datetime(2026, 9, 19, 8, 9, 10, 123456, tzinfo=timezone.utc)

    store.create(
        context,
        task_id="task-1",
        filename="报告.pdf",
        file_size_bytes=123,
        source_filepath="/data/报告.pdf",
        created_at=created_at,
    )

    task = store.get(context, "task-1")

    assert task is not None
    assert task["task_id"] == "task-1"
    assert task["owner_id"] == "owner-a"
    assert task["tenant_id"] == "tenant-a"
    assert task["org_id"] == "org-a"
    assert task["project_id"] == "project-a"
    assert task["filename"] == "报告.pdf"
    assert task["file_size_bytes"] == 123
    assert task["source_filepath"] == "/data/报告.pdf"
    assert task["status"] == "pending"
    assert task["lifecycle_status"] == "active"
    assert task["row_version"] == 0
    assert task["created_at"] == created_at
    assert task["progress"] is None
    assert task["result"] is None
    assert task["error"] is None
    assert task["updated_at"].tzinfo is not None


def test_get_is_scoped_by_owner_and_tenant(tmp_path, context) -> None:
    store = TaskStore(tmp_path / "state.sqlite3")
    store.create(context, task_id="task-1", filename="file.pdf", file_size_bytes=1)

    assert store.get(
        AccessContext("owner-b", "tenant-a", "org-a", "project-a"), "task-1"
    ) is None
    assert store.get(
        AccessContext("owner-a", "tenant-b", "org-a", "project-a"), "task-1"
    ) is None


def test_create_rejects_naive_created_at(tmp_path, context) -> None:
    store = TaskStore(tmp_path / "state.sqlite3")

    with pytest.raises(ValueError, match="timezone-aware"):
        store.create(
            context,
            task_id="naive-time",
            filename="file.pdf",
            file_size_bytes=1,
            created_at=datetime(2026, 9, 19, 8, 9, 10),
        )


def test_get_rejects_persisted_naive_datetime(tmp_path, context) -> None:
    store = TaskStore(tmp_path / "state.sqlite3")
    from persistence.sqlite import transaction

    with transaction(tmp_path / "state.sqlite3") as connection:
        connection.execute(
            """
            INSERT INTO tasks (
                task_id, owner_id, tenant_id, org_id, project_id,
                filename, created_at, updated_at, row_version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "naive-persisted",
                context.owner_id,
                context.tenant_id,
                context.org_id,
                context.project_id,
                "file.pdf",
                "2026-09-19T08:09:10",
                "2026-09-19T08:09:11",
                0,
            ),
        )

    with pytest.raises(ValueError, match="persisted datetime must be timezone-aware"):
        store.get(context, "naive-persisted")


@pytest.mark.parametrize("terminal_status", ["done", "failed"])
def test_terminal_tasks_reject_all_normal_updates(tmp_path, context, terminal_status) -> None:
    store = TaskStore(tmp_path / "state.sqlite3")
    store.create(context, task_id="terminal", filename="file.pdf", file_size_bytes=1)
    if terminal_status == "done":
        assert store.set_status(context, "terminal", "running", stage="parse")
        assert store.complete(context, "terminal", stage="index", result={"ok": True})
    else:
        assert store.fail(context, "terminal", stage="parse", error={"code": "OLD"})

    assert not store.set_status(context, "terminal", "running", stage="retry")
    assert not store.update_progress(
        context, "terminal", stage="retry", progress={"percent": 1}
    )
    assert not store.complete(context, "terminal", stage="retry", result={"ok": False})
    assert not store.fail(context, "terminal", stage="retry", error={"code": "NEW"})


def test_set_status_enforces_forward_only_running_transition(tmp_path, context) -> None:
    store = TaskStore(tmp_path / "state.sqlite3")
    store.create(context, task_id="pending", filename="pending.pdf", file_size_bytes=1)
    store.create(context, task_id="running", filename="running.pdf", file_size_bytes=1)

    assert not store.set_status(context, "pending", "done", stage="complete")
    assert not store.set_status(context, "pending", "failed", stage="failed")
    assert store.set_status(context, "running", "running", stage="parse")
    assert not store.set_status(context, "running", "pending", stage="retry")


    store = TaskStore(tmp_path / "state.sqlite3")
    store.create(context, task_id="task-1", filename="file.pdf", file_size_bytes=1)

    assert store.set_status(
        context, "task-1", "running", stage="parse", expected_row_version=0
    )
    assert not store.set_status(
        context, "task-1", "done", stage="complete", expected_row_version=0
    )
    assert store.update_progress(
        context,
        "task-1",
        stage="extract",
        progress={"percent": 50, "中文": "已完成"},
        result={"chunks": 2},
        expected_row_version=1,
    )

    task = store.get(context, "task-1")
    assert task is not None
    assert task["status"] == "running"
    assert task["stage"] == "extract"
    assert task["progress"] == {"percent": 50, "中文": "已完成"}
    assert task["result"] == {"chunks": 2}
    assert task["row_version"] == 2


def test_complete_and_fail_store_terminal_payloads(tmp_path, context) -> None:
    store = TaskStore(tmp_path / "state.sqlite3")
    store.create(context, task_id="done", filename="done.pdf", file_size_bytes=1)
    store.create(context, task_id="failed", filename="failed.pdf", file_size_bytes=1)

    assert store.set_status(context, "done", "running", stage="parse")
    assert store.complete(
        context, "done", stage="index", result={"nodes": 3}, expected_row_version=1
    )
    assert store.fail(
        context,
        "failed",
        stage="parse",
        error={"code": "PARSE_ERROR", "message": "bad file"},
        expected_row_version=0,
    )

    done = store.get(context, "done")
    failed = store.get(context, "failed")
    assert done is not None and done["status"] == "done"
    assert done["result"] == {"nodes": 3}
    assert done["stage"] == "index"
    assert failed is not None and failed["status"] == "failed"
    assert failed["error"] == {"code": "PARSE_ERROR", "message": "bad file"}
    assert failed["stage"] == "parse"


def test_mark_inflight_stale_is_atomic_and_preserves_terminal_tasks(tmp_path, context) -> None:
    store = TaskStore(tmp_path / "state.sqlite3")
    for task_id in ("pending", "running", "done", "failed"):
        store.create(context, task_id=task_id, filename=f"{task_id}.pdf", file_size_bytes=1)
    assert store.set_status(context, "running", "running", stage="parse")
    assert store.set_status(context, "done", "running", stage="parse")
    assert store.complete(context, "done", stage="index", result={"ok": True})
    assert store.fail(
        context,
        "failed",
        stage="parse",
        error={"code": "OLD_ERROR"},
    )

    assert store.mark_inflight_stale() == 2

    pending = store.get(context, "pending")
    running = store.get(context, "running")
    done = store.get(context, "done")
    failed = store.get(context, "failed")
    assert pending is not None and pending["status"] == "failed"
    assert running is not None and running["status"] == "failed"
    assert pending["lifecycle_status"] == "stale"
    assert running["lifecycle_status"] == "stale"
    assert pending["error"]["code"] == "TASK_STALE_AFTER_RESTART"
    assert running["error"]["code"] == "TASK_STALE_AFTER_RESTART"
    assert done is not None and done["status"] == "done"
    assert failed is not None and failed["error"] == {"code": "OLD_ERROR"}


def test_mark_inflight_stale_tasks_reject_all_normal_updates(tmp_path, context) -> None:
    store = TaskStore(tmp_path / "state.sqlite3")
    store.create(context, task_id="stale", filename="file.pdf", file_size_bytes=1)

    assert store.mark_inflight_stale() == 1
    assert not store.set_status(context, "stale", "running", stage="retry")
    assert not store.update_progress(
        context, "stale", stage="retry", progress={"percent": 1}
    )
    assert not store.complete(context, "stale", stage="retry", result={"ok": False})
    assert not store.fail(context, "stale", stage="retry", error={"code": "NEW"})


def test_invalid_status_is_rejected_before_sql(tmp_path, context, monkeypatch) -> None:
    store = TaskStore(tmp_path / "state.sqlite3")
    store.create(context, task_id="task-1", filename="file.pdf", file_size_bytes=1)

    def fail_if_sql_is_run(*args, **kwargs):
        raise AssertionError("invalid status reached SQL")

    monkeypatch.setattr("persistence.task_store.transaction", fail_if_sql_is_run)
    with pytest.raises(ValueError, match="invalid task status"):
        store.set_status(context, "task-1", "stale", stage=None)


def test_json_is_stored_as_utf8_and_invalid_status_is_db_protected(tmp_path, context) -> None:
    store = TaskStore(tmp_path / "state.sqlite3")
    store.create(context, task_id="task-1", filename="file.pdf", file_size_bytes=1)
    assert store.update_progress(
        context,
        "task-1",
        stage="parse",
        progress={"message": "中文"},
    )

    from persistence.sqlite import connect, transaction

    with connect(tmp_path / "state.sqlite3") as connection:
        raw = connection.execute(
            "SELECT progress_json FROM tasks WHERE task_id = ?", ("task-1",)
        ).fetchone()[0]
    assert "\\u4e2d" not in raw
    assert json.loads(raw) == {"message": "中文"}

    with pytest.raises(sqlite3.IntegrityError):
        with transaction(tmp_path / "state.sqlite3") as connection:
            connection.execute(
                "UPDATE tasks SET status = ? WHERE task_id = ?", ("stale", "task-1")
            )
