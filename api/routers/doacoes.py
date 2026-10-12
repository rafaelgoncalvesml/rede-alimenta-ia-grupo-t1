from fastapi import APIRouter, HTTPException

from api.models import Doacao, DoacaoCreate, StatusDoacao
from api.storage import get_storage

router = APIRouter(prefix="/doacoes", tags=["doacoes"])

# sem PUT nem DELETE de proposito: e o registro de quem recebeu o que e quando (base
# do tempo de match). Cancelar e voltar o lote pra disponivel em PUT /lotes/{id}.


@router.post("", response_model=Doacao, status_code=201)
def confirmar_doacao(dados: DoacaoCreate) -> Doacao:
    db = get_storage()
    if db.buscar("lotes", dados.lote_id) is None:
        raise HTTPException(status_code=404, detail="Lote nao encontrado")
    if db.buscar("ongs", dados.ong_id) is None:
        raise HTTPException(status_code=404, detail="ONG nao encontrada")
    doacao = db.confirmar_doacao(dados.lote_id, dados.ong_id, dados.distancia_km, dados.score)
    if doacao is None:
        raise HTTPException(status_code=409, detail="Lote nao esta disponivel")
    return Doacao(**doacao)


@router.get("", response_model=list[Doacao])
def listar_doacoes(
    lote_id: int | None = None, ong_id: int | None = None, status: StatusDoacao | None = None
) -> list[Doacao]:
    filtros = {}
    if lote_id is not None:
        filtros["lote_id"] = lote_id
    if ong_id is not None:
        filtros["ong_id"] = ong_id
    if status is not None:
        filtros["status"] = status.value
    return [Doacao(**d) for d in get_storage().listar("doacoes", **filtros)]


@router.get("/{doacao_id}", response_model=Doacao)
def buscar_doacao(doacao_id: int) -> Doacao:
    linha = get_storage().buscar("doacoes", doacao_id)
    if linha is None:
        raise HTTPException(status_code=404, detail="Doacao nao encontrada")
    return Doacao(**linha)
