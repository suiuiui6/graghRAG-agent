"""真实 SQLite 集成测试：旧 JSON/KG 数据迁移。"""

from __future__ import annotations

import hashlib
import json
from contextlib import contextmanager
from pathlib import Path
import shutil
import uuid

import pytest

from persistence.context import legacy_context
from persistence.document_store import DocumentStore
from persistence.schema import initialize_database
from persistence.sqlite import connect, transaction
from persistence.task_store import TaskStore
from persistence.migration.errors import (
    BackupError,
    LegacyFormatError,
    SourceChangedError,
    TargetConflictError,
)
from persistence.migration.backup import create_backup, verify_backup, write_failure_evidence
from persistence.migration import backup as migration_backup
from persistence.migration.domain import SourceFile
from persistence.migration.service import LegacyMigrationService
from persistence.migration.source_reader import parse_sources
from persistence.migration import service as migration_service


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def _legacy_tree(root: Path, *, versioned: bool = True) -> tuple[Path, Path, Path]:
    output = root / "output"
    kg = output / "kg" / "doc_report"
    tasks = {
        "task-legacy": {
            "task_id": "task-legacy",
            "status": "done",
            "stage": "completed",
            "filename": "报告.pdf",
            "file_size_bytes": 42,
            "source_filepath": "uploads/report.pdf",
            "created_at": "2026-09-19T08:09:10+00:00",
            "updated_at": "2026-09-19T08:10:10+00:00",
            "progress": {"percent": 100},
            "result": {"document_id": "report", "kg_nodes": 2, "kg_edges": 1},
        }
    }
    docs = [
        {
            "document_id": "report",
            "filename": "报告.pdf",
            "status": "indexed",
            "kg_nodes": 2,
            "kg_edges": 1,
            "pages": 3,
            "indexed_at": "2026-09-19T08:10:10+00:00",
            "file_size_bytes": 42,
            "filepath": "uploads/report.pdf",
            "metadata": {"legacy": True},
        }
    ]
    _write_json(output / "tasks_store.json", tasks)
    _write_json(output / "docs_store.json", docs)
    nodes = {"nodes": [{"node_id": "n1", "entity_type": "risk", "label": "火灾"}, {"node_id": "n2", "entity_type": "rule", "label": "审批"}]}
    edges = {"edges": [{"source_node_id": "n1", "target_node_id": "n2", "relation_type": "related_to"}]}
    if versioned:
        _write_json(kg / "versions.json", {
            "doc_id": "report",
            "versions": [{"version": 1, "created_at": "2026-09-19T08:10:10+00:00", "nodes": 2, "edges": 1, "status": "active"}],
            "active_version": 1,
        })
        _write_json(kg / "v1" / "nodes.json", nodes)
        _write_json(kg / "v1" / "edges.json", edges)
    else:
        _write_json(kg / "nodes.json", nodes)
        _write_json(kg / "edges.json", edges)
    return output / "tasks_store.json", output / "docs_store.json", output / "kg"


def _service(root: Path, db_path: Path, backup_root: Path | None = None) -> LegacyMigrationService:
    return LegacyMigrationService(
        db_path=db_path,
        source_root=root,
        backup_root=backup_root or root / "output" / "migration_backups",
    )


def _counts(db_path: Path) -> tuple[int, int, int, int, int, int]:
    with connect(db_path) as connection:
        return tuple(
            connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("tasks", "documents", "kg_versions", "tombstones", "legacy_imports", "schema_migrations")
        )


def test_migrates_tasks_documents_and_versioned_kg_with_byte_backup(sandbox_tmp_path) -> None:
    tasks_path, docs_path, kg_root = _legacy_tree(sandbox_tmp_path)
    db_path = sandbox_tmp_path / "state.sqlite3"
    backup_root = sandbox_tmp_path / "backups"
    original = {path: path.read_bytes() for path in (tasks_path, docs_path, *kg_root.rglob("*.json"))}

    result = _service(sandbox_tmp_path, db_path, backup_root).migrate(import_version="v1", source_key="legacy-test")

    assert result.status == "imported"
    assert result.counts == {"tasks": 1, "documents": 1, "kg_versions": 1, "tombstones": 0}
    assert _counts(db_path) == (1, 1, 1, 0, 1, 1)
    assert all(path.read_bytes() == data for path, data in original.items())
    manifests = list(backup_root.rglob("manifest.json"))
    assert len(manifests) == 1
    manifest = json.loads(manifests[0].read_text(encoding="utf-8"))
    assert manifest["source_key"] == "legacy-test"
    assert manifest["import_version"] == "v1"
    assert manifest["files"]
    for item in manifest["files"]:
        backed_up = manifests[0].parent / item["backup_relpath"]
        assert backed_up.stat().st_size == item["size"]
        assert hashlib.sha256(backed_up.read_bytes()).hexdigest() == item["sha256"]

    context = legacy_context()
    assert TaskStore(db_path).get(context, "task-legacy")["status"] == "done"
    document = DocumentStore(db_path).get(context, "report")
    assert document is not None
    assert document["active_kg_version"] == 1
    with connect(db_path) as connection:
        row = connection.execute("SELECT state, artifact_relpath, node_count, edge_count FROM kg_versions").fetchone()
    assert tuple(row) == ("active", "output/kg/doc_report/v1", 2, 1)


