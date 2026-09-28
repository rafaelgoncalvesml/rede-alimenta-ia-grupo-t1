from fastapi import APIRouter, HTTPException

from api.models import Lote, LoteCreate, LoteUpdate, StatusLote
from api.storage import get_storage

router = APIRouter(prefix="/lotes", tags=["lotes"])

# de onde pode ir. doado e descartado sao finais
TRANSICOES = {
    StatusLote.disponivel: {StatusLote.reservado, StatusLote.descartado},
    StatusLote.reservado: {StatusLote.disponivel, StatusLote.doado, StatusLote.descartado},
    StatusLote.doado: set(),
    StatusLote.descartado: set(),
}


def _pega_lote(lote_id: int) -> Lote:
    linha = get_storage().buscar("lotes", lote_id)
    if linha is None:
        raise HTTPException(status_code=404, detail="Lote nao encontrado")
    return Lote(**linha)


@router.post("", response_model=Lote, status_code=201)
def criar_lote(dados: LoteCreate) -> Lote:
    db = get_storage()
    if db.buscar("doadores", dados.doador_id) is None:
        raise HTTPException(status_code=404, detail="Doador nao encontrado")
    return Lote(**db.criar("lotes", dados.model_dump(mode="json")))


@router.get("", response_model=list[Lote])
def listar_lotes(status: StatusLote | None = None, doador_id: int | None = None) -> list[Lote]:
    filtros = {}
    if status is not None:
        filtros["status"] = status.value
    if doador_id is not None:
        filtros["doador_id"] = doador_id
    return [Lote(**l) for l in get_storage().listar("lotes", **filtros)]


@router.get("/{lote_id}", response_model=Lote)
def buscar_lote(lote_id: int) -> Lote:
    return _pega_lote(lote_id)


@router.put("/{lote_id}", response_model=Lote)
def atualizar_lote(lote_id: int, dados: LoteUpdate) -> Lote:
    lote = _pega_lote(lote_id)
    mudancas = dados.model_dump(exclude_unset=True, mode="json")
    if not mudancas:
        return lote

    novo_status = StatusLote(mudancas["status"]) if "status" in mudancas else None
    if novo_status is not None and novo_status != lote.status:
        if novo_status not in TRANSICOES[lote.status]:
            raise HTTPException(
                status_code=409,
                detail=f"Lote {lote.status.value} nao pode virar {novo_status.value}",
            )
    elif not TRANSICOES[lote.status]:
        # lote fechado (doado/descartado) nao aceita mais edicao
        raise HTTPException(status_code=409, detail=f"Lote {lote.status.value} nao pode ser editado")

    return Lote(**get_storage().atualizar("lotes", lote_id, mudancas))


@router.delete("/{lote_id}", status_code=204)
def remover_lote(lote_id: int) -> None:
    lote = _pega_lote(lote_id)
    if lote.status in (StatusLote.reservado, StatusLote.doado):
        raise HTTPException(status_code=409, detail=f"Lote {lote.status.value} nao pode ser apagado")
    get_storage().apagar("lotes", lote_id)
