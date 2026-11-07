from celery.result import AsyncResult
from fastapi import FastAPI, Response
from pydantic import BaseModel, Field

from app.storage import features_key, get_json
from app.worker import analyze, celery

SERVICE = "analysis"

app = FastAPI(title=SERVICE)


class AnalyzeRequest(BaseModel):
    sha: str = Field(pattern=r"^[0-9a-f]{64}$")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": SERVICE}


@app.post("/analyze")
def create_analysis(req: AnalyzeRequest, response: Response) -> dict:
    cached = get_json(features_key(req.sha))
    if cached is not None:
        return {"status": "done", "cached": True, "sha": req.sha, "features": cached}
    job = analyze.delay(req.sha)
    response.status_code = 202
    return {"status": "queued", "job_id": job.id, "sha": req.sha}


@app.get("/analyze/{job_id}")
def get_analysis(job_id: str) -> dict:
    result = AsyncResult(job_id, app=celery)
    if result.state == "SUCCESS":
        return {"status": "done", **result.result}
    if result.state == "FAILURE":
        return {"status": "failed", "error": str(result.result)}
    return {"status": result.state.lower()}  # pending | started | retry
