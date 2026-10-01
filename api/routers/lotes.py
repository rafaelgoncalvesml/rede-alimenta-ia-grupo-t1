from fastapi import APIRouter, HTTPException

from api import auditoria
from api.ia import classificar_lote
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
    novo = dados.model_dump(mode="json")
    try:
        novo.update(classificar_lote(novo))
    except ValueError as erro:
        raise HTTPException(status_code=422, detail=str(erro))
    criado = db.criar("lotes", novo)
    auditoria.registrar("lote.criado", lote_id=criado["id"], doador_id=dados.doador_id,
                        prioridade=criado.get("prioridade"))
    return Lote(**criado)


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

    db = get_storage()
    if lote.status == StatusLote.reservado and novo_status in (StatusLote.disponivel, StatusLote.descartado):
        # a reserva caiu: a doacao confirmada vira cancelada antes de o lote mudar, pra
        # um PUT que falhe no meio poder ser repetido sem deixar o lote preso
        for d in db.listar("doacoes", lote_id=lote_id, status="confirmada"):
            db.atualizar("doacoes", d["id"], {"status": "cancelada"})
            auditoria.registrar("doacao.cancelada", doacao_id=d["id"], lote_id=lote_id)
    atualizado = db.atualizar("lotes", lote_id, mudancas)
    auditoria.registrar("lote.atualizado", lote_id=lote_id, campos=sorted(mudancas),
                        status_de=lote.status.value, status_para=atualizado["status"])
    return Lote(**atualizado)


@router.delete("/{lote_id}", status_code=204)
def remover_lote(lote_id: int) -> None:
    lote = _pega_lote(lote_id)
    if lote.status in (StatusLote.reservado, StatusLote.doado):
        raise HTTPException(status_code=409, detail=f"Lote {lote.status.value} nao pode ser apagado")
    db = get_storage()
    if db.existe("doacoes", lote_id=lote_id):
        raise HTTPException(status_code=409, detail="Lote tem doacao registrada")
    db.apagar("lotes", lote_id)
    auditoria.registrar("lote.apagado", lote_id=lote_id)
