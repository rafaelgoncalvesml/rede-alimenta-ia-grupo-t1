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
    "descricao": "iogurte natural",
    "quantidade_kg": 20,
    "validade": str(date.today() + timedelta(days=2)),
    "armazenamento": "ambiente",
}


@pytest.fixture
def com_doador(client):
    client.post("/doadores", json=DOADOR)
    return client


def predict_falso(monkeypatch, fn):
    monkeypatch.setattr(ia, "predict", fn)


# com o modelo de verdade (models/prioridade_v1.joblib)

def test_post_grava_prioridade_e_categoria_do_modelo(com_doador):
    r = com_doador.post("/lotes", json=LOTE)
    assert r.status_code == 201
    lote = r.json()
    assert lote["prioridade"] in ia.PRIORIDADES
    assert lote["tipo"] == "laticinios"
    # foi pro banco, nao so pra resposta
    assert com_doador.get("/lotes/1").json()["prioridade"] == lote["prioridade"]


def test_iogurte_fora_da_geladeira_vencendo_logo_nao_e_baixa(com_doador):
    # sanidade do modelo: laticinio em ambiente vencendo em 2 dias nao pode ficar no fim da fila
    lote = com_doador.post("/lotes", json=LOTE).json()
    assert lote["prioridade"] != "baixa"


def test_tipo_informado_nao_e_reclassificado(com_doador):
    r = com_doador.post("/lotes", json={**LOTE, "tipo": "padaria"})
    assert r.status_code == 201
    assert r.json()["tipo"] == "padaria"


def test_tipo_fora_das_categorias_vira_422(com_doador):
    r = com_doador.post("/lotes", json={**LOTE, "tipo": "eletronicos"})
    assert r.status_code == 422
    assert "tipo" in r.json()["detail"]
    assert com_doador.get("/lotes").json() == []


def test_descricao_em_branco_sem_tipo_vira_422(com_doador):
    # min_length=1 do pydantic deixa "   " passar; o predict nao tem como classificar
    r = com_doador.post("/lotes", json={**LOTE, "descricao": "   "})
    assert r.status_code == 422
    assert com_doador.get("/lotes").json() == []


def test_cliente_nao_forca_prioridade(com_doador):
    # quem decide e o modelo: prioridade mandada no corpo e ignorada
    a = com_doador.post("/lotes", json={**LOTE, "prioridade": "baixa"}).json()
    b = com_doador.post("/lotes", json={**LOTE, "prioridade": "alta"}).json()
    assert a["prioridade"] == b["prioridade"]


def test_put_nao_recalcula_a_prioridade(com_doador):
    antes = com_doador.post("/lotes", json=LOTE).json()["prioridade"]
    r = com_doador.put("/lotes/1", json={"armazenamento": "congelado", "quantidade_kg": 500})
    assert r.json()["prioridade"] == antes


def test_doador_inexistente_da_404_antes_de_chamar_o_modelo(client, monkeypatch):
    chamou = []
    predict_falso(monkeypatch, lambda lote: chamou.append(1))
    assert client.post("/lotes", json=LOTE).status_code == 404
    assert chamou == []


# modelo trocado por um falso, pra forcar as falhas

def test_predict_recebe_o_lote_como_a_api_recebeu(com_doador, monkeypatch):
    recebido = {}

    def falso(lote):
        recebido.update(lote)
        return {"categoria": "hortifruti", "prioridade": "alta"}

    predict_falso(monkeypatch, falso)
    r = com_doador.post("/lotes", json=LOTE)
    assert r.json()["prioridade"] == "alta"
    assert r.json()["tipo"] == "hortifruti"
    assert recebido["descricao"] == "iogurte natural"
    assert recebido["validade"] == LOTE["validade"]
    assert recebido["armazenamento"] == "ambiente"


def test_falha_do_modelo_nao_derruba_o_cadastro(com_doador, monkeypatch, caplog):
    def quebra(lote):
        raise FileNotFoundError("models/prioridade_v1.joblib")

    predict_falso(monkeypatch, quebra)
    r = com_doador.post("/lotes", json=LOTE)
    assert r.status_code == 201
    assert r.json()["prioridade"] is None
    assert r.json()["tipo"] is None
    assert "predict() falhou" in caplog.text


@pytest.mark.parametrize("saida", [{"prioridade": "urgentissima"}, {"prioridade": None}, {}, "alta", None])
def test_saida_fora_do_contrato_e_descartada(com_doador, monkeypatch, saida):
    predict_falso(monkeypatch, lambda lote: saida)
    r = com_doador.post("/lotes", json=LOTE)
    assert r.status_code == 201
    assert r.json()["prioridade"] is None


def test_valueerror_do_modelo_nao_e_engolido(com_doador, monkeypatch):
    def recusa(lote):
        raise ValueError("lote vencido: validade 2026-09-28 e anterior a 2026-09-29")

    predict_falso(monkeypatch, recusa)
    r = com_doador.post("/lotes", json=LOTE)
    assert r.status_code == 422
    assert "lote vencido" in r.json()["detail"]
