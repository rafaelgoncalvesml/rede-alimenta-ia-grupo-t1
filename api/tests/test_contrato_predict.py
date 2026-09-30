"""
Contrato entre a API e ml/predict.py: o que o LoteCreate produz e o que a rota vai mandar pro predict().
Se o modelo do Lote mudar (campo, tipo, enum), estes testes quebram antes da rota.
"""
from datetime import date, timedelta

import pytest

from api.models import LoteCreate
from ml.predict import predict

PRIORIDADES = {"alta", "media", "baixa"}


def _lote(**mudancas) -> LoteCreate:
    base = dict(doador_id=1, descricao="iogurte natural", quantidade_kg=20,
                validade=date.today() + timedelta(days=3), armazenamento="refrigerado")
    return LoteCreate(**{**base, **mudancas})


@pytest.mark.parametrize("modo", ["json", "python"])
def test_predict_aceita_o_lote_como_o_lotecreate_produz(modo):
    # "json": validade vira texto ISO e armazenamento vira str; "python": validade e enum de verdade
    saida = predict(_lote().model_dump(mode=modo))

    assert saida["prioridade"] in PRIORIDADES


@pytest.mark.parametrize("tipo, origem", [(None, "modelo"), ("laticinios", "informada")])
def test_tipo_nulo_e_tipo_informado_funcionam_com_o_que_a_api_manda(tipo, origem):
    saida = predict(_lote(tipo=tipo).model_dump(mode="json"))

    assert saida["categoria_origem"] == origem


@pytest.mark.parametrize("armazenamento", ["ambiente", "refrigerado", "congelado"])
def test_todo_armazenamento_que_a_api_aceita_o_predict_aceita(armazenamento):
    saida = predict(_lote(armazenamento=armazenamento).model_dump(mode="json"))

    assert saida["prioridade"] in PRIORIDADES
