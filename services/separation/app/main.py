from pathlib import Path
from tempfile import TemporaryDirectory

from celery.result import AsyncResult
from fastapi import FastAPI, HTTPException, Response, UploadFile

from app.audio import InvalidAudio, normalize, sha256
from app.config import MAX_UPLOAD_BYTES
from app.storage import input_key, stem_keys, stems_cached, upload
from app.worker import celery, separate

SERVICE = "separation"

app = FastAPI(title=SERVICE)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": SERVICE}


@app.post("/separate")
def create_separation(file: UploadFile, response: Response) -> dict:
    with TemporaryDirectory() as tmp:
        raw, wav = Path(tmp) / "upload", Path(tmp) / "normalized.wav"

        size = 0
        with raw.open("wb") as f:
            while chunk := file.file.read(1 << 20):
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    raise HTTPException(413, "Arquivo maior que 25 MB")
                f.write(chunk)

        try:
            normalize(raw, wav)
        except InvalidAudio as e:
            raise HTTPException(400, f"Áudio inválido: {e}") from e

        sha = sha256(wav)
        if stems_cached(sha):
            return {"status": "done", "cached": True, "sha": sha, "stems": stem_keys(sha)}

        upload(wav, input_key(sha))

    job = separate.delay(sha)
    response.status_code = 202
    return {"status": "queued", "job_id": job.id, "sha": sha}


@app.get("/separate/{job_id}")
def get_separation(job_id: str) -> dict:
    result = AsyncResult(job_id, app=celery)
    if result.state == "SUCCESS":
        return {"status": "done", **result.result}
    if result.state == "FAILURE":
        return {"status": "failed", "error": str(result.result)}
    return {"status": result.state.lower()}  # pending | started | retry
