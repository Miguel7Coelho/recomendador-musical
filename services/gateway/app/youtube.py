"""Vídeo de uma faixa no YouTube, o plano B de player quando o Spotify está fora.

A cota gratuita paga cerca de 100 buscas por dia, então cada resposta fica guardada.
"""

import html
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
# A categoria "Música" do YouTube é preenchida por quem envia e deixa passar de tudo.
NOT_MUSIC = re.compile(
    r"\b(covers?|reaction|reacts?|reagindo|react|karaoke|tutorial|lesson|aula|review|analise"
    r"|interview|entrevista|podcast|trailer|documentary|documentario|gameplay|explained"
    r"|breakdown|parody|parodia|nightcore|slowed|sped up|mashup|remix|instrumental|type beat"
    r"|how to|making of|full album|album completo|\d+ hours?)\b"
)


class Unavailable(Exception):
    pass


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode() or text
    return " ".join(re.sub(r"[^\w]+", " ", text.casefold()).split())


def _compact(text: str) -> str:
    return _normalize(text).replace(" ", "")


def _rank(item: dict, title: str, artist: str) -> int | None:
    """Maior é melhor: faixa oficial > canal do artista > outros. None: não é a música."""
    video = html.unescape(item["snippet"]["title"])
    channel = html.unescape(item["snippet"]["channelTitle"])
    song = re.sub(r"\(.*?\)|\[.*?\]|\s-\s.*", "", title) or title
    if _compact(song) not in _compact(video):
        return None
    if _compact(artist) not in _compact(f"{channel} {video}"):
        return None
    if any(
        found.group() not in _normalize(title) for found in NOT_MUSIC.finditer(_normalize(video))
    ):
        return None
    if _normalize(channel).endswith(" topic"):
        return 2
    return int("vevo" in _normalize(channel) or _compact(artist) in _compact(channel))


def _best(items: list[dict], title: str, artist: str) -> str | None:
    ranked = [(_rank(item, title, artist), item["id"]["videoId"]) for item in items]
    music = [(rank, video_id) for rank, video_id in ranked if rank is not None]
    # max devolve o primeiro empatado, que é o mais relevante para o YouTube.
    return max(music, key=lambda pair: pair[0])[1] if music else None


def find(title: str, artist: str) -> str | None:
    store = clients.store()
    key = f"youtube:v2:{_normalize(title)}|{_normalize(artist)}"
    cached = store.get(key)
    if cached is not None:
        return json.loads(cached)
    if not YOUTUBE_API_KEY or store.get(QUOTA_KEY):
        raise Unavailable

    params = {"part": "snippet", "type": "video", "videoEmbeddable": "true"}
    params |= {"videoCategoryId": "10", "maxResults": 10, "q": f"{artist} {title} audio"}
    params["key"] = YOUTUBE_API_KEY
    try:
        r = clients.http().get(API, params=params)
    except httpx.HTTPError:
        raise Unavailable from None  # o erro traz a URL, que contém a chave
    if r.status_code == 403:  # cota esgotada: insistir só gasta tempo
        store.setex(QUOTA_KEY, QUOTA_PAUSE_S, "1")
    if r.status_code != 200:
        raise Unavailable

    video_id = _best(r.json().get("items", []), title, artist)
    store.setex(key, FOUND_TTL_S if video_id else NOT_FOUND_TTL_S, json.dumps(video_id))
    return video_id
