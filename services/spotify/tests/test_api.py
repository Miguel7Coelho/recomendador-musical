import json
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient
from tests.conftest import track

import app.main as main


@pytest.fixture
def client(fake, monkeypatch):
    states, saved = {}, {}
    monkeypatch.setattr(main, "state_put", lambda s, v: states.__setitem__(s, v))
    monkeypatch.setattr(main, "state_pop", lambda s: states.pop(s, None))
    cache = {}
    monkeypatch.setattr(main, "match_get", cache.get)
    monkeypatch.setattr(main, "match_put", lambda k, v: cache.__setitem__(k, json.dumps(v)))
    monkeypatch.setattr(main.sessions, "save", lambda sid, uid, name, t: saved.update({sid: uid}))
    monkeypatch.setattr(main.sessions, "access_token", lambda sid: "tok" if sid in saved else None)
    c = TestClient(main.app)
    c.saved = saved
    return c


def test_login_completo(client, fake) -> None:
    r = client.get("/auth/url").json()
    state = parse_qs(urlparse(r["url"]).query)["state"][0]
    assert state == r["state"]

    out = client.post("/auth/exchange", json={"code": "c", "state": state}).json()
    assert out["display_name"] == "Miguel" and client.saved[out["session_id"]] == "miguel"
    token_req = next(c for c in fake.calls if c.url.path == "/api/token")
    assert b"code_verifier=" in token_req.content  # PKCE de verdade

    # O state só vale uma vez.
    assert client.post("/auth/exchange", json={"code": "c", "state": state}).status_code == 400


def test_playlist_exige_login(client) -> None:
    body = {"name": "Minha", "spotify_ids": ["a", "b"]}
    assert client.post("/playlists", json=body).status_code == 401
    client.saved["sess"] = "miguel"
    r = client.post("/playlists", json=body, headers={"X-Session": "sess"})
    assert r.json() == {"id": "pl1", "url": "https://open.spotify.com/x"}


def _searches(fake) -> int:
    return sum(c.url.path == "/v1/search" for c in fake.calls)


def test_match_guardado_nao_busca_de_novo(client, fake) -> None:
    fake.search_results["track:Food artist:AWOL"] = [track("t1", "Food", "AWOL")]
    body = {"title": "Food", "artist": "AWOL"}
    first = client.post("/match", json=body).json()
    assert first["match"]["spotify_id"] == "t1"
    assert client.post("/match", json=body).json() == first
    assert _searches(fake) == 1


def test_match_inexistente_tambem_fica_guardado(client, fake) -> None:
    body = {"title": "Nada", "artist": "Ninguem"}
    assert client.post("/match", json=body).json() == {"match": None}
    assert client.post("/match", json=body).json() == {"match": None}
    assert _searches(fake) == 1


def test_bloqueio_do_spotify_para_de_chamar(client, fake) -> None:
    fake.rate_limited = True
    r = client.post("/match", json={"title": "Food", "artist": "AWOL"})
    assert r.status_code == 429 and r.headers["retry-after"] == "120"
    r = client.post("/match", json={"title": "Outra", "artist": "AWOL"})
    assert r.status_code == 429 and _searches(fake) == 1  # não insistiu


def test_bloqueio_nao_e_guardado_como_sem_resultado(client, fake, monkeypatch) -> None:
    fake.rate_limited = True
    body = {"title": "Food", "artist": "AWOL"}
    assert client.post("/match", json=body).status_code == 429
    fake.rate_limited = False
    monkeypatch.setitem(main.spotify._blocked, "until", 0.0)
    fake.search_results["track:Food artist:AWOL"] = [track("t1", "Food", "AWOL")]
    assert client.post("/match", json=body).json()["match"]["spotify_id"] == "t1"


def test_validacao(client) -> None:
    assert client.post("/playlists", json={"name": "x", "spotify_ids": []}).status_code == 422
    assert client.post("/match", json={"title": "", "artist": "a"}).status_code == 422
