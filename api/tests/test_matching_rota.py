"""POST /matching/{lote_id} expoe o ml/matching.py, e o POST /doacoes passa a calcular distancia e
score no servidor (o que o cliente manda nesses dois campos e ignorado)."""
from datetime import timedelta

from ml.relogio import hoje

VALIDADE = str(hoje() + timedelta(days=3))
DOADOR = {"nome": "Mercado", "tipo_pessoa": "juridica", "documento": "12345678000100",
          "cidade": "Sao Paulo", "estado": "SP", "latitude": -23.5505, "longitude": -46.6333}


def _ong(n, lat, lon, necessidades=("hortifruti",), capacidade=500, **extra):
    return {"nome": f"ONG {n}", "cnpj": f"9876543200{n:04d}", "endereco": "Rua A, 1", "cidade": "Sao Paulo",
            "estado": "SP", "latitude": lat, "longitude": lon, "capacidade_kg": capacidade,
            "necessidades": list(necessidades), **extra}


def _mundo(client, doador=DOADOR):
    assert client.post("/doadores", json=doador).status_code == 201
    for corpo in (_ong(1, -22.9099, -47.0626),               # Campinas, ~84 km
                  _ong(2, -23.5614, -46.6559),               # ~2,5 km
                  _ong(3, -23.56, -46.65, necessidades=("padaria",))):  # perto, mas nao aceita
        assert client.post("/ongs", json=corpo).status_code == 201
    lote = {"doador_id": 1, "descricao": "caixa de tomate", "quantidade_kg": 20, "validade": VALIDADE,
            "armazenamento": "refrigerado", "tipo": "hortifruti"}
    assert client.post("/lotes", json=lote).status_code == 201


def test_ranking_vem_da_mais_perto_pra_mais_longe_com_nome_e_motivo_do_descarte(client):
    _mundo(client)

    r = client.post("/matching/1")

    assert r.status_code == 200
    corpo = r.json()
    assert [(x["ong_id"], x["nome"]) for x in corpo["ranking"]] == [(2, "ONG 2"), (1, "ONG 1")]
    assert corpo["ranking"][0]["distancia_km"] < corpo["ranking"][1]["distancia_km"]
    assert corpo["descartadas"] == [{"ong_id": 3, "motivo": "categoria"}]


def test_lote_que_nao_existe_404_e_lote_que_nao_esta_disponivel_409(client):
    _mundo(client)
    assert client.post("/doacoes", json={"lote_id": 1, "ong_id": 2}).status_code == 201

    assert client.post("/matching/99").status_code == 404
    assert client.post("/matching/1").status_code == 409


def test_doador_sem_coordenada_em_cidade_sem_centro_conhecido_volta_422(client):
    _mundo(client, doador={**DOADOR, "cidade": "Santos", "latitude": None, "longitude": None})

    r = client.post("/matching/1")

    assert r.status_code == 422 and "doador" in r.json()["detail"]


def test_a_doacao_grava_a_distancia_e_o_score_calculados_no_servidor_e_ignora_os_do_cliente(client):
    _mundo(client)
    esperado = client.post("/matching/1").json()["ranking"][0]

    doacao = client.post("/doacoes", json={"lote_id": 1, "ong_id": 2, "distancia_km": 999, "score": 0}).json()

    assert (doacao["distancia_km"], doacao["score"]) == (esperado["distancia_km"], esperado["score"])


def test_doacao_pra_ong_sem_coordenada_conhecida_entra_sem_distancia(client):
    _mundo(client)
    assert client.post("/ongs", json=_ong(4, None, None, cidade="Santos")).status_code == 201

    doacao = client.post("/doacoes", json={"lote_id": 1, "ong_id": 4, "distancia_km": 3, "score": 0.03})

    assert doacao.status_code == 201
    assert (doacao.json()["distancia_km"], doacao.json()["score"]) == (None, None)
