"""Real local service artifacts; external HTTP/model boundaries are offline doubles."""
from __future__ import annotations

import asyncio
import csv
import io
import json
import os
import sqlite3
import sys
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import conversation
from services import catalog, kg_exporter, kg_service, lifecycle


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    for module in (catalog, kg_exporter, lifecycle):
        for name, relative in {"KG_DIR": "kg", "FEEDBACK_DIR": "feedback", "CONVERSATIONS_DIR": "conversations", "DOMAIN_DICT_PATH": "domain.yaml", "VECTORDB_DIR": "vectordb", "DOCS_STORE": "docs.json", "OUTPUT_DIR": ".", "LOGS_DIR": "logs", "BACKUP_DIR": "backups"}.items():
            if hasattr(module, name):
                monkeypatch.setattr(module, name, tmp_path / relative)
    monkeypatch.setattr(lifecycle.DataLifecycleManager, "AUDIT_DIR", tmp_path / "audit")
    monkeypatch.setattr(conversation, "CONVERSATIONS_DIR", tmp_path / "conversations")
    monkeypatch.setattr(conversation, "RUNTIME_CACHE_DB", tmp_path / "cache.sqlite3")
    monkeypatch.setattr(conversation, "_runtime_cache_ready", False)
    monkeypatch.setattr(conversation, "_mgr", None)
    monkeypatch.setattr(catalog, "_catalog", None)
    monkeypatch.setattr(kg_exporter, "_exporter", None)
    monkeypatch.setattr(lifecycle, "_manager", None)
    monkeypatch.setattr(kg_service, "KG_DIR", str(tmp_path / "kg"))
    monkeypatch.setattr(kg_service, "DEFAULT_NODES_PATH", str(tmp_path / "kg/nodes.json"))
    monkeypatch.setattr(kg_service, "DEFAULT_EDGES_PATH", str(tmp_path / "kg/edges.json"))
    import requests
    monkeypatch.setattr(requests.sessions.Session, "request", lambda *a, **kw: pytest.fail("External HTTP forbidden"))


def graph_files(root):
    nodes = [{"node_id": "a", "label": "电机", "entity_type": "machine", "grounding_status": "grounded", "properties": {"material": "steel"}}, {"node_id": "b", "label": "传感器", "entity_type": "sensor"}, {"node_id": "c", "label": "孤点", "entity_type": "sensor"}]
    edges = [{"source_node_id": "a", "target_node_id": "b", "relation_type": "connected"}]
    write(root / "nodes.json", {"nodes": nodes})
    write(root / "edges.json", {"edges": edges})
    return nodes, edges


def test_kg_merge_prefixes_grounding_fallback_and_corruption(tmp_path):
    assert kg_service.load_all_kgs().number_of_nodes() == 0
    assert kg_service.count_kg_nodes() == 0
    root = tmp_path / "kg"
    graph_files(root)
    assert kg_service.count_kg_nodes() == 3
    default = kg_service.load_all_kgs()
    assert set(default) == {"a", "b", "c"}
    assert set(kg_service.build_kg_from_full(default)) == {"a"}
    default.nodes["a"]["grounding_status"] = "ungrounded"
    assert kg_service.build_kg_from_full(default) is None
    graph_files(root / "doc_1")
    graph_files(root / "doc_2")
    (root / "incomplete").mkdir()
    merged = kg_service.load_all_kgs()
    assert set(merged) == {"d0_a", "d0_b", "d0_c", "d1_a", "d1_b", "d1_c"}
    assert merged.nodes["d0_a"]["origin_id"] == "a"
    assert merged.has_edge("d1_a", "d1_b") and not merged.has_edge("d0_a", "d1_b")
    assert kg_service.count_kg_nodes() == 6
    (root / "doc_2/nodes.json").write_text("invalid", encoding="utf-8")
    assert kg_service.count_kg_nodes() == 3
    with pytest.raises(json.JSONDecodeError):
        kg_service.load_all_kgs()


def test_kg_default_corrupt_count_degrades(tmp_path):
    root = tmp_path / "kg"
    graph_files(root)
    (root / "nodes.json").write_text("broken", encoding="utf-8")
    assert kg_service.count_kg_nodes() == 0


