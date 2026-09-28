import pytest

ONG = {
    "nome": "ONG Mesa Cheia",
    "cnpj": "44555666000102",
    "endereco": "Rua Exemplo, 100",
    "cidade": "Sao Paulo",
    "estado": "SP",
    "capacidade_kg": 500,
    "necessidades": ["hortifruti", "padaria"],
}


def test_crud_basico(client):
    r = client.post("/ongs", json=ONG)
    assert r.status_code == 201
    id_ = r.json()["id"]

    assert client.get(f"/ongs/{id_}").status_code == 200
    assert len(client.get("/ongs").json()) == 1

    r = client.put(f"/ongs/{id_}", json={"capacidade_kg": 800})
    assert r.status_code == 200
    assert r.json()["capacidade_kg"] == 800
    assert r.json()["nome"] == "ONG Mesa Cheia"

    assert client.delete(f"/ongs/{id_}").status_code == 204
    assert client.get(f"/ongs/{id_}").status_code == 404


def test_404_em_id_inexistente(client):
    assert client.get("/ongs/99").status_code == 404
    assert client.put("/ongs/99", json={"cidade": "X"}).status_code == 404
    assert client.delete("/ongs/99").status_code == 404


def test_cnpj_duplicado_da_409_mesmo_com_mascara(client):
    client.post("/ongs", json=ONG)
    assert client.post("/ongs", json=ONG).status_code == 409
    mascarado = {**ONG, "cnpj": "44.555.666/0001-02"}
    assert client.post("/ongs", json=mascarado).status_code == 409


def test_cnpj_com_mascara_e_guardado_sem(client):
    r = client.post("/ongs", json={**ONG, "cnpj": "44.555.666/0001-02"})
    assert r.json()["cnpj"] == "44555666000102"


@pytest.mark.parametrize("cnpj", ["123", "abc", "4455566600010"])
def test_cnpj_invalido_da_422(client, cnpj):
    assert client.post("/ongs", json={**ONG, "cnpj": cnpj}).status_code == 422


@pytest.mark.parametrize(
    "campo, valor",
    [
        ("nome", ""),
        ("nome", "  "),
        ("endereco", ""),
        ("cidade", ""),
        ("estado", "Sao Paulo"),
        ("capacidade_kg", -1),
        ("latitude", -91),
        ("longitude", 181),
    ],
)
def test_campos_invalidos_da_422(client, campo, valor):
    assert client.post("/ongs", json={**ONG, campo: valor}).status_code == 422


def test_capacidade_zero_e_aceita(client):
    # o schema.sql tem check >= 0
    assert client.post("/ongs", json={**ONG, "capacidade_kg": 0}).status_code == 201


def test_necessidades_sao_normalizadas(client):
    r = client.post("/ongs", json={**ONG, "necessidades": [" Padaria ", "padaria", "", "HORTIFRUTI"]})
    assert r.json()["necessidades"] == ["padaria", "hortifruti"]


def test_update_valida_e_nao_troca_cnpj(client):
    client.post("/ongs", json=ONG)
    assert client.put("/ongs/1", json={"capacidade_kg": -5}).status_code == 422
    assert client.put("/ongs/1", json={"nome": None}).status_code == 422
    assert client.put("/ongs/1", json={"necessidades": None}).status_code == 422

    r = client.put("/ongs/1", json={"cnpj": "99999999000199", "necessidades": [" Laticinios "]})
    assert r.json()["cnpj"] == "44555666000102"
    assert r.json()["necessidades"] == ["laticinios"]


def test_update_pode_limpar_coordenadas(client):
    client.post("/ongs", json={**ONG, "latitude": -23.5, "longitude": -46.6})
    r = client.put("/ongs/1", json={"latitude": None, "longitude": None})
    assert r.status_code == 200
    assert r.json()["latitude"] is None
