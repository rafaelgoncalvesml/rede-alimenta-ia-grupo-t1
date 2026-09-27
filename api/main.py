from fastapi import FastAPI

from api.routers import doadores, lotes, ongs

app = FastAPI(title="Rede Alimenta IA", docs_url="/docs")
app.include_router(doadores.router)
app.include_router(ongs.router)
app.include_router(lotes.router)


@app.get("/health", tags=["infra"])
def health() -> dict[str, str]:
    return {"status": "ok"}
