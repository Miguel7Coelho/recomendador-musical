from fastapi import FastAPI

SERVICE = "analysis"

app = FastAPI(title=SERVICE)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": SERVICE}
