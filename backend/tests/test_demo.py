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