def test_catalog_real_stats_search_pagination_and_quality(tmp_path):
    builder = catalog.get_catalog()
    assert builder is catalog.get_catalog()
    empty = builder.build()
    assert empty["summary"]["total_entities"] == 0
    assert empty["conversations"] is None and empty["feedback"] is None
    assert builder.search_entities("x") == []
    assert builder.list_entities()["total"] == 0
    nodes, _ = graph_files(tmp_path / "kg/doc_1")
    write(tmp_path / "kg/doc_empty/nodes.json", {"nodes": []})
    (tmp_path / "kg/doc_missing").mkdir()
    write(tmp_path / "kg/other/nodes.json", {"nodes": nodes})
    write(tmp_path / "kg/stray.json", {})
    write(tmp_path / "docs.json", [{"document_id": "doc_1", "project_id": "p"}, {"document_id": "missing"}])
    write(tmp_path / "conversations/a.json", {"turns": [1, 2], "last_active": "today"})
    (tmp_path / "conversations/b.json").write_text("bad", encoding="utf-8")
    write(tmp_path / "feedback/a.json", {"rating": "positive"})
    write(tmp_path / "feedback/b.json", {"rating": "negative"})
    (tmp_path / "feedback/bad.json").write_text("bad", encoding="utf-8")
    (tmp_path / "domain.yaml").write_text("motor:\n  category: machine\nsensor: {}\n", encoding="utf-8")
    (tmp_path / "vectordb").mkdir()
    assert builder._count_chunks() == 0
    with sqlite3.connect(tmp_path / "vectordb/chroma.sqlite3") as conn:
        conn.execute("CREATE TABLE embedding_metadata (id INTEGER)")
        conn.executemany("INSERT INTO embedding_metadata VALUES (?)", [(1,), (2,)])
    report = builder.build("p")
    assert report["summary"]["total_chunks"] == 2
    assert report["summary"]["by_project"] == {"p": {"documents": 1, "entities": 3}, "default": {"documents": 1, "entities": 0}}
    assert report["domain_dict"]["by_category"] == {"machine": 1, "general": 1}
    assert report["feedback"]["positive_ratio"] == .5
    assert report["conversations"]["avg_turns_per_session"] == 2
    assert report["quality_metrics"]["orphan_entities"] == 1
    assert report["quality_metrics"]["grounded_rate"] == .33
    assert {r["doc_id"] for r in builder.low_quality()} == {"doc_1", "doc_empty"}
    assert builder.search_entities("STEEL", entity_type="machine", limit=1) == [nodes[0]]
    assert builder.search_entities("电机", entity_type="sensor") == []
    assert builder.search_entities("no match") == []
    assert builder.list_entities("sensor", limit=1, offset=1) == {"entities": [nodes[2]], "total": 2, "limit": 1, "offset": 1}
    assert builder.build_trends(9) == {"days": 9, "entity_growth": [], "query_volume": [], "feedback_rate": []}


def test_catalog_corrupt_artifacts_and_default_graph(tmp_path, monkeypatch):
    builder = catalog.CatalogBuilder()
    graph_files(tmp_path / "kg")
    assert builder.build_summary()["total_entities"] == 3
    for path in (tmp_path / "kg/nodes.json", tmp_path / "kg/edges.json", tmp_path / "kg/doc_bad/nodes.json", tmp_path / "kg/doc_bad/edges.json", tmp_path / "docs.json"):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("broken", encoding="utf-8")
    (tmp_path / "domain.yaml").write_text("[one, two]", encoding="utf-8")
    assert builder._build_domain_dict_stats() is None
    (tmp_path / "domain.yaml").write_text("a: [bad shape]", encoding="utf-8")
    assert builder._build_domain_dict_stats() is None
    (tmp_path / "conversations").mkdir()
    (tmp_path / "feedback").mkdir()
    (tmp_path / "vectordb").mkdir()
    (tmp_path / "vectordb/chroma.sqlite3").write_text("not sqlite", encoding="utf-8")
    assert builder.build()["summary"]["total_documents"] == 0
    assert builder._count_chunks() == 0
    assert builder._by_project([{"document_id": "doc_bad"}])["default"]["entities"] == 0
    assert builder.search_entities("anything") == []
    assert builder.list_entities()["total"] == 0
    import metrics
    samples = [SimpleNamespace(labels={"source": s}, value=v) for s, v in [("kg", 1), ("vector", 1), ("bm25", 1), ("other", 0)]]
    monkeypatch.setattr(metrics.rag_retrieval_candidates, "collect", lambda: [SimpleNamespace(samples=samples)])
    assert builder._build_retrieval_stats()["source_hit_rate"] == {"kg": .7, "vector": .95, "bm25": .45}
    def broken():
        raise RuntimeError("metrics unavailable")
    monkeypatch.setattr(metrics.rag_retrieval_candidates, "collect", broken)
    assert builder._build_retrieval_stats()["source_hit_rate"] == {"kg": 0, "vector": 0, "bm25": 0}


