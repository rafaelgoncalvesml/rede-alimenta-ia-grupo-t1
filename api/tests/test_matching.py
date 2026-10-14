from datetime import date, timedelta

import pytest

from api import limites
from api.models import StatusLote
from api.storage import get_storage

DOADOR = {"nome": "Mercado Sol", "tipo_pessoa": "juridica", "documento": "12345678000199",
          "cidade": "Sao Paulo", "estado": "SP"}


def _ong(n, cidade="Sao Paulo", capacidade=500, necessidades=("hortifruti",), **extra):
    return {"nome": f"ONG {n}", "cnpj": f"9876543200{n:04d}", "endereco": "Rua A, 1", "cidade": cidade,
            "estado": "SP", "capacidade_kg": capacidade, "necessidades": list(necessidades), **extra}


LOTE = {"doador_id": 1, "descricao": "tomate", "quantidade_kg": 20,
        "validade": str(date.today() + timedelta(days=5)), "armazenamento": "refrigerado"}


@pytest.fixture
def base(client):
    # doador 1 sem coordenada em Sao Paulo: tem que cair no centro da cidade
    assert client.post("/doadores", json=DOADOR).status_code == 201
    return client


def cria_lote(c, tipo="hortifruti", **extra):
    r = c.post("/lotes", json={**LOTE, **extra})
    assert r.status_code == 201, r.text
    # o modelo escolhe o tipo; o teste fixa pra ficar deterministico
    get_storage().atualizar("lotes", r.json()["id"], {"tipo": tipo})
    return r.json()["id"]


def test_ranking_por_distancia_com_descartadas(base):
    base.post("/ongs", json=_ong(1, cidade="Campinas"))                      # ~84 km
    base.post("/ongs", json=_ong(2, cidade="Guarulhos"))                     # perto
    base.post("/ongs", json=_ong(3, necessidades=("padaria",)))              # categoria errada
    base.post("/ongs", json=_ong(4, capacidade=10))                          # nao aguenta 20 kg
    base.post("/ongs", json=_ong(5, cidade="Ribeirao Preto"))                # sem centro conhecido
    lote = cria_lote(base)
    r = base.post(f"/matching/{lote}")
    assert r.status_code == 200, r.text
    corpo = r.json()
    assert [x["ong_id"] for x in corpo["ranking"]] == [2, 1]
    assert [x["posicao"] for x in corpo["ranking"]] == [1, 2]
    assert corpo["ranking"][0]["distancia_km"] < corpo["ranking"][1]["distancia_km"]
    assert all(x["geo_aproximada"] for x in corpo["ranking"])    # doador sem coordenada
    assert {(d["ong_id"], d["motivo"]) for d in corpo["descartadas"]} == {
        (3, "categoria"), (4, "capacidade"), (5, "sem_coordenada")}


def test_a_primeira_do_ranking_confirma_a_doacao(base):
    base.post("/ongs", json=_ong(1, cidade="Campinas"))
    base.post("/ongs", json=_ong(2, cidade="Guarulhos"))
    lote = cria_lote(base)
    melhor = base.post(f"/matching/{lote}").json()["ranking"][0]
    r = base.post("/doacoes", json={"lote_id": lote, "ong_id": melhor["ong_id"],
                                    "distancia_km": melhor["distancia_km"], "score": melhor["score"]})
    assert r.status_code == 201, r.text


def test_sem_ong_que_sirva_devolve_ranking_vazio(base):
    base.post("/ongs", json=_ong(1, necessidades=("padaria",)))
    lote = cria_lote(base)
    r = base.post(f"/matching/{lote}")
    assert r.status_code == 200
    assert r.json()["ranking"] == [] and r.json()["descartadas"][0]["motivo"] == "categoria"


def test_lote_inexistente_404(base):
    assert base.post("/matching/999").status_code == 404


def test_lote_que_nao_esta_disponivel_409(base):
    base.post("/ongs", json=_ong(1))
    lote = cria_lote(base)
    assert base.post("/doacoes", json={"lote_id": lote, "ong_id": 1}).status_code == 201
    assert base.get(f"/lotes/{lote}").json()["status"] == StatusLote.reservado.value
    assert base.post(f"/matching/{lote}").status_code == 409


def test_doador_sem_coordenada_e_cidade_desconhecida_422(client):
    sem_centro = {**DOADOR, "cidade": "Ribeirao Preto"}
    client.post("/doadores", json=sem_centro)
    client.post("/ongs", json=_ong(1))
    lote = cria_lote(client)
    r = client.post(f"/matching/{lote}")
    assert r.status_code == 422
    assert "doador sem coordenada" in r.json()["detail"]


def test_doador_so_roda_o_matching_do_proprio_lote(base, usuario_de):
    base.post("/doadores", json={**DOADOR, "documento": "12345678000288"})
    base.post("/ongs", json=_ong(1))
    meu, alheio = cria_lote(base), cria_lote(base, doador_id=2)
    doador1 = usuario_de("doador", 1)
    assert doador1.post(f"/matching/{meu}").status_code == 200
    assert doador1.post(f"/matching/{alheio}").status_code == 403


def test_ong_nao_roda_matching(base, usuario_de):
    base.post("/ongs", json=_ong(1))
    lote = cria_lote(base)
    assert usuario_de("ong", 1).post(f"/matching/{lote}").status_code == 403


def test_limite_de_pedidos_por_minuto(base):
    base.post("/ongs", json=_ong(1))
    lote = cria_lote(base)
    codigos = [base.post(f"/matching/{lote}").status_code for _ in range(limites.MATCHING + 1)]
    assert codigos == [200] * limites.MATCHING + [429]
