from contextlib import asynccontextmanager

from fastapi import FastAPI

from api import auditoria, erros, seguranca
from api.routers import auth, doacoes, doadores, lotes, ongs, usuarios
from api.storage import PostgresStorage, get_storage


@asynccontextmanager
async def _ciclo_de_vida(app: FastAPI):
    seguranca.valida_config()  # sem JWT_SECRET a API nao sobe
    seguranca.garantir_admin()
    yield


app = FastAPI(title="Rede Alimenta IA", docs_url="/docs", lifespan=_ciclo_de_vida)
app.include_router(auth.router)
app.include_router(usuarios.router)
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
