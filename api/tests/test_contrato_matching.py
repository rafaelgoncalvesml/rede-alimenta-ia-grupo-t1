"""
Contrato entre ml/matching.py e a API: o matching nao pode sugerir uma ONG que a doacao recusaria,
e nao pode esconder uma que a doacao aceitaria. A regra mora em api/routers/doacoes.py.
"""
from datetime import UTC, date, datetime, timedelta
from itertools import product

import pytest
from fastapi import HTTPException

from api.models import DoadorCreate, LoteCreate, OngCreate
from api.routers.doacoes import _confere_ong_recebe
from ml.matching import matching

AGORA = datetime.now(UTC)


def _ong(id, capacidade, necessidades, **mudancas) -> dict:
    corpo = OngCreate(nome=f"ONG {id}", cnpj="44555666000102", endereco="Rua A, 1", cidade="Sao Paulo",
                      estado="sp", latitude=-23.56 - id / 100, longitude=-46.65, capacidade_kg=capacidade,
                      necessidades=necessidades, **mudancas)
    return {"id": id, "criado_em": AGORA, **corpo.model_dump(mode="json")}


def _lote(quantidade, tipo) -> dict:
    corpo = LoteCreate(doador_id=1, descricao="caixa de tomate", quantidade_kg=quantidade,
                       validade=date.today() + timedelta(days=3), armazenamento="refrigerado", tipo=tipo)
    return {"id": 1, "status": "disponivel", "prioridade": "alta", "criado_em": AGORA,
            **corpo.model_dump(mode="json")}


def _doador() -> dict:
    corpo = DoadorCreate(nome="Mercado DEMO", tipo_pessoa="juridica", documento="00000000000100",
                         cidade="Sao Paulo", estado="SP")  # sem coordenada: exercita o fallback
    return {"id": 1, "criado_em": AGORA, **corpo.model_dump(mode="json")}


def _doacao_aceita(lote: dict, ong: dict) -> bool:
    try:
        _confere_ong_recebe(lote, ong)
    except HTTPException:
        return False
    return True


@pytest.mark.parametrize("quantidade, tipo", list(product([10, 100, 101, 5000], ["hortifruti", "padaria", None])))
def test_o_matching_sugere_exatamente_as_ongs_que_a_doacao_aceita(quantidade, tipo):
    ongs = [_ong(1, 100, ["hortifruti"]), _ong(2, 100, ["padaria"]), _ong(3, 5000, ["hortifruti", "padaria"]),
            _ong(4, 5000, []), _ong(5, 0, ["hortifruti"])]
    lote = _lote(quantidade, tipo)

    resultado = matching(lote, _doador(), ongs)

    sugeridas = {r["ong_id"] for r in resultado["ranking"]}
    aceitas_pela_doacao = {o["id"] for o in ongs if _doacao_aceita(lote, o)}
    assert sugeridas == aceitas_pela_doacao
    assert sugeridas | {d["ong_id"] for d in resultado["descartadas"]} == {o["id"] for o in ongs}


def test_distancia_e_score_cabem_no_que_a_doacao_guarda():
    from api.models import DoacaoCreate

    escolhida = matching(_lote(50, "hortifruti"), _doador(), [_ong(1, 100, ["hortifruti"])])["ranking"][0]

    DoacaoCreate(lote_id=1, ong_id=escolhida["ong_id"], distancia_km=escolhida["distancia_km"],
                 score=escolhida["score"])
