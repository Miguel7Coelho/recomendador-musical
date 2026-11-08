import secrets
from functools import cache

import redis
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from app import sessions, spotify
from app.config import REDIS_URL

SERVICE = "spotify"
PKCE_TTL_S = 600

app = FastAPI(title=SERVICE)


@cache
def _redis() -> redis.Redis:
    return redis.Redis.from_url(REDIS_URL)


def state_put(state: str, verifier: str) -> None:
    _redis().setex(f"pkce:{state}", PKCE_TTL_S, verifier)


def state_pop(state: str) -> str | None:
    value = _redis().getdel(f"pkce:{state}")
    return value.decode() if value else None


class ExchangeIn(BaseModel):
    code: str
    state: str


class PlaylistIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    spotify_ids: list[str] = Field(min_length=1, max_length=500)
    public: bool = False


class MatchIn(BaseModel):
    title: str = Field(min_length=1)
    artist: str = Field(min_length=1)


def _token_or_401(session_id: str | None) -> str:
    token = sessions.access_token(session_id) if session_id else None
    if token is None:
        raise HTTPException(401, "Faça login no Spotify")
    return token


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": SERVICE}


@app.get("/auth/url")
def auth_url() -> dict:
    verifier, challenge = spotify.new_pkce()
    state = secrets.token_urlsafe(24)
    state_put(state, verifier)
    return {"url": spotify.authorize_url(state, challenge), "state": state}


@app.post("/auth/exchange")
def auth_exchange(body: ExchangeIn) -> dict:
    verifier = state_pop(body.state)
    if verifier is None:
        raise HTTPException(400, "Login expirado ou inválido; tente de novo")
    tokens = spotify.exchange_code(body.code, verifier)
    profile = spotify.me(tokens["access_token"])
    session_id = secrets.token_urlsafe(32)
    sessions.save(session_id, profile["id"], profile.get("display_name"), tokens)
    return {"session_id": session_id, "display_name": profile.get("display_name")}


@app.get("/me")
def me(x_session: str | None = Header(None)) -> dict:
    user = sessions.get(x_session) if x_session else None
    if user is None:
        raise HTTPException(401, "Faça login no Spotify")
    return user


@app.post("/auth/logout")
def logout(x_session: str | None = Header(None)) -> dict:
    if x_session:
        sessions.delete(x_session)
    return {"ok": True}


@app.post("/playlists")
def create_playlist(body: PlaylistIn, x_session: str | None = Header(None)) -> dict:
    token = _token_or_401(x_session)
    playlist = spotify.create_playlist(token, body.name, body.public)
    spotify.add_items(token, playlist["id"], body.spotify_ids)
    return {"id": playlist["id"], "url": playlist["external_urls"]["spotify"]}


@app.get("/search/genre")
def search_genre(style: str, limit: int = 5) -> dict:
    return {"ids": spotify.genre_seeds(style, min(limit, spotify.SEARCH_LIMIT))}


@app.post("/match")
def match(body: MatchIn) -> dict:
    return {"match": spotify.match(body.title, body.artist)}
