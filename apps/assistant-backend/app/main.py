from fastapi import FastAPI

app = FastAPI(title="Exobrain Assistant Backend", version="0.1.0")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}
