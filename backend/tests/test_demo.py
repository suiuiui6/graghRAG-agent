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
