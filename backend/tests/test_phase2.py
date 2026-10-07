"""
Phase 2 Integration Tests — §5.1-§5.6 of enterprise-evolution-blueprint.

Tests lineage, catalog, export, backup, quality, and lifecycle modules
on real file-system dependencies (no mocks).
"""

import json
import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Ensure backend dir is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def temp_output(sandbox_tmp_path):
    """Create temp output directory with minimal KG structure."""
    base = sandbox_tmp_path
    out_dir = base / "output"
    kg_dir = out_dir / "kg" / "doc_test"
    kg_dir.mkdir(parents=True)

    nodes = {
        "nodes": [
            {"node_id": "n001", "entity_type": "metric", "label": "预算执行率",
             "properties": {"value": "84%", "confidence": 0.85},
             "page_idx": 1, "bbox_norm": [0.1, 0.2, 0.5, 0.3],
             "grounding_status": "grounded"},
            {"node_id": "n002", "entity_type": "risk_item", "label": "高空坠落",
             "properties": {"confidence": 0.72},
             "page_idx": 2, "bbox_norm": [0.3, 0.4, 0.7, 0.5],
             "grounding_status": "grounded"},
            {"node_id": "n003", "entity_type": "process_step", "label": "动火审批",
             "properties": {"confidence": 0.55},
             "page_idx": 3,
             "grounding_status": "ungrounded"},
        ]
    }
    edges = {
        "edges": [
            {"source_node_id": "n001", "target_node_id": "n002",
             "relation_type": "related_to"},
        ]
    }

    (kg_dir / "nodes.json").write_text(json.dumps(nodes, ensure_ascii=False))
    (kg_dir / "edges.json").write_text(json.dumps(edges, ensure_ascii=False))

    # docs_store.json
    (out_dir / "docs_store.json").write_text(json.dumps([
        {"document_id": "doc_test", "filename": "test.pdf",
         "indexed_at": "2026-06-09T10:00:00Z", "project_id": "default"}
    ]))

    # Feedback
    fb_dir = out_dir / "feedback"
    fb_dir.mkdir(parents=True)
    (fb_dir / "fb001.json").write_text(json.dumps({
        "feedback_id": "fb001", "query_id": "q1", "rating": "positive",
        "status": "open", "query_text": "预算执行情况", "answer_text": "预算执行率84%"
    }))
    (fb_dir / "fb002.json").write_text(json.dumps({
        "feedback_id": "fb002", "query_id": "q2", "rating": "negative",
        "status": "open", "query_text": "应急预案", "answer_text": "未提及",
        "comment": "答案没有参考价值"
    }))

    # Conversations
    conv_dir = out_dir / "conversations"
    conv_dir.mkdir(parents=True)
    (conv_dir / "sess1.json").write_text(json.dumps({
        "session_id": "sess1", "created_at": "2026-06-09T10:00:00Z",
        "last_active": "2026-06-09T10:05:00Z",
        "turns": [
            {"turn_id": 1, "question": "高处作业", "answer": "高处作业需系安全带"}
        ]
    }))

    # Backup, logs, embedding_cache
    (out_dir / "backups").mkdir(parents=True)
    (out_dir / "logs").mkdir(parents=True)
    (out_dir / "embedding_cache").mkdir(parents=True)

    old_cwd = os.getcwd()
    os.chdir(base)
    try:
        yield base
    finally:
        os.chdir(old_cwd)


@pytest.fixture
def client():
    """TestClient for route testing."""
    from server import app
    return TestClient(app)


# ── Lineage Tests (§5.1) ──────────────────────────────────────────────

