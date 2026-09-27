from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from api.models import Lote, LoteCreate, LoteUpdate
from api.routers.doadores import _doadores

router = APIRouter(prefix="/lotes", tags=["lotes"])

_lotes: dict[int, Lote] = {}
_proximo_id = 1


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
def listar_lotes() -> list[Lote]:
    return list(_lotes.values())


@router.get("/{lote_id}", response_model=Lote)
def buscar_lote(lote_id: int) -> Lote:
    lote = _lotes.get(lote_id)
    if lote is None:
        raise HTTPException(status_code=404, detail="Lote nao encontrado")
    return lote


@router.put("/{lote_id}", response_model=Lote)
def atualizar_lote(lote_id: int, dados: LoteUpdate) -> Lote:
    lote = _lotes.get(lote_id)
    if lote is None:
        raise HTTPException(status_code=404, detail="Lote nao encontrado")
    atualizado = lote.model_copy(update=dados.model_dump(exclude_unset=True))
    _lotes[lote_id] = atualizado
    return atualizado


@router.delete("/{lote_id}", status_code=204)
def remover_lote(lote_id: int) -> None:
    if lote_id not in _lotes:
        raise HTTPException(status_code=404, detail="Lote nao encontrado")
    del _lotes[lote_id]
