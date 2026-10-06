from fastapi import APIRouter, Depends

from api import kpis
from api.models import Papel
from api.seguranca import Usuario, usuario_atual
from api.storage import get_storage

router = APIRouter(prefix="/kpis", tags=["kpis"])


def _escopo(usuario: Usuario) -> tuple[list[dict], list[dict], list[dict]]:
    """(lotes, doacoes, ongs) que o usuario pode somar: admin tudo, doador os lotes dele e
    as doacoes deles, ONG as doacoes que recebeu e os lotes delas."""
    db = get_storage()
    lotes, doacoes, ongs = db.listar("lotes"), db.listar("doacoes"), db.listar("ongs")
    if usuario.papel == Papel.doador:
        lotes = [l for l in lotes if l["doador_id"] == usuario.doador_id]
        meus = {l["id"] for l in lotes}
        doacoes = [d for d in doacoes if d["lote_id"] in meus]
    elif usuario.papel == Papel.ong:
        doacoes = [d for d in doacoes if d["ong_id"] == usuario.ong_id]
        recebidos = {d["lote_id"] for d in doacoes}
        lotes = [l for l in lotes if l["id"] in recebidos]
    return lotes, doacoes, ongs


@router.get("/impacto")
def kpis_impacto(usuario: Usuario = Depends(usuario_atual)) -> dict:
    lotes, doacoes, ongs = _escopo(usuario)
    return kpis.calcula_impacto(lotes, doacoes, ongs, kpis.kg_por_refeicao())


@router.get("/ia")
def kpis_ia(usuario: Usuario = Depends(usuario_atual)) -> dict:
    lotes = _escopo(usuario)[0]
    return kpis.calcula_ia(lotes, kpis.le_metricas())
