from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

import app.main as main


@pytest.fixture
def client(fake, monkeypatch):
    states, saved = {}, {}
    monkeypatch.setattr(main, "state_put", lambda s, v: states.__setitem__(s, v))
    monkeypatch.setattr(main, "state_pop", lambda s: states.pop(s, None))
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


def test_validacao(client) -> None:
    assert client.post("/playlists", json={"name": "x", "spotify_ids": []}).status_code == 422
    assert client.post("/match", json={"title": "", "artist": "a"}).status_code == 422
