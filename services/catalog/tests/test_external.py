import httpx
import pytest
from fastapi.testclient import TestClient

import app.main as main
from app import external


@pytest.mark.parametrize(
    ("key", "mode", "code"),
    [(0, 1, "8B"), (9, 0, "8A"), (6, 0, "11A"), (9, 1, "11B"), (1, 0, "12A"), (5, 1, "7B"),
     (4, 0, "9A"), (-1, 1, None), (None, None, None)],
)  # fmt: skip
def test_camelot_from_pitch(key, mode, code) -> None:
    assert external.camelot_from_pitch(key, mode) == code


def test_cobre_as_24_tonalidades() -> None:
    codes = {external.camelot_from_pitch(k, m) for k in range(12) for m in (0, 1)}
    assert len(codes) == 24


def _track(sid: str, title: str) -> dict:
    # Formato real de GET /v1/track/recommendation (campos que usamos).
    return {"id": f"rb-{sid}", "trackTitle": title, "artists": [{"name": f"Artista {sid}"}],
            "href": f"https://open.spotify.com/track/{sid}"}  # fmt: skip


# Tom (key, mode) e BPM de cada faixa recomendada, no formato de GET /v1/audio-features.
FEATURES = {
    "seed": (6, 0, 100.0),
    "t1": (6, 0, 101.0),   # 11A, BPM quase igual
    "t2": (6, 0, 140.0),   # 11A, BPM longe
    "t3": (1, 0, 99.0),    # 12A (compatível)
    "t4": (0, 1, 100.0),   # 8B (incompatível)
    "t5": (9, 1, 50.0),    # 11B (compatível), metade do andamento
    "book": (6, 0, 100.0), # 11A e BPM perfeito, mas é capítulo de audiolivro
    "talk": (6, 0, 100.0), # semente falada achada pela busca
}  # fmt: skip
SPEECH = {"book": 0.93, "talk": 0.9}


@pytest.fixture
def fake(monkeypatch):
    calls = []

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append(req)
        if req.url.path == "/search/genre":
            # "unknown" é uma faixa do Spotify que a ReccoBeats não tem (audio-features vazio).
            ids = ["unknown", "talk", "seed"] if req.url.params["style"] == "Synth-pop" else []
            return httpx.Response(200, json={"ids": ids})
        if req.url.path == "/v1/track/recommendation":
            order = ["book", "t4", "t2", "t1", "seed", "t3", "t5"]
            tracks = [_track(s, s.upper()) for s in order]
            return httpx.Response(200, json={"content": tracks})
        if req.url.path == "/v1/audio-features":
            content = [
                {"href": f"https://open.spotify.com/track/{i}", "key": FEATURES[i][0],
                 "mode": FEATURES[i][1], "tempo": FEATURES[i][2],
                 "speechiness": SPEECH.get(i, 0.05)}
                for i in req.url.params.get_list("ids")
                if i in FEATURES
            ]  # fmt: skip
            return httpx.Response(200, json={"content": content})
        return httpx.Response(404)

    monkeypatch.setattr(
        external, "client", lambda: httpx.Client(transport=httpx.MockTransport(handler))
    )
    return calls


QUERY = {"camelot": "11A", "bpm": 100.0, "styles": {"Electronic---House": 0.3,
         "Pop---Synth-pop": 0.2}, "genre_top": "Pop"}  # fmt: skip


def test_sementes_pelo_estilo_e_ordem_por_tom_e_bpm(fake) -> None:
    out = external.recommendations(QUERY, [], k=3, key_level="compatible")
    # House não rendeu nada; em Synth-pop saem a faixa desconhecida da ReccoBeats e a falada.
    assert out["seeds"] == ["seed"]
    ids = [r["spotify_id"] for r in out["results"]]
    assert "seed" not in ids  # a semente não volta como recomendação
    assert "book" not in ids  # audiolivro descartado mesmo com tom e BPM perfeitos
    assert ids == ["t1", "t2", "t5"]  # mesmo tom primeiro (BPM decide), depois compatíveis
    assert out["results"][0]["explanation"] == "mesmo tom 11A · 101 vs. 100 BPM · via ReccoBeats"
    assert out["results"][0]["url"] == "https://open.spotify.com/track/t1"
    assert out["relaxed"] == []


def test_relaxa_o_tom_quando_faltam_faixas(fake) -> None:
    out = external.recommendations(QUERY, ["seed"], k=5, key_level="exact")
    assert out["relaxed"] == ["key: exact → off"]  # só 2 no tom exato, 4 compatíveis
    assert [r["spotify_id"] for r in out["results"]][-1] == "t4"  # incompatível por último
    assert not any(c.url.path == "/search/genre" for c in fake)  # semente dada não busca


def test_sem_sementes(monkeypatch, fake) -> None:
    out = external.recommendations({"styles": {"Jazz---Bop": 1.0}}, [], k=3, key_level="off")
    assert out == {"results": [], "seeds": [], "relaxed": []}


def test_endpoint_e_falha_externa(fake, monkeypatch) -> None:
    c = TestClient(main.app)
    r = c.post("/recommend/external", json={"features": QUERY, "k": 2})
    assert r.status_code == 200 and len(r.json()["results"]) == 2

    def boom(*a, **k):
        raise httpx.ConnectError("sem rede")

    monkeypatch.setattr(external, "recommendations", boom)
    assert c.post("/recommend/external", json={"features": QUERY}).status_code == 502
