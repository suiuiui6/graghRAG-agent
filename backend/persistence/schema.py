"""Core SQLite schema and migration checksum management."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from datetime import datetime, timezone

from .sqlite import transaction


SCHEMA_VERSION = 1

_SCHEMA_STATEMENTS = (
    """CREATE TABLE IF NOT EXISTS schema_migrations (
        version INTEGER PRIMARY KEY,
        checksum TEXT NOT NULL,
        applied_at TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS tasks (
        task_id TEXT PRIMARY KEY,
        owner_id TEXT NOT NULL,
        tenant_id TEXT NOT NULL,
        org_id TEXT NOT NULL,
        project_id TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending'
            CHECK (status IN ('pending', 'running', 'done', 'failed')),
        lifecycle_status TEXT NOT NULL DEFAULT 'active'
            CHECK (lifecycle_status IN ('active', 'stale', 'deleted')),
        stage TEXT,
        filename TEXT,
        file_size_bytes INTEGER,
        source_filepath TEXT,
        progress_json TEXT,
        result_json TEXT,
        error_json TEXT,
        created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
        updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
        row_version INTEGER NOT NULL DEFAULT 1
    )""",
    """CREATE TABLE IF NOT EXISTS documents (
        tenant_id TEXT NOT NULL,
        document_id TEXT NOT NULL,
        owner_id TEXT NOT NULL,
        org_id TEXT NOT NULL,
        project_id TEXT NOT NULL,
        filename TEXT,
        status TEXT NOT NULL DEFAULT 'pending'
            CHECK (status IN ('pending', 'indexed', 'failed', 'deleted')),
        kg_nodes INTEGER NOT NULL DEFAULT 0,
        kg_edges INTEGER NOT NULL DEFAULT 0,
        pages INTEGER,
        indexed_at TEXT,
        file_size_bytes INTEGER,
        filepath TEXT,
        active_kg_version INTEGER,
        metadata_json TEXT,
        created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
        updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
        PRIMARY KEY (tenant_id, document_id),
        UNIQUE (tenant_id, document_id, owner_id, org_id, project_id)
    )""",
    """CREATE TABLE IF NOT EXISTS kg_versions (
        tenant_id TEXT NOT NULL,
        document_id TEXT NOT NULL,
        version INTEGER NOT NULL,
        owner_id TEXT NOT NULL,
        org_id TEXT NOT NULL,
        project_id TEXT NOT NULL,
        state TEXT NOT NULL DEFAULT 'staged'
            CHECK (state IN ('staged', 'ready', 'active', 'obsolete', 'deleted')),
        artifact_relpath TEXT,
        manifest_sha256 TEXT,
        node_count INTEGER NOT NULL DEFAULT 0,
        edge_count INTEGER NOT NULL DEFAULT 0,
        metadata_json TEXT,
        created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
        activated_at TEXT,
        PRIMARY KEY (tenant_id, document_id, version),
        FOREIGN KEY (tenant_id, document_id, owner_id, org_id, project_id)
            REFERENCES documents (tenant_id, document_id, owner_id, org_id, project_id)
            ON UPDATE CASCADE ON DELETE RESTRICT
    )""",
    """CREATE TABLE IF NOT EXISTS tombstones (
        resource_type TEXT NOT NULL,
        resource_id TEXT NOT NULL,
        owner_id TEXT NOT NULL,
        tenant_id TEXT NOT NULL,
        deleted_at TEXT NOT NULL,
        reason TEXT,
        PRIMARY KEY (resource_type, resource_id, owner_id, tenant_id)
    )""",
    """CREATE UNIQUE INDEX IF NOT EXISTS one_active_kg_per_document
    ON kg_versions (tenant_id, document_id)
    WHERE state = 'active'""",
)

_SCHEMA_SQL = "\n\n".join(_SCHEMA_STATEMENTS)
_SCHEMA_CHECKSUM = sha256(_SCHEMA_SQL.encode("utf-8")).hexdigest()

# Migration bookkeeping is intentionally independent from schema version 1.  It
# records an import operation, not a change to the runtime business schema.
_LEGACY_IMPORTS_STATEMENT = """CREATE TABLE IF NOT EXISTS legacy_imports (
    source_key TEXT NOT NULL,
    import_version TEXT NOT NULL,
    source_sha256 TEXT NOT NULL,
    backup_relpath TEXT NOT NULL,
    counts_json TEXT NOT NULL,
    committed_at TEXT NOT NULL,
    PRIMARY KEY (source_key, import_version)
)"""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def initialize_database(db_path: str | Path) -> None:
    """Create the core schema and verify the immutable migration checksum."""
    with transaction(db_path) as connection:
        for statement in _SCHEMA_STATEMENTS:
            connection.execute(statement)
        connection.execute(_LEGACY_IMPORTS_STATEMENT)
        migration = connection.execute(
            "SELECT version, checksum FROM schema_migrations WHERE version = ?",
            (SCHEMA_VERSION,),
        ).fetchone()
        if migration is None:
            connection.execute(
                "INSERT INTO schema_migrations (version, checksum, applied_at) VALUES (?, ?, ?)",
                (SCHEMA_VERSION, _SCHEMA_CHECKSUM, _utc_now()),
            )
        elif migration["checksum"] != _SCHEMA_CHECKSUM:
            raise RuntimeError(
                f"schema checksum mismatch for version {SCHEMA_VERSION}: "
                f"expected {_SCHEMA_CHECKSUM}, got {migration['checksum']}"
            )
