from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import app.main as main

SHA = "a" * 64


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(main, "get_json", lambda key: None)
    monkeypatch.setattr(main.analyze, "delay", lambda sha: SimpleNamespace(id="job-1"))
    return TestClient(main.app)


def test_enfileira(client) -> None:
    r = client.post("/analyze", json={"sha": SHA})
    assert r.status_code == 202
    assert r.json() == {"status": "queued", "job_id": "job-1", "sha": SHA}


def test_cache(client, monkeypatch) -> None:
    monkeypatch.setattr(main, "get_json", lambda key: {"features": {"camelot": "8A"}})
    r = client.post("/analyze", json={"sha": SHA})
    assert r.status_code == 200
    assert r.json()["cached"] is True
    assert r.json()["features"] == {"camelot": "8A"}


def test_sha_invalido(client) -> None:
    assert client.post("/analyze", json={"sha": "../../etc"}).status_code == 422


def test_status(client, monkeypatch) -> None:
    done = SimpleNamespace(state="SUCCESS", result={"sha": SHA, "features": {}, "cached": False})
    monkeypatch.setattr(main, "AsyncResult", lambda *a, **k: done)
    assert client.get("/analyze/job-1").json()["status"] == "done"
