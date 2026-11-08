"""Uma análise do começo ao fim: separando → analisando → buscando → pronto.

O estado fica no Redis e avança a cada consulta do front (GET /jobs/{id}); assim o gateway não
precisa de worker próprio. Cada etapa chama o serviço responsável pela API dele.
"""

import json
import uuid

import httpx

from app import clients
from app.config import ANALYSIS_URL, CATALOG_URL, EMBEDDING_MODEL, SEPARATION_URL

JOB_TTL_S = 2 * 3600


def save(job: dict) -> None:
    clients.store().setex(f"job:{job['id']}", JOB_TTL_S, json.dumps(job))


def load(job_id: str) -> dict | None:
    raw = clients.store().get(f"job:{job_id}")
    return json.loads(raw) if raw else None


def new(separation: dict, track: dict | None = None) -> dict:
    """Cria o job a partir da resposta do POST /separate (cache ou tarefa na fila)."""
    job = {"id": str(uuid.uuid4()), "sha": separation["sha"]}
    if track:
        job["track"] = track
    if separation["status"] == "done":
        job["stage"] = "analyzing"
    else:
        job.update(stage="separating", sep_job=separation["job_id"])
    return job


def _fail(job: dict, error: str) -> dict:
    return {**job, "stage": "failed", "error": error}


def _separating(job: dict) -> dict:
    r = clients.http().get(f"{SEPARATION_URL}/separate/{job['sep_job']}").raise_for_status()
    body = r.json()
    if body["status"] == "failed":
        return _fail(job, f"separação: {body['error']}")
    return {**job, "stage": "analyzing"} if body["status"] == "done" else job


def _analyzing(job: dict) -> dict:
    if "ana_job" not in job:
        r = clients.http().post(f"{ANALYSIS_URL}/analyze", json={"sha": job["sha"]})
        body = r.raise_for_status().json()
        if body["status"] != "done":
            return {**job, "ana_job": body["job_id"]}
    else:
        r = clients.http().get(f"{ANALYSIS_URL}/analyze/{job['ana_job']}").raise_for_status()
        body = r.json()
        if body["status"] == "failed":
            return _fail(job, f"análise: {body['error']}")
        if body["status"] != "done":
            return job
    analysis = {"features": body["features"], "vec": body["embeddings"][EMBEDDING_MODEL]}
    return {**job, "stage": "searching", "analysis": analysis}


def with_audio(results: list[dict]) -> list[dict]:
    """Trechos da FMA tocam pelo gateway, com crédito ao artista e a licença."""
    out = []
    for r in results:
        if r.get("source") == "fma" and r.get("audio_sha"):
            credit = " · ".join(filter(None, [r.get("artist"), r.get("license")]))
            r = {**r, "audio_url": f"/audio/track/{r['id']}", "credit": credit}
        out.append(r)
    return out


def _searching(job: dict) -> dict:
    features, vec = job["analysis"]["features"], job["analysis"]["vec"]
    body = {"model": EMBEDDING_MODEL, "vec": vec, "features": features, "k": 10}
    catalog = clients.http().post(f"{CATALOG_URL}/recommend", json=body).raise_for_status().json()
    result = {
        "catalog": with_audio(catalog["results"]),
        "relaxed": catalog["relaxed"],
        "spotify": [],
    }
    # O Spotify (via ReccoBeats) é um extra: se falhar, o resultado do catálogo segue valendo.
    ext_body = {"features": features}
    if job.get("track"):
        ext_body["track"] = job["track"]
    ext = clients.http().post(f"{CATALOG_URL}/recommend/external", json=ext_body)
    if ext.status_code == 200:
        result["spotify"] = ext.json()["results"]
        result["spotify_relaxed"] = ext.json().get("relaxed", [])
    else:
        result["spotify_error"] = "Recomendações do Spotify indisponíveis no momento"
    return {**job, "stage": "done", "result": result}


STEPS = {"separating": _separating, "analyzing": _analyzing, "searching": _searching}


def advance(job: dict) -> dict:
    """Avança o quanto der agora (ex.: separação em cache → já chama a análise).

    Se um serviço interno estiver fora do ar, para na etapa atual sem perder o que já andou;
    a próxima consulta tenta de novo.
    """
    while job["stage"] in STEPS:
        try:
            nxt = STEPS[job["stage"]](job)
        except httpx.HTTPError:
            break
        if nxt == job:  # etapa ainda rodando
            break
        job = nxt
    return job


def view(job: dict) -> dict:
    out = {"job_id": job["id"], "status": job["stage"], "sha": job["sha"]}
    if "analysis" in job:
        out["features"] = job["analysis"]["features"]
    for key in ("result", "error"):
        if key in job:
            out[key] = job[key]
    return out
