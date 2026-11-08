import httpx
import pytest
from fastapi.testclient import TestClient

import app.main as main
from app import external, lastfm


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


QUERY = {
    "camelot": "11A",
    "bpm": 100.0,
    "genre_top": "Hip Hop",
    "styles": {
        "Hip Hop---G-Funk": 0.4,
        "Folk, World, & Country---Folk": 0.3,
        "Hip Hop---Gangsta": 0.2,
        "Hip Hop---Trap": 0.01,
    },
}

TAGS = {
    "g-funk": ["both", "halftime", "samekey", "fast", "absent", "nodata", "speech", "bro1"],
    "gangsta rap": ["both", "bro2", "bro3"],
    "hip-hop": ["broad"],
    "folk": ["folky"],
}
# Tom (key, mode) e BPM, no formato de GET /v1/audio-features.
AUDIO = {
    "both": (0, 1, 104.0),  # nas duas etiquetas, tom incompatível
    "halftime": (0, 1, 50.0),  # metade do andamento
    "samekey": (6, 0, 104.0),  # 11A
    "fast": (6, 0, 140.0),  # 11A, mas fora da faixa de andamento
    "speech": (6, 0, 100.0),
    "bro1": (0, 1, 101.0),
    "bro2": (0, 1, 102.0),
    "bro3": (0, 1, 103.0),
    "broad": (0, 1, 100.0),
    "folky": (6, 0, 100.0),
}
ARTIST = {"bro1": "Bros", "bro2": "Bros", "bro3": "Bros", "Seed": "Fulano"}
SIMILAR = [("Seed", 1.0), ("folky", 0.8), ("fast", 0.7), ("samekey", 0.4)]
KNOWN = {"title": "Seed", "artist": "Fulano"}


