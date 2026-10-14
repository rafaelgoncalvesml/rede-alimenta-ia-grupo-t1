from fastapi import APIRouter, Depends, HTTPException

from api import limites
from api.models import Papel, StatusLote
from api.seguranca import Usuario, e_admin, exige, nega
from api.storage import get_storage
from ml.matching import matching

router = APIRouter(prefix="/matching", tags=["matching"])

# sugerir e coisa de quem doa: a ONG nao escolhe de quem recebe
admin_ou_doador = exige(Papel.admin, Papel.doador)


@router.post("/{lote_id}", dependencies=[Depends(limites.limita("matching", limites.MATCHING))])
def sugerir(lote_id: int, usuario: Usuario = Depends(admin_ou_doador)) -> dict:
    db = get_storage()
    lote = db.buscar("lotes", lote_id)
    if lote is None:
        raise HTTPException(status_code=404, detail="Lote nao encontrado")
    if not e_admin(usuario) and lote["doador_id"] != usuario.doador_id:
        nega(usuario, "matching de lote de outro doador")
    if lote["status"] != StatusLote.disponivel.value:
        raise HTTPException(status_code=409, detail="Lote nao esta disponivel")
    try:
        return matching(lote, db.buscar("doadores", lote["doador_id"]), db.listar("ongs"))
    except ValueError as erro:
        raise HTTPException(status_code=422, detail=str(erro)) from None