async def body(response):
    parts = []
    async for chunk in response.body_iterator:
        parts.append(chunk.encode() if isinstance(chunk, str) else chunk)
    return b"".join(parts)


def test_export_formats_have_real_contents_and_archive_members(tmp_path):
    asyncio.run(_export_formats(tmp_path))


async def _export_formats(tmp_path):
    exporter = kg_exporter.get_exporter()
    assert exporter is kg_exporter.get_exporter()
    assert exporter.export_kg("json")["counts"] == {"nodes": 0, "edges": 0}
    for fmt in ("csv", "zip", "rdf", "neo4j"):
        assert await body(exporter.export_kg(fmt))
    nodes, edges = graph_files(tmp_path / "kg/doc_1")
    result = exporter.export_kg("json")
    assert result["nodes"] == nodes and result["edges"] == edges
    csv_text = (await body(exporter.export_kg("csv"))).decode()
    assert "电机" in csv_text and "material" in csv_text and "connected" in csv_text
    cypher = (await body(exporter.export_kg("neo4j"))).decode()
    assert 'CREATE (:machine {id: "a"' in cypher and "CREATE (a)-[:connected]->(b)" in cypher
    rdf = (await body(exporter.export_kg("rdf"))).decode()
    assert "grag:a grag:connected grag:b" in rdf
    with zipfile.ZipFile(io.BytesIO(await body(exporter.export_kg("zip")))) as zf:
        assert json.loads(zf.read("nodes.json"))["nodes"] == nodes
        assert json.loads(zf.read("manifest.json"))["edges"] == 1
        assert list(csv.DictReader(io.StringIO(zf.read("nodes.csv").decode("utf-8-sig"))))[0]["label"] == "电机"
    with pytest.raises(ValueError):
        exporter.export_kg("bad")
    assert exporter.export_domain_dict() == {"error": "Domain dictionary not found"}
    (tmp_path / "domain.yaml").write_text("电机:\n  synonyms: [motor]\n  abbreviations: [M]\n  related: [轴]\n", encoding="utf-8")
    assert "电机" in (await body(exporter.export_domain_dict("yaml"))).decode()
    assert json.loads(await body(exporter.export_domain_dict("json")))["电机"]["synonyms"] == ["motor"]
    assert "motor" in (await body(exporter.export_domain_dict("csv"))).decode("utf-8-sig")
    with pytest.raises(ValueError):
        exporter.export_domain_dict("bad")
    assert json.loads(await body(exporter.export_feedback("json"))) == []
    write(tmp_path / "feedback/a.json", {"feedback_id": "a", "status": "open", "rating": "positive"})
    write(tmp_path / "feedback/b.json", {"feedback_id": "b", "status": "resolved"})
    (tmp_path / "feedback/bad.json").write_text("bad", encoding="utf-8")
    assert [r["feedback_id"] for r in json.loads(await body(exporter.export_feedback("json", "open")))] == ["a"]
    assert len(list(csv.DictReader(io.StringIO((await body(exporter.export_feedback())).decode("utf-8-sig"))))) == 2
    assert await body(exporter.export_conversations()) == b"No conversations found"
    write(tmp_path / "conversations/a.json", {"turns": [{"question": "问", "answer": "答", "rewritten": "改写"}, {}]})
    (tmp_path / "conversations/bad.json").write_text("bad", encoding="utf-8")
    with zipfile.ZipFile(io.BytesIO(await body(exporter.export_conversations()))) as zf:
        assert set(zf.namelist()) == {"a.md", "manifest.json"}
        assert "改写" in zf.read("a.md").decode()


