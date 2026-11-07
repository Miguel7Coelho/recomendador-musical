from fastapi import FastAPI

SERVICE = "catalog"

app = FastAPI(title=SERVICE)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": SERVICE}
