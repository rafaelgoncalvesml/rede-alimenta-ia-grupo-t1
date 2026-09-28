from fastapi import APIRouter, HTTPException

from api.models import Doador, DoadorCreate, DoadorUpdate
from api.storage import get_storage

router = APIRouter(prefix="/doadores", tags=["doadores"])


def _pega_doador(doador_id: int) -> Doador:
    linha = get_storage().buscar("doadores", doador_id)
    if linha is None:
        raise HTTPException(status_code=404, detail="Doador nao encontrado")
    return Doador(**linha)


@router.post("", response_model=Doador, status_code=201)
def criar_doador(dados: DoadorCreate) -> Doador:
    db = get_storage()
    if db.existe("doadores", documento=dados.documento):
        raise HTTPException(status_code=409, detail="Ja existe doador com esse documento")
    return Doador(**db.criar("doadores", dados.model_dump(mode="json")))


@router.get("", response_model=list[Doador])
def listar_doadores() -> list[Doador]:
    return [Doador(**l) for l in get_storage().listar("doadores")]


@router.get("/{doador_id}", response_model=Doador)
def buscar_doador(doador_id: int) -> Doador:
    return _pega_doador(doador_id)


@router.put("/{doador_id}", response_model=Doador)
def atualizar_doador(doador_id: int, dados: DoadorUpdate) -> Doador:
    atual = _pega_doador(doador_id)
    mudancas = dados.model_dump(exclude_unset=True, mode="json")
    if not mudancas:
        return atual
    return Doador(**get_storage().atualizar("doadores", doador_id, mudancas))


@router.delete("/{doador_id}", status_code=204)
def remover_doador(doador_id: int) -> None:
    _pega_doador(doador_id)
    db = get_storage()
    if db.existe("lotes", doador_id=doador_id):
        raise HTTPException(status_code=409, detail="Doador tem lotes cadastrados")
    db.apagar("doadores", doador_id)
