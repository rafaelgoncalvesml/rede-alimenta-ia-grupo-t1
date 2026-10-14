from datetime import date, datetime, timedelta, timezone

import pytest

from api.storage import get_storage

DOADOR = {
    "nome": "Mercado Sol",
    "tipo_pessoa": "juridica",
    "documento": "12345678000199",
    "cidade": "Sao Paulo",
    "estado": "SP",
}
ONG = {
    "nome": "ONG Mesa Cheia",
    "cnpj": "44555666000102",
    "endereco": "Rua Exemplo, 100",
    "cidade": "Sao Paulo",
    "estado": "SP",
    "capacidade_kg": 500,
    "necessidades": ["laticinios"],
}
LOTE = {
    "doador_id": 1,
    "descricao": "iogurte natural",
    "quantidade_kg": 20,
    "validade": str(date.today() + timedelta(days=3)),
    "armazenamento": "refrigerado",
}


@pytest.fixture
def base(client):
    # doador 1, ONG 1, lote 1 disponivel
    client.post("/doadores", json=DOADOR)
    client.post("/ongs", json=ONG)
    client.post("/lotes", json=LOTE)
    return client


def confirma(c, **extra):
    return c.post("/doacoes", json={"lote_id": 1, "ong_id": 1, **extra})


def test_confirma_grava_timestamps_e_reserva_o_lote(base):
    r = confirma(base, distancia_km=3.2, score=0.81)
    assert r.status_code == 201
    d = r.json()
    assert d["status"] == "confirmada"
    assert (d["lote_id"], d["ong_id"]) == (1, 1)
    # o servidor ignora 3.2/0.81 e calcula: doador e ONG sem coordenada caem no centro de SP
    assert (d["distancia_km"], d["score"]) == (0.0, 0.0)
    assert d["confirmado_em"] and d["criado_em"]
    assert d["tempo_match_s"] >= 0
    assert base.get("/lotes/1").json()["status"] == "reservado"


def test_distancia_e_score_nao_precisam_vir_do_cliente(base):
    d = confirma(base).json()
    assert (d["distancia_km"], d["score"]) == (0.0, 0.0)


def test_tempo_de_match_conta_desde_o_cadastro_do_lote(base):
    # lote cadastrado ha 2h: o tempo de match nao pode ser ~0
    duas_horas_atras = datetime.now(timezone.utc) - timedelta(hours=2)
    get_storage().atualizar("lotes", 1, {"criado_em": duas_horas_atras})
    d = confirma(base).json()
    assert 7200 <= d["tempo_match_s"] < 7260


def test_cliente_nao_controla_status_nem_timestamps(base):
    r = confirma(base, status="cancelada", confirmado_em="2020-01-01T00:00:00Z", tempo_match_s=1)
    d = r.json()
    assert d["status"] == "confirmada"
    assert d["confirmado_em"].startswith(str(date.today().year))
    assert d["tempo_match_s"] != 1


def test_lote_inexistente_da_404(base):
    r = base.post("/doacoes", json={"lote_id": 99, "ong_id": 1})
    assert r.status_code == 404


def test_ong_inexistente_da_404_e_nao_reserva_o_lote(base):
    r = base.post("/doacoes", json={"lote_id": 1, "ong_id": 99})
    assert r.status_code == 404
    assert base.get("/lotes/1").json()["status"] == "disponivel"


def test_mesmo_lote_nao_e_confirmado_duas_vezes(base):
    base.post("/ongs", json={**ONG, "cnpj": "11222333000181"})
    assert confirma(base).status_code == 201
    r = base.post("/doacoes", json={"lote_id": 1, "ong_id": 2})
    assert r.status_code == 409
    assert len(base.get("/doacoes").json()) == 1


def test_lote_descartado_nao_pode_ser_doado(base):
    base.put("/lotes/1", json={"status": "descartado"})
    assert confirma(base).status_code == 409
    assert base.get("/doacoes").json() == []


def test_lote_ja_entregue_nao_pode_ser_doado_de_novo(base):
    base.post("/ongs", json={**ONG, "cnpj": "11222333000181"})
    confirma(base)
    base.put("/lotes/1", json={"status": "doado"})
    assert base.post("/doacoes", json={"lote_id": 1, "ong_id": 2}).status_code == 409


@pytest.mark.parametrize("corpo", [
    {"lote_id": 1},
    {"ong_id": 1},
    {"lote_id": "um", "ong_id": 1},
    {"lote_id": 1, "ong_id": 1, "distancia_km": -1},
    {"lote_id": 1, "ong_id": 1, "score": -0.1},
    {"lote_id": 1, "ong_id": 1, "score": "alto"},
])
def test_corpo_invalido_da_422(base, corpo):
    assert base.post("/doacoes", json=corpo).status_code == 422
    assert base.get("/lotes/1").json()["status"] == "disponivel"


