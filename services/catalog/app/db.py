import os
from collections.abc import Iterator
from contextlib import contextmanager

import numpy as np
import psycopg
from pgvector.psycopg import register_vector
from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

# O .env usa o formato do SQLAlchemy (postgresql+psycopg://); o psycopg quer postgresql://.
DATABASE_URL = os.getenv("DATABASE_URL", "").replace("postgresql+psycopg://", "postgresql://")

FEATURE_COLUMNS = (
    "key", "scale", "camelot", "key_strength", "bpm", "bpm_confidence", "hihat_density",
    "subbass_energy", "styles", "genre_top", "vocal_presence", "vocal_gender", "vocal_confidence",
)  # fmt: skip


def _vector(vec: list[float]) -> np.ndarray:
    # O register_vector converte arrays numpy para o tipo vector (listas viram array do Postgres).
    return np.asarray(vec, dtype=np.float32)


@contextmanager
def connect() -> Iterator[psycopg.Connection]:
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
        register_vector(conn)
        yield conn


def find_track(conn, source: str, external_id: str) -> str | None:
    row = conn.execute(
        "SELECT id FROM tracks WHERE source = %s AND external_id = %s", (source, external_id)
    ).fetchone()
    return str(row["id"]) if row else None


def insert_track(conn, track: dict, features: dict, embeddings: dict[str, list[float]]) -> str:
    """Grava a faixa, os atributos e os embeddings numa transação só. Devolve o id."""
    with conn.transaction():
        track_id = conn.execute(
            """INSERT INTO tracks (source, external_id, spotify_id, title, artist, year,
                                   duration_s, dataset_genre, audio_sha, license)
               VALUES (%(source)s, %(external_id)s, %(spotify_id)s, %(title)s, %(artist)s,
                       %(year)s, %(duration_s)s, %(dataset_genre)s, %(audio_sha)s, %(license)s)
               RETURNING id""",
            {"audio_sha": None, "license": None, **track},
        ).fetchone()["id"]

        values = {c: features.get(c) for c in FEATURE_COLUMNS}
        values["styles"] = Jsonb(values["styles"]) if values["styles"] is not None else None
        cols = ", ".join(FEATURE_COLUMNS)
        params = ", ".join(f"%({c})s" for c in FEATURE_COLUMNS)
        conn.execute(
            f"INSERT INTO track_features (track_id, {cols}) VALUES (%(track_id)s, {params})",
            {"track_id": track_id, **values},
        )

        for model, vec in embeddings.items():
            conn.execute(
                "INSERT INTO track_embeddings (track_id, model, vec) VALUES (%s, %s, %s)",
                (track_id, model, _vector(vec)),
            )
    return str(track_id)


def similar(conn, model: str, vec: list[float], k: int, exclude_id: str | None) -> list[dict]:
    """k vizinhos mais próximos por distância de cosseno (sem filtros: a cascata é da F3).

    A coluna vec não tem dimensão fixa; o cast para vector(N) é o que permite ao Postgres usar
    o índice HNSW parcial do modelo (que é criado sobre vec::vector(N)).
    """
    dim = sql.SQL("vector({})").format(sql.Literal(len(vec)))
    query = sql.SQL(
        """SELECT t.id, t.title, t.artist, t.dataset_genre, f.genre_top, f.camelot, f.bpm,
                  1 - (e.vec::{dim} <=> %(vec)s) AS cosine
           FROM track_embeddings e
           JOIN tracks t ON t.id = e.track_id
           LEFT JOIN track_features f ON f.track_id = t.id
           WHERE e.model = %(model)s AND e.stem = 'mix'
             AND (%(exclude)s::uuid IS NULL OR t.id <> %(exclude)s::uuid)
           ORDER BY e.vec::{dim} <=> %(vec)s
           LIMIT %(k)s"""
    ).format(dim=dim)
    rows = conn.execute(
        query, {"vec": _vector(vec), "model": model, "k": k, "exclude": exclude_id}
    ).fetchall()
    return [{**r, "id": str(r["id"])} for r in rows]


_CANDIDATE_COLUMNS = sql.SQL(
    """t.id, t.source, t.external_id, t.spotify_id, t.title, t.artist, t.year,
       t.dataset_genre, t.audio_sha, t.license, f.camelot, f.key, f.scale, f.bpm, f.styles,
       f.genre_top, f.vocal_presence, f.vocal_gender, f.vocal_confidence"""
)


