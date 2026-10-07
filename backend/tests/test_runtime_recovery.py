import asyncio
import importlib
import types
import logging
from pathlib import Path

import networkx as nx


def _install_in_memory_artifact_store(monkeypatch, index_registry):
    store = {}

    def fake_persist(path, payload):
        store[str(path)] = payload

    def fake_restore(path):
        return store.get(str(path))

    monkeypatch.setattr(index_registry, "_persist_json_artifact", fake_persist)
    monkeypatch.setattr(index_registry, "_restore_json_artifact", fake_restore)
    return store


def test_runtime_recovers_bm25_index_from_disk(monkeypatch):
    import index_registry

    index_registry = importlib.reload(index_registry)
    _install_in_memory_artifact_store(monkeypatch, index_registry)
    sample = {"chunks": ["预算执行率 82%"]}
    path = Path("D:/graghRAG-agent/backend/tests/fixtures/runtime-bm25.json")

    index_registry.persist_bm25_artifact(path, sample)

    assert index_registry.restore_bm25_artifact(path)["chunks"] == sample["chunks"]


def test_runtime_recovers_table_index_from_disk(monkeypatch):
    import index_registry

    index_registry = importlib.reload(index_registry)
    _install_in_memory_artifact_store(monkeypatch, index_registry)
    sample = {"rows": [{"metric": "预算执行率", "value": "82%"}]}
    path = Path("D:/graghRAG-agent/backend/tests/fixtures/runtime-table.json")

    index_registry.persist_table_artifact(path, sample)

    assert index_registry.restore_table_artifact(path)["rows"] == sample["rows"]


def test_invalid_bm25_artifact_does_not_block_table_restore(monkeypatch):
    import index_registry

    index_registry = importlib.reload(index_registry)
    _install_in_memory_artifact_store(monkeypatch, index_registry)
    bm25_path = Path("D:/graghRAG-agent/backend/tests/fixtures/runtime-bm25.json")
    table_path = Path("D:/graghRAG-agent/backend/tests/fixtures/runtime-table.json")

    index_registry.persist_bm25_artifact(bm25_path, {"chunks": [1]})
    index_registry.persist_table_artifact(table_path, {"rows": [{"metric": "预算执行率", "value": "82%"}]})

    recovery = index_registry.restore_runtime_indexes(
        bm25_path=bm25_path,
        table_path=table_path,
    )

    assert recovery["bm25"]["reason"] == "invalid_payload"
    assert recovery["table"]["restored"] is True


def test_restore_runtime_indexes_does_not_persist_artifacts_again(monkeypatch):
    import index_registry

    index_registry = importlib.reload(index_registry)
    bm25_path = Path("D:/graghRAG-agent/backend/tests/fixtures/runtime-bm25.json")
    table_path = Path("D:/graghRAG-agent/backend/tests/fixtures/runtime-table.json")
    calls = {}

    monkeypatch.setattr(index_registry, "restore_bm25_artifact", lambda path: {"ok": True})
    monkeypatch.setattr(index_registry, "restore_table_artifact", lambda path: {"ok": True})
    monkeypatch.setattr(index_registry, "_deserialize_bm25_index", lambda payload: "bm25-index")
    monkeypatch.setattr(index_registry, "_deserialize_table_index", lambda payload: "table-index")
    monkeypatch.setattr(
        index_registry,
        "set_bm25_index",
        lambda index, persist=True: calls.setdefault("bm25", []).append((index, persist)),
    )
    monkeypatch.setattr(
        index_registry,
        "set_table_index",
        lambda index, persist=True: calls.setdefault("table", []).append((index, persist)),
    )

    recovery = index_registry.restore_runtime_indexes(
        bm25_path=bm25_path,
        table_path=table_path,
    )

    assert recovery["bm25"]["restored"] is True
    assert recovery["table"]["restored"] is True
    assert calls["bm25"] == [("bm25-index", False)]
    assert calls["table"] == [("table-index", False)]


def test_setup_logging_falls_back_to_console_when_file_handler_is_unwritable(monkeypatch):
    import logging_config

    logging_config = importlib.reload(logging_config)

    fallback_dir = Path("D:/graghRAG-agent/backend/output/logs")
    monkeypatch.setattr(logging_config, "_ensure_log_dir", lambda log_dir="output/logs": fallback_dir)
    monkeypatch.setattr(
        logging_config,
        "TimedRotatingFileHandler",
        lambda *args, **kwargs: (_ for _ in ()).throw(PermissionError("read-only log dir")),
    )

    logging_config.setup_logging(log_dir=str(fallback_dir))

    root = logging.getLogger()
    assert any(isinstance(handler, logging.StreamHandler) for handler in root.handlers)
    assert len(root.handlers) == 1


