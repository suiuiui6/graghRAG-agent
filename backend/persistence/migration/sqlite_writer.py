"""Dedicated SQL writer for all-or-nothing legacy imports."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import sqlite3
from typing import Any

from persistence.context import legacy_context

from .domain import ParsedLegacy
from .errors import LegacyFormatError, TargetConflictError


_TASK_FIELDS = {
    "task_id", "status", "lifecycle_status", "stage", "filename", "file_size_bytes",
    "source_filepath", "progress", "result", "error", "created_at", "updated_at", "row_version",
    "owner_id", "tenant_id", "org_id", "project_id",
}
_DOCUMENT_FIELDS = {
    "document_id", "filename", "status", "kg_nodes", "kg_edges", "pages", "indexed_at",
    "file_size_bytes", "filepath", "active_kg_version", "metadata", "created_at", "updated_at",
    "deleted_at", "deletion_reason", "reason", "owner_id", "tenant_id", "org_id", "project_id",
}
_KG_FIELDS = {
    "document_id", "version", "state", "artifact_relpath", "manifest_sha256", "node_count",
    "edge_count", "metadata", "created_at", "nodes_source", "edges_source",
}


def _json(value: Any, field_name: str) -> str | None:
    if value is None:
        return None
    try:
        return json.dumps(value, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as error:
        raise LegacyFormatError(f"{field_name} must be JSON serializable") from error


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _datetime(value: Any, field_name: str, fallback: str) -> str:
    if value is None:
        return fallback
    if not isinstance(value, str):
        raise LegacyFormatError(f"{field_name} must be a timezone-aware ISO datetime")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise LegacyFormatError(f"{field_name} is invalid") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise LegacyFormatError(f"{field_name} must be timezone-aware")
    return parsed.isoformat()


def _non_negative_int(value: Any, field_name: str, *, default: int | None = None) -> int | None:
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise LegacyFormatError(f"{field_name} must be a non-negative integer")
    return value


def _require_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise LegacyFormatError(f"{field_name} must be a non-empty string")
    return value


def _reject_unknown(record: dict[str, Any], allowed: set[str], name: str) -> None:
    unknown = sorted(set(record) - allowed)
    if unknown:
        raise LegacyFormatError(f"{name} contains unsupported fields: {', '.join(unknown)}")


def _check_duplicate_ids(records: tuple[dict[str, Any], ...], field_name: str) -> None:
    identifiers = [record.get(field_name) for record in records]
    if any(not isinstance(identifier, str) or not identifier for identifier in identifiers):
        raise LegacyFormatError(f"{field_name} must be a non-empty string")
    if len(set(identifiers)) != len(identifiers):
        raise LegacyFormatError(f"duplicate {field_name} in migration input")


def _validate_inputs(parsed: ParsedLegacy) -> None:
    _check_duplicate_ids(parsed.tasks, "task_id")
    _check_duplicate_ids(parsed.documents, "document_id")
    document_ids = {document["document_id"] for document in parsed.documents}
    kg_keys: set[tuple[str, int]] = set()
    for task in parsed.tasks:
        _reject_unknown(task, _TASK_FIELDS, "task")
        _require_string(task["task_id"], "task_id")
        status = task.get("status", "pending")
        if not isinstance(status, str) or status not in {"pending", "running", "done", "failed"}:
            raise LegacyFormatError("task status is invalid")
        lifecycle_status = task.get("lifecycle_status", "active")
        if not isinstance(lifecycle_status, str) or lifecycle_status not in {"active", "stale", "deleted"}:
            raise LegacyFormatError("task lifecycle_status is invalid")
        for field_name in ("progress", "result", "error"):
            _json(task.get(field_name), f"task {field_name}")
        _non_negative_int(task.get("file_size_bytes"), "task file_size_bytes")
        _non_negative_int(task.get("row_version"), "task row_version")
    for document in parsed.documents:
        _reject_unknown(document, _DOCUMENT_FIELDS, "document")
        _require_string(document["document_id"], "document_id")
        status = document.get("status", "pending")
        if not isinstance(status, str) or status not in {"pending", "indexed", "failed", "deleted"}:
            raise LegacyFormatError("document status is invalid")
        if status == "deleted" and document.get("active_kg_version") is not None:
            raise LegacyFormatError("deleted document cannot have an active KG version")
        for field_name in ("kg_nodes", "kg_edges", "pages", "file_size_bytes", "active_kg_version"):
            _non_negative_int(document.get(field_name), f"document {field_name}")
        _json(document.get("metadata"), "document metadata")
    for kg in parsed.kg_versions:
        _reject_unknown(kg, _KG_FIELDS, "KG version")
        document_id = _require_string(kg.get("document_id"), "KG document_id")
        if document_id not in document_ids:
            raise LegacyFormatError(f"KG document does not exist: {document_id}")
        version = kg.get("version")
        if isinstance(version, bool) or not isinstance(version, int) or version <= 0:
            raise LegacyFormatError("KG version is invalid")
        key = (document_id, version)
        if key in kg_keys:
            raise LegacyFormatError("duplicate KG version in migration input")
        kg_keys.add(key)
        if kg.get("state") not in {"staged", "ready", "active", "obsolete", "deleted"}:
            raise LegacyFormatError("KG version state is invalid")
        if not isinstance(kg.get("artifact_relpath"), str) or not kg["artifact_relpath"]:
            raise LegacyFormatError("KG artifact_relpath is required")
        manifest_sha256 = kg.get("manifest_sha256")
        if not isinstance(manifest_sha256, str) or len(manifest_sha256) != 64:
            raise LegacyFormatError("KG manifest_sha256 is required")
        try:
            int(manifest_sha256, 16)
        except ValueError as error:
            raise LegacyFormatError("KG manifest_sha256 is invalid") from error
        _non_negative_int(kg.get("node_count"), "KG node_count", default=0)
        _non_negative_int(kg.get("edge_count"), "KG edge_count", default=0)
        _json(kg.get("metadata"), "KG metadata")


def write_import(
    connection: sqlite3.Connection,
    parsed: ParsedLegacy,
    *,
    source_key: str,
    import_version: str,
    source_sha256: str,
    backup_relpath: str,
) -> dict[str, int]:
    """Validate and insert one migration batch. Caller owns the transaction."""
    _validate_inputs(parsed)
    existing_ledger = connection.execute(
        "SELECT source_sha256 FROM legacy_imports WHERE source_key = ? AND import_version = ?",
        (source_key, import_version),
    ).fetchone()
    if existing_ledger is not None:
        if existing_ledger["source_sha256"] == source_sha256:
            return {"_noop": 1}
        raise TargetConflictError("same source_key and import_version has different source bytes")

    context = legacy_context()
    scope = (context.owner_id, context.tenant_id, context.org_id, context.project_id)
    for task in parsed.tasks:
        if connection.execute(
            """SELECT 1, owner_id, tenant_id, org_id, project_id
            FROM tasks WHERE task_id = ?""",
            (task["task_id"],),
        ).fetchone() is not None:
            raise TargetConflictError(f"task already exists: {task['task_id']}")
        if connection.execute(
            """SELECT 1 FROM tasks
            WHERE task_id = ? AND owner_id = ? AND tenant_id = ? AND org_id = ? AND project_id = ?""",
            (task["task_id"], *scope),
        ).fetchone() is not None:
            raise TargetConflictError(f"task already exists: {task['task_id']}")
    for document in parsed.documents:
        if connection.execute(
            "SELECT 1 FROM documents WHERE tenant_id = ? AND document_id = ?", (context.tenant_id, document["document_id"])
        ).fetchone() is not None:
            raise TargetConflictError(f"document already exists: {document['document_id']}")
        if connection.execute(
            """SELECT 1 FROM tombstones
            WHERE resource_type = 'document' AND resource_id = ?
              AND owner_id = ? AND tenant_id = ?""",
            (document["document_id"], context.owner_id, context.tenant_id),
        ).fetchone() is not None:
            raise TargetConflictError(f"document tombstone already exists: {document['document_id']}")
    for kg in parsed.kg_versions:
        if connection.execute(
            "SELECT 1 FROM kg_versions WHERE tenant_id = ? AND document_id = ? AND version = ?",
            (context.tenant_id, kg["document_id"], kg["version"]),
        ).fetchone() is not None:
            raise TargetConflictError(f"KG version already exists: {kg['document_id']} v{kg['version']}")

    now = _utc_now()
    for task in parsed.tasks:
        created_at = _datetime(task.get("created_at"), "task created_at", now)
        updated_at = _datetime(task.get("updated_at"), "task updated_at", created_at)
        connection.execute(
            """INSERT INTO tasks (
                task_id, owner_id, tenant_id, org_id, project_id, status, lifecycle_status,
                stage, filename, file_size_bytes, source_filepath, progress_json, result_json,
                error_json, created_at, updated_at, row_version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                task["task_id"], *scope, task.get("status", "pending"), task.get("lifecycle_status", "active"),
                task.get("stage"), task.get("filename"), task.get("file_size_bytes"), task.get("source_filepath"),
                _json(task.get("progress"), "task progress"), _json(task.get("result"), "task result"),
                _json(task.get("error"), "task error"), created_at, updated_at,
                _non_negative_int(task.get("row_version"), "task row_version", default=0),
            ),
        )

    active_versions = {
        kg["document_id"]: kg["version"] for kg in parsed.kg_versions if kg["state"] == "active"
    }
    for document in parsed.documents:
        status = document.get("status", "pending")
        active = active_versions.get(document["document_id"])
        if status == "deleted":
            active = None
        created_at = _datetime(document.get("created_at"), "document created_at", now)
        updated_at = _datetime(document.get("updated_at"), "document updated_at", created_at)
        connection.execute(
            """INSERT INTO documents (
                tenant_id, document_id, owner_id, org_id, project_id, filename, status,
                kg_nodes, kg_edges, pages, indexed_at, file_size_bytes, filepath,
                active_kg_version, metadata_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                context.tenant_id, document["document_id"], context.owner_id, context.org_id, context.project_id,
                document.get("filename"), status, document.get("kg_nodes", 0), document.get("kg_edges", 0),
                document.get("pages"), document.get("indexed_at"), document.get("file_size_bytes"), document.get("filepath"),
                active, _json(document.get("metadata"), "document metadata"), created_at, updated_at,
            ),
        )

    for kg in parsed.kg_versions:
        created_at = _datetime(kg.get("created_at"), "KG created_at", now)
        connection.execute(
            """INSERT INTO kg_versions (
                tenant_id, document_id, version, owner_id, org_id, project_id, state,
                artifact_relpath, manifest_sha256, node_count, edge_count, metadata_json,
                created_at, activated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                context.tenant_id, kg["document_id"], kg["version"], context.owner_id, context.org_id, context.project_id,
                kg["state"], kg["artifact_relpath"], kg["manifest_sha256"], kg.get("node_count", 0),
                kg.get("edge_count", 0), _json(kg.get("metadata"), "KG metadata"), created_at,
                now if kg["state"] == "active" else None,
            ),
        )

    for document in parsed.documents:
        if document.get("status") == "deleted":
            deleted_at = _datetime(document.get("deleted_at"), "document deleted_at", now)
            reason = document.get("deletion_reason") or document.get("reason") or "legacy document deleted"
            if not isinstance(reason, str) or not reason.strip():
                raise LegacyFormatError("deleted document tombstone reason must be non-empty")
            connection.execute(
                """INSERT INTO tombstones (
                    resource_type, resource_id, owner_id, tenant_id, deleted_at, reason
                ) VALUES (?, ?, ?, ?, ?, ?)""",
                ("document", document["document_id"], context.owner_id, context.tenant_id, deleted_at, reason),
            )

    counts = {
        "tasks": len(parsed.tasks),
        "documents": len(parsed.documents),
        "kg_versions": len(parsed.kg_versions),
        "tombstones": sum(document.get("status") == "deleted" for document in parsed.documents),
    }
    connection.execute(
        """INSERT INTO legacy_imports
        (source_key, import_version, source_sha256, backup_relpath, counts_json, committed_at)
        VALUES (?, ?, ?, ?, ?, ?)""",
        (source_key, import_version, source_sha256, backup_relpath, json.dumps(counts), now),
    )
    return counts
