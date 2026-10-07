"""SQLite-backed task lifecycle persistence."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from .context import AccessContext
from .schema import initialize_database
from .sqlite import connect, transaction


_TASK_STATUSES = frozenset({"pending", "running", "done", "failed"})
_JSON_COLUMNS = {
    "progress_json": "progress",
    "result_json": "result",
    "error_json": "error",
}
_SCOPE_COLUMNS = ("owner_id", "tenant_id", "org_id", "project_id")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _serialize_json(value: dict[str, Any] | None) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False)


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("persisted datetime must be timezone-aware")
    return parsed


class TaskStore:
    """Persist task lifecycle state with tenant and owner scoping."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        initialize_database(self.db_path)

    @staticmethod
    def _scope_values(context: AccessContext) -> tuple[str, ...]:
        return tuple(getattr(context, column) for column in _SCOPE_COLUMNS)

    @staticmethod
    def _scope_predicate() -> str:
        return " AND ".join(f"{column} = ?" for column in _SCOPE_COLUMNS)

    @staticmethod
    def _validate_status(status: str) -> None:
        if status not in _TASK_STATUSES:
            valid = ", ".join(sorted(_TASK_STATUSES))
            raise ValueError(f"invalid task status {status!r}; expected one of: {valid}")

    @staticmethod
    def _decode_task(row: Any) -> dict[str, Any]:
        task = dict(row)
        for source_column, public_name in _JSON_COLUMNS.items():
            raw_value = task.pop(source_column)
            task[public_name] = json.loads(raw_value) if raw_value is not None else None
        task["created_at"] = _parse_datetime(task["created_at"])
        task["updated_at"] = _parse_datetime(task["updated_at"])
        return task

    def create(
        self,
        context: AccessContext,
        *,
        task_id: str,
        filename: str,
        file_size_bytes: int,
        source_filepath: str | None = None,
        created_at: datetime | None = None,
    ) -> None:
        if created_at is not None and (
            created_at.tzinfo is None or created_at.utcoffset() is None
        ):
            raise ValueError("created_at must be timezone-aware")
        timestamp = created_at or _utc_now()
        with transaction(self.db_path) as connection:
            connection.execute(
                """
                INSERT INTO tasks (
                    task_id, owner_id, tenant_id, org_id, project_id,
                    status, lifecycle_status, filename, file_size_bytes,
                    source_filepath, created_at, updated_at, row_version
                ) VALUES (?, ?, ?, ?, ?, 'pending', 'active', ?, ?, ?, ?, ?, 0)
                """,
                (
                    task_id,
                    *self._scope_values(context),
                    filename,
                    file_size_bytes,
                    source_filepath,
                    timestamp.isoformat(),
                    timestamp.isoformat(),
                ),
            )

    def get(self, context: AccessContext, task_id: str) -> dict[str, Any] | None:
        with connect(self.db_path) as connection:
            row = connection.execute(
                f"SELECT * FROM tasks WHERE task_id = ? AND {self._scope_predicate()}",
                (task_id, *self._scope_values(context)),
            ).fetchone()
        return self._decode_task(row) if row is not None else None

    def set_status(
        self,
        context: AccessContext,
        task_id: str,
        status: str,
        *,
        stage: str | None,
        expected_row_version: int | None = None,
    ) -> bool:
        self._validate_status(status)
        if status != "running":
            return False
        return self._update(
            context,
            task_id,
            {"status": status, "stage": stage},
            expected_row_version=expected_row_version,
            expected_status="pending",
        )

    def update_progress(
        self,
        context: AccessContext,
        task_id: str,
        *,
        stage: str,
        progress: dict[str, Any],
        result: dict[str, Any] | None = None,
        expected_row_version: int | None = None,
    ) -> bool:
        return self._update(
            context,
            task_id,
            {
                "stage": stage,
                "progress_json": _serialize_json(progress),
                "result_json": _serialize_json(result),
            },
            expected_row_version=expected_row_version,
        )

    def complete(
        self,
        context: AccessContext,
        task_id: str,
        *,
        stage: str,
        result: dict[str, Any],
        expected_row_version: int | None = None,
    ) -> bool:
        return self._update(
            context,
            task_id,
            {
                "status": "done",
                "stage": stage,
                "result_json": _serialize_json(result),
            },
            expected_row_version=expected_row_version,
            expected_status="running",
        )

    def fail(
        self,
        context: AccessContext,
        task_id: str,
        *,
        stage: str,
        error: dict[str, Any],
        expected_row_version: int | None = None,
    ) -> bool:
        return self._update(
            context,
            task_id,
            {
                "status": "failed",
                "stage": stage,
                "error_json": _serialize_json(error),
            },
            expected_row_version=expected_row_version,
            expected_statuses=("pending", "running"),
        )

    def _update(
        self,
        context: AccessContext,
        task_id: str,
        values: dict[str, Any],
        *,
        expected_row_version: int | None,
        expected_status: str | None = None,
        expected_statuses: tuple[str, ...] | None = None,
    ) -> bool:
        now = _utc_now().isoformat()
        assignments = [f"{column} = ?" for column in values]
        assignments.extend(("updated_at = ?", "row_version = row_version + 1"))
        parameters: list[Any] = list(values.values()) + [now, task_id]
        predicate = (
            f"task_id = ? AND {self._scope_predicate()} "
            "AND lifecycle_status = 'active' "
        )
        parameters.extend(self._scope_values(context))
        if expected_status is not None:
            predicate += "AND status = ? "
            parameters.append(expected_status)
        elif expected_statuses is not None:
            placeholders = ", ".join("?" for _ in expected_statuses)
            predicate += f"AND status IN ({placeholders}) "
            parameters.extend(expected_statuses)
        else:
            predicate += "AND status NOT IN ('done', 'failed') "
        if expected_row_version is not None:
            predicate += " AND row_version = ?"
            parameters.append(expected_row_version)

        with transaction(self.db_path) as connection:
            cursor = connection.execute(
                f"UPDATE tasks SET {', '.join(assignments)} WHERE {predicate}",
                parameters,
            )
        return cursor.rowcount == 1

    def mark_inflight_stale(self) -> int:
        now = _utc_now().isoformat()
        stale_error = _serialize_json(
            {
                "code": "TASK_STALE_AFTER_RESTART",
                "message": "Task was still in flight when the service restarted",
            }
        )
        with transaction(self.db_path) as connection:
            cursor = connection.execute(
                """
                UPDATE tasks
                SET status = 'failed', lifecycle_status = 'stale',
                    error_json = ?, updated_at = ?, row_version = row_version + 1
                WHERE status IN ('pending', 'running')
                  AND lifecycle_status = 'active'
                """,
                (stale_error, now),
            )
        return cursor.rowcount
