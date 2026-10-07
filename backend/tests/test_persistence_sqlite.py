from concurrent.futures import ThreadPoolExecutor
import sqlite3
import threading

import pytest

import persistence.sqlite as sqlite_persistence
from persistence.schema import initialize_database
from persistence.sqlite import connect, transaction


def test_initialize_database_retries_concurrent_first_wal_initialization(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "state.sqlite3"
    original_connect = sqlite3.connect
    wal_barrier = threading.Barrier(2)
    wal_calls = 0
    wal_calls_lock = threading.Lock()

    class ConnectionProxy:
        def __init__(self, connection):
            self._connection = connection

        @property
        def row_factory(self):
            return self._connection.row_factory

        @row_factory.setter
        def row_factory(self, value):
            self._connection.row_factory = value

        def execute(self, sql, parameters=()):
            nonlocal wal_calls
            if sql == "PRAGMA journal_mode = WAL":
                with wal_calls_lock:
                    wal_calls += 1
                    should_block = wal_calls <= 2
                if should_block:
                    wal_barrier.wait(timeout=5)
                    raise sqlite3.OperationalError("database is locked")
            return self._connection.execute(sql, parameters)

        def __getattr__(self, name):
            return getattr(self._connection, name)

    monkeypatch.setattr(
        sqlite_persistence.sqlite3,
        "connect",
        lambda *args, **kwargs: ConnectionProxy(original_connect(*args, **kwargs)),
    )

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(initialize_database, db_path) for _ in range(2)]
        for future in futures:
            future.result()

    with connect(db_path) as conn:
        assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
        assert conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0] == 1


def test_initialize_database_creates_schema_and_connection_pragmas(tmp_path) -> None:
    db_path = tmp_path / "state.sqlite3"

    initialize_database(db_path)

    with connect(db_path) as conn:
        tables = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        assert {
            "schema_migrations",
            "tasks",
            "documents",
            "kg_versions",
            "tombstones",
        }.issubset(tables)
        assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == 10_000
        assert isinstance(conn.row_factory, type(sqlite3.Row))


def test_initialize_database_is_idempotent_without_changing_schema_or_data(tmp_path) -> None:
    db_path = tmp_path / "state.sqlite3"

    initialize_database(db_path)
    with transaction(db_path) as conn:
        conn.execute(
            "INSERT INTO tasks (task_id, owner_id, tenant_id, org_id, project_id, filename) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("task-1", "owner-1", "tenant-1", "org-1", "project-1", "file.pdf"),
        )
        before_schema = conn.execute(
            "SELECT type, name, tbl_name, sql FROM sqlite_master "
            "WHERE type IN ('table', 'index') ORDER BY type, name"
        ).fetchall()

    initialize_database(db_path)

    with connect(db_path) as conn:
        after_schema = conn.execute(
            "SELECT type, name, tbl_name, sql FROM sqlite_master "
            "WHERE type IN ('table', 'index') ORDER BY type, name"
        ).fetchall()
        assert [tuple(row) for row in after_schema] == [tuple(row) for row in before_schema]
        assert conn.execute("SELECT task_id FROM tasks").fetchall()[0][0] == "task-1"
        assert conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0] == 1


def test_schema_exposes_required_constraints_and_indexes(tmp_path) -> None:
    db_path = tmp_path / "state.sqlite3"
    initialize_database(db_path)

    with connect(db_path) as conn:
        documents_sql = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'documents'"
        ).fetchone()[0]
        kg_sql = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'kg_versions'"
        ).fetchone()[0]
        assert "UNIQUE (tenant_id, document_id, owner_id, org_id, project_id)" in documents_sql
        assert "FOREIGN KEY (tenant_id, document_id, owner_id, org_id, project_id)" in kg_sql
        assert conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'index' AND name = 'one_active_kg_per_document'"
        ).fetchone()
        columns = {
            row[1]: row for row in conn.execute("PRAGMA table_info(documents)")
        }
        assert columns["tenant_id"][3] == 1
        assert columns["document_id"][3] == 1
        assert columns["owner_id"][3] == 1


