"""Log de auditoria: uma linha JSON por pedido e uma por mudanca de dado.

Sai no stdout (e o que o Render guarda). Nao grava corpo de pedido nem querystring: ali
vao CPF/CNPJ, e-mail e telefone, dado pessoal que nao pode parar em log (LGPD). "Quem" e o
id do usuario do token (quando ha) e o IP do cliente. Atras do proxy do Render o IP e o do
proxy (ver ip_do_cliente); o X-Forwarded-For nao entra porque o cliente pode forjar.
"""
import ipaddress
import json
import logging
import os
import sys
import time
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

log = logging.getLogger("auditoria")
log_erros = logging.getLogger("api.erros")

request_id: ContextVar[str] = ContextVar("request_id", default="-")

MUTACOES = {"POST", "PUT", "PATCH", "DELETE"}


def _configura():
    if log.handlers:
        return
    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(logging.Formatter("%(message)s"))
    log.addHandler(h)
    log.setLevel(logging.INFO)


_configura()


def _linha(**campos) -> str:
    campos = {"ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
              "request_id": request_id.get(), **campos}
    # json.dumps escapa quebra de linha, entao um path forjado nao cria linha falsa no log
    return json.dumps(campos, ensure_ascii=False, default=str)


def ip_do_cliente(request: Request) -> str | None:
    """IP de quem chamou, pro log e pro limite de pedidos.

    Atras do Render o request.client.host e o do proxy interno. O X-Forwarded-For nao serve: o
    valor que o cliente manda fica na primeira posicao. O Cloudflare na frente do Render
    sobrescreve o CF-Connecting-IP (testado em 12/10, docs/deploy-render.md), entao so ele e
    confiavel, e so se CONFIAR_CF_CONNECTING_IP=1. Fora do Render a variavel fica desligada e
    o cabecalho e ignorado, porque ali qualquer cliente poderia mandar o que quisesse. Valor que
    nao e um IP valido cai de volta no client.host.
    """
    host = request.client.host if request.client else None
    if os.getenv("CONFIAR_CF_CONNECTING_IP") == "1":
        cf = request.headers.get("cf-connecting-ip", "").strip()
        try:
            return str(ipaddress.ip_address(cf))
        except ValueError:
            pass
    return host


def registrar(acao: str, **campos) -> None:
    """Evento de negocio, ex.: registrar("doacao.confirmada", doacao_id=3, lote_id=1)."""
    log.info(_linha(tipo="evento", acao=acao, **campos))


def instala(app: FastAPI) -> None:
    @app.middleware("http")
    async def _auditoria(request: Request, call_next):
        rid = uuid.uuid4().hex[:12]
        token = request_id.set(rid)
        inicio = time.perf_counter()
        try:
            try:
                resposta = await call_next(request)
            except Exception:
                # stack trace so no log; quem chamou recebe mensagem generica + o id pra achar aqui
                log_erros.exception("erro nao tratado em %s %s", request.method, request.url.path)
                resposta = JSONResponse(
                    status_code=500,
                    content={"detail": "Erro interno do servidor", "request_id": rid},
                )
            resposta.headers["X-Request-ID"] = rid
            status = resposta.status_code
            nivel = logging.ERROR if status >= 500 else logging.WARNING if status >= 400 else logging.INFO
            log.log(nivel, _linha(
                tipo="requisicao",
                metodo=request.method,
                path=request.url.path[:200],
                status=status,
                ms=round((time.perf_counter() - inicio) * 1000, 1),
                usuario_id=getattr(request.state, "usuario_id", None),
                ip=ip_do_cliente(request),
                mutacao=request.method in MUTACOES,
            ))
            return resposta
        finally:
            request_id.reset(token)
