import io
import runpy
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from server import app

    with TestClient(app) as test_client:
        yield test_client


def test_demo_fixture_contains_grounded_answer(client):
    response = client.get("/api/v1/demo/sample")

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "offline"
    assert payload["document_id"] == "sample-handbook"
    assert payload["answer"].strip()
    assert payload["sources"]

    document = payload["document"]
    entities = {entity["id"] for entity in payload["entities"]}
    relations = payload["relations"]
    source = payload["sources"][0]

    assert source["document_id"] == document["id"] == payload["document_id"]
    assert source["start"] >= 0
    assert source["end"] <= len(document["text"])
    assert document["text"][source["start"] : source["end"]] == source["span"]
    assert set(source["entity_ids"]) <= entities
    assert relations
    assert relations[0]["source"] in entities
    assert relations[0]["target"] in entities


def test_demo_missing_fixture_returns_actionable_error(client, monkeypatch):
    from routes import demo

    monkeypatch.setattr(demo, "FIXTURE_PATH", demo.FIXTURE_PATH.with_name("missing.json"))

    response = client.get("/api/v1/demo/sample")

    assert response.status_code == 503
    assert response.json() == {"detail": "Offline demo fixture is unavailable."}


@pytest.mark.parametrize(
    "fixture_text",
    [
        pytest.param('{"answer": "unterminated}', id="malformed-json"),
        pytest.param("[\"fixture-secret\"]", id="array-json"),
        pytest.param("42", id="scalar-json"),
    ],
)
def test_demo_malformed_or_non_object_fixture_returns_safe_error(
    client, monkeypatch, fixture_text
):
    from routes import demo

    class InMemoryFixture:
        def open(self, *, encoding):
            return io.StringIO(fixture_text)

    monkeypatch.setattr(demo, "FIXTURE_PATH", InMemoryFixture())

    response = client.get("/api/v1/demo/sample")

    assert response.status_code == 503
    assert response.json() == {"detail": "Offline demo fixture is unavailable."}
    assert fixture_text not in response.text
    assert "fixture-secret" not in response.text


def test_offline_demo_smoke_script_imports_local_backend(monkeypatch):
    repo_root = Path(__file__).resolve().parents[2]
    backend_root = str(repo_root / "backend")
    smoke_script = repo_root / "tools" / "run_offline_demo.py"
    monkeypatch.setattr(sys, "path", ["foreign-backend", backend_root, *sys.path])
    sys.modules.pop("server", None)

    runpy.run_path(str(smoke_script), run_name="offline_demo_regression")

    assert sys.path[0] == backend_root
    assert Path(sys.modules["server"].__file__).resolve() == Path(backend_root) / "server.py"