def test_migrates_real_serializer_kg_envelopes_and_version_counts(sandbox_tmp_path) -> None:
    _legacy_tree(sandbox_tmp_path)
    nodes = {
        "metadata": {"schema_version": "1.1"},
        "node_count": 2,
        "nodes": [
            {
                "node_id": "n1",
                "entity_type": "risk",
                "label": "火灾",
                "properties": {},
                "page_idx": 1,
                "bbox_norm": None,
                "grounding_status": "grounded",
            },
            {
                "node_id": "n2",
                "entity_type": "rule",
                "label": "审批",
                "properties": {},
                "page_idx": 1,
                "bbox_norm": None,
                "grounding_status": "grounded",
            },
        ],
    }
    edges = {
        "metadata": {"schema_version": "1.1"},
        "edge_count": 1,
        "edges": [
            {
                "edge_id": "e1",
                "source_node_id": "n1",
                "target_node_id": "n2",
                "relation_type": "related_to",
                "properties": {},
            }
        ],
    }
    _write_json(sandbox_tmp_path / "output/kg/doc_report/v1/nodes.json", nodes)
    _write_json(sandbox_tmp_path / "output/kg/doc_report/v1/edges.json", edges)

    result = _service(sandbox_tmp_path, sandbox_tmp_path / "state.sqlite3").migrate(
        import_version="real-envelope"
    )

    assert result.status == "imported"
    with connect(sandbox_tmp_path / "state.sqlite3") as connection:
        row = connection.execute("SELECT node_count, edge_count FROM kg_versions").fetchone()
    assert tuple(row) == (2, 1)


@pytest.mark.parametrize("artifact", ["nodes", "edges"])
def test_real_serializer_envelope_rejects_unknown_fields(sandbox_tmp_path, artifact) -> None:
    _legacy_tree(sandbox_tmp_path)
    nodes = {
        "metadata": {"schema_version": "1.1"},
        "node_count": 2,
        "nodes": [
            {
                "node_id": "n1",
                "entity_type": "risk",
                "label": "火灾",
                "properties": {},
                "page_idx": 1,
                "bbox_norm": None,
                "grounding_status": "grounded",
            },
            {
                "node_id": "n2",
                "entity_type": "rule",
                "label": "审批",
                "properties": {},
                "page_idx": 1,
                "bbox_norm": None,
                "grounding_status": "grounded",
            },
        ],
    }
    edges = {
        "metadata": {"schema_version": "1.1"},
        "edge_count": 1,
        "edges": [
            {
                "edge_id": "e1",
                "source_node_id": "n1",
                "target_node_id": "n2",
                "relation_type": "related_to",
                "properties": {},
            }
        ],
    }
    target = nodes["nodes"][0] if artifact == "nodes" else edges["edges"][0]
    target["unexpected_field"] = "reject me"
    _write_json(sandbox_tmp_path / "output/kg/doc_report/v1/nodes.json", nodes)
    _write_json(sandbox_tmp_path / "output/kg/doc_report/v1/edges.json", edges)

    with pytest.raises(LegacyFormatError, match="unsupported fields"):
        _service(sandbox_tmp_path, sandbox_tmp_path / f"unexpected-{artifact}.sqlite3").migrate(
            import_version=f"unexpected-{artifact}"
        )


def _assert_real_serializer_envelope_requires_field(sandbox_tmp_path, field: str) -> None:
    _legacy_tree(sandbox_tmp_path)
    nodes = {
        "metadata": {"schema_version": "1.1"},
        "node_count": 2,
        "nodes": [
            {
                "node_id": "n1",
                "entity_type": "risk",
                "label": "火灾",
                "properties": {},
                "page_idx": 1,
                "bbox_norm": None,
                "grounding_status": "grounded",
            },
            {
                "node_id": "n2",
                "entity_type": "rule",
                "label": "审批",
                "properties": {},
                "page_idx": 1,
                "bbox_norm": None,
                "grounding_status": "grounded",
            },
        ],
    }
    edges = {
        "metadata": {"schema_version": "1.1"},
        "edge_count": 1,
        "edges": [
            {
                "edge_id": "e1",
                "source_node_id": "n1",
                "target_node_id": "n2",
                "relation_type": "related_to",
                "properties": {},
            }
        ],
    }
    target = nodes["nodes"][0] if field in {"properties", "grounding_status"} else edges["edges"][0]
    del target[field]
    _write_json(sandbox_tmp_path / "output/kg/doc_report/v1/nodes.json", nodes)
    _write_json(sandbox_tmp_path / "output/kg/doc_report/v1/edges.json", edges)

    with pytest.raises(LegacyFormatError, match="required"):
        _service(sandbox_tmp_path, sandbox_tmp_path / f"real-envelope-{field}.sqlite3").migrate(
            import_version=f"real-envelope-{field}"
        )


@pytest.mark.parametrize("field", ["properties", "grounding_status", "edge_id"])
def test_real_serializer_envelope_rejects_missing_required_fields(sandbox_tmp_path, field) -> None:
    _assert_real_serializer_envelope_requires_field(sandbox_tmp_path, field)


@pytest.mark.parametrize("field", ["node_count", "edge_count"])
def test_real_serializer_envelope_requires_declared_count(sandbox_tmp_path, field) -> None:
    _legacy_tree(sandbox_tmp_path)
    nodes_path = sandbox_tmp_path / "output/kg/doc_report/v1/nodes.json"
    edges_path = sandbox_tmp_path / "output/kg/doc_report/v1/edges.json"
    path = nodes_path if field == "node_count" else edges_path
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["metadata"] = {"schema_version": "1.1"}
    payload[field] = len(payload["nodes" if field == "node_count" else "edges"])
    del payload[field]
    _write_json(path, payload)

    with pytest.raises(LegacyFormatError, match="required for serializer envelope"):
        _service(sandbox_tmp_path, sandbox_tmp_path / f"missing-{field}.sqlite3").migrate(
            import_version=f"missing-{field}"
        )


@pytest.mark.parametrize("field", ["nodes", "edges"])
def test_version_metadata_requires_declared_counts(sandbox_tmp_path, field) -> None:
    _legacy_tree(sandbox_tmp_path)
    versions_path = sandbox_tmp_path / "output/kg/doc_report/versions.json"
    versions = json.loads(versions_path.read_text(encoding="utf-8"))
    del versions["versions"][0][field]
    _write_json(versions_path, versions)

    with pytest.raises(LegacyFormatError, match=f"version metadata {field} is required"):
        _service(sandbox_tmp_path, sandbox_tmp_path / f"missing-version-{field}.sqlite3").migrate(
            import_version=f"missing-version-{field}"
        )