@pytest.fixture
def fake(monkeypatch):
    calls = []

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append(req)
        if req.url.host == "ws.audioscrobbler.com":
            if req.url.params["method"] == "track.getsimilar":
                if req.url.params["artist"] == "Desconhecido":
                    return httpx.Response(400, json={"error": 6})
                items = [{"name": n, "artist": {"name": ARTIST.get(n, f"Artista {n}")},
                          "match": str(m)} for n, m in SIMILAR]  # fmt: skip
                return httpx.Response(200, json={"similartracks": {"track": items}})
            if req.url.params["method"] == "track.search":
                items = [
                    {"name": "kanye-stronger", "artist": "x", "listeners": "5"},
                    {"name": "lixo", "artist": "<Unknown>", "listeners": "50"},
                    {"name": "STRONGER", "artist": "kanye west", "listeners": "9"},
                    {"name": "Stronger", "artist": "Kanye West", "listeners": "900"},
                ]
                return httpx.Response(200, json={"results": {"trackmatches": {"track": items}}})
            names = TAGS.get(req.url.params["tag"], [])
            items = [{"name": n, "artist": {"name": ARTIST.get(n, f"Artista {n}")}} for n in names]
            return httpx.Response(200, json={"tracks": {"track": items}})
        if req.url.path == "/match":
            title = req.read().decode().split('"title":"')[1].split('"')[0]
            if title == "absent":
                return httpx.Response(200, json={"match": None})
            match = {"spotify_id": title, "title": title, "artists": [ARTIST.get(title, title)],
                     "url": f"https://open.spotify.com/track/{title}"}  # fmt: skip
            return httpx.Response(200, json={"match": match})
        if req.url.path == "/v1/audio-features":
            content = [
                {"href": f"https://open.spotify.com/track/{i}", "key": AUDIO[i][0],
                 "mode": AUDIO[i][1], "tempo": AUDIO[i][2],
                 "speechiness": 0.9 if i == "speech" else 0.05}
                for i in req.url.params.get_list("ids")
                if i in AUDIO
            ]  # fmt: skip
            return httpx.Response(200, json={"content": content})
        return httpx.Response(404)

    http = httpx.Client(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(external, "client", lambda: http)
    monkeypatch.setattr(lastfm, "client", lambda: http)
    lastfm.top_tracks.cache_clear()
    lastfm.similar_tracks.cache_clear()
    lastfm.search_songs.cache_clear()
    external._spotify_match.cache_clear()
    return calls


def test_etiquetas_so_do_genero_principal() -> None:
    assert external.style_tags(QUERY) == pytest.approx(
        {"g-funk": 0.4, "gangsta rap": 0.2, "hip-hop": 0.1}
    )
    assert external.style_tags({}) == {}


def _ids(out: dict) -> list[str]:
    return [r["spotify_id"] for r in out["results"]]


def test_genero_elimina_e_nunca_procura_outro_genero(fake) -> None:
    out = external.recommendations(QUERY, [], k=20)
    assert "folky" not in _ids(out)
    tags = {c.url.params["tag"] for c in fake if c.url.host == "ws.audioscrobbler.com"}
    assert tags == {"g-funk", "gangsta rap", "hip-hop"}


def test_andamento_elimina_e_aceita_metade(fake) -> None:
    ids = _ids(external.recommendations(QUERY, [], k=20))
    assert "fast" not in ids and "halftime" in ids


def test_descarta_o_que_nao_da_para_confirmar(fake) -> None:
    ids = _ids(external.recommendations(QUERY, [], k=20))
    assert "absent" not in ids  # não está no Spotify
    assert "nodata" not in ids  # sem andamento na ReccoBeats
    assert "speech" not in ids


def test_ordem_por_genero_e_tom_como_bonus(fake) -> None:
    results = external.recommendations(QUERY, [], k=20)["results"]
    ids = [r["spotify_id"] for r in results]
    assert ids[0] == "both"  # apareceu em duas etiquetas
    assert ids.index("samekey") < ids.index("bro1")  # o tom desempata dentro da mesma etiqueta
    samekey = next(r for r in results if r["spotify_id"] == "samekey")
    assert samekey["explanation"] == "g-funk · 104 vs. 100 BPM · mesmo tom 11A"
    assert samekey["url"] == "https://open.spotify.com/track/samekey"


def test_limita_faixas_por_artista(fake) -> None:
    results = external.recommendations(QUERY, [], k=20)["results"]
    assert sum(r["artists"] == ["Bros"] for r in results) == 2


def test_exclui_a_faixa_de_origem(fake) -> None:
    assert "both" not in _ids(external.recommendations(QUERY, ["both"], k=20))


def test_descarta_ruido_e_audio_repetido(monkeypatch) -> None:
    def audio(energy: float) -> dict:
        fields = dict.fromkeys(external.AUDIO_FIELDS, 0.5)
        return {**fields, "energy": energy, "key": 6, "mode": 0, "tempo": 100.0}

    names = {"n1": "挑整身體白噪音", "n2": "Deep White Noise for Sleep", "a": "Jazz Room",
             "b": "Jazz Swing", "c": "Ambient Piece"}  # fmt: skip
    pairs = [
        ({"tags": ["x"], "weight": 1.0, "order": i, "title": t, "artist": s},
         {"spotify_id": s, "title": t, "artists": [s], "url": "u"})
        for i, (s, t) in enumerate(names.items())
    ]  # fmt: skip
    feats = {"n1": audio(0.3), "n2": audio(0.31), "a": audio(0.15), "b": audio(0.15),
             "c": audio(0.07)}  # fmt: skip
    monkeypatch.setattr(external, "style_tags", lambda f: {"x": 1.0})
    monkeypatch.setattr(external, "_tagged_tracks", lambda tags: [])
    monkeypatch.setattr(external, "_find_on_spotify", lambda tracks: pairs)
    monkeypatch.setattr(external, "_recco_features", lambda ids: feats)

    assert _ids(external.recommendations({"bpm": 100.0}, [], k=10)) == ["a", "c"]


def test_ouvintes_vem_primeiro_e_dispensam_o_genero(fake) -> None:
    results = external.recommendations(QUERY, [], k=2, track=KNOWN)["results"]
    assert [r["spotify_id"] for r in results] == ["folky", "samekey"]  # folk entra pelos ouvintes
    assert results[0]["explanation"].startswith("ouvintes também escutam")


def test_ouvintes_respeitam_o_andamento_e_a_propria_faixa_sai(fake) -> None:
    ids = _ids(external.recommendations(QUERY, [], k=20, track=KNOWN))
    assert "fast" not in ids and "Seed" not in ids


def test_etiquetas_completam_a_lista(fake) -> None:
    ids = _ids(external.recommendations(QUERY, [], k=20, track=KNOWN))
    assert ids[:2] == ["folky", "samekey"] and "both" in ids


def test_lista_cheia_nao_consulta_etiquetas(fake) -> None:
    external.recommendations(QUERY, [], k=2, track=KNOWN)
    assert not any(c.url.params.get("method") == "tag.gettoptracks" for c in fake)


def test_musica_sem_dados_usa_etiquetas(fake) -> None:
    track = {"title": "Beat", "artist": "Desconhecido"}
    assert _ids(external.recommendations(QUERY, [], k=1, track=track)) == ["both"]


def test_busca_de_musicas_sem_repetir(fake) -> None:
    r = TestClient(main.app).get("/songs/search", params={"q": "stro"})
    assert r.json() == {
        "results": [
            {"title": "Stronger", "artist": "Kanye West"},
            {"title": "kanye-stronger", "artist": "x"},
        ]
    }


def test_sem_estilos_nao_recomenda(fake) -> None:
    assert external.recommendations({"bpm": 100.0}, [], k=3)["results"] == []


def test_uma_busca_falha_as_outras_seguem(monkeypatch) -> None:
    def match(title, artist):
        if title == "ruim":
            raise httpx.ConnectError("sem rede")
        return {"spotify_id": title}

    monkeypatch.setattr(external, "_spotify_match", match)
    tracks = [{"title": "boa", "artist": "x"}, {"title": "ruim", "artist": "y"}]
    assert external._find_on_spotify(tracks) == [(tracks[0], {"spotify_id": "boa"})]

    with pytest.raises(httpx.ConnectError):
        external._find_on_spotify([tracks[1]])


def test_endpoint_e_falha_externa(fake, monkeypatch) -> None:
    c = TestClient(main.app)
    r = c.post("/recommend/external", json={"features": QUERY, "k": 2})
    assert r.status_code == 200 and len(r.json()["results"]) == 2

    def boom(*a, **k):
        raise httpx.ConnectError("https://ws.audioscrobbler.com/2.0/?api_key=SEGREDO")

    monkeypatch.setattr(external, "recommendations", boom)
    r = c.post("/recommend/external", json={"features": QUERY})
    assert r.status_code == 502 and "SEGREDO" not in r.text  # a URL do erro contém a chave
