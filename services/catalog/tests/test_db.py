"""Testes do SQL contra um Postgres de verdade com pgvector.

Só rodam com TEST_DATABASE_URL definido (a CI sobe um contêiner para isso). ATENÇÃO: o teste
APAGA o schema public desse banco antes de recriar as tabelas com o infra/init.sql.
"""

import os
from pathlib import Path

import numpy as np
import psycopg
import pytest

from app import db

URL = os.getenv("TEST_DATABASE_URL")
INIT_SQL = Path(__file__).resolve().parents[3] / "infra" / "init.sql"

pytestmark = pytest.mark.skipif(not URL, reason="TEST_DATABASE_URL não definido")


@pytest.fixture
def conn(monkeypatch):
    with psycopg.connect(URL, autocommit=True) as admin:
        admin.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
        admin.execute(INIT_SQL.read_text())
    monkeypatch.setattr(db, "DATABASE_URL", URL)
    with db.connect() as c:
        yield c


def track(external_id: str, genre: str) -> dict:
    return {
        "source": "fma", "external_id": external_id, "spotify_id": None, "title": "t",
        "artist": "a", "year": 2010, "duration_s": 30.0, "dataset_genre": genre,
    }  # fmt: skip


FEATURES = {"camelot": "8A", "bpm": 120.0, "styles": {"Pop---Indie Pop": 0.5}, "genre_top": "Pop"}


def test_insere_busca_e_vizinhos(conn) -> None:
    def add(tid: str, genre: str, clap: list, effnet: list) -> str:
        return db.insert_track(conn, track(tid, genre), FEATURES, {"clap": clap, "effnet": effnet})

    a = add("1", "Pop", [1.0, 0.0], [1.0, 0, 0])
    b = add("2", "Pop", [0.9, 0.1], [0, 1.0, 0])
    c = add("3", "Rock", [0.0, 1.0], [0, 0, 1.0])

    assert db.find_track(conn, "fma", "2") == b
    assert db.find_track(conn, "fma", "999") is None

    res = db.similar(conn, "clap", [1.0, 0.0], k=2, exclude_id=a)
    assert [r["id"] for r in res] == [b, c]
    assert res[0]["cosine"] > res[1]["cosine"]
    assert res[0]["dataset_genre"] == "Pop" and res[0]["camelot"] == "8A"

    # Modelos com dimensões diferentes convivem na mesma tabela.
    assert [r["id"] for r in db.similar(conn, "effnet", [0, 0, 1.0], k=1, exclude_id=None)] == [c]

    row = conn.execute("SELECT styles FROM track_features WHERE track_id = %s", (a,)).fetchone()
    assert row["styles"] == {"Pop---Indie Pop": 0.5}


def test_duplicata_e_atomicidade(conn) -> None:
    db.insert_track(conn, track("1", "Pop"), FEATURES, {"clap": [1.0, 0.0]})
    with pytest.raises(psycopg.errors.UniqueViolation):
        db.insert_track(conn, track("1", "Pop"), FEATURES, {"clap": [1.0, 0.0]})
    conn.rollback()
    # Embedding inválido (vazio) desfaz a faixa inteira: nada pela metade no banco.
    with pytest.raises(psycopg.Error):
        db.insert_track(conn, track("2", "Pop"), FEATURES, {"clap": []})
    conn.rollback()
    assert db.find_track(conn, "fma", "2") is None


def test_busca_usa_indice_hnsw_do_modelo_combinado(conn) -> None:
    rng = np.random.default_rng(0)
    for i in range(30):
        v = rng.normal(size=1792)
        db.insert_track(
            conn, track(str(i), "Pop"), FEATURES, {"effnet_clap": list(v / (v @ v) ** 0.5)}
        )
    conn.execute("ANALYZE track_embeddings")
    # Tabela pequena: desliga as alternativas para o planejador mostrar se o índice serve à busca.
    conn.execute("SET enable_seqscan = off")
    conn.execute("SET enable_sort = off")
    q = db._vector([1.0] + [0.0] * 1791)
    plan = conn.execute(
        """EXPLAIN SELECT track_id FROM track_embeddings
           WHERE model = 'effnet_clap' ORDER BY vec::vector(1792) <=> %s LIMIT 5""",
        (q,),
    ).fetchall()
    assert "track_embeddings_effnet_clap_hnsw" in str(plan)
    assert len(db.similar(conn, "effnet_clap", [1.0] + [0.0] * 1791, k=5, exclude_id=None)) == 5


def _features(camelot, styles, genre, presence, gender=None, conf=None, bpm=100.0):
    return {
        "camelot": camelot, "bpm": bpm, "styles": styles, "genre_top": genre,
        "vocal_presence": presence, "vocal_gender": gender, "vocal_confidence": conf,
    }  # fmt: skip