def test_export_load_fallback_and_corrupt_documents(tmp_path):
    exporter = kg_exporter.KgExporter()
    nodes, edges = graph_files(tmp_path / "kg")
    assert exporter._load_all_kg() == (nodes, edges)
    for relative in ("nodes.json", "edges.json", "doc_bad/nodes.json", "doc_bad/edges.json"):
        path = tmp_path / "kg" / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("bad", encoding="utf-8")
    (tmp_path / "kg/doc_empty").mkdir()
    (tmp_path / "kg/other").mkdir()
    assert exporter._load_all_kg() == ([], [])


def test_conversation_persistence_ttl_rotation_history_and_cleanup(tmp_path, monkeypatch):
    manager = conversation.get_conversation_manager()
    assert manager is conversation.get_conversation_manager()
    assert manager.load("missing") is None
    assert manager.append_turn("missing", "q") is None
    assert manager.export_markdown("missing") is None
    assert not manager.delete("missing")
    conv = manager.create("标题" * 40, session_id="stable")
    assert conv.title.endswith("...")
    assert manager.get_or_create("stable").session_id == "stable"
    assert manager._path("../../escape").parent == manager.base_dir
    for i in range(22):
        manager.append_turn("stable", f"q{i}", "a" * 400, rewritten=f"rewrite{i}", rewrite_reason="消歧", sources=["doc"])
    loaded = manager.load("stable")
    assert len(loaded.turns) == 20 and loaded.turns[0].turn_id == 3
    assert loaded.turns[-1].turn_id == 22
    assert len(loaded.recent_history(2)) == 2
    assert len(loaded.recent_history(1)[0]["answer"]) == 300
    markdown = manager.export_markdown("stable")
    assert "消歧" in markdown and "rewrite21" in markdown and "来源: doc" in markdown
    loaded.last_active = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
    manager._save(loaded)
    assert not manager.load("stable").is_active
    assert manager.list_all() == []
    assert manager.list_all(include_inactive=True, limit=1)[0]["turns"] == 20
    assert manager.get_or_create("stable").session_id == "stable"
    automatic = manager.create()
    automatic.last_active = "invalid"
    manager._save(automatic)
    assert manager.get_or_create(automatic.session_id).session_id != automatic.session_id
    assert not conversation._should_preserve_requested_session_id(None)
    bad = write(manager.base_dir / "bad.json", {})
    bad.write_text("bad", encoding="utf-8")
    assert manager.load("bad") is None
    dead = manager.create(session_id="old")
    dead.is_active = False
    manager._save(dead)
    old = (datetime.now(timezone.utc) - timedelta(days=10)).timestamp()
    os.utime(manager._path("old"), (old, old))
    os.utime(bad, (old, old))
    assert manager.cleanup() == 1
    assert manager.cleanup() == 0
    assert manager.delete("stable")
    assert manager.list_all(include_inactive=True)
    blank = conversation.Conversation()
    blank.add_turn("", "")
    blank.add_turn("q", "")
    assert blank.recent_history() == []
    assert conversation.Conversation.from_dict(blank.to_dict()).turns[1].question == "q"


def test_conversation_atomic_permission_fallback_keeps_payload(tmp_path, monkeypatch):
    manager = conversation.ConversationManager(tmp_path / "sessions")
    def denied(*args):
        raise PermissionError("replace denied")
    monkeypatch.setattr(conversation.os, "replace", denied)
    conv = manager.create("问题", session_id="stable")
    assert manager.load(conv.session_id).title == "问题"
    assert not manager._path("stable").with_suffix(".json.tmp").exists()
    original_unlink = Path.unlink
    def deny_tmp(path, *args, **kwargs):
        if path.suffix == ".tmp":
            raise PermissionError("cleanup denied")
        return original_unlink(path, *args, **kwargs)
    monkeypatch.setattr(Path, "unlink", deny_tmp)
    manager.append_turn("stable", "q", "a")
    assert manager.load("stable").turns[-1].answer == "a"


