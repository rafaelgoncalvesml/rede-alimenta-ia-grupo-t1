"""Respostas de erro da API. Todo erro sai como JSON {"detail": ...}.

400 JSON que nao da pra ler, 404/405 do proprio FastAPI, 409 conflito, 422 dado invalido,
503 banco fora, 500 o resto (esse fica no middleware de api/auditoria.py).
"""
import psycopg
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from psycopg_pool import PoolTimeout

from api.auditoria import request_id


def instala(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def _validacao(request, exc: RequestValidationError):
        # corpo que nem e JSON e erro de quem chamou (400); JSON valido com campo errado e 422
        if any(e["type"] == "json_invalid" for e in exc.errors()):
            return JSONResponse(status_code=400, content={"detail": "Corpo do pedido nao e um JSON valido"})
        # sem "input" nem "ctx": o padrao do FastAPI devolve o valor recebido, e com NaN ou
        # Infinity a propria resposta 422 nao serializa e vira 500
        erros = [{"type": e["type"], "loc": e["loc"], "msg": e["msg"]} for e in exc.errors()]
        return JSONResponse(status_code=422, content={"detail": erros})

    @app.exception_handler(psycopg.errors.UniqueViolation)
    @app.exception_handler(psycopg.errors.ForeignKeyViolation)
    async def _conflito_no_banco(request, exc):
        # o pre-check dos routers pega o caso comum; isto cobre corrida entre dois pedidos
        return JSONResponse(status_code=409, content={"detail": "Conflito com dados ja existentes"})

    @app.exception_handler(psycopg.DataError)
    async def _dado_que_o_banco_recusa(request, exc):
        # id maior que bigint, texto com byte nulo... o Pydantic deixa passar, o Postgres nao
        return JSONResponse(status_code=422, content={"detail": "Valor fora do que o banco aceita"})

    @app.exception_handler(psycopg.OperationalError)
    @app.exception_handler(PoolTimeout)
    async def _banco_fora(request, exc):
        return JSONResponse(
            status_code=503,
            content={"detail": "Banco de dados indisponivel", "request_id": request_id.get()},
        )
