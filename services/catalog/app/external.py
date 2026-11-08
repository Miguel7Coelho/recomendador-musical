"""Candidatas do Spotify escolhidas por gênero (sem áudio para analisarmos).

Com a música conhecida, a base é o que os ouvintes dela também escutam (Last.fm); senão, as
etiquetas de gênero do Last.fm. A faixa tocável vem do Spotify e o tom e o andamento da ReccoBeats.
O andamento elimina; tom compatível só melhora a posição.
"""

import os
import re
from concurrent.futures import ThreadPoolExecutor
from functools import cache, lru_cache

import httpx

from app import lastfm, recommend

RECCOBEATS = "https://api.reccobeats.com/v1"
SPOTIFY_API = os.getenv("SPOTIFY_API_URL", "http://spotify-api:8000")

MAX_STYLES = 4
MIN_STYLE_PROB = 0.05  # abaixo disso o estilo é ruído do classificador
TAG_POOL = 50  # faixas pedidas por etiqueta
POOL = 30  # faixas procuradas no Spotify por consulta: cada uma gasta o limite da API
MATCH_WORKERS = 2
BPM_TOLERANCE = 0.10  # dobro e metade do andamento também contam
MAX_PER_ARTIST = 2
LISTENER_LIMIT = 100
LISTENER_POOL = 30  # faixas de ouvintes procuradas no Spotify
LISTENER_PER_ARTIST = 4  # os primeiros similares costumam ser do próprio artista
SCORE_WEIGHTS = {"style": 0.60, "bpm": 0.25, "key": 0.15}

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


def style_tags(features: dict) -> dict[str, float]:
    """Etiquetas a procurar e seu peso. Só estilos do gênero principal, para que um palpite
    fraco do classificador não traga folk ou latina para uma faixa de hip-hop."""
    genre = features.get("genre_top")
    styles = sorted((features.get("styles") or {}).items(), key=lambda s: -s[1])
    kept = [
        (style, prob)
        for style, prob in styles
        if prob >= MIN_STYLE_PROB and (not genre or style.split("---")[0] == genre)
    ][:MAX_STYLES]
    tags = {lastfm.tag_for(style.split("---")[-1]): prob for style, prob in kept}
    if genre:  # o gênero amplo só completa a lista, depois dos estilos
        tags.setdefault(lastfm.tag_for(genre), min(tags.values(), default=0.1) / 2)
    return tags


def _tagged_tracks(tags: dict[str, float]) -> list[dict]:
    """Faixas das etiquetas; a que aparece em várias soma o peso de todas."""
    found: dict[tuple[str, str], dict] = {}
    for tag, weight in tags.items():
        for position, (title, artist) in enumerate(lastfm.top_tracks(tag, TAG_POOL)):
            key = (title.casefold(), artist.casefold())
            track = found.setdefault(
                key, {"title": title, "artist": artist, "weight": 0.0, "tags": [], "order": 1e9}
            )
            track["weight"] += weight
            track["tags"].append(tag)
            track["order"] = min(track["order"], position)
    return sorted(found.values(), key=lambda t: (-t["weight"], t["order"]))[:POOL]


@lru_cache(maxsize=4096)
def _spotify_match(title: str, artist: str) -> dict | None:
    body = {"title": title, "artist": artist}
    r = client().post(f"{SPOTIFY_API}/match", json=body).raise_for_status()
    return r.json()["match"]


def _find_on_spotify(tracks: list[dict]) -> list[tuple[dict, dict]]:
    """Pares (faixa, correspondência). Uma busca que falha só perde aquela faixa, exceto se
    todas falharem: aí o Spotify está fora e quem chamou precisa saber."""

    def lookup(track: dict) -> dict | None | Exception:
        try:
            return _spotify_match(track["title"], track["artist"])
        except httpx.HTTPError as e:
            return e

    with ThreadPoolExecutor(MATCH_WORKERS) as pool:
        answers = list(pool.map(lookup, tracks))
    errors = [a for a in answers if isinstance(a, Exception)]
    if tracks and len(errors) == len(tracks):
        raise errors[0]
    return [(t, a) for t, a in zip(tracks, answers) if isinstance(a, dict)]


def _is_speech(features: dict) -> bool:
    return (features.get("speechiness") or 0) > MAX_SPEECHINESS


def _recco_features(spotify_ids: list[str]) -> dict[str, dict]:
    out = {}
    for i in range(0, len(spotify_ids), 20):
        r = client().get(f"{RECCOBEATS}/audio-features", params={"ids": spotify_ids[i : i + 20]})
        for f in r.raise_for_status().json()["content"]:
            out[_spotify_id(f["href"])] = f
    return out


