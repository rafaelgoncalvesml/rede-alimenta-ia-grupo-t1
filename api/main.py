from fastapi import FastAPI

from api import auditoria, erros
from api.routers import doacoes, doadores, lotes, ongs
from api.storage import PostgresStorage, get_storage

app = FastAPI(title="Rede Alimenta IA", docs_url="/docs")
app.include_router(doadores.router)
app.include_router(ongs.router)
app.include_router(lotes.router)
app.include_router(doacoes.router)
erros.instala(app)
auditoria.instala(app)


@app.get("/health", tags=["infra"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/db", tags=["infra"])
def health_db() -> dict[str, str]:
    db = get_storage()
    if isinstance(db, PostgresStorage):
        db.ping()
        return {"status": "ok", "storage": "postgres"}
    return {"status": "ok", "storage": "memory"}
