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


def _as_list(items: list | dict) -> list:
    return [items] if isinstance(items, dict) else items  # uma só faixa vem como objeto


@lru_cache(maxsize=2048)
def similar_tracks(title: str, artist: str, limit: int) -> tuple[tuple[str, str, float], ...]:
    """(título, artista, afinidade) do que quem ouve esta faixa também ouve."""
    params = {"method": "track.getsimilar", "track": title, "artist": artist, "limit": limit}
    params |= {"autocorrect": 1, "api_key": API_KEY, "format": "json"}
    r = client().get(API, params=params).raise_for_status()
    items = _as_list(r.json().get("similartracks", {}).get("track", []))
    return tuple((t["name"], t["artist"]["name"], float(t["match"])) for t in items)


@lru_cache(maxsize=2048)
def search_songs(query: str, limit: int) -> tuple[tuple[str, str], ...]:
    """(título, artista) para o usuário dizer qual música enviou."""
    params = {"method": "track.search", "track": query, "limit": limit}
    params |= {"api_key": API_KEY, "format": "json"}
    r = client().get(API, params=params).raise_for_status()
    items = _as_list(r.json().get("results", {}).get("trackmatches", {}).get("track", []))
    # Sem esta ordem, grafias erradas com poucos ouvintes aparecem antes da música de verdade.
    items = sorted(items, key=lambda t: -int(t.get("listeners") or 0))
    seen: dict[tuple[str, str], tuple[str, str]] = {}
    for t in items:
        if t["artist"].casefold() in ("<unknown>", "[unknown]"):
            continue
        seen.setdefault((t["name"].casefold(), t["artist"].casefold()), (t["name"], t["artist"]))
    return tuple(seen.values())


@lru_cache(maxsize=2048)
def top_tags(title: str, artist: str) -> tuple[str, ...]:
    """Etiquetas da faixa, sem as que só repetem o nome do artista ou da música."""
    params = {"method": "track.gettoptags", "track": title, "artist": artist}
    params |= {"autocorrect": 1, "api_key": API_KEY, "format": "json"}
    r = client().get(API, params=params).raise_for_status()
    names = [t["name"] for t in _as_list(r.json().get("toptags", {}).get("tag", []))]
    return tuple(n for n in names if n.casefold() not in (artist.casefold(), title.casefold()))