@pytest.mark.parametrize(
    ("name", "mutate"),
    [
        (
            "envelope-count",
            lambda root: _write_json(
                root / "output/kg/doc_report/v1/nodes.json",
                {
                    "metadata": {"schema_version": "1.1"},
                    "node_count": 99,
                    "nodes": [{"node_id": "n1", "entity_type": "risk", "label": "火灾"}],
                },
            ),
        ),
        (
            "version-count",
            lambda root: _write_json(
                root / "output/kg/doc_report/versions.json",
                {
                    "doc_id": "report",
                    "versions": [
                        {
                            "version": 1,
                            "created_at": "2026-09-19T08:10:10+00:00",
                            "nodes": 99,
                            "edges": 1,
                            "status": "active",
                        }
                    ],
                    "active_version": 1,
                },
            ),
        ),
    ],
)
def test_kg_count_mismatches_reject_the_batch(sandbox_tmp_path, name, mutate) -> None:
    _legacy_tree(sandbox_tmp_path)
    mutate(sandbox_tmp_path)

    with pytest.raises(LegacyFormatError, match="count does not match"):
        _service(sandbox_tmp_path, sandbox_tmp_path / f"{name}.sqlite3").migrate(
            import_version=name
        )


@pytest.mark.parametrize("missing_field", ["relation_type", "entity_type"])
def test_kg_required_relation_and_node_type_are_rejected(sandbox_tmp_path, missing_field) -> None:
    _legacy_tree(sandbox_tmp_path)
    if missing_field == "relation_type":
        edge_path = sandbox_tmp_path / "output/kg/doc_report/v1/edges.json"
        edges = json.loads(edge_path.read_text(encoding="utf-8"))
        del edges["edges"][0][missing_field]
        _write_json(edge_path, edges)
    else:
        node_path = sandbox_tmp_path / "output/kg/doc_report/v1/nodes.json"
        nodes = json.loads(node_path.read_text(encoding="utf-8"))
        del nodes["nodes"][0][missing_field]
        _write_json(node_path, nodes)

    with pytest.raises(LegacyFormatError, match="required|must be"):
        _service(sandbox_tmp_path, sandbox_tmp_path / f"missing-{missing_field}.sqlite3").migrate(
            import_version=f"missing-{missing_field}"
        )


def test_kg_duplicate_edge_identity_is_rejected(sandbox_tmp_path) -> None:
    _legacy_tree(sandbox_tmp_path)
    edge_path = sandbox_tmp_path / "output/kg/doc_report/v1/edges.json"
    edges = json.loads(edge_path.read_text(encoding="utf-8"))["edges"]
    edges.append({**edges[0], "edge_id": "e2"})
    _write_json(edge_path, {"edges": edges})

    with pytest.raises(LegacyFormatError, match="edge identity"):
        _service(sandbox_tmp_path, sandbox_tmp_path / "duplicate-edge.sqlite3").migrate(
            import_version="duplicate-edge"
        )


def test_kg_malformed_edge_endpoint_is_rejected(sandbox_tmp_path) -> None:
    _legacy_tree(sandbox_tmp_path)
    edge_path = sandbox_tmp_path / "output/kg/doc_report/v1/edges.json"
    edges = json.loads(edge_path.read_text(encoding="utf-8"))
    edges["edges"][0]["target_node_id"] = {"node": "n2"}
    _write_json(edge_path, edges)

    with pytest.raises(LegacyFormatError, match="endpoint"):
        _service(sandbox_tmp_path, sandbox_tmp_path / "bad-endpoint.sqlite3").migrate(
            import_version="bad-endpoint"
        )


def test_flat_document_kg_is_imported_as_active_v1(sandbox_tmp_path) -> None:
    _legacy_tree(sandbox_tmp_path, versioned=False)
    db_path = sandbox_tmp_path / "state.sqlite3"

    result = _service(sandbox_tmp_path, db_path).migrate(import_version="v1")

    assert result.status == "imported"
    with connect(db_path) as connection:
        row = connection.execute("SELECT version, state, artifact_relpath FROM kg_versions").fetchone()
    assert tuple(row) == (1, "active", "output/kg/doc_report")


def test_same_source_and_version_is_noop_without_new_backup(sandbox_tmp_path) -> None:
    _legacy_tree(sandbox_tmp_path)
    db_path = sandbox_tmp_path / "state.sqlite3"
    backup_root = sandbox_tmp_path / "backups"
    service = _service(sandbox_tmp_path, db_path, backup_root)
    first = service.migrate(import_version="v1", source_key="same")
    manifests_before = sorted(backup_root.rglob("manifest.json"))
    second = service.migrate(import_version="v1", source_key="same")

    assert first.status == "imported"
    assert second.status == "noop"
    assert sorted(backup_root.rglob("manifest.json")) == manifests_before
    assert _counts(db_path) == (1, 1, 1, 0, 1, 1)


def test_changed_source_same_version_is_rejected_without_new_import(sandbox_tmp_path) -> None:
    tasks_path, _, _ = _legacy_tree(sandbox_tmp_path)
    db_path = sandbox_tmp_path / "state.sqlite3"
    backup_root = sandbox_tmp_path / "backups"
    service = _service(sandbox_tmp_path, db_path, backup_root)
    service.migrate(import_version="v1", source_key="changed")
    before = _counts(db_path)
    manifests_before = sorted(backup_root.rglob("manifest.json"))
    tasks_path.write_text(tasks_path.read_text(encoding="utf-8").replace("报告.pdf", "新报告.pdf"), encoding="utf-8")

    with pytest.raises(SourceChangedError):
        service.migrate(import_version="v1", source_key="changed")

    assert _counts(db_path) == before
    assert sorted(backup_root.rglob("manifest.json")) == manifests_before
    assert len(list(manifests_before[0].parent.glob("failure.json"))) == 1


