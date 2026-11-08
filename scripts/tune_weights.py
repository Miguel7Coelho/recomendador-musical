# /// script
# requires-python = ">=3.12"
# dependencies = ["httpx>=0.27", "psycopg[binary]>=3.2"]
# ///
"""Ajuste dos pesos da pontuação: tabela de compromisso entre gênero, tom e voz.

Para cada faixa da FMA, pede ao catálogo as 200 candidatas mais próximas SEM filtros. A resposta
já traz as notas de cada componente (cosseno, tom, estilo, voz), então qualquer combinação de
pesos é recalculada aqui, sem novas requisições. A cascata (com filtros) é medida à parte, para
três mínimos de candidatas.

Uso (com o docker compose no ar):  uv run scripts/tune_weights.py [--k 10] [--csv pesos.csv]
"""

import argparse
import csv
import itertools
import os
from pathlib import Path

import httpx
import psycopg

CATALOG = "http://localhost:8003"
POOL = 200
OFF = {"key": "off", "genre": "off", "voice": "off"}
GRID = {"key": [0.0, 0.05, 0.10, 0.15, 0.20], "genre": [0.10, 0.15, 0.25], "voice": [0.05, 0.10]}
SPEC = {"cosine": 0.55, "key": 0.20, "genre": 0.15, "voice": 0.10}


def database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        env = Path(__file__).resolve().parents[1] / ".env"
        for line in env.read_text().splitlines():
            if line.startswith("DATABASE_URL="):
                url = line.split("=", 1)[1].strip()
    url = url.replace("postgresql+psycopg://", "postgresql://")
    return url.replace("@postgres:", "@localhost:")


def metrics(queries: list[dict], results: list[list[dict]]) -> dict[str, float]:
    """Médias de gênero FMA, tom compatível (nota de tom > 0) e voz nas k recomendações."""
    genre = key = 0.0
    voice_hits = voice_n = 0
    for q, res in zip(queries, results):
        n = len(res) or 1
        genre += sum(r["dataset_genre"] == q["genre"] for r in res) / n
        key += sum(r["components"]["key"] > 0 for r in res) / n
        if q["voice"] is not None and (q["voice"] >= 0.7 or q["voice"] <= 0.3):
            vocal = q["voice"] >= 0.7
            voice_n += len(res)
            voice_hits += sum(((r["vocal_presence"] or 0) >= 0.5) == vocal for r in res)
    return {
        "p_genre": genre / len(queries),
        "p_key": key / len(queries),
        "p_voice": voice_hits / voice_n if voice_n else float("nan"),
    }


def rerank(pool: list[dict], w: dict[str, float], k: int) -> list[dict]:
    score = lambda r: sum(w[c] * r["components"][c] for c in w)  # noqa: E731
    return sorted(pool, key=score, reverse=True)[:k]


def pareto(rows: list[dict]) -> set[int]:
    """Configurações que nenhuma outra supera ao mesmo tempo em gênero e em tom."""
    best = set()
    for i, a in enumerate(rows):
        dominated = any(
            b["p_genre"] >= a["p_genre"]
            and b["p_key"] >= a["p_key"]
            and (b["p_genre"], b["p_key"]) != (a["p_genre"], a["p_key"])
            for b in rows
        )  # fmt: skip
        if not dominated:
            best.add(i)
    return best


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=10)
    ap.add_argument("--csv", type=Path, help="salva todas as configurações num CSV")
    args = ap.parse_args()

    with psycopg.connect(database_url()) as conn:
        rows = conn.execute(
            """SELECT t.id::text, t.dataset_genre, f.vocal_presence
               FROM tracks t JOIN track_features f ON f.track_id = t.id
               JOIN track_embeddings e ON e.track_id = t.id AND e.model = 'effnet_clap'
               WHERE t.source = 'fma' AND t.dataset_genre IS NOT NULL"""
        ).fetchall()
    queries = [{"id": i, "genre": g, "voice": v} for i, g, v in rows]
    print(f"{len(queries)} consultas, k = {args.k}. Buscando candidatas...")

    pools, cascades = [], {20: [], 10: [], 5: []}
    with httpx.Client(timeout=60) as client:
        for q in queries:
            # Todas as candidatas que o sistema real pontuaria (o pool inteiro), sem filtros.
            body = {"filters": OFF, "k": POOL, "pool": POOL, "min_candidates": 1}
            r = client.post(f"{CATALOG}/recommend/track/{q['id']}", json=body).raise_for_status()
            pools.append(r.json()["results"])
            for n in cascades:
                body = {"k": args.k, "min_candidates": n}
                r = client.post(f"{CATALOG}/recommend/track/{q['id']}", json=body)
                cascades[n].append(r.raise_for_status().json()["results"])

    table = []
    pure = {"cosine": 1.0, "key": 0.0, "genre": 0.0, "voice": 0.0}
    for key, genre, voice in itertools.product(GRID["key"], GRID["genre"], GRID["voice"]):
        w = {
            "cosine": round(1 - key - genre - voice, 2),
            "key": key,
            "genre": genre,
            "voice": voice,
        }
        m = metrics(queries, [rerank(p, w, args.k) for p in pools])
        table.append({"weights": w, **m})
    table.append({"weights": pure, **metrics(queries, [rerank(p, pure, args.k) for p in pools])})
    front = pareto(table)

    print("\n  cos   tom estilo   voz | gênero tom ok voz ok")
    for i in sorted(range(len(table)), key=lambda i: -table[i]["p_genre"]):
        t, w = table[i], table[i]["weights"]
        mark = " ◀ fronteira" if i in front else ""
        spec = "  (especificação)" if w == SPEC else ""
        print(f"{w['cosine']:5.2f} {w['key']:5.2f} {w['genre']:6.2f} {w['voice']:5.2f} | "
              f"{t['p_genre']:6.3f} {t['p_key']:6.3f} {t['p_voice']:6.3f}{mark}{spec}")  # fmt: skip

    print("\nCascata (filtros tom → estilo → voz) com os pesos da especificação:")
    for n, res in cascades.items():
        m = metrics(queries, res)
        print(f"  mínimo de {n:2d} candidatas: gênero {m['p_genre']:.3f}  tom ok {m['p_key']:.3f}  "
              f"voz ok {m['p_voice']:.3f}")  # fmt: skip

    if args.csv:
        with args.csv.open("w", newline="") as f:
            cols = ["cosine", "key", "genre", "voice", "p_genre", "p_key", "p_voice", "fronteira"]
            out = csv.DictWriter(f, fieldnames=cols)
            out.writeheader()
            for i, t in enumerate(table):
                row = {**t["weights"], **{c: t[c] for c in ("p_genre", "p_key", "p_voice")}}
                out.writerow({**row, "fronteira": i in front})
        print(f"\nTabela completa em {args.csv}")


if __name__ == "__main__":
    main()
