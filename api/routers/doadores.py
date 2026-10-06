from fastapi import APIRouter, Depends, HTTPException

from api import auditoria
from api.models import Doador, DoadorCreate, DoadorUpdate, Papel
from api.seguranca import Usuario, e_admin, exige, nega
from api.storage import get_storage

router = APIRouter(prefix="/doadores", tags=["doadores"])

# admin cadastra e apaga; o doador so le e edita o proprio cadastro
admin = exige(Papel.admin)
admin_ou_doador = exige(Papel.admin, Papel.doador)


def _so_o_proprio(usuario: Usuario, doador_id: int) -> None:
    if not e_admin(usuario) and usuario.doador_id != doador_id:
        nega(usuario, "doador de outro")


def _pega_doador(doador_id: int) -> Doador:
    linha = get_storage().buscar("doadores", doador_id)
    if linha is None:
        raise HTTPException(status_code=404, detail="Doador nao encontrado")
    return Doador(**linha)


@router.post("", response_model=Doador, status_code=201, dependencies=[Depends(admin)])
def criar_doador(dados: DoadorCreate) -> Doador:
    db = get_storage()
    if db.existe("doadores", documento=dados.documento):
        raise HTTPException(status_code=409, detail="Ja existe doador com esse documento")
    criado = db.criar("doadores", dados.model_dump(mode="json"))
    auditoria.registrar("doador.criado", doador_id=criado["id"])
    return Doador(**criado)


@router.get("", response_model=list[Doador], dependencies=[Depends(admin)])
def listar_doadores() -> list[Doador]:
    return [Doador(**l) for l in get_storage().listar("doadores")]


@router.get("/{doador_id}", response_model=Doador)
def buscar_doador(doador_id: int, usuario: Usuario = Depends(admin_ou_doador)) -> Doador:
    _so_o_proprio(usuario, doador_id)
    return _pega_doador(doador_id)


@router.put("/{doador_id}", response_model=Doador)
def atualizar_doador(
    doador_id: int, dados: DoadorUpdate, usuario: Usuario = Depends(admin_ou_doador)
) -> Doador:
    _so_o_proprio(usuario, doador_id)
    atual = _pega_doador(doador_id)
    mudancas = dados.model_dump(exclude_unset=True, mode="json")
    if not mudancas:
        return atual
    novo = get_storage().atualizar("doadores", doador_id, mudancas)
    auditoria.registrar("doador.atualizado", doador_id=doador_id, campos=sorted(mudancas))
    return Doador(**novo)


@router.delete("/{doador_id}", status_code=204, dependencies=[Depends(admin)])
def remover_doador(doador_id: int) -> None:
    _pega_doador(doador_id)
    db = get_storage()
    if db.existe("lotes", doador_id=doador_id):
        raise HTTPException(status_code=409, detail="Doador tem lotes cadastrados")
    if db.existe("usuarios", doador_id=doador_id):
        raise HTTPException(status_code=409, detail="Doador tem usuario de acesso")
    db.apagar("doadores", doador_id)
    auditoria.registrar("doador.apagado", doador_id=doador_id)
