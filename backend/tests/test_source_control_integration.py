"""Real local FastAPI/BM25/SQLite/file-store integration; no model or remote service.

The fixed software fixture exercises deterministic correction, not paper quality.
Only single-source BM25 and configuration semantics are integration-tested here.
"""

import socket

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import conversation
import retrieval
import routes.rag_query as route
from config import RetrievalConfig
from doc_processor import Chunk
from index_registry import build_bm25_from_chunks
from services import lineage_store

QUERY = "储能使产量降低，对吗？"


@pytest.fixture
def local_client(monkeypatch, sandbox_tmp_path):
    # These are concrete production dependencies at isolated paths, not fake services.
    monkeypatch.setattr(conversation, "_mgr", conversation.ConversationManager(sandbox_tmp_path / "conversations"))
    monkeypatch.setattr(lineage_store, "_store", lineage_store.LineageStore(sandbox_tmp_path / "lineage"))
    cache = retrieval.QueryRewriteCache(sandbox_tmp_path / "rewrite.sqlite3")
    monkeypatch.setattr(retrieval, "_rewrite_cache", cache)
    base_url = "https://invalid.example"
    monkeypatch.setenv("LANGEXTRACT_BASE_URL", base_url)
    monkeypatch.setenv("LANGEXTRACT_API_KEY", "")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")
    # Freeze preprocessing inputs through the real cache replay path; no LLM mock.
    for question in (QUERY, "请用一段简洁的中文总结以下内容要点：\n\n" + QUERY):
        cache_key = retrieval._build_rewrite_cache_key("query_preprocess", question, "deepseek-chat", base_url, [])
        cache.set(cache_key, {"rewritten": question, "intent": "hybrid", "entity_types": [], "table_conditions": []})
    index = build_bm25_from_chunks([
        Chunk("software_fixture_storage", "软件测试夹具：加装储能后年产量从9023提升至10903吨。", "text"),
        Chunk("software_fixture_other", "软件测试夹具：采购流程由本地记录定义。", "text"),
    ])
    assert index is not None, "Existing rank_bm25 dependency is required for this real integration test"
    pipeline = retrieval.RetrievalPipeline(None, None, bm25_index=index, config=RetrievalConfig(enable_cross_encoder=False))
    monkeypatch.setattr(route, "_rag_pipeline", pipeline)
    # Guard the network boundary; retrieval/generation/router dependencies remain real.
    def no_network(*args, **kwargs):
        pytest.fail("integration test must not attempt a network connection")
    monkeypatch.setattr(socket, "create_connection", no_network)
    monkeypatch.setattr("requests.sessions.Session.request", no_network)
    app = FastAPI()
    app.include_router(route.router, prefix="/api/v1")
    with TestClient(app) as client:
        yield client, pipeline


@pytest.mark.parametrize("endpoint", ["query", "summarize"])
def test_real_local_deterministic_answer_records_mask(local_client, endpoint):
    client, pipeline = local_client
    response = client.post("/api/v1/rag/" + endpoint, json={
        "query": QUERY, "options": {"enabled_sources": ["bm25"], "enable_cross_encoder": False},
    })
    assert response.status_code == 200
    payload = response.json()
    assert payload["metadata"]["mode"] == "rag_pipeline"
    assert payload["answer"].startswith("不是")
    assert "software_fixture_storage" in payload["answer"]
    trace = payload["metadata"]["effective_config"]
    assert trace["requested_sources"] == trace["allowed_sources"] == trace["executed_sources"] == ["bm25"]
    assert trace["stages"]["normal"]["bm25"]["candidate_count"] == 1
    assert trace["stages"]["generator_rescue"]["kg"]["reason"] == "source_disabled"
    assert trace["stages"]["generator_rescue"]["vector"]["reason"] == "source_disabled"
    assert pipeline.config.enabled_sources is None


def test_real_local_retrieve_records_mask(local_client):
    client, _ = local_client
    response = client.post("/api/v1/rag/retrieve", json={
        "query": QUERY, "options": {"enabled_sources": ["bm25"], "enable_cross_encoder": False},
    })
    assert response.status_code == 200
    assert response.json()["chunks"]
    assert response.json()["metadata"]["effective_config"]["executed_sources"] == ["bm25"]


@pytest.mark.parametrize("options", [{"enable_cross_encoder": False}, {"enabled_sources": None, "enable_cross_encoder": False}])
def test_real_local_default_mask_preserves_available_sources(local_client, options):
    client, _ = local_client
    response = client.post("/api/v1/rag/query", json={"query": QUERY, "options": options})
    assert response.status_code == 200
    trace = response.json()["metadata"]["effective_config"]
    assert trace["requested_sources"] is None
    assert trace["allowed_sources"] == ["vector", "kg", "bm25", "table", "multi_query"]
    assert trace["executed_sources"] == ["bm25"]
    assert response.json()["answer"].startswith("不是")


@pytest.mark.parametrize("endpoint", ["query", "retrieve", "summarize"])
@pytest.mark.parametrize("sources", [[], ["unknown"], "bm25"])
def test_real_api_rejects_invalid_masks(local_client, endpoint, sources):
    client, _ = local_client
    response = client.post("/api/v1/rag/" + endpoint, json={"query": QUERY, "options": {"enabled_sources": sources}})
    assert response.status_code == 422


@pytest.mark.parametrize("endpoint", ["query", "retrieve", "summarize"])
def test_real_api_explicit_mask_blocks_unavailable_pipeline(local_client, monkeypatch, endpoint):
    client, _ = local_client
    monkeypatch.setattr(route, "_rag_pipeline", None)
    monkeypatch.setattr(route, "_init_failed", True)  # concrete initialization-failure state
    response = client.post("/api/v1/rag/" + endpoint, json={"query": QUERY, "options": {"enabled_sources": ["bm25"]}})
    assert response.status_code == 503
