from fastapi import APIRouter, Depends

from api import seguranca
from api.models import LoginIn, Token
from api.seguranca import Usuario, usuario_atual

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=Token)
def login(dados: LoginIn) -> Token:
    linha = seguranca.autentica(dados.email, dados.senha)
    token, expira_em = seguranca.emite_token(linha)
    return Token(access_token=token, expires_in=expira_em)


@router.get("/eu")
def quem_sou_eu(usuario: Usuario = Depends(usuario_atual)) -> dict:
    return {"id": usuario.id, "papel": usuario.papel, "doador_id": usuario.doador_id,
            "ong_id": usuario.ong_id}
