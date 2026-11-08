import re
from uuid import UUID

import httpx
from botocore.exceptions import ClientError
from fastapi import (
    Body,
    Cookie,
    FastAPI,
    Form,
    Header,
    HTTPException,
    Request,
    Response,
    UploadFile,
)
from fastapi.responses import RedirectResponse, StreamingResponse

from app import clients, jobs
from app.config import (
    CATALOG_URL,
    COOKIE_SECURE,
    EMBEDDING_MODEL,
    FRONTEND_URL,
    S3_BUCKET,
    SEPARATION_URL,
    SPOTIFY_API_URL,
)

SERVICE = "gateway"
SESSION_COOKIE = "session"
SESSION_MAX_AGE_S = 30 * 24 * 3600
BYTE_RANGE = re.compile(r"bytes=(\d+-\d*|-\d+)")

app = FastAPI(title=SERVICE)


def _ok(r: httpx.Response) -> dict:
    """Repassa erros dos serviços internos com o mesmo status e mensagem."""
    if r.status_code >= 400:
        try:
            detail = r.json().get("detail", r.text)
        except ValueError:
            detail = r.text
        raise HTTPException(r.status_code, detail)
    return r.json()


def _session(session: str | None) -> dict:
    return {"X-Session": session} if session else {}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": SERVICE}


# --- Análise de uma faixa ------------------------------------------------------------------


@app.post("/analyze", status_code=202)
def analyze(
    file: UploadFile, title: str | None = Form(None), artist: str | None = Form(None)
) -> dict:
    files = {"file": (file.filename or "audio", file.file, file.content_type)}
    separation = _ok(clients.http().post(f"{SEPARATION_URL}/separate", files=files))
    track = {"title": title, "artist": artist} if title and artist else None
    job = jobs.advance(jobs.new(separation, track))
    jobs.save(job)
    return jobs.view(job)


@app.get("/jobs/{job_id}")
def get_job(job_id: UUID) -> dict:
    job = jobs.load(str(job_id))
    if job is None:
        raise HTTPException(404, "Análise não encontrada ou expirada")
    job = jobs.advance(job)
    jobs.save(job)
    return jobs.view(job)


@app.post("/jobs/{job_id}/recommend")
def recommend_from_job(job_id: UUID, options: dict | None = Body(None)) -> dict:
    """Refaz a busca no catálogo com novos filtros, reaproveitando a análise guardada no job."""
    job = jobs.load(str(job_id))
    if job is None:
        raise HTTPException(404, "Análise não encontrada ou expirada")
    if "analysis" not in job:
        raise HTTPException(409, "A análise desta faixa ainda não terminou")
    # A consulta é sempre a análise do job: o corpo só escolhe filtros, k e pesos.
    body = {**(options or {}), **job["analysis"], "model": EMBEDDING_MODEL}
    try:
        r = clients.http().post(f"{CATALOG_URL}/recommend", json=body)
    except httpx.HTTPError as e:
        raise HTTPException(503, "Catálogo indisponível no momento") from e
    out = _ok(r)
    jobs.save(job)  # quem segue ajustando filtros não perde a análise após 2 h
    return {**out, "results": jobs.with_audio(out["results"])}


@app.get("/songs/search")
def search_songs(q: str) -> dict:
    return _ok(clients.http().get(f"{CATALOG_URL}/songs/search", params={"q": q}))


# --- Mais recomendações ----------------------------------------------------------------------


@app.post("/recommend/track/{track_id}")
async def more_like_catalog_track(track_id: UUID, request: Request) -> dict:
    """Mais parecidas com uma faixa do catálogo (cascata completa)."""
    body = await request.json() if await request.body() else None
    r = clients.http().post(f"{CATALOG_URL}/recommend/track/{track_id}", json=body)
    out = _ok(r)
    return {**out, "results": jobs.with_audio(out["results"])}


@app.post("/recommend/spotify/{spotify_id}")
async def more_like_spotify_track(spotify_id: str, request: Request) -> dict:
    """Mais parecidas com uma faixa do Spotify, sem repetir a própria faixa."""
    features = await request.json() if await request.body() else {}
    track = features.pop("track", None)
    body = {"features": features, "exclude_spotify_ids": [spotify_id]}
    if track:
        body["track"] = track
    return _ok(clients.http().post(f"{CATALOG_URL}/recommend/external", json=body))