def test_budgeted_cross_encoder_rerank_reports_unavailable_reason(monkeypatch):
    import retrieval

    monkeypatch.setattr(
        retrieval,
        "cross_encoder_rerank",
        lambda query, candidates, top_k: (candidates[:top_k], "cross_encoder_unavailable"),
    )

    results, timed_out, reason = retrieval._budgeted_cross_encoder_rerank(
        query="budget status",
        candidates=[{"chunk_id": "c00001", "text": "budget 82%"}],
        top_k=1,
        budget_ms=200,
    )

    assert timed_out is False
    assert reason == "cross_encoder_unavailable"
    assert results[0]["chunk_id"] == "c00001"


def test_safe_timed_rotating_file_handler_ignores_permission_error_on_rollover(monkeypatch):
    import logging_config

    logging_config = importlib.reload(logging_config)
    handler = logging_config.SafeTimedRotatingFileHandler(
        filename=str(Path("D:/graghRAG-agent/backend/output/logs/test-app.log")),
        when="midnight",
        interval=1,
        backupCount=1,
        encoding="utf-8",
    )

    monkeypatch.setattr(
        logging_config.TimedRotatingFileHandler,
        "doRollover",
        lambda self: (_ for _ in ()).throw(PermissionError("file locked")),
    )

    handler.doRollover()




def test_generation_timeout_policy_is_bounded():
    from generator import GenerationConfig

    cfg = GenerationConfig(timeout=30, max_retries=1)

    assert cfg.timeout == 30
    assert cfg.max_retries == 1


