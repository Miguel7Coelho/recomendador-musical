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