# --- Áudio dos trechos da FMA (Creative Commons) --------------------------------------------


@app.get("/audio/track/{track_id}")
def audio(
    track_id: UUID, byte_range: str | None = Header(None, alias="Range")
) -> StreamingResponse:
    track = _ok(clients.http().get(f"{CATALOG_URL}/tracks/{track_id}"))
    # Só trechos da FMA: o áudio que um usuário envia nunca é servido a terceiros.
    if track["source"] != "fma" or not track.get("audio_sha"):
        raise HTTPException(404, "Esta faixa não tem trecho próprio para tocar")
    # Sem Range o navegador não consegue pular para outro ponto da faixa.
    extra = {"Range": byte_range} if byte_range and BYTE_RANGE.fullmatch(byte_range) else {}
    key = f"inputs/{track['audio_sha']}.wav"
    try:
        obj = clients.s3().get_object(Bucket=S3_BUCKET, Key=key, **extra)
    except ClientError as e:
        if e.response["Error"]["Code"] == "InvalidRange":
            raise HTTPException(416, "Intervalo de áudio inválido") from e
        raise
    headers = {
        "Accept-Ranges": "bytes",
        "Content-Length": str(obj["ContentLength"]),
        "Cache-Control": "max-age=86400",
    }
    status = 200
    if obj.get("ContentRange"):
        headers["Content-Range"] = obj["ContentRange"]
        status = 206
    return StreamingResponse(
        obj["Body"].iter_chunks(), status_code=status, media_type="audio/wav", headers=headers
    )


# --- Spotify: login, perfil, correspondência e playlist --------------------------------------


@app.get("/auth/login")
def login() -> RedirectResponse:
    url = _ok(clients.http().get(f"{SPOTIFY_API_URL}/auth/url"))["url"]
    return RedirectResponse(url)


@app.get("/auth/callback")
def callback(code: str | None = None, state: str | None = None, error: str | None = None):
    if error or not code or not state:
        return RedirectResponse(f"{FRONTEND_URL}/?login=cancelado")
    r = clients.http().post(f"{SPOTIFY_API_URL}/auth/exchange", json={"code": code, "state": state})
    if r.status_code != 200:
        return RedirectResponse(f"{FRONTEND_URL}/?login=erro")
    resp = RedirectResponse(f"{FRONTEND_URL}/?login=ok")
    resp.set_cookie(
        SESSION_COOKIE,
        r.json()["session_id"],
        max_age=SESSION_MAX_AGE_S,
        httponly=True,  # o JavaScript do front nunca vê a sessão
        samesite="lax",
        secure=COOKIE_SECURE,
    )
    return resp


@app.get("/me")
def me(session: str | None = Cookie(None)) -> dict:
    return _ok(clients.http().get(f"{SPOTIFY_API_URL}/me", headers=_session(session)))


@app.post("/auth/logout")
def logout(response: Response, session: str | None = Cookie(None)) -> dict:
    clients.http().post(f"{SPOTIFY_API_URL}/auth/logout", headers=_session(session))
    response.delete_cookie(SESSION_COOKIE)
    return {"ok": True}


@app.post("/tracks/{track_id}/spotify")
def match_on_spotify(track_id: UUID) -> dict:
    """Procura no Spotify a mesma faixa do catálogo (para salvar na playlist)."""
    track = _ok(clients.http().get(f"{CATALOG_URL}/tracks/{track_id}"))
    if not track.get("title") or not track.get("artist"):
        return {"match": None}
    body = {"title": track["title"], "artist": track["artist"]}
    return _ok(clients.http().post(f"{SPOTIFY_API_URL}/match", json=body))


@app.post("/playlists")
async def create_playlist(request: Request, session: str | None = Cookie(None)) -> dict:
    r = clients.http().post(
        f"{SPOTIFY_API_URL}/playlists", json=await request.json(), headers=_session(session)
    )
    return _ok(r)
