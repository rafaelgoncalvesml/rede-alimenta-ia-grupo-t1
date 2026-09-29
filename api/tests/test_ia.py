from datetime import date, timedelta

import pytest

from api import ia

DOADOR = {
    "nome": "Mercado Sol",
    "tipo_pessoa": "juridica",
    "documento": "12345678000199",
    "cidade": "Sao Paulo",
    "estado": "SP",
}
LOTE = {
    "doador_id": 1,
    "descricao": "tomate",
    "quantidade_kg": 20,
    "validade": str(date.today() + timedelta(days=2)),
    "armazenamento": "refrigerado",
}


@pytest.fixture
def com_doador(client):
    client.post("/doadores", json=DOADOR)
    return client


def usa_predict(monkeypatch, fn):
    monkeypatch.setattr(ia, "_predict", fn)


def test_post_grava_a_prioridade_do_modelo(com_doador, monkeypatch):
    recebido = {}

    def falso(lote):
        recebido.update(lote)
        return {"prioridade": "alta"}

    usa_predict(monkeypatch, falso)
    r = com_doador.post("/lotes", json=LOTE)
    assert r.status_code == 201
    assert r.json()["prioridade"] == "alta"
    assert com_doador.get("/lotes/1").json()["prioridade"] == "alta"
    assert recebido["descricao"] == "tomate"
    assert recebido["validade"] == LOTE["validade"]
    assert recebido["armazenamento"] == "refrigerado"


def test_cliente_nao_forca_prioridade_com_modelo_ligado(com_doador, monkeypatch):
    usa_predict(monkeypatch, lambda lote: {"prioridade": "baixa"})
    r = com_doador.post("/lotes", json={**LOTE, "prioridade": "alta"})
    assert r.json()["prioridade"] == "baixa"


def test_sem_modelo_o_lote_entra_sem_prioridade(com_doador):
    r = com_doador.post("/lotes", json=LOTE)
    assert r.status_code == 201
    assert r.json()["prioridade"] is None


def test_modelo_que_quebra_nao_derruba_o_post(com_doador, monkeypatch):
    def quebra(lote):
        raise ValueError("entrada estranha")

    usa_predict(monkeypatch, quebra)
    r = com_doador.post("/lotes", json=LOTE)
    assert r.status_code == 201
    assert r.json()["prioridade"] is None


@pytest.mark.parametrize("saida", [{"prioridade": "urgentissima"}, {"prioridade": None}, {}, "alta", None])
def test_saida_fora_do_contrato_e_descartada(com_doador, monkeypatch, saida):
    usa_predict(monkeypatch, lambda lote: saida)
    r = com_doador.post("/lotes", json=LOTE)
    assert r.status_code == 201
    assert r.json()["prioridade"] is None


def test_doador_inexistente_nao_chama_o_modelo(client, monkeypatch):
    chamou = []
    usa_predict(monkeypatch, lambda lote: chamou.append(1) or {"prioridade": "alta"})
    assert client.post("/lotes", json=LOTE).status_code == 404
    assert chamou == []
