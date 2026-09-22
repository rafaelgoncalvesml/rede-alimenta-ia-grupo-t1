from datetime import datetime, timezone

from fastapi import FastAPI

app = FastAPI(title="Rede Alimenta IA - deploy test")


@app.get("/")
def root():
    return {
        "service": "rede-alimenta-ia-deploy-test",
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/health")
def health():
    return {"status": "healthy"}