def test_generate_answer_retries_without_request_thread_sleep(monkeypatch):
    import generator

    generator = importlib.reload(generator)
    post_calls = []
    sleep_calls = []

    class DummyResponse:
        def __init__(self, status_code, payload=None):
            self.status_code = status_code
            self._payload = payload or {}

        def raise_for_status(self):
            if self.status_code >= 400:
                raise RuntimeError(f"status={self.status_code}")

        def json(self):
            return self._payload

    responses = [
        DummyResponse(429),
        DummyResponse(
            200,
            {
                "choices": [
                    {
                        "message": {"content": "最终答案 [c00001]"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 4},
            },
        ),
    ]

    def fake_post(*args, **kwargs):
        post_calls.append((args, kwargs))
        return responses.pop(0)

    def fake_sleep(seconds):
        sleep_calls.append(seconds)

    monkeypatch.setattr("requests.post", fake_post)
    monkeypatch.setattr(generator.time, "sleep", fake_sleep)

    result = generator.generate_answer(
        messages=[{"role": "user", "content": "预算执行率是多少？"}],
        config=generator.GenerationConfig(api_key="test-key", base_url="https://example.com", max_retries=1),
        context_chunks=[{"chunk_id": "c00001", "text": "预算执行率 82%"}],
    )

    assert result.finish_reason == "stop"
    assert result.answer_text.startswith("最终答案")
    assert len(post_calls) == 2
    assert sleep_calls == [2.0]  # 429 → 2s backoff before retry


def test_metrics_export_runtime_observability_metrics():
    import metrics

    metrics.record_rag_response_observability(
        {
            "metadata": {
                "query_mode": "global",
                "token_usage": {
                    "context_tokens_used": 512,
                    "rerank_latency_ms": 42,
                    "cache_hit": "rewrite",
                },
            }
        }
    )
    payload = asyncio.run(metrics.metrics_endpoint()).body.decode("utf-8")

    assert "rag_query_budget_tokens" in payload
    assert "rag_cache_hits_total" in payload
    assert "rag_rerank_duration_seconds" in payload
    assert "rag_query_mode_total" in payload
    assert 'mode="global"' in payload
    assert 'cache="rewrite"' in payload


def test_health_reports_runtime_recovery_components(monkeypatch):
    import routes.health as health

    async def fake_status():
        return await health.health_check()

    monkeypatch.setattr(health, "_count_kg_nodes", lambda: 1)
    monkeypatch.setattr(health, "_count_kg_edges", lambda: 2)
    monkeypatch.setattr(
        "index_registry.get_runtime_recovery_status",
        lambda: {
            "bm25": {"artifact_exists": True, "loaded": False},
            "table": {"artifact_exists": False, "loaded": False},
        },
    )

    response = asyncio.run(fake_status())

    assert "runtime_recovery" in response.components
    assert "index_artifacts" in response.dependencies
    assert response.components["runtime_recovery"] == "degraded"
    assert response.status == "degraded"


def test_startup_restores_runtime_indexes(monkeypatch):
    import index_registry
    import routes.documents
    import routes.query as query_route
    import routes.rag_query as rag_query_route
    import server

    called = {}

    class DummyScheduler:
        def add_job(self, *args, **kwargs):
            return None

        def start(self):
            return None

        def shutdown(self, wait=True):
            return None

    class DummyBus:
        async def start(self):
            return None

        async def stop(self):
            return None

    monkeypatch.setattr(
        index_registry,
        "restore_runtime_indexes",
        lambda: called.setdefault(
            "recovery",
            {
                "bm25": {"restored": True, "reason": "ok"},
                "table": {"restored": False, "reason": "not_found"},
            },
        ),
    )
    monkeypatch.setattr("kg_store.load_all_kg_graphs", lambda: nx.Graph())
    monkeypatch.setattr(query_route, "_build_kg_from_full", lambda graph: None)
    monkeypatch.setattr(rag_query_route, "warm_rag_runtime", lambda: True)
    monkeypatch.setattr(routes.documents, "get_docs_snapshot", lambda: [])
    monkeypatch.setattr("apscheduler.schedulers.background.BackgroundScheduler", DummyScheduler)
    monkeypatch.setattr("services.backup.get_backup_manager", lambda: types.SimpleNamespace(scheduled_backup=lambda: None))
    monkeypatch.setattr("services.lifecycle.get_lifecycle_manager", lambda: types.SimpleNamespace(run_cleanup=lambda: None))
    monkeypatch.setattr("services.health_checker.get_health_checker", lambda: types.SimpleNamespace(probe_all=lambda: None))
    monkeypatch.setattr(
        "services.event_bus.get_event_bus",
        lambda: DummyBus(),
    )

    async def run_lifespan():
        async with server.lifespan(server.app):
            return None

    asyncio.run(run_lifespan())

    assert called["recovery"]["bm25"]["restored"] is True


def test_startup_rebuilds_sparse_table_runtime_index_from_mineru_output(monkeypatch):
    import index_registry
    import routes.documents
    import routes.query as query_route
    import routes.rag_query as rag_query_route
    import server

    called = {}

    class DummyScheduler:
        def add_job(self, *args, **kwargs):
            return None

        def start(self):
            return None

        def shutdown(self, wait=True):
            return None

    class DummyBus:
        async def start(self):
            return None

        async def stop(self):
            return None

    sparse_table = types.SimpleNamespace(get_stats=lambda: {"total_rows": 1})

    monkeypatch.setattr(
        index_registry,
        "restore_runtime_indexes",
        lambda: {
            "bm25": {"restored": True, "reason": "ok"},
            "table": {"restored": True, "reason": "ok"},
        },
    )
    monkeypatch.setattr(index_registry, "get_table_index", lambda: sparse_table)
    monkeypatch.setattr(server, "_iter_mineru_runtime_sources", lambda: [(Path("D:/fake/mineru"), "paper.pdf")])
    monkeypatch.setattr(
        "worker._build_runtime_indexes_from_mineru_output",
        lambda mineru_dir, filename: called.setdefault("rebuilt", (mineru_dir, filename)) or [],
    )
    monkeypatch.setattr("kg_store.load_all_kg_graphs", lambda: nx.Graph())
    monkeypatch.setattr(query_route, "_build_kg_from_full", lambda graph: None)
    monkeypatch.setattr(rag_query_route, "warm_rag_runtime", lambda: True)
    monkeypatch.setattr(routes.documents, "get_docs_snapshot", lambda: [])
    monkeypatch.setattr("apscheduler.schedulers.background.BackgroundScheduler", DummyScheduler)
    monkeypatch.setattr("services.backup.get_backup_manager", lambda: types.SimpleNamespace(scheduled_backup=lambda: None))
    monkeypatch.setattr("services.lifecycle.get_lifecycle_manager", lambda: types.SimpleNamespace(run_cleanup=lambda: None))
    monkeypatch.setattr("services.health_checker.get_health_checker", lambda: types.SimpleNamespace(probe_all=lambda: None))
    monkeypatch.setattr("services.event_bus.get_event_bus", lambda: DummyBus())

    async def run_lifespan():
        async with server.lifespan(server.app):
            return None

    asyncio.run(run_lifespan())

    assert Path(called["rebuilt"][0]) == Path("D:/fake/mineru")
    assert called["rebuilt"][1] == "paper.pdf"


def test_runtime_recovery_prefers_mineru_candidate_with_nonzero_table_rows(monkeypatch):
    import server

    candidates = [
        (Path("D:/fake/mineru_latest"), "latest.pdf"),
        (Path("D:/fake/mineru_rich"), "rich.pdf"),
    ]
    rows_after_build = {
        "latest.pdf": 0,
        "rich.pdf": 12,
    }
    called = []

    monkeypatch.setattr(server, "_table_index_row_count", lambda index: 0 if index is None else index)
    monkeypatch.setattr(
        server,
        "_iter_mineru_runtime_sources",
        lambda: list(candidates),
    )
    monkeypatch.setattr("index_registry.get_table_index", lambda: 0 if not called else rows_after_build[called[-1][1]])

    def fake_rebuild(mineru_dir, filename):
        called.append((Path(mineru_dir), filename))
        return ["chunk-a", "chunk-b"]

    monkeypatch.setattr("worker._build_runtime_indexes_from_mineru_output", fake_rebuild)

    result = server._recover_sparse_runtime_table_index()

    assert [filename for _, filename in called] == ["latest.pdf", "rich.pdf"]
    assert result["rebuilt"] is True
    assert result["filename"] == "rich.pdf"
    assert result["table_rows_after"] == 12


def test_lifespan_shuts_down_scheduler_on_exit(monkeypatch):
    import routes.documents
    import routes.query as query_route
    import routes.rag_query as rag_query_route
    import server

    calls = {"started": 0, "shutdown": 0}

    class DummyScheduler:
        def add_job(self, *args, **kwargs):
            return None

        def start(self):
            calls["started"] += 1

        def shutdown(self, wait=True):
            calls["shutdown"] += 1

    class DummyBus:
        async def start(self):
            return None

        async def stop(self):
            return None

    monkeypatch.setattr("apscheduler.schedulers.background.BackgroundScheduler", DummyScheduler)
    monkeypatch.setattr("index_registry.restore_runtime_indexes", lambda: {})
    monkeypatch.setattr("kg_store.load_all_kg_graphs", lambda: nx.Graph())
    monkeypatch.setattr(query_route, "_build_kg_from_full", lambda graph: None)
    monkeypatch.setattr(rag_query_route, "warm_rag_runtime", lambda: True)
    monkeypatch.setattr(routes.documents, "get_docs_snapshot", lambda: [])
    monkeypatch.setattr("services.backup.get_backup_manager", lambda: types.SimpleNamespace(scheduled_backup=lambda: None))
    monkeypatch.setattr("services.lifecycle.get_lifecycle_manager", lambda: types.SimpleNamespace(run_cleanup=lambda: None))
    monkeypatch.setattr("services.health_checker.get_health_checker", lambda: types.SimpleNamespace(probe_all=lambda: None))
    monkeypatch.setattr("services.event_bus.get_event_bus", lambda: DummyBus())

    async def run_lifespan():
        async with server.lifespan(server.app):
            return None

    asyncio.run(run_lifespan())

    assert calls["started"] == 1
    assert calls["shutdown"] == 1


def test_init_rag_pipeline_builds_bm25_from_vector_store_when_runtime_cache_is_missing(monkeypatch):
    import routes.rag_query as rag_query

    rag_query._rag_pipeline = None
    rag_query._embedding_client = None
    rag_query._vector_store = None
    rag_query._init_failed = False

    class DummyEmbeddingClient:
        pass

    class DummyCollection:
        def get(self, include=None):
            return {
                "ids": ["c00001"],
                "documents": ["A 题绿电直连型电氢氨园区优化运行 002196"],
                "metadatas": [{"content_type": "text"}],
            }

    class DummyVectorStore:
        def __init__(self):
            self._collection = DummyCollection()

    class DummyPipeline:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    built = {}

    monkeypatch.setattr("embedding.EmbeddingClient", DummyEmbeddingClient)
    monkeypatch.setattr("vector_store.VectorStore", DummyVectorStore)
    monkeypatch.setattr("routes.query._build_kg", lambda: nx.Graph())
    monkeypatch.setattr("index_registry.get_bm25_index", lambda: None)
    monkeypatch.setattr("index_registry.get_table_index", lambda: None)
    monkeypatch.setattr("domain_dict.get_domain_dict", lambda: None)
    monkeypatch.setattr("retrieval.RetrievalPipeline", lambda **kwargs: DummyPipeline(**kwargs))
    monkeypatch.setattr(
        "index_registry.build_bm25_from_chunks",
        lambda chunks: (built.setdefault("chunk_count", len(chunks)), "bm25")[1],
    )
    monkeypatch.setattr("index_registry.set_bm25_index", lambda index: built.setdefault("index", index))

    assert rag_query._init_rag_pipeline() is True
    assert built["chunk_count"] == 1
    assert built["index"] == "bm25"
