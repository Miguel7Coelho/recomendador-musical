from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient

import app.main as main

TRACK = {
    "source": "fma",
    "external_id": "2",
    "title": "Food",
    "artist": "AWOL",
    "dataset_genre": "Hip-Hop",
    "features": {"camelot": "8A", "bpm": 92.0, "styles": {"Hip Hop---Boom Bap": 0.4}},
    "embeddings": {"clap": [0.1, 0.2], "effnet": [0.3]},
}


@pytest.fixture
def fake_db(monkeypatch):
    state = {"tracks": {}, "inserted": []}

    @contextmanager
    def connect():
        yield None

    def find_track(conn, source, external_id):
        return state["tracks"].get((source, external_id))

    def insert_track(conn, track, features, embeddings):
        state["inserted"].append((track, features, embeddings))
        state["tracks"][(track["source"], track["external_id"])] = "id-1"
        return "id-1"

    monkeypatch.setattr(main.db, "connect", connect)
    monkeypatch.setattr(main.db, "find_track", find_track)
    monkeypatch.setattr(main.db, "insert_track", insert_track)
    monkeypatch.setattr(
        main.db, "similar", lambda conn, model, vec, k, exclude: [{"id": "x", "model": model}] * k
    )
    return state


def test_cria_e_nao_duplica(fake_db) -> None:
    c = TestClient(main.app)
    assert c.post("/tracks", json=TRACK).json() == {"id": "id-1", "created": True}
    assert c.post("/tracks", json=TRACK).json() == {"id": "id-1", "created": False}
    assert len(fake_db["inserted"]) == 1
    track, features, embeddings = fake_db["inserted"][0]
    assert track["dataset_genre"] == "Hip-Hop" and "features" not in track
    assert set(embeddings) == {"clap", "effnet"}


def test_lookup(fake_db) -> None:
    c = TestClient(main.app)
    assert c.get("/tracks/lookup", params={"source": "fma", "external_id": "2"}).status_code == 404
    c.post("/tracks", json=TRACK)
    assert c.get("/tracks/lookup", params={"source": "fma", "external_id": "2"}).json() == {
        "id": "id-1"
    }


def test_validacao(fake_db) -> None:
    c = TestClient(main.app)
    assert c.post("/tracks", json={**TRACK, "audio_sha": "../x"}).status_code == 422
    assert c.post("/tracks", json={**TRACK, "source": "spotify"}).status_code == 422
    assert c.post("/tracks", json={**TRACK, "embeddings": {}}).status_code == 422
    assert c.post("/similar", json={"model": "clap", "vec": [0.1], "k": 0}).status_code == 422


def test_similar(fake_db) -> None:
    r = TestClient(main.app).post("/similar", json={"model": "clap", "vec": [0.1], "k": 3})
    assert len(r.json()["results"]) == 3
