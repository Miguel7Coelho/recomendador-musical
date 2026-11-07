from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app import db

SERVICE = "catalog"

app = FastAPI(title=SERVICE)


class TrackIn(BaseModel):
    source: Literal["fma", "reccobeats", "upload"]
    external_id: str | None = None
    spotify_id: str | None = None
    title: str | None = None
    artist: str | None = None
    year: int | None = None
    duration_s: float | None = None
    dataset_genre: str | None = None  # rótulo da base (ex.: gênero da FMA), usado na avaliação
    features: dict
    embeddings: dict[str, list[float]] = Field(min_length=1)


class SimilarIn(BaseModel):
    model: str
    vec: list[float] = Field(min_length=1)
    k: int = Field(10, ge=1, le=100)
    exclude_id: str | None = None


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": SERVICE}


@app.get("/tracks/lookup")
def lookup(source: str, external_id: str) -> dict:
    with db.connect() as conn:
        track_id = db.find_track(conn, source, external_id)
    if track_id is None:
        raise HTTPException(404, "Faixa não encontrada")
    return {"id": track_id}


@app.post("/tracks")
def create_track(track: TrackIn) -> dict:
    data = track.model_dump(exclude={"features", "embeddings"})
    with db.connect() as conn:
        if track.external_id and (existing := db.find_track(conn, track.source, track.external_id)):
            return {"id": existing, "created": False}
        track_id = db.insert_track(conn, data, track.features, track.embeddings)
    return {"id": track_id, "created": True}


@app.post("/similar")
def similar(req: SimilarIn) -> dict:
    with db.connect() as conn:
        results = db.similar(conn, req.model, req.vec, req.k, req.exclude_id)
    return {"results": results}