@pytest.fixture
def catalogo(conn):
    """Seis faixas com atributos escolhidos para exercitar cada filtro."""
    pop = {"Pop---Synth-pop": 0.6, "Electronic---House": 0.2}
    rock = {"Rock---Punk": 0.7}
    rows = {
        "exata": _features("11A", pop, "Pop", 0.9, "female", 0.9, bpm=102),
        "vizinha": _features("12A", pop, "Pop", 0.9, "female", 0.8),
        "masculina": _features("11A", pop, "Pop", 0.9, "male", 0.9),
        "instrumental": _features("11A", pop, "Pop", 0.1),
        "rock": _features("11A", rock, "Rock", 0.9, "female", 0.9, bpm=51),
        "longe": _features("5B", rock, "Rock", 0.1, bpm=170),
    }
    ids = {}
    for i, (name, feats) in enumerate(rows.items()):
        vec = [1.0, i * 0.1, 0.0]
        ids[name] = db.insert_track(conn, track(str(i), "x"), feats, {"m": vec})
    return ids


def _names(ids, rows):
    inv = {v: k for k, v in ids.items()}
    return {inv[r["id"]] for r in rows}


def test_filtros_da_cascata(conn, catalogo) -> None:
    q = [1.0, 0.0, 0.0]
    get = lambda cond, **kw: _names(catalogo, db.candidates(conn, "m", q, cond, **kw))  # noqa: E731
    none = {"keys": None, "styles": None, "genre": None, "voice": None}

    assert get(none) == set(catalogo)
    assert get({**none, "keys": ["11A"]}) == {"exata", "masculina", "instrumental", "rock"}
    assert get({**none, "keys": ["10A", "11A", "11B", "12A"]}) >= {"vizinha"}
    assert get({**none, "styles": ["Pop---Synth-pop"]}) == {
        "exata", "vizinha", "masculina", "instrumental"
    }  # fmt: skip
    assert get({**none, "genre": "Rock"}) == {"rock", "longe"}
    assert get({**none, "voice": {"vocal": True, "gender": "female"}}) == {
        "exata", "vizinha", "rock"
    }  # fmt: skip
    assert get({**none, "voice": {"vocal": False}}) == {"instrumental", "longe"}
    # Faixa 101–106: 102 entra direto e 51 entra pelo dobro; 100 e 170 (85 na metade) ficam fora.
    assert get(none, bpm=(101, 106)) == {"exata", "rock"}
    assert get(none, exclude=[catalogo["exata"]]) == set(catalogo) - {"exata"}


def test_track_query(conn, catalogo) -> None:
    q = db.track_query(conn, catalogo["exata"], "m")
    assert q["camelot"] == "11A" and q["vec"] == [1.0, 0.0, 0.0]
    assert db.track_query(conn, catalogo["exata"], "outro_modelo") is None


def test_endpoint_mais_parecidas_com_esta(conn, catalogo) -> None:
    from fastapi.testclient import TestClient

    from app.main import app

    c = TestClient(app)
    body = {"model": "m", "min_candidates": 2}
    r = c.post(f"/recommend/track/{catalogo['exata']}", json=body).json()
    names = [_names(catalogo, [x]).pop() for x in r["results"]]
    # Tom exato + synth-pop + vocal feminino: só sobra "rock" (estilo diferente) → relaxa o tom.
    assert "exata" not in names
    assert names[0] == "vizinha"
    assert r["relaxed"] and r["levels"]["key"] != "exact"
    assert r["results"][0]["explanation"].startswith("tom compatível 12A · synth-pop · vocal")

    travado = {**body, "filters": {"locked": ["key"]}}
    r = c.post(f"/recommend/track/{catalogo['exata']}", json=travado).json()
    assert all(x["camelot"] == "11A" for x in r["results"])  # tom travado nunca relaxa

    import uuid

    assert c.post(f"/recommend/track/{uuid.uuid4()}", json=body).status_code == 404


def test_audio_e_licenca(conn) -> None:
    t = {**track("9", "Pop"), "audio_sha": "a" * 64, "license": "CC BY 4.0"}
    tid = db.insert_track(conn, t, FEATURES, {"m": [1.0, 0.0]})
    got = db.get_track(conn, tid)
    assert got["audio_sha"] == "a" * 64 and got["license"] == "CC BY 4.0"
    assert db.candidates(conn, "m", [1.0, 0.0], {})[0]["license"] == "CC BY 4.0"
    assert db.get_track(conn, "00000000-0000-0000-0000-000000000000") is None
