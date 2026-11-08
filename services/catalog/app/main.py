from typing import Literal
from uuid import UUID

import httpx
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from app import db, external, lastfm, recommend

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
    audio_sha: str | None = Field(None, pattern=r"^[0-9a-f]{64}$")  # trecho no S3 (FMA)
    license: str | None = None
    features: dict
    embeddings: dict[str, list[float]] = Field(min_length=1)


class SimilarIn(BaseModel):
    model: str
    vec: list[float] = Field(min_length=1)
    k: int = Field(10, ge=1, le=100)
    exclude_id: str | None = None


class Filters(BaseModel):
    key: Literal["exact", "compatible", "off"] = "exact"
    genre: Literal["style", "genre", "off"] = "style"
    voice: Literal["on", "off"] = "on"
    locked: list[Literal["key", "genre", "voice"]] = []  # nunca relaxados
    bpm_min: float | None = None
    bpm_max: float | None = None
    year_min: int | None = None
    year_max: int | None = None


class RecommendOptions(BaseModel):
    model: str = "effnet_clap"
    filters: Filters = Filters()
    k: int = Field(10, ge=1, le=200)  # até o tamanho do pool, para a avaliação dos pesos
    min_candidates: int = Field(20, ge=1, le=200)
    pool: int = Field(200, ge=10, le=1000)
    exclude_ids: list[UUID] = []
    weights: dict[str, float] | None = None  # para a avaliação e o ajuste de pesos

    @field_validator("weights")
    @classmethod
    def _weights(cls, w: dict[str, float] | None) -> dict[str, float] | None:
        if w is not None and set(w) != set(recommend.WEIGHTS):
            raise ValueError(f"pesos precisam ter exatamente {sorted(recommend.WEIGHTS)}")
        return w


class RecommendIn(RecommendOptions):
    vec: list[float] = Field(min_length=1)
    features: dict


class TrackRef(BaseModel):
    title: str = Field(min_length=1)
    artist: str = Field(min_length=1)


class ExternalIn(BaseModel):
    features: dict
    track: TrackRef | None = None  # a música enviada, quando o usuário disse qual é
    exclude_spotify_ids: list[str] = Field([], max_length=50)
    k: int = Field(10, ge=1, le=40)


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


@app.get("/tracks/{track_id}")
def get_track(track_id: UUID) -> dict:
    with db.connect() as conn:
        track = db.get_track(conn, str(track_id))
    if track is None:
        raise HTTPException(404, "Faixa não encontrada")
    return track


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


def _recommend(
    opts: RecommendOptions, vec: list[float], features: dict, exclude: list[str]
) -> dict:
    f = opts.filters
    bpm = (f.bpm_min or 0.0, f.bpm_max or 1000.0) if (f.bpm_min or f.bpm_max) else None
    year = (f.year_min or 0, f.year_max or 9999) if (f.year_min or f.year_max) else None
    start = {"key": f.key, "genre": f.genre, "voice": f.voice}
    with db.connect() as conn:

        def fetch(cond: dict) -> list[dict]:
            return db.candidates(
                conn, opts.model, vec, cond, bpm=bpm, year=year, exclude=exclude, pool=opts.pool
            )

        cands, levels, relaxed = recommend.run_cascade(
            features, start, set(f.locked), fetch, opts.min_candidates
        )
    ranked = recommend.rank(features, cands, opts.weights or recommend.WEIGHTS)
    return {"results": ranked[: opts.k], "levels": levels, "relaxed": relaxed, "pool": len(cands)}


@app.post("/recommend")
def recommend_by_features(req: RecommendIn) -> dict:
    return _recommend(req, req.vec, req.features, [str(i) for i in req.exclude_ids])


@app.post("/recommend/track/{track_id}")
def recommend_by_track(track_id: UUID, opts: RecommendOptions | None = None) -> dict:
    """Mais parecidas com esta: usa a própria faixa do catálogo como consulta."""
    opts = opts or RecommendOptions()
    with db.connect() as conn:
        query = db.track_query(conn, str(track_id), opts.model)
    if query is None:
        raise HTTPException(404, "Faixa sem embedding desse modelo no catálogo")
    exclude = [str(track_id), *(str(i) for i in opts.exclude_ids)]
    return _recommend(opts, query.pop("vec"), query, exclude)


@app.get("/songs/search")
def search_songs(q: str = Query(min_length=2, max_length=100)) -> dict:
    """Sugestões para o usuário dizer qual música enviou."""
    try:
        found = lastfm.search_songs(q, 6)
    except httpx.HTTPError as e:
        raise HTTPException(502, "Last.fm indisponível") from e  # a URL do erro contém a chave
    return {"results": [{"title": title, "artist": artist} for title, artist in found]}


@app.post("/recommend/external")
def recommend_external(req: ExternalIn) -> dict:
    """Faixas do Spotify do mesmo gênero (Last.fm), na faixa de andamento e priorizando o tom."""
    try:
        track = req.track.model_dump() if req.track else None
        return external.recommendations(req.features, req.exclude_spotify_ids, req.k, track)
    except httpx.HTTPError as e:
        # O texto do erro não vai na resposta: a URL do Last.fm contém a chave da API.
        raise HTTPException(502, "Last.fm, Spotify ou ReccoBeats indisponível") from e
