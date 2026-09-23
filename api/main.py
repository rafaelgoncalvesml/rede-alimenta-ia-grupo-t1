from fastapi import FastAPI

from api.routers import doadores

app = FastAPI(title="Rede Alimenta IA")
app.include_router(doadores.router)