def test_runtime_cache_namespace_update_and_coreference_http_boundary(tmp_path, monkeypatch):
    assert conversation.runtime_cache_get("one", {"a": 1}) is None
    conversation.runtime_cache_put("one", {"a": 1}, "first")
    conversation.runtime_cache_put("one", {"a": 1}, "updated")
    assert conversation.runtime_cache_get("one", {"a": 1}) == "updated"
    assert conversation.runtime_cache_get("two", {"a": 1}) is None
    assert conversation._hash_cache_payload({"a": 1, "b": 2}) == conversation._hash_cache_payload({"b": 2, "a": 1})
    assert conversation.resolve_coreference("q", []) == "q"
    history = [{"content": "电机", "answer": "答案"}]
    calls = []
    class Reply:
        def raise_for_status(self):
            pass
        def json(self):
            return {"choices": [{"message": {"content": ' "电机参数" '}}]}
    def post(url, **kwargs):
        calls.append((url, kwargs))
        return Reply()
    monkeypatch.setattr(conversation.requests, "post", post)
    assert conversation.resolve_coreference("它呢", history, api_key="placeholder", base_url="https://example.invalid/") == "电机参数"
    assert conversation.resolve_coreference("它呢", history, api_key="placeholder", base_url="https://example.invalid/") == "电机参数"
    assert len(calls) == 1 and calls[0][0] == "https://example.invalid/chat/completions"
    assert calls[0][1]["timeout"] == 15
    def cache_failed(*args):
        raise sqlite3.OperationalError("cache unavailable")
    monkeypatch.setattr(conversation, "runtime_cache_get", cache_failed)
    monkeypatch.setattr(conversation, "runtime_cache_put", cache_failed)
    assert conversation.resolve_coreference("继续", history, api_key="placeholder") == "电机参数"
    monkeypatch.setattr(Reply, "json", lambda self: {"choices": [{"message": {"content": "x"}}]})
    assert conversation.resolve_coreference("继续", history) == "继续"
    def failed(*args, **kwargs):
        raise TimeoutError("offline timeout")
    monkeypatch.setattr(conversation.requests, "post", failed)
    assert conversation.resolve_coreference("继续", history) == "继续"


def test_lifecycle_removes_expired_kg_versions_under_configured_root(tmp_path):
    root = tmp_path / "kg/doc_1"
    for i in range(12):
        write(root / f"v{i}" / "nodes.json", {"nodes": []})
    write(root / "versions.json", {"active_version": 11, "versions": [{"version": i} for i in range(12)]})
    manager = lifecycle.DataLifecycleManager()
    assert [Path(p).as_posix() for p in manager._find_expired_versions()] == ["doc_1/v0", "doc_1/v1"]
    assert manager._clean_kg_versions() == 2
    assert not (root / "v0").exists() and not (root / "v1").exists()
    assert all((root / f"v{i}").exists() for i in range(2, 12))


def test_lifecycle_refuses_version_paths_outside_kg_root(tmp_path, monkeypatch):
    outside = tmp_path / "outside"
    write(outside / "sentinel.json", {"keep": True})
    manager = lifecycle.DataLifecycleManager()
    monkeypatch.setattr(manager, "_find_expired_versions", lambda: [str(outside)])
    assert manager._clean_kg_versions() == 0
    assert json.loads((outside / "sentinel.json").read_text(encoding="utf-8")) == {"keep": True}


