from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from api.models import Ong, OngCreate, OngUpdate

router = APIRouter(prefix="/ongs", tags=["ongs"])

# em memoria, mesma ideia do doadores.py
_ongs: dict[int, Ong] = {}
_proximo_id = 1


@router.post("", response_model=Ong, status_code=201)
def criar_ong(dados: OngCreate) -> Ong:
    global _proximo_id
    ong = Ong(id=_proximo_id, criado_em=datetime.now(timezone.utc), **dados.model_dump())
    _ongs[ong.id] = ong
    _proximo_id += 1
    return ong


@router.get("", response_model=list[Ong])
def listar_ongs() -> list[Ong]:
    return list(_ongs.values())


@router.get("/{ong_id}", response_model=Ong)
def buscar_ong(ong_id: int) -> Ong:
    ong = _ongs.get(ong_id)
    if ong is None:
        raise HTTPException(status_code=404, detail="ONG nao encontrada")
    return ong


@router.put("/{ong_id}", response_model=Ong)
def atualizar_ong(ong_id: int, dados: OngUpdate) -> Ong:
    ong = _ongs.get(ong_id)
    if ong is None:
        raise HTTPException(status_code=404, detail="ONG nao encontrada")
    atualizada = ong.model_copy(update=dados.model_dump(exclude_unset=True))
    _ongs[ong_id] = atualizada
    return atualizada


@router.delete("/{ong_id}", status_code=204)
def remover_ong(ong_id: int) -> None:
    if ong_id not in _ongs:
        raise HTTPException(status_code=404, detail="ONG nao encontrada")
    del _ongs[ong_id]
