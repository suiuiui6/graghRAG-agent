from datetime import datetime, timezone

import pytest

from persistence.context import AccessContext
from persistence.document_store import DocumentStore
from persistence.sqlite import connect, transaction


@pytest.fixture
def context() -> AccessContext:
    return AccessContext(
        owner_id="owner-a",
        tenant_id="tenant-a",
        org_id="org-a",
        project_id="project-a",
    )


@pytest.fixture
def other_owner_context() -> AccessContext:
    return AccessContext(
        owner_id="owner-b",
        tenant_id="tenant-a",
        org_id="org-a",
        project_id="project-a",
    )


@pytest.fixture
def other_tenant_context() -> AccessContext:
    return AccessContext(
        owner_id="owner-a",
        tenant_id="tenant-b",
        org_id="org-b",
        project_id="project-b",
    )


@pytest.fixture
def same_tenant_other_project_context() -> AccessContext:
    return AccessContext(
        owner_id="owner-a",
        tenant_id="tenant-a",
        org_id="org-a",
        project_id="project-b",
    )


@pytest.fixture
def same_tenant_other_org_context() -> AccessContext:
    return AccessContext(
        owner_id="owner-a",
        tenant_id="tenant-a",
        org_id="org-b",
        project_id="project-a",
    )


def _document(document_id: str = "doc-1") -> dict:
    return {
        "document_id": document_id,
        "filename": "安全报告.pdf",
        "status": "indexed",
        "kg_nodes": 3,
        "kg_edges": 2,
        "pages": 8,
        "indexed_at": datetime(2026, 9, 19, 8, 9, 10, tzinfo=timezone.utc),
        "file_size_bytes": 123,
        "filepath": "/safe/uploads/doc-1.pdf",
        "active_kg_version": 1,
        "metadata": {"source": "upload", "labels": ["hse", "2026"]},
    }


def test_upsert_get_and_list_round_trip_scoped_payload(tmp_path, context, other_tenant_context) -> None:
    store = DocumentStore(tmp_path / "state.sqlite3")
    payload = _document()

    store.upsert(context, payload)
    store.upsert(other_tenant_context, _document())

    document = store.get(context, "doc-1")
    assert document is not None
    assert document["document_id"] == "doc-1"
    assert document["owner_id"] == context.owner_id
    assert document["tenant_id"] == context.tenant_id
    assert document["org_id"] == context.org_id
    assert document["project_id"] == context.project_id
    for key in (
        "filename",
        "status",
        "kg_nodes",
        "kg_edges",
        "pages",
        "file_size_bytes",
        "filepath",
        "active_kg_version",
        "metadata",
    ):
        assert document[key] == payload[key]
    assert document["indexed_at"] == payload["indexed_at"]
    assert document["created_at"].tzinfo is not None
    assert document["updated_at"].tzinfo is not None
    assert store.list(context) == [document]
    assert store.get(other_tenant_context, "doc-1") is not None


def test_scopes_prevent_foreign_reads_list_and_mutation(
    tmp_path, context, other_owner_context, other_tenant_context, same_tenant_other_project_context
) -> None:
    store = DocumentStore(tmp_path / "state.sqlite3")
    store.upsert(context, _document())

    assert store.get(other_owner_context, "doc-1") is None
    assert store.list(other_owner_context) == []
    assert store.get(other_tenant_context, "doc-1") is None
    assert store.get(same_tenant_other_project_context, "doc-1") is None
    assert store.list(same_tenant_other_project_context) == []
    assert not store.tombstone(other_owner_context, "doc-1", reason="foreign delete")
    assert not store.tombstone(other_tenant_context, "doc-1", reason="foreign delete")
    assert not store.tombstone(same_tenant_other_project_context, "doc-1", reason="foreign delete")

    retained = store.get(context, "doc-1")
    assert retained is not None
    assert retained["status"] == "indexed"
    assert retained["filepath"] == "/safe/uploads/doc-1.pdf"


def test_tombstones_are_scoped_through_the_document_ownership_row(
    tmp_path, context, same_tenant_other_project_context
) -> None:
    store = DocumentStore(tmp_path / "state.sqlite3")
    store.upsert(context, _document())
    assert store.tombstone(context, "doc-1", reason="retention cleanup")

    assert store.is_tombstoned(context, "doc-1")
    assert not store.is_tombstoned(same_tenant_other_project_context, "doc-1")
    with pytest.raises(PermissionError, match="immutable"):
        store.upsert(same_tenant_other_project_context, _document())