def test_second_ledger_hash_conflict_records_both_backups(sandbox_tmp_path, monkeypatch) -> None:
    _legacy_tree(sandbox_tmp_path)
    db_path = sandbox_tmp_path / "state.sqlite3"
    backup_root = sandbox_tmp_path / "backups"
    first = _service(sandbox_tmp_path, db_path, backup_root).migrate(
        import_version="v1", source_key="same"
    )
    service = _service(sandbox_tmp_path, db_path, backup_root)
    original_transaction = migration_service.transaction_with_pre_commit
    transaction_calls = 0

    @contextmanager
    def insert_conflicting_ledger(path, *, pre_commit):
        nonlocal transaction_calls
        transaction_calls += 1
        with original_transaction(path, pre_commit=pre_commit) as connection:
            if transaction_calls == 1:
                connection.execute(
                    "INSERT INTO legacy_imports "
                    "(source_key, import_version, source_sha256, backup_relpath, counts_json, committed_at) "
                    "SELECT ?, ?, ?, backup_relpath, counts_json, committed_at "
                    "FROM legacy_imports WHERE source_key = ? AND import_version = ?",
                    ("new", "v2", "f" * 64, "same", "v1"),
                )
            yield connection

    monkeypatch.setattr(migration_service, "transaction_with_pre_commit", insert_conflicting_ledger)
    with pytest.raises(SourceChangedError, match="existing import"):
        service.migrate(import_version="v2", source_key="new")

    batches = sorted(path.parent for path in backup_root.rglob("manifest.json"))
    assert len(batches) == 2
    assert (backup_root / first.backup_relpath / "failure.json").is_file()
    assert all((batch / "failure.json").is_file() for batch in batches)


@pytest.mark.parametrize(
    ("case", "mutate"),
    [
        ("truncated", lambda root: (root / "output/tasks_store.json").write_text("{", encoding="utf-8")),
        ("invalid-status", lambda root: _write_json(root / "output/tasks_store.json", {"t": {"task_id": "t", "status": "wat"}})),
        ("naive-datetime", lambda root: _write_json(root / "output/tasks_store.json", {"t": {"task_id": "t", "status": "done", "created_at": "2026-09-19T08:00:00"}})),
        ("missing-edge-pair", lambda root: (root / "output/kg/doc_report/v1/edges.json").unlink()),
        ("missing-active-version", lambda root: _write_json(root / "output/kg/doc_report/versions.json", {"doc_id": "report", "versions": []})),
    ],
)
def test_invalid_legacy_batch_rolls_back_and_preserves_sources(sandbox_tmp_path, case, mutate) -> None:
    tasks_path, docs_path, kg_root = _legacy_tree(sandbox_tmp_path)
    mutate(sandbox_tmp_path)
    db_path = sandbox_tmp_path / f"{case}.sqlite3"
    original = {path: path.read_bytes() for path in (tasks_path, docs_path, *kg_root.rglob("*.json"))}

    with pytest.raises(LegacyFormatError):
        _service(sandbox_tmp_path, db_path).migrate(import_version=case)
    assert _counts(db_path) == (0, 0, 0, 0, 0, 1)
    assert all(path.read_bytes() == data for path, data in original.items())
    assert list((sandbox_tmp_path / "output/migration_backups").rglob("manifest.json"))


def test_global_flat_kg_is_rejected(sandbox_tmp_path) -> None:
    output = sandbox_tmp_path / "output"
    _write_json(output / "tasks_store.json", {})
    _write_json(output / "docs_store.json", [{"document_id": "doc-1"}])
    _write_json(output / "kg/nodes.json", {"nodes": []})
    _write_json(output / "kg/edges.json", {"edges": []})

    with pytest.raises(LegacyFormatError, match="global"):
        _service(sandbox_tmp_path, sandbox_tmp_path / "state.sqlite3").migrate(import_version="global")


def test_explicit_non_default_scope_is_rejected(sandbox_tmp_path) -> None:
    _legacy_tree(sandbox_tmp_path)
    _write_json(sandbox_tmp_path / "output/docs_store.json", [{"document_id": "report", "org_id": "org-a"}])

    with pytest.raises(LegacyFormatError, match="scope"):
        _service(sandbox_tmp_path, sandbox_tmp_path / "state.sqlite3").migrate(import_version="scope")


def test_new_version_conflicts_are_rejected_without_upsert(sandbox_tmp_path) -> None:
    _legacy_tree(sandbox_tmp_path)
    db_path = sandbox_tmp_path / "state.sqlite3"
    service = _service(sandbox_tmp_path, db_path)
    service.migrate(import_version="v1", source_key="conflict")
    before = _counts(db_path)

    with pytest.raises(TargetConflictError):
        service.migrate(import_version="v2", source_key="other-version")
    assert _counts(db_path) == before


