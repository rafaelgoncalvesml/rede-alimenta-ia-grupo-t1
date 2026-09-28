from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from api.models import Doador, DoadorCreate, DoadorUpdate

router = APIRouter(prefix="/doadores", tags=["doadores"])

# storage em memoria ate a conexao com o Supabase entrar (dia 10 do
# cronograma) - ver infra/db/schema.sql pra tabela real
_doadores: dict[int, Doador] = {}
_proximo_id = 1


@router.post("", response_model=Doador, status_code=201)
def criar_doador(dados: DoadorCreate) -> Doador:
    global _proximo_id
    if any(d.documento == dados.documento for d in _doadores.values()):
        raise HTTPException(status_code=409, detail="Ja existe doador com esse documento")
    doador = Doador(id=_proximo_id, criado_em=datetime.now(timezone.utc), **dados.model_dump())
    _doadores[doador.id] = doador
    _proximo_id += 1
    return doador


@router.get("", response_model=list[Doador])
def listar_doadores() -> list[Doador]:
    return list(_doadores.values())


@router.get("/{doador_id}", response_model=Doador)
def buscar_doador(doador_id: int) -> Doador:
    doador = _doadores.get(doador_id)
    if doador is None:
        raise HTTPException(status_code=404, detail="Doador nao encontrado")
    return doador


@router.put("/{doador_id}", response_model=Doador)
def atualizar_doador(doador_id: int, dados: DoadorUpdate) -> Doador:
    doador = _doadores.get(doador_id)
    if doador is None:
        raise HTTPException(status_code=404, detail="Doador nao encontrado")
    atualizado = doador.model_copy(update=dados.model_dump(exclude_unset=True))
    _doadores[doador_id] = atualizado
    return atualizado


@router.delete("/{doador_id}", status_code=204)
def remover_doador(doador_id: int) -> None:
    if doador_id not in _doadores:
        raise HTTPException(status_code=404, detail="Doador nao encontrado")
    # import aqui dentro porque lotes.py ja importa este modulo
    from api.routers import lotes

    if any(l.doador_id == doador_id for l in lotes._lotes.values()):
        raise HTTPException(status_code=409, detail="Doador tem lotes cadastrados")
    del _doadores[doador_id]
