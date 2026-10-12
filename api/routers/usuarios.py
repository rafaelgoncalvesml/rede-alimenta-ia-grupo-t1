from fastapi import APIRouter, Depends, HTTPException

from api import auditoria, limites, seguranca
from api.models import Papel, Usuario, UsuarioCreate
from api.storage import get_storage

# so o admin mexe aqui. Nao ha cadastro aberto: quem entra na plataforma e decisao do grupo
router = APIRouter(prefix="/usuarios", tags=["usuarios"],
                   dependencies=[Depends(seguranca.exige(Papel.admin))])


def _publico(linha: dict) -> Usuario:
    return Usuario(**{k: v for k, v in linha.items() if k != "senha_hash"})


@router.post("", response_model=Usuario, status_code=201,
             dependencies=[Depends(limites.limita("usuarios", limites.USUARIOS))])
def criar_usuario(dados: UsuarioCreate) -> Usuario:
    db = get_storage()
    if db.existe("usuarios", email=dados.email):
        raise HTTPException(status_code=409, detail="Ja existe usuario com esse e-mail")
    if dados.doador_id is not None and db.buscar("doadores", dados.doador_id) is None:
        raise HTTPException(status_code=404, detail="Doador nao encontrado")
    if dados.ong_id is not None and db.buscar("ongs", dados.ong_id) is None:
        raise HTTPException(status_code=404, detail="ONG nao encontrada")
    criado = db.criar("usuarios", {
        "email": dados.email, "senha_hash": seguranca.hasher.hash(dados.senha),
        "papel": dados.papel.value, "doador_id": dados.doador_id, "ong_id": dados.ong_id,
    })
    auditoria.registrar("usuario.criado", usuario_id=criado["id"], papel=dados.papel.value)
    return _publico(criado)


@router.get("", response_model=list[Usuario])
def listar_usuarios() -> list[Usuario]:
    return [_publico(u) for u in get_storage().listar("usuarios")]
