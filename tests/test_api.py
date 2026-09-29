import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient  # noqa: E402

from app.prompt_app import app  # noqa: E402

client = TestClient(app)


def test_health_exposes_prompt_sha():
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok" and len(body["prompt_sha256"]) == 64


def test_triage_validates_input():
    assert client.post("/triage", json={"message": ""}).status_code == 422


def test_triage_always_has_disclaimer():
    r = client.post("/triage", json={"message": "I have a headache"})
    assert r.status_code == 200 and "Not a diagnosis" in r.json()["disclaimer"]