def test_transaction_commits_all_writes_on_success(tmp_path) -> None:
    db_path = tmp_path / "state.sqlite3"
    initialize_database(db_path)

    with transaction(db_path) as conn:
        conn.execute(
            "INSERT INTO tasks (task_id, owner_id, tenant_id, org_id, project_id, filename) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("task-committed", "owner-1", "tenant-1", "org-1", "project-1", "file.pdf"),
        )

    with connect(db_path) as conn:
        assert conn.execute(
            "SELECT filename FROM tasks WHERE task_id = ?", ("task-committed",)
        ).fetchone()[0] == "file.pdf"


def test_transaction_rolls_back_all_writes_on_exception(tmp_path) -> None:
    db_path = tmp_path / "state.sqlite3"
    initialize_database(db_path)

    with pytest.raises(RuntimeError, match="abort transaction"):
        with transaction(db_path) as conn:
            conn.execute(
                "INSERT INTO tasks (task_id, owner_id, tenant_id, org_id, project_id, filename) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                ("task-1", "owner-1", "tenant-1", "org-1", "project-1", "file.pdf"),
            )
            raise RuntimeError("abort transaction")

    with connect(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0] == 0


def test_kg_versions_require_document_and_allow_one_active_version(tmp_path) -> None:
    db_path = tmp_path / "state.sqlite3"
    initialize_database(db_path)

    with transaction(db_path) as conn:
        conn.execute(
            "INSERT INTO documents (tenant_id, document_id, owner_id, org_id, project_id, filename) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("tenant-1", "doc-1", "owner-1", "org-1", "project-1", "file.pdf"),
        )
        conn.execute(
            "INSERT INTO kg_versions "
            "(tenant_id, document_id, version, owner_id, org_id, project_id, state) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("tenant-1", "doc-1", 1, "owner-1", "org-1", "project-1", "active"),
        )

    with pytest.raises(sqlite3.IntegrityError):
        with transaction(db_path) as conn:
            conn.execute(
                "INSERT INTO kg_versions "
                "(tenant_id, document_id, version, owner_id, org_id, project_id, state) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                ("tenant-1", "doc-1", 2, "owner-1", "org-1", "project-1", "active"),
            )

    with pytest.raises(sqlite3.IntegrityError):
        with transaction(db_path) as conn:
            conn.execute(
                "INSERT INTO kg_versions "
                "(tenant_id, document_id, version, owner_id, org_id, project_id, state) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                ("tenant-1", "doc-1", 2, "owner-2", "org-1", "project-1", "ready"),
            )

    with pytest.raises(sqlite3.IntegrityError):
        with transaction(db_path) as conn:
            conn.execute(
                "INSERT INTO kg_versions "
                "(tenant_id, document_id, version, owner_id, org_id, project_id, state) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                ("tenant-1", "doc-1", 3, "owner-1", "org-2", "project-1", "ready"),
            )

    with pytest.raises(sqlite3.IntegrityError):
        with transaction(db_path) as conn:
            conn.execute(
                "INSERT INTO kg_versions "
                "(tenant_id, document_id, version, owner_id, org_id, project_id, state) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                ("tenant-1", "doc-1", 4, "owner-1", "org-1", "project-2", "ready"),
            )

    with pytest.raises(sqlite3.IntegrityError):
        with transaction(db_path) as conn:
            conn.execute(
                "INSERT INTO kg_versions "
                "(tenant_id, document_id, version, owner_id, org_id, project_id, state) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                ("tenant-2", "doc-1", 5, "owner-1", "org-1", "project-1", "ready"),
            )

    with pytest.raises(sqlite3.IntegrityError):
        with transaction(db_path) as conn:
            conn.execute(
                "INSERT INTO kg_versions "
                "(tenant_id, document_id, version, owner_id, org_id, project_id, state) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                ("tenant-1", "doc-2", 6, "owner-1", "org-1", "project-1", "ready"),
            )


