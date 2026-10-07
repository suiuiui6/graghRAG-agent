"""SQLite-backed, tenant-scoped document persistence with tombstone deletion."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from .context import AccessContext
from .schema import initialize_database
from .sqlite import connect, transaction


_DOCUMENT_STATUSES = frozenset({"pending", "indexed", "failed", "deleted"})
_SCOPE_COLUMNS = ("owner_id", "tenant_id", "org_id", "project_id")
_DOCUMENT_COLUMNS = (
    "filename",
    "status",
    "kg_nodes",
    "kg_edges",
    "pages",
    "indexed_at",
    "file_size_bytes",
    "filepath",
    "active_kg_version",
    "metadata_json",
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("persisted datetime must be timezone-aware")
    return parsed


def _serialize_datetime(value: datetime | str | None, *, field_name: str) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        parsed = _parse_datetime(value)
        return parsed.isoformat()
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value.isoformat()


def _validate_identifier(value: object, *, field_name: str, allow_tenant_separator: bool = False) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    if "\x00" in value or "\\" in value or ".." in value:
        raise ValueError(f"{field_name} must not contain a traversal sequence")
    if not allow_tenant_separator and "/" in value:
        raise ValueError(f"{field_name} must not contain a path separator")
    return value


def _validate_non_negative_int(value: object, *, field_name: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative integer")
    return value


class DocumentStore:
    """Persist document records without allowing cross-scope access or resurrection."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        initialize_database(self.db_path)

    @staticmethod
    def _validate_context(context: AccessContext) -> None:
        for field_name in ("owner_id", "org_id", "project_id"):
            _validate_identifier(getattr(context, field_name), field_name=field_name)
        _validate_identifier(
            context.tenant_id,
            field_name="tenant_id",
            allow_tenant_separator=True,
        )

    @classmethod
    def _scope_values(cls, context: AccessContext) -> tuple[str, ...]:
        cls._validate_context(context)
        return tuple(getattr(context, column) for column in _SCOPE_COLUMNS)

    @staticmethod
    def _scope_predicate(table_alias: str | None = None) -> str:
        prefix = f"{table_alias}." if table_alias else ""
        return " AND ".join(f"{prefix}{column} = ?" for column in _SCOPE_COLUMNS)

    @classmethod
    def _has_tombstone(cls, connection: Any, context: AccessContext, document_id: str) -> bool:
        """Check tombstones through their retained document ownership row."""
        row = connection.execute(
            f"""
            SELECT 1
            FROM tombstones AS tombstone
            JOIN documents AS document
              ON document.tenant_id = tombstone.tenant_id
             AND document.document_id = tombstone.resource_id
             AND document.owner_id = tombstone.owner_id
            WHERE tombstone.resource_type = ?
              AND tombstone.resource_id = ?
              AND tombstone.owner_id = ?
              AND tombstone.tenant_id = ?
              AND {cls._scope_predicate("document")}
            """,
            ("document", document_id, context.owner_id, context.tenant_id, *cls._scope_values(context)),
        ).fetchone()
        return row is not None

    @staticmethod
    def _decode_document(row: Any) -> dict[str, Any]:
        document = dict(row)
        raw_metadata = document.pop("metadata_json")
        document["metadata"] = json.loads(raw_metadata) if raw_metadata is not None else None
        for field_name in ("indexed_at", "created_at", "updated_at"):
            if document[field_name] is not None:
                document[field_name] = _parse_datetime(document[field_name])
        return document

    @staticmethod
    def _document_values(document: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        if not isinstance(document, dict):
            raise ValueError("document must be a dictionary")
        document_id = _validate_identifier(document.get("document_id"), field_name="document_id")
        status = document.get("status", "indexed")
        if status not in _DOCUMENT_STATUSES - {"deleted"}:
            raise ValueError("document status must be pending, indexed, or failed")

        metadata = document.get("metadata")
        if metadata is not None and not isinstance(metadata, dict):
            raise ValueError("metadata must be a dictionary or None")
        try:
            metadata_json = json.dumps(metadata, ensure_ascii=False) if metadata is not None else None
        except (TypeError, ValueError) as error:
            raise ValueError("metadata must be JSON serializable") from error

        filename = document.get("filename")
        filepath = document.get("filepath")
        if filename is not None and not isinstance(filename, str):
            raise ValueError("filename must be a string or None")
        if filepath is not None and not isinstance(filepath, str):
            raise ValueError("filepath must be a string or None")

        values = {
            "filename": filename,
            "status": status,
            "kg_nodes": _validate_non_negative_int(document.get("kg_nodes", 0), field_name="kg_nodes") or 0,
            "kg_edges": _validate_non_negative_int(document.get("kg_edges", 0), field_name="kg_edges") or 0,
            "pages": _validate_non_negative_int(document.get("pages"), field_name="pages"),
            "indexed_at": _serialize_datetime(document.get("indexed_at"), field_name="indexed_at"),
            "file_size_bytes": _validate_non_negative_int(
                document.get("file_size_bytes"), field_name="file_size_bytes"
            ),
            "filepath": filepath,
            "active_kg_version": _validate_non_negative_int(
                document.get("active_kg_version"), field_name="active_kg_version"
            ),
            "metadata_json": metadata_json,
        }
        return document_id, values

    def upsert(self, context: AccessContext, document: dict) -> None:
        """Create or update a scoped document, without changing its ownership."""
        document_id, values = self._document_values(document)
        scope_values = self._scope_values(context)
        now = _utc_now().isoformat()

        with transaction(self.db_path) as connection:
            existing = connection.execute(
                """
                SELECT owner_id, tenant_id, org_id, project_id, status
                FROM documents
                WHERE tenant_id = ? AND document_id = ?
                """,
                (context.tenant_id, document_id),
            ).fetchone()
            if existing is not None:
                existing_scope = tuple(existing[column] for column in _SCOPE_COLUMNS)
                if existing_scope != scope_values:
                    raise PermissionError("document ownership is immutable")
            if self._has_tombstone(connection, context, document_id) or (
                existing is not None and existing["status"] == "deleted"
            ):
                raise ValueError("tombstoned documents cannot be resurrected")
            if existing is None:
                connection.execute(
                    f"""
                    INSERT INTO documents (
                        tenant_id, document_id, owner_id, org_id, project_id,
                        {", ".join(_DOCUMENT_COLUMNS)}, created_at, updated_at
                    ) VALUES ({", ".join("?" for _ in range(5 + len(_DOCUMENT_COLUMNS) + 2))})
                    """,
                    (
                        context.tenant_id,
                        document_id,
                        *scope_values[:1],
                        *scope_values[2:],
                        *(values[column] for column in _DOCUMENT_COLUMNS),
                        now,
                        now,
                    ),
                )
                return

            assignments = ", ".join(f"{column} = ?" for column in _DOCUMENT_COLUMNS)
            connection.execute(
                f"""
                UPDATE documents
                SET {assignments}, updated_at = ?
                WHERE document_id = ? AND {self._scope_predicate()} AND status != 'deleted'
                """,
                (
                    *(values[column] for column in _DOCUMENT_COLUMNS),
                    now,
                    document_id,
                    *scope_values,
                ),
            )

    def get(self, context: AccessContext, document_id: str) -> dict[str, Any] | None:
        """Return one active document visible to the exact authenticated scope."""
        document_id = _validate_identifier(document_id, field_name="document_id")
        with connect(self.db_path) as connection:
            row = connection.execute(
                f"""
                SELECT * FROM documents
                WHERE document_id = ? AND {self._scope_predicate()} AND status != 'deleted'
                """,
                (document_id, *self._scope_values(context)),
            ).fetchone()
        return self._decode_document(row) if row is not None else None

    def list(self, context: AccessContext) -> list[dict[str, Any]]:
        """Return active documents visible to the exact authenticated scope."""
        with connect(self.db_path) as connection:
            rows = connection.execute(
                f"""
                SELECT * FROM documents
                WHERE {self._scope_predicate()} AND status != 'deleted'
                ORDER BY created_at, document_id
                """,
                self._scope_values(context),
            ).fetchall()
        return [self._decode_document(row) for row in rows]

    def tombstone(self, context: AccessContext, document_id: str, *, reason: str) -> bool:
        """Atomically hide a document and deactivate all of its KG versions."""
        document_id = _validate_identifier(document_id, field_name="document_id")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("reason must be a non-empty string")
        scope_values = self._scope_values(context)
        now = _utc_now().isoformat()

        with transaction(self.db_path) as connection:
            existing = connection.execute(
                f"""
                SELECT 1 FROM documents
                WHERE document_id = ? AND {self._scope_predicate()} AND status != 'deleted'
                """,
                (document_id, *scope_values),
            ).fetchone()
            if existing is None:
                return False
            if self._has_tombstone(connection, context, document_id):
                return False

            document_update = connection.execute(
                f"""
                UPDATE documents
                SET status = 'deleted', active_kg_version = NULL, updated_at = ?
                WHERE document_id = ? AND {self._scope_predicate()} AND status != 'deleted'
                """,
                (now, document_id, *scope_values),
            )
            if document_update.rowcount != 1:
                return False
            connection.execute(
                f"""
                UPDATE kg_versions
                SET state = CASE WHEN state = 'active' THEN 'obsolete' ELSE 'deleted' END
                WHERE document_id = ? AND {self._scope_predicate()} AND state != 'deleted'
                """,
                (document_id, *scope_values),
            )
            connection.execute(
                """
                INSERT INTO tombstones (
                    resource_type, resource_id, owner_id, tenant_id, deleted_at, reason
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                ("document", document_id, context.owner_id, context.tenant_id, now, reason),
            )
        return True

    def is_tombstoned(self, context: AccessContext, document_id: str) -> bool:
        """Return whether an exact scoped document has a deletion tombstone."""
        document_id = _validate_identifier(document_id, field_name="document_id")
        with connect(self.db_path) as connection:
            return self._has_tombstone(connection, context, document_id)