class TestLineageStore:
    def test_record_entity(self, temp_output):
        from services.lineage_store import LineageStore
        store = LineageStore(base_dir=temp_output / "lineage")
        node = store.record_entity("n001", "metric", "预算执行率",
                                   doc_id="doc_test", page_idx=1,
                                   kg_version=1)
        assert node.node_type.value == "entity"
        assert "doc_test" in node.parent_ids[0]

    def test_trace_entity_roundtrip(self, temp_output):
        from services.lineage_store import LineageStore
        store = LineageStore(base_dir=temp_output / "lineage")
        store.record_entity("n050", "metric", "测试指标", doc_id="doc_x")
        trace = store.trace_entity("n050")
        assert trace is not None
        assert trace.entity_id == "n050"
        assert len(trace.trace) >= 1

    def test_trace_nonexistent(self, temp_output):
        from services.lineage_store import LineageStore
        store = LineageStore(base_dir=temp_output / "lineage")
        assert store.trace_entity("nonexistent") is None

    def test_record_retrieval_and_generation(self, temp_output):
        from services.lineage_store import LineageStore
        store = LineageStore(base_dir=temp_output / "lineage")
        store.record_domain_expand("q1", "JSA", "JSA 作业安全分析", ["JSA"])
        store.record_retrieval("q1", "JSA执行情况", ["vector", "kg"], 42,
                               domain_terms=["JSA"], session_id="sess1")
        store.record_generation("q1", "答案内容...", ["c00042"], ["n001"],
                                session_id="sess1")
        trace = store.trace_answer("q1")
        assert trace is not None
        node_types = [n.node_type.value for n in trace.trace]
        assert "domain_expand" in node_types
        assert "retrieval" in node_types
        assert "generation" in node_types

    def test_trace_conversation(self, temp_output):
        from services.lineage_store import LineageStore
        store = LineageStore(base_dir=temp_output / "lineage")
        store.record_retrieval("qa", "test query", ["vector"], 10,
                               session_id="sessX")
        result = store.trace_conversation("sessX")
        assert result["total"] >= 1

    def test_trace_term(self, temp_output):
        from services.lineage_store import LineageStore
        store = LineageStore(base_dir=temp_output / "lineage")
        store.record_domain_expand("qt", "动火作业", "动火作业 热工", ["动火作业", "热工"])
        result = store.trace_term("动火作业")
        assert result["total"] >= 1

    def test_export_dot(self, temp_output):
        from services.lineage_store import LineageStore
        store = LineageStore(base_dir=temp_output / "lineage")
        store.record_entity("n100", "metric", "DOT测试", doc_id="doc_z")
        dot = store.export_dot("n100")
        assert dot is not None
        assert "digraph lineage" in dot
        assert "n100" in dot

    def test_feedback_lineage(self, temp_output):
        from services.lineage_store import LineageStore
        store = LineageStore(base_dir=temp_output / "lineage")
        store.record_retrieval("qf", "query with feedback", ["vector"], 5)
        store.record_generation("qf", "answer", ["c1"], ["n001"])
        store.record_feedback("fb_test", "qf", "negative")
        trace = store.trace_feedback("fb_test")
        assert trace is not None


# ── Catalog Tests (§5.2) ──────────────────────────────────────────────

class TestCatalog:
    def test_build_catalog(self, temp_output):
        from services.catalog import CatalogBuilder
        cat = CatalogBuilder()
        result = cat.build()
        assert "summary" in result
        assert result["summary"]["total_entities"] >= 3
        assert result["summary"]["total_edges"] >= 1

    def test_low_quality(self, temp_output):
        from services.catalog import CatalogBuilder
        cat = CatalogBuilder()
        items = cat.low_quality(threshold=0.6)
        assert isinstance(items, list)

    def test_search_entities(self, temp_output):
        from services.catalog import CatalogBuilder
        cat = CatalogBuilder()
        results = cat.search_entities("预算")
        assert any("预算" in r.get("label", "") for r in results)

    def test_list_entities_by_type(self, temp_output):
        from services.catalog import CatalogBuilder
        cat = CatalogBuilder()
        result = cat.list_entities(entity_type="metric")
        assert result["total"] >= 1
        for e in result["entities"]:
            assert e["entity_type"] == "metric"


# ── Export Tests (§5.3) ───────────────────────────────────────────────

class TestKgExporter:
    def test_export_kg_json(self, temp_output):
        from services.kg_exporter import KgExporter
        exp = KgExporter()
        result = exp.export_kg("json")
        assert isinstance(result, dict)
        assert result["counts"]["nodes"] >= 3
        assert result["counts"]["edges"] >= 1

    def test_export_kg_csv(self, temp_output):
        from services.kg_exporter import KgExporter
        exp = KgExporter()
        from fastapi.responses import StreamingResponse
        result = exp.export_kg("csv")
        assert isinstance(result, StreamingResponse)

    def test_export_kg_neo4j(self, temp_output):
        from services.kg_exporter import KgExporter
        exp = KgExporter()
        from fastapi.responses import StreamingResponse
        result = exp.export_kg("neo4j")
        assert isinstance(result, StreamingResponse)

    def test_export_kg_rdf(self, temp_output):
        from services.kg_exporter import KgExporter
        exp = KgExporter()
        from fastapi.responses import StreamingResponse
        result = exp.export_kg("rdf")
        assert isinstance(result, StreamingResponse)

    def test_export_feedback_csv(self, temp_output):
        from services.kg_exporter import KgExporter
        exp = KgExporter()
        from fastapi.responses import StreamingResponse
        result = exp.export_feedback("csv")
        assert isinstance(result, StreamingResponse)

    def test_export_feedback_filtered(self, temp_output):
        from services.kg_exporter import KgExporter
        exp = KgExporter()
        from fastapi.responses import StreamingResponse
        result = exp.export_feedback("csv", status="open")
        assert isinstance(result, StreamingResponse)

    def test_export_conversations(self, temp_output):
        from services.kg_exporter import KgExporter
        exp = KgExporter()
        from fastapi.responses import StreamingResponse
        result = exp.export_conversations()
        assert isinstance(result, StreamingResponse)

    def test_export_invalid_format(self, temp_output):
        from services.kg_exporter import KgExporter
        import pytest
        exp = KgExporter()
        with pytest.raises(ValueError):
            exp.export_kg("invalid")


# ── Backup Tests (§5.4) ───────────────────────────────────────────────

