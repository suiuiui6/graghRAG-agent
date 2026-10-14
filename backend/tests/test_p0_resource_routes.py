"""API regressions use actual temporary documents/graphs and signed principals.

Only the model generation boundary is substituted; no provider/network calls.
"""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def resource_app(sandbox_tmp_path, monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "p0-route-test-signing-secret-at-least-32-characters")
    from services import auth_service
    from models import User
    monkeypatch.setattr(auth_service, "USERS_DIR", sandbox_tmp_path / "users")
    monkeypatch.setattr(auth_service, "OAUTH_STATES_DIR", sandbox_tmp_path / "oauth")
    service = auth_service.AuthService()
    monkeypatch.setattr(auth_service, "_service", service)
    for user_id in ("admin", "alice", "bob", "unknown"):
        service._save_user(User(user_id=user_id, username=user_id,
                               email="", display_name=user_id, created_at=service._now(),
                               roles=["admin"] if user_id == "admin" else ["viewer"]))
    from middleware.jwt_middleware import create_access_token, decode_token
    import routes
    import routes.documents as documents
    import routes.query as query
    import routes.graph as graph
    import routes.rag_query as rag

    base = sandbox_tmp_path / "backend"
    (base / "uploads").mkdir(parents=True)
    (base / "output" / "kg").mkdir(parents=True)
    monkeypatch.setattr(documents, "__file__", str(base / "routes" / "documents.py"))
    monkeypatch.setattr(documents, "UPLOADS_DIR", str(base / "uploads"))
    monkeypatch.setattr(query, "KG_DIR", str(base / "output" / "kg"))
    monkeypatch.setattr(graph, "KG_DIR", str(base / "output" / "kg"))
    monkeypatch.setattr(routes, "DOCS_JSON_PATH", str(base / "output" / "docs_store.json"))
    docs = []
    for name, owner in [("a", "alice"), ("b", "bob")]:
        original = base / "uploads" / f"{name}.pdf"
        original.write_bytes(f"ORIGINAL_{name}".encode())
        kg = base / "output" / "kg" / f"doc_{name}"
        kg.mkdir()
        (kg / "nodes.json").write_text(json.dumps({"nodes": [{
            "node_id": "n1", "label": f"CONTENT_{name}", "entity_type": "claim",
            "properties": {}, "grounding_status": "grounded", "page_idx": 0,
        }]}), encoding="utf-8")
        (kg / "edges.json").write_text('{"edges":[]}', encoding="utf-8")
        docs.append({"document_id": f"doc_{name}", "filename": f"{name}.pdf",
                     "filepath": str(original), "kg_path": str(kg),
                     "owner_id": owner, "status": "indexed"})
    monkeypatch.setattr(routes, "_docs_store", docs)
    routes._save_docs(docs)

    # Actual signed JWT verification, without importing server/lifespan/providers.
    app = FastAPI()
    @app.middleware("http")
    async def principal(request, call_next):
        token = request.headers.get("authorization", "").removeprefix("Bearer ")
        payload = decode_token(token)
        if payload:
            request.state.user = {"user_id": payload["sub"], "roles": payload["roles"]}
        return await call_next(request)
    app.include_router(documents.router, prefix="/api/v1")
    app.include_router(query.router, prefix="/api/v1")
    app.include_router(graph.router, prefix="/api/v1")
    app.include_router(rag.router, prefix="/api/v1")
    client = TestClient(app, raise_server_exceptions=False)
    def headers(user="admin", roles=None):
        token = create_access_token(user, user, roles=roles or (["admin"] if user == "admin" else ["viewer"]))
        return {"Authorization": f"Bearer {token}"}
    return SimpleNamespace(client=client, base=base, docs=docs, headers=headers, query=query, rag=rag)


def test_unknown_empty_prefix_delete_preserves_all_originals(resource_app):
    env = resource_app
    before = {p.name: p.read_bytes() for p in (env.base / "uploads").iterdir()}
    response = env.client.delete("/api/v1/documents/doc_", headers=env.headers())
    assert response.status_code == 404
    assert {p.name: p.read_bytes() for p in (env.base / "uploads").iterdir()} == before


