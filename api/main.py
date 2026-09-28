import psycopg
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from psycopg_pool import PoolTimeout

from api.routers import doadores, lotes, ongs
from api.storage import PostgresStorage, get_storage

app = FastAPI(title="Rede Alimenta IA", docs_url="/docs")
app.include_router(doadores.router)
app.include_router(ongs.router)
app.include_router(lotes.router)


@app.exception_handler(psycopg.errors.UniqueViolation)
@app.exception_handler(psycopg.errors.ForeignKeyViolation)
async def _conflito_no_banco(request, exc):
    # o pre-check dos routers pega o caso comum; isto cobre corrida entre dois pedidos
    return JSONResponse(status_code=409, content={"detail": "Conflito com dados ja existentes"})


@app.exception_handler(psycopg.OperationalError)
@app.exception_handler(PoolTimeout)
async def _banco_fora(request, exc):
    return JSONResponse(status_code=503, content={"detail": "Banco de dados indisponivel"})


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