def test_lifecycle_preview_retention_and_real_cleanup(tmp_path, monkeypatch):
    from services import backup, audit_logger, event_bus
    manager = lifecycle.get_lifecycle_manager()
    assert manager is lifecycle.get_lifecycle_manager()
    assert all(p.items_to_remove == 0 for p in manager.preview_cleanup())
    backups = backup.BackupManager(tmp_path / "backups")
    monkeypatch.setattr(backup, "_manager", backups)
    monkeypatch.setattr(event_bus, "EVENTS_DIR", tmp_path / "events")
    monkeypatch.setattr(event_bus, "_bus", event_bus.EventBus())
    monkeypatch.setattr(audit_logger, "_logger", audit_logger.AuditLogger(tmp_path / "audit"), raising=False)
    monkeypatch.setattr(audit_logger, "get_audit_logger", lambda: audit_logger.AuditLogger(tmp_path / "audit"))
    old = manager._now - timedelta(days=400)
    recent = manager._now.isoformat()
    for name, data in [("expired", {"last_active": old.isoformat()}), ("keep_feedback", {"last_active": old.isoformat(), "has_feedback": True}), ("recent", {"last_active": recent}), ("mtime", {})]:
        p = write(tmp_path / "conversations" / f"{name}.json", data)
        if name == "mtime":
            os.utime(p, (old.timestamp(), old.timestamp()))
    corrupt = tmp_path / "conversations/corrupt.json"
    corrupt.write_text("bad", encoding="utf-8")
    os.utime(corrupt, (old.timestamp(), old.timestamp()))
    for name in ("logs/server.log.1", "audit/audit-2025.jsonl"):
        p = tmp_path / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("old", encoding="utf-8")
        os.utime(p, (old.timestamp(), old.timestamp()))
    (tmp_path / "logs/recent.log").write_text("new", encoding="utf-8")
    (tmp_path / "audit/audit-current.jsonl").write_text("new", encoding="utf-8")
    for kind, count in (("daily", 9), ("weekly", 6)):
        for i in range(count):
            p = tmp_path / "backups" / f"{kind}-{i}.tar.gz"
            p.write_bytes(b"fixture")
            os.utime(p, (old.timestamp() + i, old.timestamp() + i))
    preview = {p.category: p.items_to_remove for p in manager.preview_cleanup()}
    assert preview == {"conversations": 3, "kg_versions": 0, "logs": 1, "backups": 4, "audit": 1}
    assert corrupt.exists()
    report = manager.run_cleanup()
    assert report.total_removed == 9 and report.errors == []
    assert (tmp_path / "conversations/keep_feedback.json").exists()
    assert (tmp_path / "conversations/recent.json").exists()
    assert not corrupt.exists()
    assert manager.run_cleanup().total_removed == 0
    storage = manager.storage_report()
    assert storage.directories["backups"]["files"] == 11
    assert storage.total_size_bytes >= 11 * len(b"fixture")


@pytest.mark.parametrize("method, category", [("_clean_conversations", "conversations"), ("_clean_kg_versions", "kg_versions"), ("_clean_logs", "logs"), ("_clean_backups", "backups"), ("_clean_audit", "audit")])
def test_lifecycle_category_failure_is_reported_without_stopping_others(tmp_path, monkeypatch, method, category):
    from services import backup, event_bus, audit_logger
    monkeypatch.setattr(backup, "_manager", backup.BackupManager(tmp_path / "backups"))
    def failed(*a, **kw):
        raise OSError("boundary denied")
    # Simulated filesystem category failure; target cleanup aggregation still runs.
    monkeypatch.setattr(lifecycle.DataLifecycleManager, method, failed)
    monkeypatch.setattr(event_bus, "get_event_bus", failed)
    monkeypatch.setattr(audit_logger, "get_audit_logger", failed)
    report = lifecycle.DataLifecycleManager().run_cleanup()
    assert report.errors == [f"{category}: boundary denied"]
    assert category not in report.categories
    assert len(report.categories) == 4 and report.total_removed == 0


def test_lifecycle_filesystem_delete_failures_are_best_effort(tmp_path, monkeypatch):
    manager = lifecycle.DataLifecycleManager()
    old = manager._now - timedelta(days=400)
    for relative in ("conversations/expired.json", "logs/a.log", "audit/audit-old.jsonl"):
        p = write(tmp_path / relative, {"last_active": old.isoformat()})
        os.utime(p, (old.timestamp(), old.timestamp()))
    original = Path.unlink
    def denied(path, *a, **kw):
        if path.name in {"expired.json", "a.log", "audit-old.jsonl"}:
            raise PermissionError("denied")
        return original(path, *a, **kw)
    monkeypatch.setattr(Path, "unlink", denied)
    assert manager._clean_conversations() == manager._clean_logs() == manager._clean_audit() == 0
    assert (tmp_path / "logs/a.log").exists()
    def broken_walk(*a, **kw):
        raise OSError("walk failure")
    monkeypatch.setattr(lifecycle.os, "walk", broken_walk)
    assert manager._dir_size(tmp_path) == 0 and manager._file_count(tmp_path) == 0