def _listener_tracks(track: dict) -> list[dict]:
    """O que quem ouve a faixa também ouve. Sem dados, a recomendação segue pelas etiquetas."""
    try:
        similar = lastfm.similar_tracks(track["title"], track["artist"], LISTENER_LIMIT)
    except httpx.HTTPError:
        return []
    own = (track["title"].casefold(), track["artist"].casefold())
    per_artist: dict[str, int] = {}
    out = []
    for position, (title, artist, match) in enumerate(similar):
        name = artist.casefold()
        if (title.casefold(), name) == own or per_artist.get(name, 0) >= LISTENER_PER_ARTIST:
            continue
        per_artist[name] = per_artist.get(name, 0) + 1
        out.append(
            {"title": title, "artist": artist, "weight": match, "order": position, "tags": []}
        )
    return out[:LISTENER_POOL]


def _candidate(track: dict, match: dict, feats: dict, scale: float, tier: int, query: dict) -> dict:
    camelot = camelot_from_pitch(feats.get("key"), feats.get("mode"))
    key = recommend.key_match(query.get("camelot"), camelot)
    q_bpm = query.get("bpm")
    distance = recommend.bpm_ratio(feats["tempo"], q_bpm) if q_bpm else 0.0
    parts = {
        "style": min(track["weight"] / scale, 1.0),
        "bpm": max(1 - distance / BPM_TOLERANCE, 0.0),
        "key": key,
    }
    why = [track["tags"][0] if track["tags"] else "ouvintes também escutam"]
    if q_bpm:
        why.append(f"{feats['tempo']:.0f} vs. {q_bpm:.0f} BPM")
    if key:
        why.append(f"{'mesmo tom' if key == 1.0 else 'tom compatível'} {camelot}")
    return {
        "source": "lastfm",
        "spotify_id": match["spotify_id"],
        "title": match["title"],
        "artists": match["artists"],
        "url": match["url"],
        "camelot": camelot,
        "bpm": feats["tempo"],
        "explanation": " · ".join(why),
        "score": round(sum(SCORE_WEIGHTS[name] * value for name, value in parts.items()), 4),
        "_tier": tier,
        "_distance": distance,
        "_order": track["order"],
    }


def _screen(
    tracks: list[dict], scale: float, tier: int, query: dict, exclude: list[str], seen: tuple
) -> list[dict]:
    """Localiza no Spotify e elimina o que está fora do andamento ou não é música."""
    seen_ids, seen_audio = seen
    matches = [(t, m) for t, m in _find_on_spotify(tracks) if m["spotify_id"] not in exclude]
    audio = _recco_features(list({m["spotify_id"] for _, m in matches}))
    q_bpm = query.get("bpm")

    cands = []
    for track, match in matches:
        sid = match["spotify_id"]
        f = audio.get(sid)
        if sid in seen_ids or not f or not f.get("tempo"):
            continue  # sem andamento conhecido não dá para garantir que combina
        seen_ids.add(sid)
        if _is_speech(f) or NOISE_TITLE.search(match["title"]):
            continue
        if q_bpm and recommend.bpm_ratio(f["tempo"], q_bpm) > BPM_TOLERANCE:
            continue
        fingerprint = tuple(f.get(name) for name in AUDIO_FIELDS)
        if None not in fingerprint:
            if fingerprint in seen_audio:
                continue
            seen_audio.add(fingerprint)
        cands.append(_candidate(track, match, f, scale, tier, query))
    return cands


def _pick(cands: list[dict], k: int) -> list[dict]:
    """Primeiro o que vem dos ouvintes, depois a pontuação, sem repetir demais o artista."""
    results: list[dict] = []
    per_artist: dict[str, int] = {}
    for c in sorted(cands, key=lambda c: (c["_tier"], -c["score"], c["_distance"], c["_order"])):
        lead = c["artists"][0].casefold()
        if per_artist.get(lead, 0) >= MAX_PER_ARTIST:
            continue
        per_artist[lead] = per_artist.get(lead, 0) + 1
        results.append(c)
        if len(results) == k:
            break
    return results


def recommendations(
    features: dict, exclude_ids: list[str], k: int, track: dict | None = None
) -> dict:
    """Com a música conhecida, o gosto dos ouvintes vale mais que o estilo detectado e dispensa
    o filtro de gênero; as etiquetas só completam a lista."""
    seen: tuple[set, set] = (set(), set())
    cands: list[dict] = []
    if track:
        listeners = _listener_tracks(track)
        scale = max((t["weight"] for t in listeners), default=1.0)
        cands = _screen(listeners, scale, 0, features, exclude_ids, seen)

    tags = style_tags(features) if len(_pick(cands, k)) < k else {}
    if tags:
        cands += _screen(_tagged_tracks(tags), sum(tags.values()), 1, features, exclude_ids, seen)

    results = [
        {name: v for name, v in c.items() if not name.startswith("_")} for c in _pick(cands, k)
    ]
    return {"results": results, "tags": list(tags), "relaxed": []}