def candidates(
    conn,
    model: str,
    vec: list[float],
    cond: dict,
    *,
    bpm: tuple[float, float] | None = None,
    year: tuple[int, int] | None = None,
    exclude: list[str] = (),
    pool: int = 200,
) -> list[dict]:
    """Vizinhos mais próximos que passam pelos filtros da cascata (filtros + kNN numa consulta).

    cond vem de recommend.conditions(): keys (Camelot permitidos), styles (algum desses estilos
    no top-5 do candidato), genre (gênero amplo) e voice ({"vocal": bool, "gender": str|None}).
    """
    dim = sql.SQL("vector({})").format(sql.Literal(len(vec)))
    where = [sql.SQL("e.model = %(model)s AND e.stem = 'mix'")]
    params: dict = {"vec": _vector(vec), "model": model, "pool": pool, "exclude": list(exclude)}

    if exclude:
        where.append(sql.SQL("t.id <> ALL(%(exclude)s::uuid[])"))
    if cond.get("keys"):
        where.append(sql.SQL("f.camelot = ANY(%(keys)s)"))
        params["keys"] = cond["keys"]
    if cond.get("styles"):
        where.append(sql.SQL("f.styles ?| %(styles)s"))
        params["styles"] = cond["styles"]
    if cond.get("genre"):
        where.append(sql.SQL("f.genre_top = %(genre)s"))
        params["genre"] = cond["genre"]
    voice = cond.get("voice")
    if voice is not None:
        if voice["vocal"]:
            where.append(sql.SQL("f.vocal_presence >= 0.5"))
            if voice.get("gender"):
                where.append(sql.SQL("f.vocal_gender = %(gender)s"))
                params["gender"] = voice["gender"]
        else:
            where.append(sql.SQL("f.vocal_presence < 0.5"))
    if bpm:
        # Aceita dobro e metade do andamento (o mesmo pulso contado de outro jeito).
        where.append(
            sql.SQL(
                "(f.bpm BETWEEN %(bpm_lo)s AND %(bpm_hi)s"
                " OR f.bpm * 2 BETWEEN %(bpm_lo)s AND %(bpm_hi)s"
                " OR f.bpm / 2 BETWEEN %(bpm_lo)s AND %(bpm_hi)s)"
            )
        )
        params["bpm_lo"], params["bpm_hi"] = bpm
    if year:
        where.append(sql.SQL("t.year BETWEEN %(year_lo)s AND %(year_hi)s"))
        params["year_lo"], params["year_hi"] = year

    query = sql.SQL(
        """SELECT {cols}, 1 - (e.vec::{dim} <=> %(vec)s) AS cosine
           FROM track_embeddings e
           JOIN tracks t ON t.id = e.track_id
           JOIN track_features f ON f.track_id = t.id
           WHERE {where}
           ORDER BY e.vec::{dim} <=> %(vec)s
           LIMIT %(pool)s"""
    ).format(cols=_CANDIDATE_COLUMNS, dim=dim, where=sql.SQL(" AND ").join(where))
    rows = conn.execute(query, params).fetchall()
    return [{**r, "id": str(r["id"])} for r in rows]


def track_query(conn, track_id: str, model: str) -> dict | None:
    """Atributos e embedding de uma faixa do catálogo, para "mais parecidas com esta"."""
    row = conn.execute(
        sql.SQL(
            """SELECT {cols}, e.vec::real[] AS vec
               FROM tracks t
               JOIN track_features f ON f.track_id = t.id
               JOIN track_embeddings e ON e.track_id = t.id AND e.model = %s AND e.stem = 'mix'
               WHERE t.id = %s"""
        ).format(cols=_CANDIDATE_COLUMNS),
        (model, track_id),
    ).fetchone()
    return {**row, "id": str(row["id"])} if row else None


def get_track(conn, track_id: str) -> dict | None:
    row = conn.execute(
        sql.SQL("SELECT {cols} FROM tracks t JOIN track_features f ON f.track_id = t.id"
                " WHERE t.id = %s").format(cols=_CANDIDATE_COLUMNS),
        (track_id,),
    ).fetchone()  # fmt: skip
    return {**row, "id": str(row["id"])} if row else None
