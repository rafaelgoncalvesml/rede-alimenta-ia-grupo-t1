from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, FastAPI

from api import auditoria, erros, ia, limites, seguranca
from api.routers import auth, doacoes, doadores, kpis, lotes, matching, ongs, usuarios
from api.storage import PostgresStorage, get_storage

# o .env tem que estar carregado antes do lifespan: ele valida o JWT_SECRET na subida, e o
# get_storage (que tambem le o .env) so roda depois. No Render e no container nao ha .env
load_dotenv(Path(__file__).resolve().parent.parent / ".env")


@asynccontextmanager
async def _ciclo_de_vida(app: FastAPI):
    seguranca.valida_config()  # sem JWT_SECRET a API nao sobe
    seguranca.garantir_admin()
    ia.pre_carregar_modelo()  # nunca levanta: sem modelo a API sobe e o lote entra sem prioridade
    yield


app = FastAPI(title="Rede Alimenta IA", docs_url="/docs", lifespan=_ciclo_de_vida,
              dependencies=[Depends(limites.limite_geral)])
app.include_router(auth.router)
app.include_router(usuarios.router)
app.include_router(doadores.router)
app.include_router(ongs.router)
app.include_router(lotes.router)
app.include_router(doacoes.router)
app.include_router(matching.router)
app.include_router(kpis.router)
# o corpo e conferido por dentro da auditoria, pra o 413 sair no log
app.add_middleware(limites.LimiteDeCorpo)
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