def test_delete_only_exact_registered_asset(resource_app):
    env = resource_app
    unrelated = env.base / "uploads" / "doc_a_unrelated.pdf"
    unrelated.write_bytes(b"KEEP")
    response = env.client.delete("/api/v1/documents/doc_a", headers=env.headers())
    assert response.status_code == 200
    assert not (env.base / "uploads" / "a.pdf").exists()
    assert unrelated.read_bytes() == b"KEEP"
    assert (env.base / "uploads" / "b.pdf").exists()


def test_foreign_delete_is_not_found_and_preserves_files(resource_app):
    env = resource_app
    response = env.client.delete("/api/v1/documents/doc_b", headers=env.headers("alice"))
    assert response.status_code == 404
    assert (env.base / "uploads" / "b.pdf").exists()


def test_list_filters_owner_and_download_checks_resource(resource_app):
    env = resource_app
    response = env.client.get("/api/v1/documents", headers=env.headers("alice"))
    assert response.status_code == 200
    assert [d["document_id"] for d in response.json()["documents"]] == ["doc_a"]
    assert env.client.get("/api/v1/documents/doc_b/download", headers=env.headers("alice")).status_code == 404
    assert env.client.get("/api/v1/documents/doc_a/download", headers=env.headers("alice")).content == b"ORIGINAL_a"


def test_graph_cannot_fall_back_to_foreign_or_global_data(resource_app):
    env = resource_app
    denied = env.client.get("/api/v1/graph/doc_b", headers=env.headers("alice"))
    assert denied.status_code == 404
    response = env.client.get("/api/v1/graph/all", headers=env.headers("alice"))
    assert response.status_code == 200
    assert "CONTENT_a" in response.text
    assert "CONTENT_b" not in response.text


def test_legacy_query_uses_requested_graph_before_generation(resource_app, monkeypatch):
    env = resource_app
    class ModelBoundary:
        def __init__(self, labels):
            self.labels = labels
        def invoke(self, *args, **kwargs):
            return {"messages": [SimpleNamespace(content=" ".join(self.labels))]}
    monkeypatch.setattr(env.query, "_get_agent", lambda: ModelBoundary(["CONTENT_a", "CONTENT_b"]))
    monkeypatch.setattr(env.query, "_build_agent", lambda g: ModelBoundary([d["label"] for _, d in g.nodes(data=True)]))
    response = env.client.post("/api/v1/query", json={"query": "list", "document_id": "doc_a"}, headers=env.headers())
    assert response.status_code == 200
    assert "CONTENT_a" in response.json()["answer"]
    assert "CONTENT_b" not in response.text


def test_legacy_query_checks_unauthorized_document_before_model(resource_app, monkeypatch):
    env = resource_app
    def forbidden_model(*args, **kwargs):
        pytest.fail("unauthorized request reached model")
    monkeypatch.setattr(env.query, "_get_agent", forbidden_model)
    monkeypatch.setattr(env.query, "_build_agent", forbidden_model)
    response = env.client.post("/api/v1/query", json={"query": "list", "document_id": "doc_b"}, headers=env.headers("alice"))
    assert response.status_code == 404


def test_anonymous_document_routes_reject(resource_app):
    assert resource_app.client.get("/api/v1/documents").status_code == 401


def test_rag_scopes_before_global_initialization(resource_app, monkeypatch):
    env = resource_app
    def forbidden_init():
        raise AssertionError("restricted request initialized global indexes")
    monkeypatch.setattr(env.rag, "_init_rag_pipeline", forbidden_init)
    import generator
    seen = {}
    class GenerationBoundary:
        def __init__(self, pipeline, config=None):
            seen["graph"] = pipeline.kg_graph
            assert pipeline.vector_store is None
            assert pipeline.bm25_index is None
            assert pipeline.table_index is None
        def generate(self, query, **kwargs):
            assert kwargs["retrieval_config"].enabled_sources == ("kg",)
            return {"answer": " ".join(d["label"] for _, d in seen["graph"].nodes(data=True)), "sources": [], "metadata": {}}
    monkeypatch.setattr(generator, "RAGGenerator", GenerationBoundary)
    response = env.client.post("/api/v1/rag/query", json={"query": "list", "document_id": "doc_a"}, headers=env.headers("alice"))
    assert response.status_code == 200
    assert "CONTENT_a" in response.text
    assert "CONTENT_b" not in response.text
    assert response.json()["metadata"]["document_ids"] == ["doc_a"]


