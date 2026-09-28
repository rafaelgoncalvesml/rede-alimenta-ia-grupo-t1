from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from api.models import Lote, LoteCreate, LoteUpdate, StatusLote
from api.routers.doadores import _doadores

router = APIRouter(prefix="/lotes", tags=["lotes"])

_lotes: dict[int, Lote] = {}
_proximo_id = 1

# de onde pode ir. doado e descartado sao finais
TRANSICOES = {
    StatusLote.disponivel: {StatusLote.reservado, StatusLote.descartado},
    StatusLote.reservado: {StatusLote.disponivel, StatusLote.doado, StatusLote.descartado},
    StatusLote.doado: set(),
    StatusLote.descartado: set(),
}


def _pega_lote(lote_id: int) -> Lote:
    lote = _lotes.get(lote_id)
    if lote is None:
        raise HTTPException(status_code=404, detail="Lote nao encontrado")
    return lote


@router.post("", response_model=Lote, status_code=201)
def criar_lote(dados: LoteCreate) -> Lote:
    global _proximo_id
    if dados.doador_id not in _doadores:
        raise HTTPException(status_code=404, detail="Doador nao encontrado")
    lote = Lote(id=_proximo_id, criado_em=datetime.now(timezone.utc), **dados.model_dump())
    _lotes[lote.id] = lote
    _proximo_id += 1
    return lote


@router.get("", response_model=list[Lote])
def listar_lotes(status: StatusLote | None = None, doador_id: int | None = None) -> list[Lote]:
    lotes = _lotes.values()
    if status is not None:
        lotes = [l for l in lotes if l.status == status]
    if doador_id is not None:
        lotes = [l for l in lotes if l.doador_id == doador_id]
    return list(lotes)


@router.get("/{lote_id}", response_model=Lote)
def buscar_lote(lote_id: int) -> Lote:
    return _pega_lote(lote_id)


@router.put("/{lote_id}", response_model=Lote)
def atualizar_lote(lote_id: int, dados: LoteUpdate) -> Lote:
    lote = _pega_lote(lote_id)
    mudancas = dados.model_dump(exclude_unset=True)

    novo_status = mudancas.get("status")
    if novo_status is not None and novo_status != lote.status:
        if novo_status not in TRANSICOES[lote.status]:
            raise HTTPException(
                status_code=409,
                detail=f"Lote {lote.status.value} nao pode virar {novo_status.value}",
            )
    elif not TRANSICOES[lote.status] and mudancas:
        # lote fechado (doado/descartado) nao aceita mais edicao
        raise HTTPException(status_code=409, detail=f"Lote {lote.status.value} nao pode ser editado")

    atualizado = lote.model_copy(update=mudancas)
    _lotes[lote_id] = atualizado
    return atualizado


@router.delete("/{lote_id}", status_code=204)
def remover_lote(lote_id: int) -> None:
    lote = _pega_lote(lote_id)
    if lote.status in (StatusLote.reservado, StatusLote.doado):
        raise HTTPException(status_code=409, detail=f"Lote {lote.status.value} nao pode ser apagado")
    del _lotes[lote_id]
