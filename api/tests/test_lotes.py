from datetime import date, timedelta

import pytest

DOADOR = {
    "nome": "Mercado Sol",
    "tipo_pessoa": "juridica",
    "documento": "12345678000199",
    "cidade": "Sao Paulo",
    "estado": "SP",
}


def lote(**extra):
    base = {
        "doador_id": 1,
        "descricao": "tomate",
        "quantidade_kg": 20,
        "validade": str(date.today() + timedelta(days=7)),
        "armazenamento": "refrigerado",
    }
    return {**base, **extra}


@pytest.fixture
def com_doador(client):
    client.post("/doadores", json=DOADOR)
    return client


def test_crud_basico(com_doador):
    c = com_doador
    r = c.post("/lotes", json=lote())
    assert r.status_code == 201
    assert c.get("/lotes/1").status_code == 200

    r = c.put("/lotes/1", json={"quantidade_kg": 30, "tipo": "hortifruti"})
    assert r.status_code == 200
    assert r.json()["quantidade_kg"] == 30
    assert r.json()["tipo"] == "hortifruti"
    assert r.json()["descricao"] == "tomate"

    assert c.delete("/lotes/1").status_code == 204
    assert c.get("/lotes/1").status_code == 404


def test_404_em_id_inexistente(com_doador):
    assert com_doador.get("/lotes/99").status_code == 404
    assert com_doador.put("/lotes/99", json={"tipo": "x"}).status_code == 404
    assert com_doador.delete("/lotes/99").status_code == 404


def test_validade_de_hoje_passa_e_de_ontem_nao(com_doador):
    hoje = str(date.today())
    ontem = str(date.today() - timedelta(days=1))
    assert com_doador.post("/lotes", json=lote(validade=hoje)).status_code == 201
    assert com_doador.post("/lotes", json=lote(validade=ontem)).status_code == 422


def test_validade_invalida_da_422(com_doador):
    assert com_doador.post("/lotes", json=lote(validade="amanha")).status_code == 422


def test_update_valida_igual_ao_create(com_doador):
    com_doador.post("/lotes", json=lote())
    ontem = str(date.today() - timedelta(days=1))
    assert com_doador.put("/lotes/1", json={"validade": ontem}).status_code == 422
    assert com_doador.put("/lotes/1", json={"quantidade_kg": 0}).status_code == 422
    assert com_doador.put("/lotes/1", json={"descricao": None}).status_code == 422
    assert com_doador.put("/lotes/1", json={"status": None}).status_code == 422
    assert com_doador.put("/lotes/1", json={"status": "sumiu"}).status_code == 422


def test_update_nao_troca_doador_nem_prioridade(com_doador):
    do_modelo = com_doador.post("/lotes", json=lote()).json()["prioridade"]
    outra = next(p for p in ("alta", "media", "baixa") if p != do_modelo)
    r = com_doador.put("/lotes/1", json={"doador_id": 5, "prioridade": outra})
    assert r.json()["doador_id"] == 1
    assert r.json()["prioridade"] == do_modelo


def test_filtros_da_listagem(com_doador):
    c = com_doador
    c.post("/doadores", json={**DOADOR, "documento": "98765432000188"})
    c.post("/lotes", json=lote())
    c.post("/lotes", json=lote(doador_id=2))
    c.put("/lotes/1", json={"status": "reservado"})

    assert len(c.get("/lotes").json()) == 2
    assert [l["id"] for l in c.get("/lotes?status=reservado").json()] == [1]
    assert [l["id"] for l in c.get("/lotes?status=disponivel").json()] == [2]
    assert [l["id"] for l in c.get("/lotes?doador_id=2").json()] == [2]
    assert c.get("/lotes?status=disponivel&doador_id=1").json() == []
    assert c.get("/lotes?status=qualquer").status_code == 422


@pytest.mark.parametrize(
    "caminho",
    [
        ["reservado"],
        ["reservado", "disponivel"],
        ["reservado", "doado"],
        ["reservado", "descartado"],
        ["descartado"],
    ],
)
def test_transicoes_permitidas(com_doador, caminho):
    com_doador.post("/lotes", json=lote())
    for status in caminho:
        r = com_doador.put("/lotes/1", json={"status": status})
        assert r.status_code == 200, (status, r.text)
        assert r.json()["status"] == status


def test_disponivel_nao_pula_direto_pra_doado(com_doador):
    com_doador.post("/lotes", json=lote())
    assert com_doador.put("/lotes/1", json={"status": "doado"}).status_code == 409
    assert com_doador.get("/lotes/1").json()["status"] == "disponivel"


@pytest.mark.parametrize("final", ["doado", "descartado"])
def test_lote_fechado_nao_muda_mais(com_doador, final):
    c = com_doador
    c.post("/lotes", json=lote())
    c.put("/lotes/1", json={"status": "reservado"})
    c.put("/lotes/1", json={"status": final})

    assert c.put("/lotes/1", json={"status": "disponivel"}).status_code == 409
    assert c.put("/lotes/1", json={"quantidade_kg": 5}).status_code == 409
    assert c.get("/lotes/1").json()["quantidade_kg"] == 20


def test_mesmo_status_em_lote_aberto_nao_da_erro(com_doador):
    com_doador.post("/lotes", json=lote())
    r = com_doador.put("/lotes/1", json={"status": "disponivel", "tipo": "padaria"})
    assert r.status_code == 200


def test_delete_so_de_lote_livre(com_doador):
    c = com_doador
    for _ in range(3):
        c.post("/lotes", json=lote())
    c.put("/lotes/1", json={"status": "reservado"})
    c.put("/lotes/2", json={"status": "descartado"})

    assert c.delete("/lotes/1").status_code == 409  # reservado
    assert c.delete("/lotes/2").status_code == 204  # descartado
    assert c.delete("/lotes/3").status_code == 204  # disponivel

    c.put("/lotes/1", json={"status": "doado"})
    assert c.delete("/lotes/1").status_code == 409  # doado


def test_lote_vencido_depois_de_gravado_ainda_e_lido(com_doador):
    # a checagem de validade e so na entrada
    com_doador.post("/lotes", json=lote())
    from api.storage import get_storage

    get_storage().atualizar("lotes", 1, {"validade": str(date.today() - timedelta(days=3))})
    assert com_doador.get("/lotes/1").status_code == 200
    assert len(com_doador.get("/lotes").json()) == 1
