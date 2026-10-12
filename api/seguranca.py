"""Login, token e permissao por papel.

O token e um JWT HS256 assinado com JWT_SECRET (so no ambiente, nunca no repo). Leva o
papel e a entidade do usuario (doador_id ou ong_id), entao cada pedido se decide sem ir
ao banco. O preco: um usuario apagado continua valendo ate o token expirar (30 min por
padrao). Uma API key estatica nao carregaria quem e o dono, e sem isso nao da pra barrar
um doador de abrir o lote de outro.

Dependencias pros routers: `usuario_atual` (401 sem token valido) e `exige(...)` (403 se
o papel nao esta na lista). A checagem de dono do objeto fica no router, com `pode_ver_*`.
"""
import hashlib
import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from api import auditoria
from api.models import Papel
from api.storage import get_storage

ALGORITMO = "HS256"
_bearer = HTTPBearer(auto_error=False, description="Token do POST /auth/login")
hasher = PasswordHasher()

# 5 erros de senha por e-mail a cada 15 min. Fica na memoria do processo: serve pro Render
# com um worker so. Com varios workers o limite vira por processo.
MAX_FALHAS = 5
JANELA_S = 15 * 60
_falhas: dict[str, list[float]] = {}

# hash de uma senha que ninguem tem, pra login de e-mail inexistente gastar o mesmo tempo
# que um de verdade e nao revelar quais e-mails existem
_HASH_FALSO = hasher.hash("senha-que-nao-existe-em-lugar-nenhum")


@dataclass(frozen=True)
class Usuario:
    id: int
    papel: Papel
    doador_id: int | None = None
    ong_id: int | None = None


def segredo() -> str:
    s = os.getenv("JWT_SECRET", "")
    if len(s) < 32:
        raise RuntimeError(
            "JWT_SECRET ausente ou curto (minimo 32 caracteres). "
            'Gere com: python -c "import secrets; print(secrets.token_urlsafe(48))"'
        )
    return s


def minutos_de_validade() -> int:
    return int(os.getenv("TOKEN_MINUTOS", "30"))


def valida_config() -> None:
    """Chamado na subida da API: sem segredo ela nao sobe."""
    segredo()


def garantir_admin() -> None:
    """Cria o admin de ADMIN_EMAIL/ADMIN_PASSWORD se ainda nao existe. Sem as duas
    variaveis nao faz nada (o admin entao vem de um insert manual no banco)."""
    email = os.getenv("ADMIN_EMAIL", "").strip().lower()
    senha = os.getenv("ADMIN_PASSWORD", "")
    if not email or not senha:
        return
    if len(senha) < 10:
        raise RuntimeError("ADMIN_PASSWORD precisa ter pelo menos 10 caracteres")
    db = get_storage()
    if not db.existe("usuarios", email=email):
        db.criar("usuarios", {"email": email, "senha_hash": hasher.hash(senha),
                              "papel": Papel.admin.value, "doador_id": None, "ong_id": None})
        auditoria.registrar("usuario.admin_criado")


def _chave(email: str) -> str:
    return hashlib.sha256(email.strip().lower().encode()).hexdigest()


def _bloqueado(chave: str) -> int:
    """Segundos ate poder tentar de novo, 0 se pode."""
    agora = time.monotonic()
    recentes = [t for t in _falhas.get(chave, []) if agora - t < JANELA_S]
    _falhas[chave] = recentes
    if len(recentes) >= MAX_FALHAS:
        return int(JANELA_S - (agora - recentes[0])) + 1
    return 0


def autentica(email: str, senha: str) -> dict:
    """Devolve a linha do usuario ou levanta 401/429. A mensagem e a mesma pra e-mail
    errado e senha errada."""
    chave = _chave(email)
    espera = _bloqueado(chave)
    if espera:
        auditoria.registrar("auth.bloqueado", email_sha=chave[:10])
        raise HTTPException(
            status_code=429, detail="Muitas tentativas. Tente de novo mais tarde.",
            headers={"Retry-After": str(espera)},
        )
    linhas = get_storage().listar("usuarios", email=email.strip().lower())
    linha = linhas[0] if linhas else None
    try:
        hasher.verify(linha["senha_hash"] if linha else _HASH_FALSO, senha)
        ok = linha is not None
    except (VerificationError, InvalidHashError):
        ok = False
    if not ok:
        _falhas.setdefault(chave, []).append(time.monotonic())
        auditoria.registrar("auth.falhou", email_sha=chave[:10])
        raise HTTPException(status_code=401, detail="E-mail ou senha incorretos",
                            headers={"WWW-Authenticate": "Bearer"})
    _falhas.pop(chave, None)
    if hasher.check_needs_rehash(linha["senha_hash"]):
        get_storage().atualizar("usuarios", linha["id"], {"senha_hash": hasher.hash(senha)})
    auditoria.registrar("auth.login", usuario_id=linha["id"], papel=linha["papel"])
    return linha


def emite_token(linha: dict) -> tuple[str, int]:
    agora = datetime.now(timezone.utc)
    validade = timedelta(minutes=minutos_de_validade())
    claims = {"sub": str(linha["id"]), "papel": linha["papel"], "iat": agora,
              "exp": agora + validade}
    if linha.get("doador_id") is not None:
        claims["doador_id"] = linha["doador_id"]
    if linha.get("ong_id") is not None:
        claims["ong_id"] = linha["ong_id"]
    return jwt.encode(claims, segredo(), algorithm=ALGORITMO), int(validade.total_seconds())


def _nao_autenticado() -> HTTPException:
    return HTTPException(status_code=401, detail="Token ausente, invalido ou expirado",
                         headers={"WWW-Authenticate": "Bearer"})


def usuario_atual(
    request: Request,
    cred: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> Usuario:
    if cred is None:
        raise _nao_autenticado()
    try:
        # algorithms fixo: sem isso um token com "alg": "none" passaria
        c = jwt.decode(cred.credentials, segredo(), algorithms=[ALGORITMO],
                       options={"require": ["exp", "sub", "papel"]})
        usuario = Usuario(id=int(c["sub"]), papel=Papel(c["papel"]),
                          doador_id=c.get("doador_id"), ong_id=c.get("ong_id"))
    except (jwt.PyJWTError, ValueError):
        raise _nao_autenticado() from None
    request.state.usuario_id = usuario.id  # o log de auditoria le daqui
    return usuario


def exige(*papeis: Papel):
    """Dependencia: so deixa passar quem tem um dos papeis (403 pro resto)."""
    def _confere(usuario: Usuario = Depends(usuario_atual)) -> Usuario:
        if usuario.papel not in papeis:
            auditoria.registrar("acesso.negado", usuario_id=usuario.id, papel=usuario.papel.value,
                                motivo="papel")
            raise HTTPException(status_code=403, detail="Sem permissao para esta operacao")
        return usuario
    return _confere


def nega(usuario: Usuario, motivo: str):
    """403 por objeto que nao e do usuario (o papel ate serve, o dono e outro)."""
    auditoria.registrar("acesso.negado", usuario_id=usuario.id, papel=usuario.papel.value,
                        motivo=motivo)
    raise HTTPException(status_code=403, detail="Sem permissao para este recurso")


def e_admin(u: Usuario) -> bool:
    return u.papel == Papel.admin