def test_global_task_id_conflict_is_rejected_before_insert_and_records_failure_evidence(
    sandbox_tmp_path,
) -> None:
    _legacy_tree(sandbox_tmp_path)
    db_path = sandbox_tmp_path / "foreign-task-conflict.sqlite3"
    backup_root = sandbox_tmp_path / "backups"
    service = _service(sandbox_tmp_path, db_path, backup_root)
    initialize_database(db_path)
    with transaction(db_path) as connection:
        connection.execute(
            """INSERT INTO tasks (
                task_id, owner_id, tenant_id, org_id, project_id, filename
            ) VALUES (?, ?, ?, ?, ?, ?)""",
            (
                "task-legacy",
                "foreign-owner",
                "foreign-tenant",
                "foreign-org",
                "foreign-project",
                "foreign.pdf",
            ),
        )
    before = _counts(db_path)

    with pytest.raises(TargetConflictError, match="task already exists: task-legacy"):
        service.migrate(import_version="foreign-task-conflict", source_key="legacy")

    assert _counts(db_path) == before
    with connect(db_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM legacy_imports").fetchone()[0] == 0
    failure_files = list(backup_root.rglob("failure.json"))
    assert len(failure_files) == 1
    assert failure_files[0].parent.joinpath("manifest.json").is_file()


    _legacy_tree(sandbox_tmp_path)
    db_path = sandbox_tmp_path / "state.sqlite3"
    backup_root = sandbox_tmp_path / "backups"

    result = _service(sandbox_tmp_path, db_path, backup_root).migrate(import_version="manifest")

    nodes = (sandbox_tmp_path / "output/kg/doc_report/v1/nodes.json").read_bytes()
    edges = (sandbox_tmp_path / "output/kg/doc_report/v1/edges.json").read_bytes()
    expected_manifest_hash = hashlib.sha256(nodes + edges).hexdigest()
    with connect(db_path) as connection:
        row = connection.execute("SELECT manifest_sha256 FROM kg_versions").fetchone()
    assert row["manifest_sha256"] == expected_manifest_hash
    assert (backup_root / result.backup_relpath / "manifest.json").is_file()


def test_tasks_and_docs_have_strict_root_shapes_and_task_map_identity(sandbox_tmp_path) -> None:
    _legacy_tree(sandbox_tmp_path)
    db_path = sandbox_tmp_path / "strict.sqlite3"
    tasks_path = sandbox_tmp_path / "output/tasks_store.json"
    docs_path = sandbox_tmp_path / "output/docs_store.json"

    _write_json(tasks_path, [{"task_id": "task-legacy", "status": "done"}])
    with pytest.raises(LegacyFormatError, match="root must be an object map"):
        _service(sandbox_tmp_path, db_path).migrate(import_version="task-list")

    _legacy_tree(sandbox_tmp_path)
    _write_json(tasks_path, {"wrong-key": {"task_id": "task-legacy", "status": "done"}})
    with pytest.raises(LegacyFormatError, match="map key"):
        _service(sandbox_tmp_path, db_path).migrate(import_version="task-key")

    _legacy_tree(sandbox_tmp_path)
    _write_json(docs_path, {"report": {"document_id": "report"}})
    with pytest.raises(LegacyFormatError, match="root must be an array"):
        _service(sandbox_tmp_path, db_path).migrate(import_version="docs-map")


def test_deleted_document_imports_tombstone_and_no_readable_business_state(sandbox_tmp_path) -> None:
    _legacy_tree(sandbox_tmp_path)
    docs_path = sandbox_tmp_path / "output/docs_store.json"
    document = json.loads(docs_path.read_text(encoding="utf-8"))[0]
    document.update({"status": "deleted", "active_kg_version": None, "deletion_reason": "legacy cleanup"})
    _write_json(docs_path, [document])
    kg_versions = sandbox_tmp_path / "output/kg/doc_report/versions.json"
    metadata = json.loads(kg_versions.read_text(encoding="utf-8"))
    metadata["versions"][0]["status"] = "deleted"
    metadata["active_version"] = 1
    _write_json(kg_versions, metadata)

    db_path = sandbox_tmp_path / "deleted.sqlite3"
    result = _service(sandbox_tmp_path, db_path).migrate(import_version="deleted")

    assert result.counts["tombstones"] == 1
    context = legacy_context()
    assert DocumentStore(db_path).get(context, "report") is None
    assert DocumentStore(db_path).is_tombstoned(context, "report")
    with connect(db_path) as connection:
        row = connection.execute("SELECT status, active_kg_version FROM documents").fetchone()
        kg_state = connection.execute("SELECT state FROM kg_versions").fetchone()[0]
    assert tuple(row) == ("deleted", None)
    assert kg_state == "deleted"




def test_preflight_evidence(sandbox_tmp_path, monkeypatch) -> None:
    _legacy_tree(sandbox_tmp_path)
    db_path = sandbox_tmp_path / "preflight.sqlite3"
    backup_root = Path("C:/tmp") / f"preflight-{uuid.uuid4().hex}"
    backup_root.mkdir()
    service = _service(sandbox_tmp_path, db_path, backup_root)

    @contextmanager
    def failing_transaction(path):
        raise RuntimeError("preflight unavailable")
        yield path

    monkeypatch.setattr(migration_service, "transaction", failing_transaction)

    with pytest.raises(RuntimeError, match="preflight unavailable"):
        service.migrate(import_version="preflight-failure", source_key="legacy")

    evidence = list(backup_root.rglob("*.failure.json"))
    assert len(evidence) == 1
    payload = json.loads(evidence[0].read_text(encoding="utf-8"))
    assert payload["error_type"] == "RuntimeError"
    assert payload["error_message"] == "preflight unavailable"
    assert _counts(db_path) == (0, 0, 0, 0, 0, 1)


def test_failure_evidence_persists_safe_cause_chain_and_legacy_error_field(tmp_path) -> None:
    backup_root = tmp_path / "backups"
    batch_dir = backup_root / "b"
    batch_dir.mkdir(parents=True)
    try:
        raise ValueError("inner input failure")
    except ValueError as cause:
        try:
            raise RuntimeError("outer migration failure") from cause
        except RuntimeError as error:
            write_failure_evidence(
                backup_root,
                "b",
                error,
                source_key="legacy-source",
                import_version="v1",
            )

    payload = json.loads((batch_dir / "failure.json").read_text(encoding="utf-8"))
    assert payload["error"] == "outer migration failure"
    assert payload["error_type"] == "RuntimeError"
    assert payload["error_message"] == "outer migration failure"
    assert payload["cause_chain"] == [
        {"error_type": "ValueError", "error_message": "inner input failure"}
    ]
    assert payload["timestamp"]
    assert payload["source_key"] == "legacy-source"
    assert payload["import_version"] == "v1"


def test_failure_evidence_redacts_credential_shaped_error_text(tmp_path) -> None:
    backup_root = tmp_path / "backups"
    batch_dir = backup_root / "b"
    batch_dir.mkdir(parents=True)
    error = RuntimeError("api_key=sk-test-secret token=do-not-persist")

    write_failure_evidence(
        backup_root,
        "b",
        error,
        source_key="legacy-source",
        import_version="v1",
    )

    payload_text = (batch_dir / "failure.json").read_text(encoding="utf-8")
    assert "sk-test-secret" not in payload_text
    assert "do-not-persist" not in payload_text


def test_initialization_failure_is_evidenced_inside_migration_lock(
    sandbox_tmp_path, monkeypatch
) -> None:
    backup_root = Path("C:/tmp") / f"init-failure-{uuid.uuid4().hex}"
    backup_root.mkdir(parents=True)
    db_path = sandbox_tmp_path / "init-failure.sqlite3"
    service = _service(sandbox_tmp_path, db_path, backup_root)
    init_error = RuntimeError("database initialization failed")

    def fail_initialize(path):
        raise init_error

    monkeypatch.setattr(migration_service, "initialize_database", fail_initialize)

    with pytest.raises(RuntimeError) as raised:
        service.migrate(import_version="init-v1", source_key="init-source")

    assert raised.value is init_error
    evidence = list(backup_root.rglob("*.failure.json"))
    assert len(evidence) == 1
    payload = json.loads(evidence[0].read_text(encoding="utf-8"))
    assert payload["error"] == "database initialization failed"
    assert payload["error_type"] == "RuntimeError"
    assert payload["error_message"] == "database initialization failed"
    assert payload["cause_chain"] == []
    assert payload["source_key"] == "init-source"
    assert payload["import_version"] == "init-v1"


def test_parse_failure_after_backup_keeps_failure_evidence_and_business_tables_empty(sandbox_tmp_path) -> None:
    _legacy_tree(sandbox_tmp_path)
    docs_path = sandbox_tmp_path / "output/docs_store.json"
    _write_json(docs_path, [{"document_id": "report", "status": "indexed", "metadata": {"bad": float("nan")}}])
    db_path = sandbox_tmp_path / "parse-failure.sqlite3"
    backup_root = sandbox_tmp_path / "backups"

    with pytest.raises(LegacyFormatError):
        _service(sandbox_tmp_path, db_path, backup_root).migrate(import_version="parse-failure")
    assert list(backup_root.rglob("failure.json"))
    assert _counts(db_path) == (0, 0, 0, 0, 0, 1)


def test_source_change_after_write_import_rolls_back_and_records_failure_evidence(
    sandbox_tmp_path, monkeypatch
) -> None:
    _legacy_tree(sandbox_tmp_path)
    db_path = sandbox_tmp_path / "source-changed-in-transaction.sqlite3"
    backup_root = sandbox_tmp_path / "backups"
    original_write_import = migration_service.write_import
    docs_path = sandbox_tmp_path / "output/docs_store.json"

    def mutate_during_write(*args, **kwargs):
        docs_path.write_bytes(docs_path.read_bytes() + b"\n")
        return original_write_import(*args, **kwargs)

    monkeypatch.setattr(migration_service, "write_import", mutate_during_write)
    with pytest.raises(SourceChangedError):
        _service(sandbox_tmp_path, db_path, backup_root).migrate(import_version="tx-source-change")

    assert _counts(db_path) == (0, 0, 0, 0, 0, 1)
    assert list(backup_root.rglob("failure.json"))




def test_source_change_at_pre_commit_boundary_rolls_back_and_records_failure_evidence(
    sandbox_tmp_path, monkeypatch
) -> None:
    _legacy_tree(sandbox_tmp_path)
    db_path = sandbox_tmp_path / "source-changed-before-commit.sqlite3"
    backup_root = sandbox_tmp_path / "backups"
    docs_path = sandbox_tmp_path / "output/docs_store.json"
    original_transaction = migration_service.transaction_with_pre_commit

    @contextmanager
    def mutate_before_pre_commit(path, *, pre_commit):
        def mutate_then_validate():
            docs_path.write_bytes(docs_path.read_bytes() + b"\n")
            pre_commit()

        with original_transaction(path, pre_commit=mutate_then_validate) as connection:
            yield connection

    monkeypatch.setattr(migration_service, "transaction_with_pre_commit", mutate_before_pre_commit)

    with pytest.raises(SourceChangedError, match="source bytes changed"):
        _service(sandbox_tmp_path, db_path, backup_root).migrate(import_version="commit-boundary")

    assert _counts(db_path) == (0, 0, 0, 0, 0, 1)
    failure_files = list(backup_root.rglob("failure.json"))
    assert len(failure_files) == 1
    evidence = json.loads(failure_files[0].read_text(encoding="utf-8"))
    assert evidence["error"] == "source bytes changed during migration"
    assert evidence["error_type"] == "SourceChangedError"
    assert evidence["error_message"] == "source bytes changed during migration"
    assert evidence["cause_chain"] == []
    assert evidence["timestamp"]


def test_noop_rejects_invalid_ledger_committed_at_and_records_batch_evidence(
    sandbox_tmp_path,
) -> None:
    _legacy_tree(sandbox_tmp_path)
    db_path = sandbox_tmp_path / "invalid-ledger-time.sqlite3"
    backup_root = sandbox_tmp_path / "backups"
    service = _service(sandbox_tmp_path, db_path, backup_root)
    result = service.migrate(import_version="invalid-ledger-time")

    with transaction(db_path) as connection:
        connection.execute(
            "UPDATE legacy_imports SET committed_at = ? WHERE source_key = ? AND import_version = ?",
            ("2026-09-19T08:10:10", "legacy", "invalid-ledger-time"),
        )

    with pytest.raises(ValueError, match="legacy_imports.committed_at must be timezone-aware"):
        service.migrate(import_version="invalid-ledger-time")

    evidence_path = backup_root / result.backup_relpath / "failure.json"
    assert evidence_path.is_file()
    assert "legacy_imports.committed_at" in json.loads(evidence_path.read_text(encoding="utf-8"))["error"]


@pytest.mark.parametrize("created_at", [None, "2026-09-19T08:10:10", "not-a-datetime"])
def test_noop_rejects_invalid_manifest_created_at_and_records_batch_evidence(
    sandbox_tmp_path, created_at
) -> None:
    _legacy_tree(sandbox_tmp_path)
    db_path = sandbox_tmp_path / "invalid-manifest-time.sqlite3"
    backup_root = sandbox_tmp_path / "backups"
    service = _service(sandbox_tmp_path, db_path, backup_root)
    result = service.migrate(import_version="invalid-manifest-time")
    manifest_path = backup_root / result.backup_relpath / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if created_at is None:
        del manifest["created_at"]
    else:
        manifest["created_at"] = created_at
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(BackupError, match="invalid created_at"):
        service.migrate(import_version="invalid-manifest-time")

    assert (backup_root / result.backup_relpath / "failure.json").is_file()


def _assert_noop_falls_back_to_readable_failure_evidence(
    sandbox_tmp_path, damage: str
) -> None:
    _legacy_tree(sandbox_tmp_path)
    db_path = sandbox_tmp_path / f"fallback-{damage}.sqlite3"
    backup_root = Path("C:/tmp") / f"fallback-{uuid.uuid4().hex}"
    source_key = "fallback-source"
    import_version = f"fallback-{damage}"
    service = _service(sandbox_tmp_path, db_path, backup_root)
    result = service.migrate(import_version=import_version, source_key=source_key)
    manifest_paths_before = sorted(backup_root.rglob("manifest.json"))

    batch_dir = backup_root / result.backup_relpath
    if damage == "missing":
        shutil.rmtree(batch_dir)
    elif damage == "corrupt":
        shutil.rmtree(batch_dir)
        batch_dir.write_text("not a directory", encoding="utf-8")
    else:
        with transaction(db_path) as connection:
            connection.execute(
                "UPDATE legacy_imports SET backup_relpath = ? "
                "WHERE source_key = ? AND import_version = ?",
                ("../illegal-backup", source_key, import_version),
            )

    with pytest.raises(BackupError):
        service.migrate(import_version=import_version, source_key=source_key)

    evidence_paths = sorted(backup_root.rglob("*.failure.json"))
    assert len(evidence_paths) == 1
    evidence = json.loads(evidence_paths[0].read_text(encoding="utf-8"))
    assert evidence["source_key"] == source_key
    assert evidence["import_version"] == import_version
    assert evidence["error_type"] == "BackupError"
    assert sorted(backup_root.rglob("manifest.json")) == (
        manifest_paths_before if damage == "illegal" else []
    )


@pytest.mark.parametrize("damage", ["missing", "illegal", "corrupt"])
def test_noop_uses_fallback_failure_evidence_for_unusable_backup(
    sandbox_tmp_path, damage
) -> None:
    _assert_noop_falls_back_to_readable_failure_evidence(sandbox_tmp_path, damage)


def test_noop_fallback_failure_preserves_verify_error_as_cause(sandbox_tmp_path, monkeypatch) -> None:
    _legacy_tree(sandbox_tmp_path)
    db_path = sandbox_tmp_path / "fallback-error.sqlite3"
    backup_root = sandbox_tmp_path / "fallback-error"
    service = _service(sandbox_tmp_path, db_path, backup_root)
    result = service.migrate(import_version="fallback-error", source_key="fallback-source")
    shutil.rmtree(backup_root / result.backup_relpath)

    verify_error = BackupError("original verify failure")
    fallback_error = BackupError("fallback evidence failure")

    def fail_verify(*args, **kwargs):
        raise verify_error

    def fail_fallback(*args, **kwargs):
        raise fallback_error

    monkeypatch.setattr(migration_service, "verify_backup", fail_verify)
    monkeypatch.setattr(migration_service, "write_fallback_failure_evidence", fail_fallback)

    with pytest.raises(BackupError, match="fallback evidence failure") as raised:
        service.migrate(import_version="fallback-error", source_key="fallback-source")

    assert raised.value is fallback_error
    assert raised.value.__cause__ is verify_error


def test_create_backup_preserves_copy_failure_as_cause_when_batch_evidence_write_fails(
    sandbox_tmp_path, monkeypatch
) -> None:
    source_path = sandbox_tmp_path / "source.json"
    source_path.write_bytes(b"{}")
    source = SourceFile(
        source_path=str(source_path),
        relative_path="output/tasks_store.json",
        content=b"{}",
        size=2,
        sha256=hashlib.sha256(b"{}").hexdigest(),
    )
    copy_error = OSError("copy failed")

    def fail_copy(*args, **kwargs):
        raise copy_error

    original_write_text = Path.write_text

    def fail_evidence_write(self, data, *args, **kwargs):
        if self.name == "failure.json":
            raise OSError("evidence write failed")
        return original_write_text(self, data, *args, **kwargs)

    monkeypatch.setattr(migration_backup.shutil, "copyfile", fail_copy)
    monkeypatch.setattr(Path, "write_text", fail_evidence_write)

    with pytest.raises(BackupError, match="failure evidence could not be written") as raised:
        create_backup(
            (source,),
            sandbox_tmp_path / "backups",
            source_key="legacy",
            import_version="copy-evidence-failure",
        )

    assert raised.value.__cause__ is copy_error


def test_create_backup_preserves_directory_failure_as_cause_when_fallback_evidence_write_fails(
    sandbox_tmp_path, monkeypatch
) -> None:
    source_path = sandbox_tmp_path / "source.json"
    source_path.write_bytes(b"{}")
    source = SourceFile(
        source_path=str(source_path),
        relative_path="output/tasks_store.json",
        content=b"{}",
        size=2,
        sha256=hashlib.sha256(b"{}").hexdigest(),
    )
    directory_error = OSError("batch directory unavailable")

    def fail_batch_directory(root):
        raise directory_error

    def fail_fallback_evidence(*args, **kwargs):
        raise BackupError("fallback evidence unavailable")

    monkeypatch.setattr(migration_backup, "_new_batch_dir", fail_batch_directory)
    monkeypatch.setattr(migration_backup, "write_fallback_failure_evidence", fail_fallback_evidence)

    with pytest.raises(BackupError, match="fallback failure evidence could not be written") as raised:
        create_backup(
            (source,),
            sandbox_tmp_path / "backups",
            source_key="legacy",
            import_version="directory-evidence-failure",
        )

    assert raised.value.__cause__ is directory_error


def test_verify_backup_rejects_manifest_reusing_backup_path(sandbox_tmp_path) -> None:
    _legacy_tree(sandbox_tmp_path)
    backup_root = sandbox_tmp_path / "backups"
    result = _service(sandbox_tmp_path, sandbox_tmp_path / "manifest.sqlite3", backup_root).migrate(
        import_version="manifest-duplicate"
    )
    manifest_path = backup_root / result.backup_relpath / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"][1]["backup_relpath"] = manifest["files"][0]["backup_relpath"]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(BackupError, match="duplicate backup paths"):
        verify_backup(
            backup_root,
            result.backup_relpath,
            source_key="legacy",
            import_version="manifest-duplicate",
            source_sha256=result.source_sha256,
        )


def test_verify_backup_rejects_duplicate_source_paths(sandbox_tmp_path) -> None:
    _legacy_tree(sandbox_tmp_path)
    backup_root = sandbox_tmp_path / "backups"
    result = _service(sandbox_tmp_path, sandbox_tmp_path / "manifest-source.sqlite3", backup_root).migrate(
        import_version="manifest-source-duplicate"
    )
    manifest_path = backup_root / result.backup_relpath / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"][1]["source_path"] = manifest["files"][0]["source_path"]
    manifest["files"][1]["relative_path"] = "other/" + Path(
        manifest["files"][1]["relative_path"]
    ).name
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(BackupError, match="duplicate source paths"):
        verify_backup(
            backup_root,
            result.backup_relpath,
            source_key="legacy",
            import_version="manifest-source-duplicate",
            source_sha256=result.source_sha256,
        )


def test_verify_backup_rejects_source_relative_basename_mismatch(sandbox_tmp_path) -> None:
    _legacy_tree(sandbox_tmp_path)
    backup_root = sandbox_tmp_path / "backups"
    result = _service(sandbox_tmp_path, sandbox_tmp_path / "manifest-basename.sqlite3", backup_root).migrate(
        import_version="manifest-basename-mismatch"
    )
    manifest_path = backup_root / result.backup_relpath / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"][0]["source_path"] = str(sandbox_tmp_path / "different-name.json")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(BackupError, match="basename does not match"):
        verify_backup(
            backup_root,
            result.backup_relpath,
            source_key="legacy",
            import_version="manifest-basename-mismatch",
            source_sha256=result.source_sha256,
        )


    source_path = sandbox_tmp_path / "source.json"
    source_path.write_bytes(b"{}")
    source = SourceFile(
        source_path=str(source_path),
        relative_path="output/tasks_store.json",
        content=b"{}",
        size=2,
        sha256=hashlib.sha256(b"{}").hexdigest(),
    )

    with pytest.raises(LegacyFormatError, match="duplicate source relative_path"):
        parse_sources((source, source))


def test_parse_sources_rejects_inconsistent_source_metadata(sandbox_tmp_path) -> None:
    source_path = sandbox_tmp_path / "source.json"
    source_path.write_bytes(b"actual")
    source = SourceFile(
        source_path=str(source_path),
        relative_path="output/tasks_store.json",
        content=b"declared",
        size=len(b"declared"),
        sha256=hashlib.sha256(b"declared").hexdigest(),
    )

    with pytest.raises(LegacyFormatError, match="source file metadata is inconsistent"):
        parse_sources((source,))


def test_deleted_document_rejects_active_version_missing_from_version_set(sandbox_tmp_path) -> None:
    _legacy_tree(sandbox_tmp_path)
    docs_path = sandbox_tmp_path / "output/docs_store.json"
    document = json.loads(docs_path.read_text(encoding="utf-8"))[0]
    document.update({"status": "deleted", "active_kg_version": None})
    _write_json(docs_path, [document])
    versions_path = sandbox_tmp_path / "output/kg/doc_report/versions.json"
    versions = json.loads(versions_path.read_text(encoding="utf-8"))
    versions["active_version"] = 99
    versions["versions"][0]["status"] = "deleted"
    _write_json(versions_path, versions)

    with pytest.raises(LegacyFormatError, match="active_version must exist"):
        _service(sandbox_tmp_path, sandbox_tmp_path / "deleted-invalid.sqlite3").migrate(
            import_version="deleted-invalid"
        )


def test_task_conflict_probe_contains_complete_access_scope(sandbox_tmp_path, monkeypatch) -> None:
    _legacy_tree(sandbox_tmp_path)
    statements: list[str] = []
    original_write_import = migration_service.write_import

    def capture_scope(connection, *args, **kwargs):
        connection.set_trace_callback(statements.append)
        return original_write_import(connection, *args, **kwargs)

    monkeypatch.setattr(migration_service, "write_import", capture_scope)
    _service(sandbox_tmp_path, sandbox_tmp_path / "scope.sqlite3").migrate(import_version="scope-query")

    task_selects = [statement for statement in statements if "FROM tasks" in statement]
    assert task_selects
    assert "owner_id" in task_selects[0]
    assert "tenant_id" in task_selects[0]
    assert "org_id" in task_selects[0]
    assert "project_id" in task_selects[0]


def test_migration_cli_help_runs_from_repository_root() -> None:
    import subprocess
    import sys

    repository_root = Path(__file__).resolve().parents[2]
    completed = subprocess.run(
        [sys.executable, "backend/scripts/migrate_legacy.py", "--help"],
        cwd=repository_root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0
    assert "Import legacy JSON state into SQLite" in completed.stdout