def test_reserva_desfeita_cancela_a_doacao_e_libera_o_lote(base):
    base.post("/ongs", json={**ONG, "cnpj": "11222333000181"})
    confirma(base)
    assert base.put("/lotes/1", json={"status": "disponivel"}).status_code == 200
    assert base.get("/doacoes/1").json()["status"] == "cancelada"
    # o lote pode ser doado pra outra ONG
    r = base.post("/doacoes", json={"lote_id": 1, "ong_id": 2})
    assert r.status_code == 201
    status = {d["id"]: d["status"] for d in base.get("/doacoes").json()}
    assert status == {1: "cancelada", 2: "confirmada"}


def test_lote_descartado_depois_de_reservado_cancela_a_doacao(base):
    confirma(base)
    base.put("/lotes/1", json={"status": "descartado"})
    assert base.get("/doacoes/1").json()["status"] == "cancelada"


def test_lote_entregue_mantem_a_doacao_confirmada(base):
    confirma(base)
    assert base.put("/lotes/1", json={"status": "doado"}).status_code == 200
    assert base.get("/doacoes/1").json()["status"] == "confirmada"


def test_listagem_e_filtros(base):
    base.post("/ongs", json={**ONG, "cnpj": "11222333000181"})
    base.post("/lotes", json=LOTE)
    confirma(base)
    base.post("/doacoes", json={"lote_id": 2, "ong_id": 2})
    base.put("/lotes/2", json={"status": "disponivel"})
    assert len(base.get("/doacoes").json()) == 2
    assert [d["id"] for d in base.get("/doacoes?ong_id=2").json()] == [2]
    assert [d["id"] for d in base.get("/doacoes?lote_id=1").json()] == [1]
    assert [d["id"] for d in base.get("/doacoes?status=cancelada").json()] == [2]
    assert base.get("/doacoes?status=sumiu").status_code == 422


def test_buscar_doacao_inexistente_da_404(client):
    assert client.get("/doacoes/1").status_code == 404


def test_doacao_nao_se_edita_nem_se_apaga(base):
    confirma(base)
    assert base.put("/doacoes/1", json={"status": "cancelada"}).status_code == 405
    assert base.delete("/doacoes/1").status_code == 405


def test_ong_com_doacao_nao_pode_ser_apagada(base):
    confirma(base)
    assert base.delete("/ongs/1").status_code == 409
    assert base.get("/ongs/1").status_code == 200


def test_lote_com_doacao_cancelada_continua_sem_poder_ser_apagado(base):
    confirma(base)
    base.put("/lotes/1", json={"status": "disponivel"})
    assert base.delete("/lotes/1").status_code == 409


def test_fluxo_do_cadastro_ate_a_doacao(client):
    # POST /lotes (com o modelo de verdade) -> prioridade gravada -> POST /doacoes
    client.post("/doadores", json=DOADOR)
    client.post("/ongs", json=ONG)
    lote = client.post("/lotes", json=LOTE).json()
    assert lote["prioridade"] in ("alta", "media", "baixa")
    assert client.post("/doacoes", json={"lote_id": lote["id"], "ong_id": 1}).status_code == 201
    depois = client.get(f"/lotes/{lote['id']}").json()
    assert depois["status"] == "reservado"
    assert depois["prioridade"] == lote["prioridade"]


# ---- a ONG precisa aguentar o peso e aceitar a categoria (issue 9) ----

def test_ong_com_capacidade_menor_que_o_lote_da_409(client):
    client.post("/doadores", json=DOADOR)
    client.post("/ongs", json={**ONG, "capacidade_kg": 10})
    client.post("/lotes", json=LOTE)          # 20 kg
    r = confirma(client)
    assert r.status_code == 409
    assert "capacidade" in r.json()["detail"]
    assert client.get("/lotes/1").json()["status"] == "disponivel"
    assert client.get("/doacoes").json() == []


def test_lote_do_tamanho_exato_da_capacidade_passa(client):
    client.post("/doadores", json=DOADOR)
    client.post("/ongs", json={**ONG, "capacidade_kg": 20})
    client.post("/lotes", json=LOTE)
    assert confirma(client).status_code == 201


def test_ong_sem_a_categoria_do_lote_da_409(client):
    client.post("/doadores", json=DOADOR)
    client.post("/ongs", json={**ONG, "necessidades": ["padaria"]})
    client.post("/lotes", json=LOTE)          # iogurte = laticinios
    r = confirma(client)
    assert r.status_code == 409
    assert "necessidade" in r.json()["detail"]
    assert client.get("/lotes/1").json()["status"] == "disponivel"


def test_ong_sem_nenhuma_necessidade_nao_recebe(client):
    # o caso da rodada 3 do dia 13: capacidade 0 e necessidades vazias voltavam 201
    client.post("/doadores", json=DOADOR)
    client.post("/ongs", json={**ONG, "capacidade_kg": 0, "necessidades": []})
    client.post("/lotes", json={**LOTE, "quantidade_kg": 300})
    assert confirma(client).status_code == 409


def test_lote_sem_categoria_so_confere_a_capacidade(client):
    # modelo fora do ar no cadastro grava tipo nulo; isso nao pode travar a doacao
    client.post("/doadores", json=DOADOR)
    client.post("/ongs", json={**ONG, "necessidades": []})
    client.post("/lotes", json=LOTE)
    get_storage().atualizar("lotes", 1, {"tipo": None})
    assert confirma(client).status_code == 201
