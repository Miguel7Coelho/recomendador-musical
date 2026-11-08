# /// script
# requires-python = ">=3.12"
# dependencies = ["httpx>=0.27", "psycopg[binary]>=3.2"]
# ///
"""Compara três formas de recomendar, usando cada faixa da FMA do catálogo como consulta.

  1. só embedding        kNN puro pelo vetor combinado (sem filtros, só o cosseno)
  2. pontuação           sem filtros, com a pontuação 0,55/0,20/0,15/0,10
  3. cascata + pontuação filtros tom → estilo → voz com relaxamento, depois a pontuação

Métricas nas k primeiras recomendações (média sobre as consultas):
  gênero FMA   fração com o mesmo gênero da FMA da consulta
  tom          fração com tom igual ou compatível na roda de Camelot
  BPM ±8%      fração com andamento a até 8% (aceitando dobro/metade)
  voz          fração com a mesma presença de voz (só consultas com voz inequívoca)

Uso (com o docker compose no ar):  uv run scripts/eval_recommend.py [--k 10]
"""

import argparse
import os
from pathlib import Path

import httpx
import psycopg

CATALOG = "http://localhost:8003"
NO_FILTERS = {"key": "off", "genre": "off", "voice": "off"}
CONFIGS = {
    "só embedding": {
        "filters": NO_FILTERS,
        "weights": {"cosine": 1.0, "key": 0.0, "genre": 0.0, "voice": 0.0},
    },
    "pontuação": {"filters": NO_FILTERS},
    "cascata + pontuação": {},
}


def database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        env = Path(__file__).resolve().parents[1] / ".env"
        for line in env.read_text().splitlines():
            if line.startswith("DATABASE_URL="):
                url = line.split("=", 1)[1].strip()
    url = url.replace("postgresql+psycopg://", "postgresql://")
    return url.replace("@postgres:", "@localhost:")


def camelot_neighbors(code: str) -> set[str]:
    n, letter = int(code[:-1]), code[-1]
    other = "B" if letter == "A" else "A"
    return {f"{(n - 2) % 12 + 1}{letter}", f"{n % 12 + 1}{letter}", f"{n}{other}"}


def bpm_close(a: float | None, b: float | None) -> bool:
    if not a or not b:
        return False
    return min(abs(a * m - b) / b for m in (0.5, 1.0, 2.0)) <= 0.08


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=10)
    args = ap.parse_args()

    with psycopg.connect(database_url()) as conn:
        queries = conn.execute(
            """SELECT t.id::text, t.dataset_genre, f.camelot, f.bpm, f.vocal_presence
               FROM tracks t JOIN track_features f ON f.track_id = t.id
               JOIN track_embeddings e ON e.track_id = t.id AND e.model = 'effnet_clap'
               WHERE t.source = 'fma' AND t.dataset_genre IS NOT NULL"""
        ).fetchall()
    print(f"{len(queries)} consultas, k = {args.k}\n")

    header = f"{'':22s} {'gênero FMA':>11s} {'tom':>7s} {'BPM ±8%':>8s} {'voz':>7s} {'relaxou':>8s}"
    print(header)
    with httpx.Client(timeout=60) as client:
        for name, opts in CONFIGS.items():
            genre = key = bpm = 0.0
            voice_hits = voice_n = relaxed = 0
            for tid, qgenre, qkey, qbpm, qvoice in queries:
                body = {"k": args.k, **opts}
                r = client.post(f"{CATALOG}/recommend/track/{tid}", json=body).raise_for_status()
                data = r.json()
                res = data["results"]
                n = len(res) or 1
                allowed = ({qkey} | camelot_neighbors(qkey)) if qkey else set()
                genre += sum(x["dataset_genre"] == qgenre for x in res) / n
                key += sum(x["camelot"] in allowed for x in res) / n
                bpm += sum(bpm_close(x["bpm"], qbpm) for x in res) / n
                relaxed += bool(data["relaxed"])
                if qvoice is not None and (qvoice >= 0.7 or qvoice <= 0.3):
                    voice_n += len(res)
                    voice_hits += (
                        sum((x["vocal_presence"] or 0) >= 0.5 for x in res)
                        if qvoice >= 0.7
                        else sum((x["vocal_presence"] or 0) < 0.5 for x in res)
                    )
            q = len(queries)
            voice = voice_hits / voice_n if voice_n else float("nan")
            print(f"{name:22s} {genre / q:11.3f} {key / q:7.3f} {bpm / q:8.3f} {voice:7.3f} "
                  f"{relaxed / q:7.0%}")  # fmt: skip


if __name__ == "__main__":
    main()