@pytest.mark.parametrize("body,expected", [
    ({"query": "x", "document_id": "doc_b"}, 404),
    ({"query": "x", "document_id": "doc_a", "options": {"enabled_sources": ["vector"]}}, 503),
    ({"query": "x", "document_id": "doc_a", "session_id": "unbound-old-session"}, 409),
])
def test_rag_rejects_unsafe_scope_before_models(resource_app, monkeypatch, body, expected):
    def forbidden_init():
        raise AssertionError("unauthorized/unsupported request reached global indexes")
    monkeypatch.setattr(resource_app.rag, "_init_rag_pipeline", forbidden_init)
    response = resource_app.client.post("/api/v1/rag/query", json=body, headers=resource_app.headers("alice"))
    assert response.status_code == expected


def test_delete_rejects_registered_asset_outside_root(resource_app):
    env = resource_app
    outside = env.base / "outside.pdf"
    outside.write_bytes(b"KEEP")
    env.docs[0]["filepath"] = str(outside)
    response = env.client.delete("/api/v1/documents/doc_a", headers=env.headers())
    assert response.status_code == 409
    assert outside.read_bytes() == b"KEEP"
    assert (env.base / "output" / "kg" / "doc_a" / "nodes.json").exists()


def test_real_server_middleware_authenticates_before_resource_filter(resource_app):
    from server import app
    client = TestClient(app, raise_server_exceptions=False)
    assert client.get("/api/v1/documents").status_code == 401
    response = client.get("/api/v1/documents", headers=resource_app.headers("alice"))
    assert response.status_code == 200
    assert [doc["document_id"] for doc in response.json()["documents"]] == ["doc_a"]
    assert client.get("/api/v1/catalog/summary", headers=resource_app.headers("alice")).status_code == 403
    assert client.get("/api/v1/files/b.pdf", headers=resource_app.headers("alice")).status_code == 404


def test_ingest_records_verified_owner_and_protects_task(resource_app, monkeypatch):
    from server import app
    import routes.ingest as ingest
    import routes
    import worker
    monkeypatch.setattr(ingest, "UPLOADS_DIR", str(resource_app.base / "uploads"))
    monkeypatch.setattr(ingest, "TASKS_STORE_PATH", str(resource_app.base / "output" / "tasks.json"))
    monkeypatch.setattr(ingest, "_tasks", {})
    monkeypatch.setattr(resource_app.query, "reload_kg", lambda: None)
    def provider_boundary(task_id, filepath, filename, progress, options):
        return {"document_id": "doc_" + task_id, "kg_nodes": 0, "kg_edges": 0,
                "grounded_entities": 0, "entity_types": 0, "pages_parsed": 1,
                "kg_path": str(resource_app.base / "output" / "kg" / ("doc_" + task_id))}
    monkeypatch.setattr(worker, "run_real_pipeline", provider_boundary)
    client = TestClient(app, raise_server_exceptions=False)
    response = client.post("/api/v1/ingest", headers=resource_app.headers("alice"),
                           files={"file": ("upload.pdf", b"local fixture", "application/pdf")},
                           data={"owner_id": "bob"})
    assert response.status_code == 200
    task_id = response.json()["task_id"]
    assert len(task_id.removeprefix("ingest_")) == 32
    doc = next(doc for doc in routes.get_docs_snapshot() if doc["document_id"] == "doc_" + task_id)
    assert doc["owner_id"] == "alice"
    assert Path(doc["filepath"]).read_bytes() == b"local fixture"
    assert client.get(f"/api/v1/status/{task_id}", headers=resource_app.headers("alice")).status_code == 200
    assert client.get(f"/api/v1/status/{task_id}", headers=resource_app.headers("bob")).status_code == 404


def test_graph_loads_only_active_version_with_real_provenance(resource_app):
    env = resource_app
    kg = Path(env.docs[0]["kg_path"])
    (kg / "versions.json").write_text('{"active_version":2}', encoding="utf-8")
    active = kg / "v2"
    active.mkdir()
    (active / "nodes.json").write_text(json.dumps({"nodes":[{
        "node_id":"n1", "label":"ACTIVE_CONTENT", "entity_type":"claim",
        "properties":{}, "grounding_status":"grounded", "page_idx":0,
    }]}), encoding="utf-8")
    (active / "edges.json").write_text('{"edges":[]}', encoding="utf-8")
    from services.document_snapshot import authorized_graph
    graph = authorized_graph([env.docs[0]], env.base / "output" / "kg")
    assert list(graph.nodes) == ["doc_a__n1"]
    assert graph.nodes["doc_a__n1"]["document_id"] == "doc_a"
    assert graph.nodes["doc_a__n1"]["document_version"] == 2
    response = env.client.get("/api/v1/graph/doc_a", headers=env.headers("alice"))
    assert response.status_code == 200
    assert "ACTIVE_CONTENT" in response.text
    assert "CONTENT_a" not in response.text and "CONTENT_b" not in response.text


