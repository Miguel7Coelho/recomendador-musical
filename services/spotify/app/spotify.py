"""Chamadas à Web API e ao serviço de contas do Spotify (endpoints pós-fevereiro de 2026)."""

import base64
import hashlib
import math
import re
import secrets
import time
import unicodedata
from functools import cache
from urllib.parse import urlencode

import httpx

from app.config import (
    SCOPES,
    SPOTIFY_CLIENT_ID,
    SPOTIFY_CLIENT_SECRET,
    SPOTIFY_REDIRECT_URI,
)

ACCOUNTS = "https://accounts.spotify.com"
API = "https://api.spotify.com/v1"
SEARCH_LIMIT = 10  # máximo no Development Mode


@cache
def client() -> httpx.Client:
    return httpx.Client(timeout=15)


# --- Login (Authorization Code + PKCE) ---------------------------------------------------


def new_pkce() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


def authorize_url(state: str, challenge: str) -> str:
    params = {
        "client_id": SPOTIFY_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": SPOTIFY_REDIRECT_URI,
        "code_challenge_method": "S256",
        "code_challenge": challenge,
        "scope": SCOPES,
        "state": state,
    }
    return f"{ACCOUNTS}/authorize?{urlencode(params)}"


def _token(data: dict) -> dict:
    r = client().post(f"{ACCOUNTS}/api/token", data=data)
    r.raise_for_status()
    return r.json()


def exchange_code(code: str, verifier: str) -> dict:
    return _token(
        {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": SPOTIFY_REDIRECT_URI,
            "client_id": SPOTIFY_CLIENT_ID,
            "code_verifier": verifier,
        }
    )


def refresh(refresh_token: str) -> dict:
    data = {"grant_type": "refresh_token", "refresh_token": refresh_token}
    return _token({**data, "client_id": SPOTIFY_CLIENT_ID})


# --- Token do app (client credentials): busca não precisa de usuário logado ---------------

_app_token: dict = {"value": None, "expires": 0.0}


def app_token() -> str:
    if _app_token["value"] and time.time() < _app_token["expires"] - 60:
        return _app_token["value"]
    basic = base64.b64encode(f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}".encode()).decode()
    r = client().post(
        f"{ACCOUNTS}/api/token",
        data={"grant_type": "client_credentials"},
        headers={"Authorization": f"Basic {basic}"},
    )
    r.raise_for_status()
    body = r.json()
    _app_token.update(value=body["access_token"], expires=time.time() + body["expires_in"])
    return body["access_token"]


class RateLimited(Exception):
    def __init__(self, retry_after: int):
        super().__init__(f"Spotify pediu para aguardar {retry_after} s")
        self.retry_after = retry_after


_blocked: dict = {"until": 0.0}


def _get(path: str, token: str, params: dict | None = None) -> dict:
    # Insistir durante o bloqueio só o prolonga: nem chega a chamar o Spotify.
    wait = _blocked["until"] - time.time()
    if wait > 0:
        raise RateLimited(math.ceil(wait))
    r = client().get(f"{API}{path}", params=params, headers={"Authorization": f"Bearer {token}"})
    if r.status_code == 429:
        retry_after = int(r.headers.get("retry-after", 30))
        _blocked["until"] = time.time() + retry_after
        raise RateLimited(retry_after)
    r.raise_for_status()
    return r.json()


def _post(path: str, token: str, body: dict) -> dict:
    r = client().post(f"{API}{path}", json=body, headers={"Authorization": f"Bearer {token}"})
    r.raise_for_status()
    return r.json()


# --- Usuário e playlists -----------------------------------------------------------------


def me(access: str) -> dict:
    return _get("/me", access)


def create_playlist(access: str, name: str, public: bool) -> dict:
    body = {"name": name, "public": public, "description": "Criada pelo Recomendador Musical"}
    return _post("/me/playlists", access, body)


def add_items(access: str, playlist_id: str, track_ids: list[str]) -> None:
    uris = [f"spotify:track:{t}" for t in track_ids]
    for i in range(0, len(uris), 100):  # até 100 por requisição
        _post(f"/playlists/{playlist_id}/items", access, {"uris": uris[i : i + 100]})


# --- Busca --------------------------------------------------------------------------------


def search_tracks(q: str, limit: int = SEARCH_LIMIT) -> list[dict]:
    params = {"q": q, "type": "track", "limit": min(limit, SEARCH_LIMIT)}
    body = _get("/search", app_token(), params)
    return body["tracks"]["items"]


def normalize(text: str) -> str:
    """Minúsculas, sem acento, sem "(feat. …)"/"[…]" e sem pontuação, para comparar nomes."""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[\(\[].*?[\)\]]", " ", text.lower())
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())


def _same(a: str, b: str) -> bool:
    return bool(a and b) and (a == b or a in b or b in a)


def match(title: str, artist: str) -> dict | None:
    """Procura a mesma faixa no Spotify; só aceita quando título E artista conferem."""
    t, a = normalize(title), normalize(artist)
    for item in search_tracks(f"track:{title} artist:{artist}", limit=5):
        artists = [normalize(x["name"]) for x in item["artists"]]
        if _same(normalize(item["name"]), t) and any(_same(x, a) for x in artists):
            return {
                "spotify_id": item["id"],
                "title": item["name"],
                "artists": [x["name"] for x in item["artists"]],
                "url": item["external_urls"]["spotify"],
            }
    return None


def genre_seeds(style: str, limit: int = 5) -> list[str]:
    """IDs de faixas de um estilo, para semear a ReccoBeats. Tenta o filtro genre: e, se não
    achar nada, busca o nome do estilo como texto."""
    items = search_tracks(f'genre:"{style}"', limit=limit) or search_tracks(style, limit=limit)
    return [item["id"] for item in items][:limit]