def test_tombstones_remain_isolated_for_same_owner_tenant_different_org(
    tmp_path, context, same_tenant_other_org_context
) -> None:
    store = DocumentStore(tmp_path / "state.sqlite3")
    store.upsert(context, _document())
    assert store.tombstone(context, "doc-1", reason="retention cleanup")

    assert not store.is_tombstoned(same_tenant_other_org_context, "doc-1")
    assert store.get(same_tenant_other_org_context, "doc-1") is None
    assert store.list(same_tenant_other_org_context) == []
    assert not store.tombstone(same_tenant_other_org_context, "doc-1", reason="foreign delete")
    with pytest.raises(PermissionError, match="immutable"):
        store.upsert(same_tenant_other_org_context, _document())

    assert store.is_tombstoned(context, "doc-1")
    assert store.get(context, "doc-1") is None
    assert store.list(context) == []


def test_upsert_cannot_hijack_different_owner_or_resurrect_tombstoned_document(
    tmp_path, context, other_owner_context
) -> None:
    store = DocumentStore(tmp_path / "state.sqlite3")
    store.upsert(context, _document())

    with pytest.raises(PermissionError, match="immutable"):
        store.upsert(other_owner_context, _document())
    assert store.get(context, "doc-1") is not None

    assert store.tombstone(context, "doc-1", reason="retention cleanup")
    with pytest.raises(ValueError, match="tombstoned"):
        store.upsert(context, _document())
    assert store.get(context, "doc-1") is None


def test_tombstone_is_idempotent_and_atomically_deactivates_related_kg_versions(tmp_path, context) -> None:
    db_path = tmp_path / "state.sqlite3"
    store = DocumentStore(db_path)
    store.upsert(context, _document())
    with transaction(db_path) as connection:
        connection.execute(
            """
            INSERT INTO kg_versions (
                tenant_id, document_id, version, owner_id, org_id, project_id, state
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                context.tenant_id,
                "doc-1",
                1,
                context.owner_id,
                context.org_id,
                context.project_id,
                "active",
            ),
        )
        connection.execute(
            """
            INSERT INTO kg_versions (
                tenant_id, document_id, version, owner_id, org_id, project_id, state
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                context.tenant_id,
                "doc-1",
                2,
                context.owner_id,
                context.org_id,
                context.project_id,
                "ready",
            ),
        )

    before_cleanup = store.get(context, "doc-1")
    assert before_cleanup is not None
    assert before_cleanup["filepath"] == "/safe/uploads/doc-1.pdf"

    assert store.tombstone(context, "doc-1", reason="user requested deletion")
    assert not store.tombstone(context, "doc-1", reason="duplicate request")
    assert store.is_tombstoned(context, "doc-1")
    assert store.get(context, "doc-1") is None
    assert store.list(context) == []

    with connect(db_path) as connection:
        document_row = connection.execute(
            """
            SELECT status, active_kg_version FROM documents
            WHERE document_id = ? AND owner_id = ? AND tenant_id = ? AND org_id = ? AND project_id = ?
            """,
            ("doc-1", context.owner_id, context.tenant_id, context.org_id, context.project_id),
        ).fetchone()
        version_states = connection.execute(
            """
            SELECT state FROM kg_versions
            WHERE document_id = ? AND owner_id = ? AND tenant_id = ? AND org_id = ? AND project_id = ?
            ORDER BY version
            """,
            ("doc-1", context.owner_id, context.tenant_id, context.org_id, context.project_id),
        ).fetchall()
        tombstone = connection.execute(
            """
            SELECT reason FROM tombstones
            WHERE resource_type = ? AND resource_id = ? AND owner_id = ? AND tenant_id = ?
            """,
            ("document", "doc-1", context.owner_id, context.tenant_id),
        ).fetchone()

    assert document_row is not None
    assert document_row["status"] == "deleted"
    assert document_row["active_kg_version"] is None
    assert [row["state"] for row in version_states] == ["obsolete", "deleted"]
    assert tombstone["reason"] == "user requested deletion"


def test_document_id_rejects_path_traversal(tmp_path, context) -> None:
    store = DocumentStore(tmp_path / "state.sqlite3")

    with pytest.raises(ValueError, match="document_id"):
        store.upsert(context, _document("../other-tenant"))
    with pytest.raises(ValueError, match="document_id"):
        store.get(context, "../other-tenant")
