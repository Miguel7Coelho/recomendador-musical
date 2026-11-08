# /// script
# requires-python = ">=3.12"
# dependencies = ["httpx>=0.27", "pandas>=2"]
# ///
"""Carrega faixas da FMA small no catálogo: separação → análise → catálogo.

Uso (com o docker compose no ar):
    uv run scripts/load_fma.py --metadata ~/dev/datasets/fma/fma_metadata \\
                               --audio ~/dev/datasets/fma/fma_small --per-genre 50

Pode ser interrompido com Ctrl+C e rodado de novo: faixas já no catálogo são puladas.
"""

import argparse
import time
from pathlib import Path

import httpx
import pandas as pd

SEPARATION = "http://localhost:8001"
ANALYSIS = "http://localhost:8002"
CATALOG = "http://localhost:8003"


def load_tracks(metadata_dir: Path, per_genre: int, seed: int) -> pd.DataFrame:
    tracks = pd.read_csv(metadata_dir / "tracks.csv", index_col=0, header=[0, 1])
    small = tracks[tracks[("set", "subset")] == "small"]
    df = pd.DataFrame(
        {
            "genre": small[("track", "genre_top")],
            "title": small[("track", "title")],
            "artist": small[("artist", "name")],
            "year": pd.to_datetime(small[("album", "date_released")], errors="coerce").dt.year,
            "duration_s": small[("track", "duration")],
            "license": small[("track", "license")],
        }
    )
    # Embaralha com semente fixa e pega as primeiras N de cada gênero (amostra reprodutível).
    return df.sample(frac=1, random_state=seed).groupby("genre").head(per_genre).sort_index()


def wait(client: httpx.Client, url: str, timeout_s: int = 600) -> dict:
    start = time.monotonic()
    while time.monotonic() - start < timeout_s:
        body = client.get(url).raise_for_status().json()
        if body["status"] == "done":
            return body
        if body["status"] == "failed":
            raise RuntimeError(body.get("error", "falhou"))
        time.sleep(1)
    raise TimeoutError(url)


def process(client: httpx.Client, tid: int, row: pd.Series, audio_dir: Path) -> str:
    path = audio_dir / f"{tid:06d}"[:3] / f"{tid:06d}.mp3"
    with path.open("rb") as f:
        r = client.post(f"{SEPARATION}/separate", files={"file": (path.name, f)})
    if r.status_code == 400:
        raise ValueError(r.json()["detail"])
    sep = r.raise_for_status().json()
    if sep["status"] != "done":
        sep = wait(client, f"{SEPARATION}/separate/{sep['job_id']}")

    ana = client.post(f"{ANALYSIS}/analyze", json={"sha": sep["sha"]}).raise_for_status().json()
    if ana["status"] != "done":
        ana = wait(client, f"{ANALYSIS}/analyze/{ana['job_id']}")

    track = {
        "source": "fma",
        "external_id": str(tid),
        "title": None if pd.isna(row.title) else str(row.title),
        "artist": None if pd.isna(row.artist) else str(row.artist),
        "year": None if pd.isna(row.year) else int(row.year),
        "duration_s": None if pd.isna(row.duration_s) else float(row.duration_s),
        "dataset_genre": row.genre,
        "audio_sha": sep["sha"],
        "license": None if pd.isna(row.license) else str(row.license),
        "features": ana["features"],
        "embeddings": ana["embeddings"],
    }
    return client.post(f"{CATALOG}/tracks", json=track).raise_for_status().json()["id"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--metadata", type=Path, required=True)
    ap.add_argument("--audio", type=Path, required=True)
    ap.add_argument("--per-genre", type=int, default=50, help="faixas por gênero (8 gêneros)")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    df = load_tracks(args.metadata.expanduser(), args.per_genre, args.seed)
    print(f"{len(df)} faixas selecionadas ({args.per_genre} por gênero)")

    done = skipped = failed = 0
    start = time.monotonic()
    with httpx.Client(timeout=60) as client:
        for i, (tid, row) in enumerate(df.iterrows(), 1):
            lookup = client.get(
                f"{CATALOG}/tracks/lookup", params={"source": "fma", "external_id": str(tid)}
            )
            if lookup.status_code == 200:
                skipped += 1
                continue
            try:
                process(client, tid, row, args.audio.expanduser())
                done += 1
            except Exception as e:  # uma faixa ruim não para a carga inteira
                failed += 1
                print(f"  [{i}/{len(df)}] {tid:06d} falhou: {str(e).splitlines()[0][:200]}")
                continue
            per_track = (time.monotonic() - start) / done
            eta_min = per_track * (len(df) - i) / 60
            print(f"  [{i}/{len(df)}] {tid:06d} {row.genre:<14} ok · {per_track:.0f} s/faixa · "
                  f"faltam ~{eta_min:.0f} min")  # fmt: skip

    print(f"Fim: {done} carregadas, {skipped} já estavam no catálogo, {failed} falharam.")


if __name__ == "__main__":
    main()