class TestBackupManager:
    def test_create_backup(self, temp_output):
        from services.backup import BackupManager
        mgr = BackupManager(base_dir=temp_output / "backups")
        result = mgr.create_backup("manual")
        assert result.status == "completed"
        assert result.manifest is not None
        tars = list((temp_output / "backups").glob("*.tar.gz"))
        assert len(tars) >= 1

    def test_list_backups(self, temp_output):
        from services.backup import BackupManager
        mgr = BackupManager(base_dir=temp_output / "backups")
        mgr.create_backup("manual")
        backups = mgr.list_backups()
        assert len(backups) >= 1
        assert "backup_id" in backups[0]

    def test_get_manifest(self, temp_output):
        from services.backup import BackupManager
        mgr = BackupManager(base_dir=temp_output / "backups")
        result = mgr.create_backup("manual")
        manifest = mgr.get_manifest(result.backup_id)
        assert manifest is not None
        assert manifest["backup_type"] == "manual"

    def test_verify_backup(self, temp_output):
        from services.backup import BackupManager
        mgr = BackupManager(base_dir=temp_output / "backups")
        result = mgr.create_backup("manual")
        v = mgr.verify(result.backup_id)
        assert v["valid"] is True

    def test_verify_nonexistent(self, temp_output):
        from services.backup import BackupManager
        mgr = BackupManager(base_dir=temp_output / "backups")
        v = mgr.verify("nonexistent")
        assert v["valid"] is False

    def test_cleanup_old_backups(self, temp_output):
        from services.backup import BackupManager
        mgr = BackupManager(base_dir=temp_output / "backups")
        mgr.create_backup("daily")
        removed = mgr.cleanup_old_backups(keep_daily=7)
        assert removed == 0  # Should not remove the only backup


# ── Quality Tests (§5.5) ──────────────────────────────────────────────

class TestQualityMonitor:
    def test_compute_quality(self, temp_output):
        from services.quality import QualityMonitor
        qm = QualityMonitor()
        report = qm.compute()
        assert report.extraction_quality["grounding_rate"] > 0
        assert report.extraction_quality["total_entities"] >= 3
        assert "overall_score" in report.model_dump()

    def test_feedback_stats(self, temp_output):
        from services.quality import QualityMonitor
        qm = QualityMonitor()
        fb = qm._feedback_quality()
        assert fb["total"] >= 2
        assert fb["positive"] >= 1
        assert fb["negative"] >= 1

    def test_freshness(self, temp_output):
        from services.quality import QualityMonitor
        qm = QualityMonitor()
        fresh = qm._data_freshness()
        assert "days_since_last_ingest" in fresh
        assert "stale_entities" in fresh


# ── Lifecycle Tests (§5.6) ────────────────────────────────────────────

class TestDataLifecycleManager:
    def test_preview_cleanup(self, temp_output):
        from services.lifecycle import DataLifecycleManager
        lm = DataLifecycleManager()
        previews = lm.preview_cleanup()
        assert len(previews) == 5  # conversations, kg_versions, logs, backups, audit
        for p in previews:
            assert p.category in ["conversations", "kg_versions", "logs", "backups", "audit"]

    def test_run_cleanup(self, temp_output):
        from services.lifecycle import DataLifecycleManager
        lm = DataLifecycleManager()
        report = lm.run_cleanup()
        assert "categories" in report.model_dump()
        assert isinstance(report.total_removed, int)

    def test_storage_report(self, temp_output):
        from services.lifecycle import DataLifecycleManager
        lm = DataLifecycleManager()
        sr = lm.storage_report()
        assert "kg" in sr.directories
        assert sr.total_size_bytes >= 0

    def test_retention_policies(self):
        from services.lifecycle import DataLifecycleManager
        lm = DataLifecycleManager()
        assert "conversations" in lm.RETENTION_POLICIES
        assert lm.RETENTION_POLICIES["conversations"]["max_age_days"] == 7
        assert lm.RETENTION_POLICIES["feedback"]["max_age_days"] is None
        assert lm.RETENTION_POLICIES["kg_versions"]["max_versions"] == 10


# ── API Endpoint Tests ────────────────────────────────────────────────

class TestPhase2Endpoints:
    def test_catalog_summary(self, client):
        r = client.get("/api/v1/catalog/summary")
        assert r.status_code in (200, 401)  # 401 if auth required

    def test_catalog_low_quality(self, client):
        r = client.get("/api/v1/catalog/low-quality")
        assert r.status_code in (200, 401)

    def test_export_kg_json(self, client):
        r = client.get("/api/v1/export/kg?format=json")
        assert r.status_code in (200, 401)

    def test_system_quality(self, client):
        r = client.get("/api/v1/system/quality")
        assert r.status_code in (200, 401)

    def test_system_storage(self, client):
        r = client.get("/api/v1/system/storage")
        assert r.status_code in (200, 401)

    def test_system_cleanup_preview(self, client):
        r = client.get("/api/v1/system/cleanup/preview")
        assert r.status_code in (200, 401)
