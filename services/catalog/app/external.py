"""Candidatas do Spotify via ReccoBeats (faixas que tocam no Spotify, sem áudio para analisarmos).

A ReccoBeats precisa de faixas-semente; o tom e o andamento das recomendações vêm do
/audio-features dela. Sem embedding, gênero ou voz: a ordenação usa só tom e BPM.
"""

import os
import re
from functools import cache

import httpx

from app import recommend

RECCOBEATS = "https://api.reccobeats.com/v1"
SPOTIFY_API = os.getenv("SPOTIFY_API_URL", "http://spotify-api:8000")
POOL = 40
# Acima disso a faixa é quase só fala (definição do Spotify para speechiness): audiolivros e
# podcasts aparecem como "faixas" no catálogo do Spotify e não servem como recomendação musical.
MAX_SPEECHINESS = 0.66
# Ruído para dormir não se distingue de música ambiente pelos atributos da ReccoBeats (medido em
# docs/resumo_projeto.json), então só o título, quando a própria faixa se declara ruído, serve.
NOISE_TITLE = re.compile(
    r"(white|pink|brown) noise|ru[ií]do (branco|blanco|rosa|marrom)|白噪音|白噪声|ホワイトノイズ",
    re.IGNORECASE,
)
# Atributos idênticos em todos os campos: o mesmo áudio publicado com outro título e artista.
AUDIO_FIELDS = (
    "acousticness",
    "danceability",
    "energy",
    "instrumentalness",
    "liveness",
    "loudness",
    "valence",
    "tempo",
)


@cache
def client() -> httpx.Client:
    return httpx.Client(timeout=20)


def camelot_from_pitch(key: int | None, mode: int | None) -> str | None:
    """Classe de altura (0 = Dó … 11 = Si) + modo (1 maior, 0 menor) → código Camelot."""
    if key is None or key < 0 or mode is None:
        return None
    pitch = key if mode == 1 else (key + 3) % 12  # menor → número da relativa maior
    return f"{(7 * pitch % 12 + 7) % 12 + 1}{'B' if mode == 1 else 'A'}"


def _spotify_id(href: str) -> str:
    return href.rstrip("/").rsplit("/", 1)[-1]


def seeds_for(features: dict) -> list[str]:
    """Faixas do Spotify do mesmo estilo da consulta (o primeiro estilo que render resultado)."""
    names = [s.split("---")[-1] for s in (features.get("styles") or {})]
    if features.get("genre_top"):
        names.append(features["genre_top"])
    for name in names:
        r = client().get(f"{SPOTIFY_API}/search/genre", params={"style": name, "limit": 10})
        ids = r.raise_for_status().json()["ids"]
        feats = _recco_features(ids) if ids else {}
        # A semente precisa existir na ReccoBeats (senão ela responde 400) e ser música.
        music = [i for i in ids if i in feats and not _is_speech(feats[i])][:5]
        if music:
            return music
    return []


def _is_speech(features: dict | None) -> bool:
    return bool(features) and (features.get("speechiness") or 0) > MAX_SPEECHINESS


def _recco_recommendations(seeds: list[str]) -> list[dict]:
    r = client().get(
        f"{RECCOBEATS}/track/recommendation", params={"seeds": seeds[:5], "size": POOL}
    )
    return r.raise_for_status().json()["content"]


def _recco_features(spotify_ids: list[str]) -> dict[str, dict]:
    out = {}
    for i in range(0, len(spotify_ids), 20):
        r = client().get(f"{RECCOBEATS}/audio-features", params={"ids": spotify_ids[i : i + 20]})
        for f in r.raise_for_status().json()["content"]:
            out[_spotify_id(f["href"])] = f
    return out


def recommendations(features: dict, seed_ids: list[str], k: int, key_level: str) -> dict:
    seeds = seed_ids or seeds_for(features)
    if not seeds:
        return {"results": [], "seeds": [], "relaxed": []}

    tracks = [t for t in _recco_recommendations(seeds) if _spotify_id(t["href"]) not in seeds]
    feats = _recco_features([_spotify_id(t["href"]) for t in tracks])
    cands = []
    seen_audio = set()
    for order, t in enumerate(tracks):
        sid = _spotify_id(t["href"])
        f = feats.get(sid, {})
        if _is_speech(f) or NOISE_TITLE.search(t["trackTitle"]):
            continue
        audio = tuple(f.get(name) for name in AUDIO_FIELDS)
        if None not in audio:
            if audio in seen_audio:
                continue
            seen_audio.add(audio)
        cands.append(
            {
                "source": "reccobeats",
                "spotify_id": sid,
                "title": t["trackTitle"],
                "artists": [a["name"] for a in t["artists"]],
                "url": t["href"],
                "camelot": camelot_from_pitch(f.get("key"), f.get("mode")),
                "bpm": f.get("tempo"),
                "_order": order,
            }
        )

    # Filtro de tom com relaxamento (compatível → sem filtro), como na cascata do catálogo.
    q_key, relaxed = features.get("camelot"), []
    levels = recommend.LADDER["key"][recommend.LADDER["key"].index(key_level) :]
    for level in levels:
        allowed = recommend.conditions(features, {"key": level, "genre": "off", "voice": "off"})
        keys = allowed["keys"]
        chosen = [c for c in cands if keys is None or c["camelot"] in keys]
        if len(chosen) >= k or level == levels[-1]:
            break
    if level != key_level:
        relaxed.append(f"key: {key_level} → {level}")

    q_bpm = features.get("bpm")

    def sort_key(c: dict) -> tuple:
        bpm = recommend.bpm_ratio(c["bpm"], q_bpm) if c["bpm"] and q_bpm else 1.0
        return (-recommend.key_match(q_key, c["camelot"]), bpm, c["_order"])

    results = []
    for c in sorted(chosen, key=sort_key)[:k]:
        comps = {"key": recommend.key_match(q_key, c["camelot"]), "voice": 0.0}
        why = recommend.explain(features, {**c, "styles": None}, comps)
        item = {name: v for name, v in c.items() if name != "_order"}
        item["explanation"] = " · ".join(filter(None, [why, "via ReccoBeats"]))
        results.append(item)
    return {"results": results, "seeds": seeds, "relaxed": relaxed}