def test_documents_status_has_contract_and_default(tmp_path) -> None:
    db_path = tmp_path / "state.sqlite3"
    initialize_database(db_path)

    with transaction(db_path) as conn:
        conn.execute(
            "INSERT INTO documents (tenant_id, document_id, owner_id, org_id, project_id, filename) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("tenant-1", "doc-1", "owner-1", "org-1", "project-1", "file.pdf"),
        )
        assert conn.execute(
            "SELECT status FROM documents WHERE tenant_id = ? AND document_id = ?",
            ("tenant-1", "doc-1"),
        ).fetchone()[0] == "pending"

    for status in ("pending", "indexed", "failed", "deleted"):
        with transaction(db_path) as conn:
            conn.execute(
                "INSERT INTO documents "
                "(tenant_id, document_id, owner_id, org_id, project_id, status) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                ("tenant-1", f"{status}-doc", "owner-1", "org-1", "project-1", status),
            )

    with pytest.raises(sqlite3.IntegrityError):
        with transaction(db_path) as conn:
            conn.execute(
                "INSERT INTO documents "
                "(tenant_id, document_id, owner_id, org_id, project_id, status) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                ("tenant-1", "invalid-status", "owner-1", "org-1", "project-1", "unknown"),
            )

    with pytest.raises(sqlite3.IntegrityError):
        with transaction(db_path) as conn:
            conn.execute(
                "INSERT INTO documents "
                "(tenant_id, document_id, owner_id, org_id, project_id, status) "
                "VALUES (?, ?, ?, ?, ?, NULL)",
                ("tenant-1", "null-status", "owner-1", "org-1", "project-1"),
            )


def test_status_and_scope_constraints_reject_invalid_values(tmp_path) -> None:
    db_path = tmp_path / "state.sqlite3"
    initialize_database(db_path)

    invalid_tasks = (
        ("status", "unknown", "active"),
        ("lifecycle_status", "pending", "unknown"),
    )
    for field_name, status, lifecycle_status in invalid_tasks:
        with pytest.raises(sqlite3.IntegrityError):
            with transaction(db_path) as conn:
                conn.execute(
                    "INSERT INTO tasks "
                    "(task_id, owner_id, tenant_id, org_id, project_id, status, lifecycle_status) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        f"invalid-{field_name}",
                        "owner-1",
                        "tenant-1",
                        "org-1",
                        "project-1",
                        status,
                        lifecycle_status,
                    ),
                )

    with transaction(db_path) as conn:
        conn.execute(
            "INSERT INTO documents "
            "(tenant_id, document_id, owner_id, org_id, project_id) "
            "VALUES (?, ?, ?, ?, ?)",
            ("tenant-1", "doc-1", "owner-1", "org-1", "project-1"),
        )

    with pytest.raises(sqlite3.IntegrityError):
        with transaction(db_path) as conn:
            conn.execute(
                "INSERT INTO kg_versions "
                "(tenant_id, document_id, version, owner_id, org_id, project_id, state) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                ("tenant-1", "doc-1", 1, "owner-1", "org-1", "project-1", "invalid"),
            )

    for column in ("owner_id", "tenant_id", "org_id", "project_id"):
        values = {
            "owner_id": "owner-1",
            "tenant_id": "tenant-1",
            "org_id": "org-1",
            "project_id": "project-1",
        }
        values[column] = None
        with pytest.raises(sqlite3.IntegrityError):
            with transaction(db_path) as conn:
                conn.execute(
                    "INSERT INTO tasks "
                    "(task_id, owner_id, tenant_id, org_id, project_id) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (
                        f"null-{column}",
                        values["owner_id"],
                        values["tenant_id"],
                        values["org_id"],
                        values["project_id"],
                    ),
                )


def test_tombstone_composite_primary_key_rejects_duplicates(tmp_path) -> None:
    db_path = tmp_path / "state.sqlite3"
    initialize_database(db_path)
    values = (
        "document",
        "doc-1",
        "owner-1",
        "tenant-1",
        "2026-09-19T00:00:00+00:00",
        "cleanup",
    )

    with transaction(db_path) as conn:
        conn.execute(
            "INSERT INTO tombstones "
            "(resource_type, resource_id, owner_id, tenant_id, deleted_at, reason) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            values,
        )

    with pytest.raises(sqlite3.IntegrityError):
        with transaction(db_path) as conn:
            conn.execute(
                "INSERT INTO tombstones "
                "(resource_type, resource_id, owner_id, tenant_id, deleted_at, reason) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                values,
            )


def test_schema_checksum_mismatch_raises_runtime_error(tmp_path) -> None:
    db_path = tmp_path / "state.sqlite3"
    initialize_database(db_path)

    with connect(db_path) as conn:
        conn.execute("UPDATE schema_migrations SET checksum = 'tampered'")
        conn.commit()

    with pytest.raises(RuntimeError, match="schema checksum mismatch"):
        initialize_database(db_path)
