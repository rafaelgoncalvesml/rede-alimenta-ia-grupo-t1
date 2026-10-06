"""Limite de pedidos por minuto e de tamanho do corpo.

Os dois guardam estado so na memoria do processo: servem pro Render com um worker. Com mais
de um worker cada um conta o seu limite (o certo seria Redis, fora do escopo).
"""
import json
import math
import os
import threading
import time
from collections import deque

from fastapi import HTTPException, Request

from api import auditoria, seguranca

# quanto cada rota aguenta por usuario (ou IP, sem token valido) em 60 s. O custo vem do que
# a rota faz: lote roda o modelo, usuario cria conta, matching vai cruzar lote com todas as ONGs
GERAL = 120
LOTES = 30
DOACOES = 30
USUARIOS = 10
MATCHING = 20
JANELA_S = 60

_MAX_CHAVES = 10_000
_pedidos: dict[str, deque] = {}
_trava = threading.Lock()


def _agora() -> float:
    return time.monotonic()


def reset() -> None:
    with _trava:
        _pedidos.clear()


def _confere(chave: str, maximo: int, janela_s: int) -> int:
    """0 se o pedido passa (e ja conta), senao os segundos ate liberar."""
    agora = _agora()
    with _trava:
        if len(_pedidos) > _MAX_CHAVES:  # nao deixa a memoria crescer com chave que nao volta
            for k in [k for k, q in _pedidos.items() if not q or agora - q[-1] > janela_s]:
                del _pedidos[k]
        fila = _pedidos.setdefault(chave, deque())
        while fila and agora - fila[0] >= janela_s:
            fila.popleft()
        if len(fila) >= maximo:
            return max(1, math.ceil(janela_s - (agora - fila[0])))
        fila.append(agora)
        return 0


def limita(nome: str, maximo: int, janela_s: int = JANELA_S):
    """Dependencia: `dependencies=[Depends(limita("lotes", 30))]` na rota. O contador e por
    rota e por quem chama, entao estourar uma nao trava as outras."""

    def _dependencia(request: Request) -> None:
        quem = seguranca.quem_chama(request)
        espera = _confere(f"{nome}:{quem}", maximo, janela_s)
        if espera:
            auditoria.registrar("limite.estourado", rota=nome, quem=quem)
            raise HTTPException(
                status_code=429, detail="Muitos pedidos. Tente de novo em instantes.",
                headers={"Retry-After": str(espera)},
            )

    return _dependencia


# o login ja tem limite proprio por e-mail, e o /health e o que o Render chama pra saber se
# a API esta viva: nenhum dos dois entra no limite geral
_SEM_LIMITE_GERAL = {"/health", "/health/db", "/auth/login"}
_geral = limita("geral", GERAL)


def limite_geral(request: Request) -> None:
    if request.url.path not in _SEM_LIMITE_GERAL:
        _geral(request)


# ---- tamanho do corpo ----

def max_corpo() -> int:
    return int(os.getenv("MAX_BODY_BYTES", "65536"))


class _CorpoGrande(BaseException):
    # BaseException de proposito: o FastAPI embrulha qualquer Exception levantada ao ler o
    # corpo num 400 "error parsing the body", e o corpo grande tem que virar 413
    pass


class LimiteDeCorpo:
    """Middleware ASGI: recusa com 413 corpo maior que MAX_BODY_BYTES (64 KiB por padrao;
    o maior pedido legitimo da API tem alguns KB). Confere o Content-Length antes de ler e
    tambem conta os bytes que chegam, pra pegar corpo em chunks sem o cabecalho."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        limite = max_corpo()
        declarado = dict(scope["headers"]).get(b"content-length", b"")
        if declarado.isdigit() and int(declarado) > limite:
            return await self._recusa(send, limite)

        recebido = 0
        resposta_comecou = False

        async def receive_contando():
            nonlocal recebido
            msg = await receive()
            if msg["type"] == "http.request":
                recebido += len(msg.get("body", b""))
                if recebido > limite:
                    raise _CorpoGrande
            return msg

        async def send_vigiando(msg):
            nonlocal resposta_comecou
            if msg["type"] == "http.response.start":
                resposta_comecou = True
            await send(msg)

        try:
            await self.app(scope, receive_contando, send_vigiando)
        except _CorpoGrande:
            if resposta_comecou:
                raise
            await self._recusa(send, limite)

    @staticmethod
    async def _recusa(send, limite: int):
        corpo = json.dumps(
            {"detail": "Corpo do pedido grande demais", "limite_bytes": limite}).encode()
        await send({"type": "http.response.start", "status": 413, "headers": [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(corpo)).encode()),
            (b"connection", b"close")]})
        await send({"type": "http.response.body", "body": corpo})