@pytest.fixture
def bot_boundaries(monkeypatch, tmp_path):
    from services import bot_handler, feishu_client, feedback_store, event_bus, audit_logger
    # Feishu transport and embedding/model/index constructors are external boundaries.
    # All message extraction, quotas, feedback validation and persistence stay real.
    calls = []
    state = SimpleNamespace(configured=True, fail_send=False, fail_model=False, result={"answer": "本地答案", "sources": [{"text_snippet": "出处"}]})
    class Client:
        @property
        def configured(self):
            return state.configured
        def reply_text(self, chat, text):
            calls.append(("text", chat, text))
        def build_qa_card(self, question, answer, sources, **kwargs):
            return {"question": question, "answer": answer, "sources": sources}
        def build_error_card(self):
            return {"error": True}
        def reply_card(self, chat, card):
            if state.fail_send:
                raise OSError("transport offline")
            calls.append(("card", chat, card))
    class Config:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)
    class Pipeline:
        def __init__(self, **kwargs):
            assert kwargs["config"].max_total_candidates == 8
    class Generator:
        def __init__(self, pipeline, config):
            assert config.model
        def generate(self, query):
            calls.append(("query", query))
            if state.fail_model:
                raise TimeoutError("model offline")
            return state.result
    monkeypatch.setattr(feishu_client, "FeishuClient", Client)
    monkeypatch.setitem(sys.modules, "embedding", SimpleNamespace(EmbeddingClient=object))
    monkeypatch.setitem(sys.modules, "vector_store", SimpleNamespace(VectorStore=object))
    monkeypatch.setitem(sys.modules, "retrieval", SimpleNamespace(RetrievalPipeline=Pipeline, RetrievalConfig=Config))
    monkeypatch.setitem(sys.modules, "generator", SimpleNamespace(RAGGenerator=Generator, GenerationConfig=Config))
    store = feedback_store.FeedbackStore(tmp_path / "feedback")
    monkeypatch.setattr(feedback_store, "_store", store)
    monkeypatch.setattr(event_bus, "EVENTS_DIR", tmp_path / "events")
    monkeypatch.setattr(event_bus, "_bus", event_bus.EventBus())
    monkeypatch.setattr(audit_logger, "_audit", audit_logger.AuditLogger(tmp_path / "audit"))
    return SimpleNamespace(handler=bot_handler.BotHandler(), calls=calls, state=state, store=store)


def bot_message(text="@机器人 电机参数", *, sender=None, kind="text", content=None):
    return {"sender": {"sender_id": sender if sender is not None else {"open_id": "user"}}, "message": {"chat_id": "chat", "msg_type": kind, "content": json.dumps(content if content is not None else {"text": text}, ensure_ascii=False)}}


def test_bot_event_routing_message_extraction_model_reply_and_limits(bot_boundaries, monkeypatch):
    b = bot_boundaries
    assert b.handler.handle_event("url_verification", {"challenge": "abc"}) == {"challenge": "abc"}
    assert b.handler.handle_event("unknown", {}) is None
    for message in (bot_message(" "), bot_message("@robot"), bot_message(kind="image"), bot_message(kind="post", content={}), bot_message(kind="post", content={"content": [[]]})):
        assert b.handler.handle_event("im.message.receive_v1", message) is None
    assert b.calls == []
    b.handler.handle_event("im.message.receive_v1", bot_message())
    assert b.calls == [("query", "电机参数"), ("card", "chat", {"question": "电机参数", "answer": "本地答案", "sources": ["出处"]})]
    b.handler.handle_event("im.message.receive_v1", bot_message(kind="post", sender="legacy", content={"content": [[[{"tag": "text", "text": "富文本"}, {"tag": "image"}], {"tag": "text", "text": "参数"}, "ignored"]]}))
    assert ("query", "富文本参数") in b.calls
    monkeypatch.setenv("BOT_DAILY_LIMIT", "0")
    before = len(b.calls)
    b.handler.handle_event("im.message.receive_v1", bot_message("再次"))
    assert len(b.calls) == before + 1 and b.calls[-1][0] == "text"
    b.state.configured = False
    before = len(b.calls)
    b.handler.handle_event("im.message.receive_v1", bot_message("再次"))
    assert len(b.calls) == before


