# /// script
# requires-python = ">=3.12"
# dependencies = ["numpy>=2", "psycopg[binary]>=3.2"]
# ///
"""Precisão@k por gênero da FMA para cada modelo de embedding do catálogo.

Para cada faixa, busca as k mais parecidas (cosseno, excluindo ela mesma) e mede a fração
que tem o mesmo gênero da FMA. Alimenta a escolha do embedding e o capítulo 5 do TCC.

Uso:  uv run scripts/eval_precision_at_k.py [--k 10]
"""

import argparse
import os
from collections import Counter
from pathlib import Path

import numpy as np
import psycopg


def database_url() -> str:
    """DATABASE_URL do .env, apontado para o Postgres exposto em localhost."""
    url = os.getenv("DATABASE_URL")
    if not url:
        env = Path(__file__).resolve().parents[1] / ".env"
        for line in env.read_text().splitlines():
            if line.startswith("DATABASE_URL="):
                url = line.split("=", 1)[1].strip()
    url = url.replace("postgresql+psycopg://", "postgresql://")
    return url.replace("@postgres:", "@localhost:")


def precision_at_k(vectors: np.ndarray, labels: np.ndarray, k: int) -> np.ndarray:
    """Precisão@k de cada faixa (vetor de tamanho N)."""
    unit = vectors / np.linalg.norm(vectors, axis=1, keepdims=True)
    sim = unit @ unit.T
    np.fill_diagonal(sim, -np.inf)  # a própria faixa não conta
    neighbors = np.argsort(-sim, axis=1)[:, :k]
    return (labels[neighbors] == labels[:, None]).mean(axis=1)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=10)
    args = ap.parse_args()

    with psycopg.connect(database_url()) as conn:
        models = [r[0] for r in conn.execute("SELECT DISTINCT model FROM track_embeddings")]
        for model in sorted(models):
            rows = conn.execute(
                """SELECT t.dataset_genre, e.vec::real[] FROM track_embeddings e
                   JOIN tracks t ON t.id = e.track_id
                   WHERE t.source = 'fma' AND e.model = %s AND e.stem = 'mix'
                     AND t.dataset_genre IS NOT NULL""",
                (model,),
            ).fetchall()
            labels = np.array([r[0] for r in rows])
            vectors = np.stack([np.asarray(r[1], dtype=np.float32) for r in rows])
            p = precision_at_k(vectors, labels, args.k)

            # Linha de base: escolher vizinhos ao acaso acerta, em média, a soma de p(gênero)².
            freq = np.array(list(Counter(labels).values())) / len(labels)
            print(f"\n=== {model}  ({len(labels)} faixas, {vectors.shape[1]} dimensões)")
            print(f"precisão@{args.k}: {p.mean():.3f}   (acaso: {np.sum(freq**2):.3f})")
            for genre in sorted(set(labels)):
                mask = labels == genre
                print(f"  {genre:<14} {p[mask].mean():.3f}  ({mask.sum()} faixas)")


if __name__ == "__main__":
    main()
