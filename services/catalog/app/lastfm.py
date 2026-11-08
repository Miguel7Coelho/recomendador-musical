"""Faixas por gênero no Last.fm: a ReccoBeats e o Spotify não informam o gênero das faixas."""

import logging
import os
from functools import cache, lru_cache

import httpx

API = "https://ws.audioscrobbler.com/2.0/"
API_KEY = os.getenv("LASTFM_API_KEY", "")
# A chave vai na URL, que o httpx registra em nível INFO.
logging.getLogger("httpx").setLevel(logging.WARNING)

# Estilos do Discogs cujo nome não é a etiqueta usada no Last.fm.
TAG_ALIASES = {
    "Gangsta": "gangsta rap",
    "Screw": "chopped and screwed",
    "RnB/Swing": "rnb",
    "Instrumental": "instrumental hip-hop",
    "Jazzy Hip-Hop": "jazz hop",
    "Hardcore Hip-Hop": "hardcore hip hop",
    "Conscious": "conscious hip hop",
    "Hip Hop": "hip-hop",
    "Folk, World, & Country": "folk",
    "Funk / Soul": "soul",
    "Stage & Screen": "soundtrack",
}


@cache
def client() -> httpx.Client:
    return httpx.Client(timeout=15)


def tag_for(name: str) -> str:
    """Nome de um estilo ou gênero do Discogs → etiqueta do Last.fm."""
    return TAG_ALIASES.get(name, name.lower())


@lru_cache(maxsize=512)
def top_tracks(tag: str, limit: int) -> tuple[tuple[str, str], ...]:
    """(título, artista) das faixas mais associadas à etiqueta, da mais forte para a mais fraca."""
    params = {"method": "tag.gettoptracks", "tag": tag, "limit": limit}
    params |= {"api_key": API_KEY, "format": "json"}
    r = client().get(API, params=params).raise_for_status()
    items = r.json().get("tracks", {}).get("track", [])
    if isinstance(items, dict):  # a API devolve objeto em vez de lista quando só há uma faixa
        items = [items]
    return tuple((t["name"], t["artist"]["name"]) for t in items)
