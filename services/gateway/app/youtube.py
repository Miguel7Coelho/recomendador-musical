"""Vídeo de uma faixa no YouTube, o plano B de player quando o Spotify está fora.

A cota gratuita paga cerca de 100 buscas por dia, então cada resposta fica guardada.
"""

import json
import logging
import re
import unicodedata

import httpx

from app import clients
from app.config import YOUTUBE_API_KEY

API = "https://www.googleapis.com/youtube/v3/search"
FOUND_TTL_S = 30 * 24 * 3600
NOT_FOUND_TTL_S = 7 * 24 * 3600
QUOTA_PAUSE_S = 3600
QUOTA_KEY = "youtube:sem-cota"
# A chave vai na URL, que o httpx registra em nível INFO.
logging.getLogger("httpx").setLevel(logging.WARNING)


class Unavailable(Exception):
    pass


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode() or text
    return " ".join(re.sub(r"[^\w]+", " ", text.casefold()).split())


def find(title: str, artist: str) -> str | None:
    store = clients.store()
    key = f"youtube:v1:{_normalize(title)}|{_normalize(artist)}"
    cached = store.get(key)
    if cached is not None:
        return json.loads(cached)
    if not YOUTUBE_API_KEY or store.get(QUOTA_KEY):
        raise Unavailable

    params = {"part": "snippet", "type": "video", "videoEmbeddable": "true"}
    params |= {"videoCategoryId": "10", "maxResults": 1, "q": f"{artist} {title}"}
    params["key"] = YOUTUBE_API_KEY
    try:
        r = clients.http().get(API, params=params)
    except httpx.HTTPError:
        raise Unavailable from None  # o erro traz a URL, que contém a chave
    if r.status_code == 403:  # cota esgotada: insistir só gasta tempo
        store.setex(QUOTA_KEY, QUOTA_PAUSE_S, "1")
    if r.status_code != 200:
        raise Unavailable

    items = r.json().get("items", [])
    video_id = items[0]["id"]["videoId"] if items else None
    store.setex(key, FOUND_TTL_S if video_id else NOT_FOUND_TTL_S, json.dumps(video_id))
    return video_id
