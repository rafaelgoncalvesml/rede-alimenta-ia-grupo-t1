from fastapi import APIRouter, Depends, HTTPException

from api import auditoria, limites
from api.models import Doacao, DoacaoCreate, Papel, StatusDoacao
from api.seguranca import Usuario, e_admin, exige, nega, usuario_atual
from api.storage import get_storage

router = APIRouter(prefix="/doacoes", tags=["doacoes"])

# confirma: admin ou o doador dono do lote. le: admin, o doador do lote e a ONG recebedora
admin_ou_doador = exige(Papel.admin, Papel.doador)

# sem PUT nem DELETE de proposito: e o registro de quem recebeu o que e quando (base
# do tempo de match). Cancelar e voltar o lote pra disponivel em PUT /lotes/{id}.


@router.post("", response_model=Doacao, status_code=201,
             dependencies=[Depends(limites.limita("doacoes", limites.DOACOES))])
def confirmar_doacao(
    dados: DoacaoCreate, usuario: Usuario = Depends(admin_ou_doador)
) -> Doacao:
    db = get_storage()
    lote = db.buscar("lotes", dados.lote_id)
    if lote is None:
        raise HTTPException(status_code=404, detail="Lote nao encontrado")
    if not e_admin(usuario) and lote["doador_id"] != usuario.doador_id:
        nega(usuario, "doar lote de outro doador")
    if db.buscar("ongs", dados.ong_id) is None:
        raise HTTPException(status_code=404, detail="ONG nao encontrada")
    doacao = db.confirmar_doacao(dados.lote_id, dados.ong_id, dados.distancia_km, dados.score)
    if doacao is None:
        raise HTTPException(status_code=409, detail="Lote nao esta disponivel")
    auditoria.registrar("doacao.confirmada", doacao_id=doacao["id"], lote_id=dados.lote_id,
                        ong_id=dados.ong_id, tempo_match_s=doacao["tempo_match_s"])
    return Doacao(**doacao)


@router.get("", response_model=list[Doacao])
def listar_doacoes(
    lote_id: int | None = None,
    ong_id: int | None = None,
    status: StatusDoacao | None = None,
    usuario: Usuario = Depends(usuario_atual),
) -> list[Doacao]:
    if usuario.papel == Papel.ong:
        if ong_id is not None and ong_id != usuario.ong_id:
            nega(usuario, "doacoes de outra ong")
        ong_id = usuario.ong_id
    meus_lotes = None
    if usuario.papel == Papel.doador:
        meus_lotes = {l["id"] for l in get_storage().listar("lotes", doador_id=usuario.doador_id)}
        if lote_id is not None and lote_id not in meus_lotes:
            nega(usuario, "doacoes de lote de outro doador")
    filtros = {}
    if lote_id is not None:
        filtros["lote_id"] = lote_id
    if ong_id is not None:
        filtros["ong_id"] = ong_id
    if status is not None:
        filtros["status"] = status.value
    linhas = get_storage().listar("doacoes", **filtros)
    if meus_lotes is not None:
        linhas = [d for d in linhas if d["lote_id"] in meus_lotes]
    return [Doacao(**d) for d in linhas]


@router.get("/{doacao_id}", response_model=Doacao)
def buscar_doacao(doacao_id: int, usuario: Usuario = Depends(usuario_atual)) -> Doacao:
    db = get_storage()
    linha = db.buscar("doacoes", doacao_id)
    if linha is None:
        raise HTTPException(status_code=404, detail="Doacao nao encontrada")
    if usuario.papel == Papel.ong and linha["ong_id"] != usuario.ong_id:
        nega(usuario, "doacao de outra ong")
    if usuario.papel == Papel.doador:
        lote = db.buscar("lotes", linha["lote_id"])
        if lote is None or lote["doador_id"] != usuario.doador_id:
            nega(usuario, "doacao de lote de outro doador")
    return Doacao(**linha)
