from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import app.main as main


@pytest.fixture
def client(monkeypatch):
    calls = {"upload": [], "delay": []}
    monkeypatch.setattr(main, "stems_cached", lambda sha: False)
    monkeypatch.setattr(main, "upload", lambda path, key: calls["upload"].append(key))
    monkeypatch.setattr(
        main.separate,
        "delay",
        lambda sha: calls["delay"].append(sha) or SimpleNamespace(id="job-1"),
    )
    c = TestClient(main.app)
    c.calls = calls
    return c


def post(client, path):
    with open(path, "rb") as f:
        return client.post("/separate", files={"file": (path.name, f)})


def test_enfileira(client, make_tone) -> None:
    r = post(client, make_tone())
    assert r.status_code == 202
    body = r.json()
    assert body["status"] == "queued" and body["job_id"] == "job-1"
    assert client.calls["upload"] == [f"inputs/{body['sha']}.wav"]
    assert client.calls["delay"] == [body["sha"]]


def test_cache_nao_enfileira(client, make_tone, monkeypatch) -> None:
    monkeypatch.setattr(main, "stems_cached", lambda sha: True)
    r = post(client, make_tone())
    assert r.status_code == 200
    assert r.json()["cached"] is True
    assert set(r.json()["stems"]) == {"vocals", "drums", "bass", "other"}
    assert client.calls["delay"] == []


def test_audio_invalido(client, tmp_path) -> None:
    bad = tmp_path / "x.mp3"
    bad.write_bytes(b"nada" * 50)
    assert post(client, bad).status_code == 400


def test_arquivo_grande(client, make_tone, monkeypatch) -> None:
    monkeypatch.setattr(main, "MAX_UPLOAD_BYTES", 100)
    assert post(client, make_tone()).status_code == 413


@pytest.mark.parametrize(
    ("state", "result", "esperado"),
    [
        ("PENDING", None, {"status": "pending"}),
        ("STARTED", None, {"status": "started"}),
        ("SUCCESS", {"sha": "abc", "stems": {}, "cached": False},
         {"status": "done", "sha": "abc", "stems": {}, "cached": False}),
        ("FAILURE", RuntimeError("boom"), {"status": "failed", "error": "boom"}),
    ],
)  # fmt: skip
def test_status(client, monkeypatch, state, result, esperado) -> None:
    monkeypatch.setattr(
        main, "AsyncResult", lambda *a, **k: SimpleNamespace(state=state, result=result)
    )
    assert client.get("/separate/job-1").json() == esperado
