"""Limites por visitante: cada análise custa CPU da VM e cada busca gasta cota de APIs externas."""

import logging

import redis

from app import clients

log = logging.getLogger("uvicorn.error")

GENERAL = ("api", 300, 60)  # folgado: a tela de progresso consulta o job a cada 1,5 s
RULES = {
    ("POST", "/analyze"): ("analyze", 20, 3600),
    ("POST", "/songs/recommend"): ("song", 60, 3600),
    ("GET", "/songs/youtube"): ("video", 120, 3600),
}
ANALYZE_PER_DAY = 300  # teto para todos os visitantes somados
DAY_S = 24 * 3600


def _over(key: str, limit: int, window_s: int) -> bool:
    store = clients.store()
    count = store.incr(key)
    if count == 1:
        store.expire(key, window_s)
    return count > limit


def retry_after(method: str, path: str, client: str) -> int | None:
    """Segundos de espera se o pedido passou do limite; None se pode seguir."""
    name, limit, window_s = RULES.get((method, path), GENERAL)
    try:
        if _over(f"limit:{name}:{client}", limit, window_s):
            return window_s
        if name == "analyze" and _over("limit:analyze:all", ANALYZE_PER_DAY, DAY_S):
            return DAY_S
    except redis.RedisError as e:  # sem Redis o site já está degradado; não derruba o resto
        log.warning("Limite de uso indisponível: %s", e)
    return None