def test_real_server_cors_preflight_preserves_authenticated_request_boundary(resource_app):
    from server import app
    client = TestClient(app, raise_server_exceptions=False)
    origin = "http://localhost:5173"
    preflight = client.options("/api/v1/documents", headers={"Origin":origin,
        "Access-Control-Request-Method":"GET", "Access-Control-Request-Headers":"authorization,x-project-id"})
    assert preflight.status_code == 200
    assert preflight.headers["access-control-allow-origin"] == "*"
    response = client.get("/api/v1/documents", headers={"Origin":origin})
    assert response.status_code == 401
    assert response.headers["access-control-allow-origin"] == "*"


def test_public_widget_script_is_exact_public_route(resource_app):
    from server import app
    client = TestClient(app, raise_server_exceptions=False)
    assert client.get("/static/chat-widget.js").status_code == 200
    assert client.get("/static/chat-widget.js/private").status_code == 401


@pytest.mark.parametrize("endpoint", ["/api/v1/query", "/api/v1/rag/query", "/api/v1/rag/summarize"])
def test_no_authorized_data_never_reaches_model(resource_app, monkeypatch, endpoint):
    def forbidden(*args, **kwargs):
        pytest.fail("empty authorized data reached model boundary")
    monkeypatch.setattr(resource_app.query, "_build_agent", forbidden)
    monkeypatch.setattr(resource_app.rag, "_init_rag_pipeline", forbidden)
    import generator
    monkeypatch.setattr(generator, "RAGGenerator", forbidden)
    response = resource_app.client.post(endpoint, json={"query":"x"}, headers=resource_app.headers("unknown"))
    assert response.status_code == 200
    assert response.json()["metadata"]["status"] == "no_data"


def test_delete_rejects_symlink_to_other_registered_graph(resource_app):
    env = resource_app
    link = env.base / "output" / "kg" / "alias_a"
    link.symlink_to(env.docs[1]["kg_path"], target_is_directory=True)
    env.docs[0]["kg_path"] = str(link)
    response = env.client.delete("/api/v1/documents/doc_a", headers=env.headers())
    assert response.status_code == 409
    assert (env.base / "uploads" / "a.pdf").exists()
    assert (Path(env.docs[1]["kg_path"]) / "nodes.json").exists()


def test_delete_rejects_windows_junction_to_other_registered_graph(resource_app):
    import os
    import subprocess
    if os.name != "nt":
        return  # Windows junction behavior is exercised on the target host.
    env = resource_app
    link = env.base / "output" / "kg" / "junction_a"
    subprocess.run(["cmd", "/c", "mklink", "/J", str(link), env.docs[1]["kg_path"]],
                   check=True, capture_output=True)
    try:
        assert link.is_junction()
        env.docs[0]["kg_path"] = str(link)
        response = env.client.delete("/api/v1/documents/doc_a", headers=env.headers())
        assert response.status_code == 409
        assert (env.base / "uploads" / "a.pdf").exists()
        assert (Path(env.docs[1]["kg_path"]) / "nodes.json").exists()
    finally:
        link.rmdir()


def test_ingest_explicit_legacy_cache_is_rejected_before_side_effects(resource_app, monkeypatch):
    from server import app
    import worker
    def forbidden(*args, **kwargs):
        pytest.fail("cache request reached indexing")
    monkeypatch.setattr(worker, "run_real_pipeline", forbidden)
    before = {p.name:p.read_bytes() for p in (resource_app.base / "uploads").iterdir()}
    client = TestClient(app, raise_server_exceptions=False)
    response = client.post("/api/v1/ingest", headers=resource_app.headers("alice"),
                           data={"url":"https://example.invalid/fixture.pdf", "allow_cached_mineru_output":"true"})
    assert response.status_code == 400
    assert {p.name:p.read_bytes() for p in (resource_app.base / "uploads").iterdir()} == before
