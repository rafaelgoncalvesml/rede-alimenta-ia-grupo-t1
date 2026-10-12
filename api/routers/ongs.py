from fastapi import APIRouter, HTTPException

from api import auditoria
from api.models import Ong, OngCreate, OngUpdate
from api.storage import get_storage

router = APIRouter(prefix="/ongs", tags=["ongs"])


def _pega_ong(ong_id: int) -> Ong:
    linha = get_storage().buscar("ongs", ong_id)
    if linha is None:
        raise HTTPException(status_code=404, detail="ONG nao encontrada")
    return Ong(**linha)


@router.post("", response_model=Ong, status_code=201)
def criar_ong(dados: OngCreate) -> Ong:
    db = get_storage()
    if db.existe("ongs", cnpj=dados.cnpj):
        raise HTTPException(status_code=409, detail="Ja existe ONG com esse CNPJ")
    criada = db.criar("ongs", dados.model_dump(mode="json"))
    auditoria.registrar("ong.criada", ong_id=criada["id"])
    return Ong(**criada)


@router.get("", response_model=list[Ong])
def listar_ongs() -> list[Ong]:
    return [Ong(**l) for l in get_storage().listar("ongs")]


@router.get("/{ong_id}", response_model=Ong)
def buscar_ong(ong_id: int) -> Ong:
    return _pega_ong(ong_id)


@router.put("/{ong_id}", response_model=Ong)
def atualizar_ong(ong_id: int, dados: OngUpdate) -> Ong:
    atual = _pega_ong(ong_id)
    mudancas = dados.model_dump(exclude_unset=True, mode="json")
    if not mudancas:
        return atual
    nova = get_storage().atualizar("ongs", ong_id, mudancas)
    auditoria.registrar("ong.atualizada", ong_id=ong_id, campos=sorted(mudancas))
    return Ong(**nova)


@router.delete("/{ong_id}", status_code=204)
def remover_ong(ong_id: int) -> None:
    _pega_ong(ong_id)
    db = get_storage()
    if db.existe("doacoes", ong_id=ong_id):
        raise HTTPException(status_code=409, detail="ONG tem doacoes registradas")
    db.apagar("ongs", ong_id)
    auditoria.registrar("ong.apagada", ong_id=ong_id)
