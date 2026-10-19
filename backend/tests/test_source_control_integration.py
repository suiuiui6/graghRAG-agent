"""Real local FastAPI/BM25/SQLite/file-store integration; no model or remote service.

The fixed software fixture exercises deterministic correction, not paper quality.
Only single-source BM25 and configuration semantics are integration-tested here.
"""

import socket

import pytest
from fastapi import FastAPI
from tests.request_helpers import authenticated_client
from auth import create_auth_middleware
from middleware.jwt_middleware import create_jwt_middleware
from services.resource_access import create_resource_guard_middleware

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
    monkeypatch.setenv("LANGEXTRACT_MODEL_ID", "deepseek-flash")
    monkeypatch.setenv("LANGEXTRACT_API_KEY", "")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")
    # Freeze preprocessing inputs through the real cache replay path; no LLM mock.
    for question in (QUERY, "请用一段简洁的中文总结以下内容要点：\n\n" + QUERY):
        cache_key = retrieval._build_rewrite_cache_key("query_preprocess", question, "deepseek-flash", base_url, [])
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
    # Match production authentication order; use concrete temporary User/JWT storage.
    monkeypatch.setattr("routes.get_docs_snapshot", lambda: [])
    app = FastAPI()
    app.middleware("http")(create_resource_guard_middleware())
    app.middleware("http")(create_auth_middleware())
    app.middleware("http")(create_jwt_middleware())
    app.include_router(route.router, prefix="/api/v1")
    with authenticated_client(app, monkeypatch, sandbox_tmp_path) as client:
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


@pytest.mark.parametrize("endpoint", ["query", "summarize", "retrieve"])
def test_real_api_optional_evidence_trace(local_client, endpoint):
    client, _ = local_client
    payload = {"query": QUERY, "options": {"enabled_sources": ["bm25"], "enable_cross_encoder": False, "include_evidence_trace": True}}
    response = client.post("/api/v1/rag/" + endpoint, json=payload)
    assert response.status_code == 200
    trace = response.json()["metadata"]["evidence_trace"]
    assert trace["retrieval_stages"]["retrieval_final"]["evidence"]
    if endpoint != "retrieve":
        assert trace["serialized_model_context"] is None
        assert trace["raw_model_answer"] is None
        assert trace["generation_mode"] == "deterministic_correction"
        assert trace["final_answer"] == response.json()["answer"]
    payload["options"]["include_evidence_trace"] = False
    response = client.post("/api/v1/rag/" + endpoint, json=payload)
    assert "evidence_trace" not in response.json()["metadata"]


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


def test_real_api_trace_requires_pipeline_even_without_mask(local_client, monkeypatch):
    client, _ = local_client
    monkeypatch.setattr(route, "_rag_pipeline", None)
    monkeypatch.setattr(route, "_init_failed", True)
    response = client.post("/api/v1/rag/query", json={"query": QUERY, "options": {"include_evidence_trace": True}})
    assert response.status_code == 503


def test_real_api_trace_flag_is_strict_boolean(local_client):
    client, _ = local_client
    response = client.post("/api/v1/rag/query", json={"query": QUERY, "options": {"include_evidence_trace": "false"}})
    assert response.status_code == 422


def test_real_chroma_adapter_and_bm25_share_long_evidence_identity(monkeypatch, sandbox_tmp_path):
    from vector_store import VectorStore, HAS_CHROMADB
    from doc_processor import ChunkMetadata
    assert HAS_CHROMADB, "Existing local Chroma dependency required; do not install or skip silently"
    def no_network(*args, **kw):
        pytest.fail("TEST_ONLY vector integration may not access network")
    monkeypatch.setattr(socket, "create_connection", no_network)
    monkeypatch.setattr("requests.sessions.Session.request", no_network)
    text = "TEST_ONLY alpha retrieval passage " * 65
    metadata = ChunkMetadata(chunk_id="test_only_long", source_file="test_only.md", source_format="md", char_start=0, char_end=len(text))
    chunk = Chunk("test_only_long", text, "text", metadata=metadata)
    store = VectorStore(collection_name="test_only_p2", persist_dir=str(sandbox_tmp_path / "chroma"), embedding_dim=2)
    # Explicit software-test vectors: no embedding model or model download.
    store.add_chunks([chunk], [[1.0, 0.0]])
    config = RetrievalConfig(enable_cross_encoder=False)
    vector = retrieval._vector_recall([[1.0, 0.0]], store, config)
    bm25 = retrieval._bm25_recall("alpha retrieval", build_bm25_from_chunks([chunk]), config)
    assert len(vector[0]["text"]) == 1200
    assert len(bm25[0]["text"]) == len(text)
    fused = retrieval.rrf_fusion([("vector", vector), ("bm25", bm25)])
    assert len(fused) == 1
    assert fused[0]["source_paths"] == ["vector", "bm25"]
    assert fused[0]["identity_conflicts"] == []
