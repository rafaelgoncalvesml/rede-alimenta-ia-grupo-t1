from fastapi import APIRouter, Depends, HTTPException

from api import auditoria, limites
from api.ia import classificar_lote
from api.models import Lote, LoteCreate, LoteUpdate, Papel, StatusLote
from api.seguranca import Usuario, e_admin, exige, nega, usuario_atual
from api.storage import get_storage

router = APIRouter(prefix="/lotes", tags=["lotes"])

# escreve: admin ou o doador dono do lote. le: tambem a ONG que recebeu a doacao
admin_ou_doador = exige(Papel.admin, Papel.doador)

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


def _lotes_da_ong(ong_id: int) -> set[int]:
    doacoes = get_storage().listar("doacoes", ong_id=ong_id, status="confirmada")
    return {d["lote_id"] for d in doacoes}


def _so_dono(usuario: Usuario, lote: Lote) -> None:
    if not e_admin(usuario) and usuario.doador_id != lote.doador_id:
        nega(usuario, "lote de outro doador")


@router.post("", response_model=Lote, status_code=201,
             dependencies=[Depends(limites.limita("lotes", limites.LOTES))])
def criar_lote(dados: LoteCreate, usuario: Usuario = Depends(admin_ou_doador)) -> Lote:
    if not e_admin(usuario) and dados.doador_id != usuario.doador_id:
        nega(usuario, "lote em nome de outro doador")
    db = get_storage()
    if db.buscar("doadores", dados.doador_id) is None:
        raise HTTPException(status_code=404, detail="Doador nao encontrado")
    novo = dados.model_dump(mode="json")
    try:
        novo.update(classificar_lote(novo))
    except ValueError as erro:
        raise HTTPException(status_code=422, detail=str(erro)) from None
    criado = db.criar("lotes", novo)
    auditoria.registrar("lote.criado", lote_id=criado["id"], doador_id=dados.doador_id,
                        prioridade=criado.get("prioridade"))
    return Lote(**criado)


@router.get("", response_model=list[Lote])
def listar_lotes(
    status: StatusLote | None = None,
    doador_id: int | None = None,
    usuario: Usuario = Depends(usuario_atual),
) -> list[Lote]:
    if usuario.papel == Papel.doador:
        if doador_id is not None and doador_id != usuario.doador_id:
            nega(usuario, "lotes de outro doador")
        doador_id = usuario.doador_id
    filtros = {}
    if status is not None:
        filtros["status"] = status.value
    if doador_id is not None:
        filtros["doador_id"] = doador_id
    linhas = get_storage().listar("lotes", **filtros)
    if usuario.papel == Papel.ong:
        meus = _lotes_da_ong(usuario.ong_id)
        linhas = [l for l in linhas if l["id"] in meus]
    return [Lote(**l) for l in linhas]


@router.get("/{lote_id}", response_model=Lote)
def buscar_lote(lote_id: int, usuario: Usuario = Depends(usuario_atual)) -> Lote:
    lote = _pega_lote(lote_id)
    if usuario.papel == Papel.ong:
        if lote_id not in _lotes_da_ong(usuario.ong_id):
            nega(usuario, "lote sem doacao pra essa ong")
    else:
        _so_dono(usuario, lote)
    return lote


@router.put("/{lote_id}", response_model=Lote)
def atualizar_lote(
    lote_id: int, dados: LoteUpdate, usuario: Usuario = Depends(admin_ou_doador)
) -> Lote:
    lote = _pega_lote(lote_id)
    _so_dono(usuario, lote)
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
def remover_lote(lote_id: int, usuario: Usuario = Depends(admin_ou_doador)) -> None:
    lote = _pega_lote(lote_id)
    _so_dono(usuario, lote)
    if lote.status in (StatusLote.reservado, StatusLote.doado):
        raise HTTPException(status_code=409, detail=f"Lote {lote.status.value} nao pode ser apagado")
    db = get_storage()
    if db.existe("doacoes", lote_id=lote_id):
        raise HTTPException(status_code=409, detail="Lote tem doacao registrada")
    db.apagar("lotes", lote_id)
    auditoria.registrar("lote.apagado", lote_id=lote_id)
