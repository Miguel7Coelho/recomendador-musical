"""Lógica de recomendação (seção 5 da especificação): cascata de filtros e pontuação.

Funções puras: o acesso ao banco fica em db.py e a orquestração em main.py.
"""

from collections.abc import Callable

# Pesos escolhidos na F3c (scripts/tune_weights.py, 399 faixas da FMA, k = 10): gênero 0,474,
# tom compatível 0,569 e voz 0,934, contra 0,391 / 0,866 / 0,898 dos pesos iniciais da
# especificação (0,55 / 0,20 / 0,15 / 0,10), que ficavam fora da fronteira gênero × tom.
WEIGHTS = {"cosine": 0.70, "key": 0.10, "genre": 0.10, "voice": 0.10}

# O filtro de voz só é aplicado quando a presença vocal da consulta é inequívoca.
VOCAL_SURE = 0.7
INSTRUMENTAL_SURE = 0.3
GENDER_SURE = 0.6

# Ordem de relaxamento: tom exato → compatível → só na ordenação; estilo → gênero amplo → sem
# filtro; por último a voz. Dimensões travadas pelo usuário nunca são relaxadas.
LADDER = {
    "key": ["exact", "compatible", "off"],
    "genre": ["style", "genre", "off"],
    "voice": ["on", "off"],
}


def camelot_neighbors(code: str) -> set[str]:
    n, letter = int(code[:-1]), code[-1]
    prev_n, next_n = (n - 2) % 12 + 1, n % 12 + 1
    other = "B" if letter == "A" else "A"
    return {f"{prev_n}{letter}", f"{next_n}{letter}", f"{n}{other}"}


def key_match(query: str | None, cand: str | None) -> float:
    if not query or not cand:
        return 0.0
    if query == cand:
        return 1.0
    return 0.7 if cand in camelot_neighbors(query) else 0.0


def genre_match(query: dict | None, cand: dict | None) -> float:
    """Fração da massa dos estilos da consulta que o candidato compartilha (0 a 1)."""
    if not query or not cand:
        return 0.0
    total = sum(query.values())
    shared = sum(min(p, cand.get(style, 0.0)) for style, p in query.items())
    return shared / total if total else 0.0


def is_vocal(presence: float | None) -> bool | None:
    """True/False quando a presença vocal é inequívoca; None quando está em dúvida."""
    if presence is None:
        return None
    if presence >= VOCAL_SURE:
        return True
    if presence <= INSTRUMENTAL_SURE:
        return False
    return None


def voice_match(query: dict, cand: dict) -> float:
    qp, cp = query.get("vocal_presence"), cand.get("vocal_presence")
    if qp is None or cp is None:
        return 0.0
    if (qp >= 0.5) != (cp >= 0.5):
        return 0.0
    if qp < 0.5:
        return 1.0  # os dois instrumentais
    qg, cg = query.get("vocal_gender"), cand.get("vocal_gender")
    if not qg or not cg:
        return 0.5  # os dois cantados, tipo de voz desconhecido em um deles
    if qg != cg:
        return 0.0
    return min(query.get("vocal_confidence") or 0.0, cand.get("vocal_confidence") or 0.0)


def score(components: dict[str, float], weights: dict[str, float] = WEIGHTS) -> float:
    return sum(weights[name] * components[name] for name in weights)


def bpm_ratio(a: float, b: float) -> float:
    """Diferença relativa de andamento, aceitando dobro/metade (90 e 180 BPM são o mesmo pulso)."""
    return min(abs(a * m - b) / b for m in (0.5, 1.0, 2.0))


def explain(query: dict, cand: dict, components: dict[str, float]) -> str:
    """Texto "parecida porque…" com os atributos que coincidiram."""
    parts = []
    if components["key"] == 1.0:
        parts.append(f"mesmo tom {cand['camelot']}")
    elif components["key"] > 0:
        parts.append(f"tom compatível {cand['camelot']}")
    shared = [s for s in (query.get("styles") or {}) if s in (cand.get("styles") or {})]
    if shared:
        parts.append(shared[0].split("---")[-1].lower())
    elif query.get("genre_top") and query.get("genre_top") == cand.get("genre_top"):
        parts.append(query["genre_top"].lower())
    if components["voice"] > 0:
        gender = {"female": "vocal feminino", "male": "vocal masculino"}
        vocal = (cand.get("vocal_presence") or 0) >= 0.5
        parts.append(gender.get(cand.get("vocal_gender"), "com vocal") if vocal else "instrumental")
    qb, cb = query.get("bpm"), cand.get("bpm")
    if qb and cb and bpm_ratio(qb, cb) <= 0.08:
        parts.append(f"{cb:.0f} vs. {qb:.0f} BPM")
    return " · ".join(parts)


def rank(query: dict, candidates: list[dict], weights: dict[str, float] = WEIGHTS) -> list[dict]:
    out = []
    for cand in candidates:
        comps = {
            "cosine": cand["cosine"],
            "key": key_match(query.get("camelot"), cand.get("camelot")),
            "genre": genre_match(query.get("styles"), cand.get("styles")),
            "voice": voice_match(query, cand),
        }
        out.append(
            {
                **cand,
                "score": round(score(comps, weights), 4),
                "components": {k: round(v, 4) for k, v in comps.items()},
                "explanation": explain(query, cand, comps),
            }
        )
    return sorted(out, key=lambda r: r["score"], reverse=True)


def relaxation_plan(start: dict[str, str], locked: set[str]) -> list[dict[str, str]]:
    """Sequência de níveis de filtro, do mais restritivo ao mais solto."""
    state = dict(start)
    plan = [dict(state)]
    for dim, levels in LADDER.items():
        if dim in locked:
            continue
        for level in levels[levels.index(state[dim]) + 1 :]:
            state[dim] = level
            plan.append(dict(state))
    return plan


def conditions(query: dict, levels: dict[str, str]) -> dict:
    """Converte os níveis em condições concretas para a consulta ao banco."""
    cond: dict = {"keys": None, "styles": None, "genre": None, "voice": None}

    camelot = query.get("camelot")
    if camelot and levels["key"] == "exact":
        cond["keys"] = [camelot]
    elif camelot and levels["key"] == "compatible":
        cond["keys"] = sorted({camelot} | camelot_neighbors(camelot))

    styles = list(query.get("styles") or {})[:3]
    if levels["genre"] == "style" and styles:
        cond["styles"] = styles
    elif levels["genre"] in ("style", "genre") and query.get("genre_top"):
        cond["genre"] = query["genre_top"]

    if levels["voice"] == "on":
        vocal = is_vocal(query.get("vocal_presence"))
        if vocal is False:
            cond["voice"] = {"vocal": False}
        elif vocal is True:
            sure = (query.get("vocal_confidence") or 0) >= GENDER_SURE
            cond["voice"] = {"vocal": True, "gender": query.get("vocal_gender") if sure else None}
    return cond


def run_cascade(
    query: dict,
    start: dict[str, str],
    locked: set[str],
    fetch: Callable[[dict], list[dict]],
    min_candidates: int,
) -> tuple[list[dict], dict[str, str], list[str]]:
    """Aplica os filtros e relaxa até ter candidatas suficientes.

    Devolve (candidatas, níveis usados, descrição dos relaxamentos).
    """
    plan = relaxation_plan(start, locked)
    for levels in plan:
        candidates = fetch(conditions(query, levels))
        if len(candidates) >= min_candidates:
            break
    relaxed = [f"{dim}: {start[dim]} → {levels[dim]}" for dim in start if start[dim] != levels[dim]]
    return candidates, levels, relaxed