def test_bot_model_failures_default_answer_and_reply_failure(bot_boundaries):
    b = bot_boundaries
    b.state.fail_model = True
    answer, sources = b.handler._rag_query("query")
    assert answer == "抱歉，查询失败，请稍后重试。" and sources == []
    b.state.fail_model = False
    b.state.result = {}
    assert b.handler._rag_query("query") == ("抱歉，未找到相关信息。", [])
    b.state.result = {"answer": "答", "sources": [{"text_snippet": "s" * 200}, {}]}
    assert b.handler._rag_query("query")[1] == ["s" * 100, ""]
    b.state.fail_send = True
    assert b.handler.handle_event("im.message.receive_v1", bot_message()) is None
    b.state.configured = False
    assert b.handler.handle_event("im.message.receive_v1", bot_message()) is None


def test_bot_card_and_reaction_feedback_really_persist_validation_failures(bot_boundaries):
    b = bot_boundaries
    assert b.handler.handle_event("card.action.trigger", {"action": {"value": "invalid"}}) is None
    assert b.handler.handle_event("im.message.reaction.created", {"action": {"value": "invalid"}}) is None
    response = b.handler.handle_event("card.action.trigger", {"open_id": "u", "action": {"value": "positive|q"}})
    assert response["toast"]["content"] == "感谢反馈！"
    b.handler.handle_event("im.message.reaction.created", {"sender": {"sender_id": {"open_id": "u"}}, "action": {"value": "negative|q2"}})
    records = b.store.list_all()
    assert {r.query_id for r in records} == {"q", "q2"}
    assert any("飞书卡片" in r.comment for r in records)
    assert any("飞书 Bot" in r.comment for r in records)
    response = b.handler.handle_event("card.action.trigger", {"action": {"value": "bad-rating|q"}})
    assert response["toast"]["content"] == "感谢反馈，我们会改进！"
    assert b.handler.handle_event("im.message.reaction.created", {"sender": {"sender_id": "legacy"}, "action": {"value": "bad-rating|q"}}) is None
    assert len(b.store.list_all()) == 2


def test_conversation_new_session_plain_export_and_active_retention(tmp_path):
    manager = conversation.ConversationManager(tmp_path / "sessions")
    conv = manager.get_or_create(None)
    assert conv.session_id
    assert manager.get_or_create("new-stable").session_id == "new-stable"
    manager.append_turn(conv.session_id, "问题", "答案", rewritten="问题")
    markdown = manager.export_markdown(conv.session_id)
    assert "答案" in markdown and "改写:" not in markdown and "来源:" not in markdown
    old = (datetime.now(timezone.utc) - timedelta(days=10)).timestamp()
    os.utime(manager._path(conv.session_id), (old, old))
    assert manager.cleanup() == 0
    assert manager._path(conv.session_id).exists()


def test_lifecycle_recent_malformed_versions_and_delete_failure(tmp_path, monkeypatch):
    manager = lifecycle.DataLifecycleManager()
    write(tmp_path / "conversations/recent-empty.json", {})
    (tmp_path / "conversations/recent-bad.json").write_text("bad", encoding="utf-8")
    assert manager._find_expired_conversations() == []
    write(tmp_path / "kg/doc_short/v1/nodes.json", {})
    write(tmp_path / "kg/doc_long/vbad/nodes.json", {})
    for i in range(11):
        write(tmp_path / "kg/doc_long" / f"v{i}" / "nodes.json", {})
    write(tmp_path / "kg/doc_long/versions.json", {"active_version": 10, "versions": [{"version": i} for i in range(11)]})
    write(tmp_path / "kg/not_doc/file.json", {})
    write(tmp_path / "kg/stray.json", {})
    assert len(manager._find_expired_versions()) == 1
    def denied(*args, **kwargs):
        raise PermissionError("version delete denied")
    monkeypatch.setattr(lifecycle.shutil, "rmtree", denied)
    assert manager._clean_kg_versions() == 1
    assert len(list((tmp_path / "kg/doc_long").glob(".retired-*"))) == 1
    assert (tmp_path / "kg/doc_long/vbad").exists()
