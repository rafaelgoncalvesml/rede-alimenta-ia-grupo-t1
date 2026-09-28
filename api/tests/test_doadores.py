from datetime import date, timedelta

import pytest

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
    "validade": str(date.today() + timedelta(days=7)),
    "armazenamento": "refrigerado",
}


def test_crud_basico(client):
    r = client.post("/doadores", json=DOADOR)
    assert r.status_code == 201
    id_ = r.json()["id"]

    assert client.get(f"/doadores/{id_}").status_code == 200
    assert len(client.get("/doadores").json()) == 1

    r = client.put(f"/doadores/{id_}", json={"cidade": "Campinas"})
    assert r.status_code == 200
    assert r.json()["cidade"] == "Campinas"
    assert r.json()["nome"] == "Mercado Sol"

    assert client.delete(f"/doadores/{id_}").status_code == 204
    assert client.get(f"/doadores/{id_}").status_code == 404


def test_404_em_id_inexistente(client):
    assert client.get("/doadores/99").status_code == 404
    assert client.put("/doadores/99", json={"cidade": "X"}).status_code == 404
    assert client.delete("/doadores/99").status_code == 404


def test_documento_duplicado_da_409(client):
    client.post("/doadores", json=DOADOR)
    assert client.post("/doadores", json=DOADOR).status_code == 409


def test_documento_com_mascara_e_guardado_sem(client):
    r = client.post("/doadores", json={**DOADOR, "documento": "12.345.678/0001-99"})
    assert r.status_code == 201
    assert r.json()["documento"] == "12345678000199"
    # a mascara tambem nao escapa da checagem de duplicado
    assert client.post("/doadores", json=DOADOR).status_code == 409


@pytest.mark.parametrize(
    "tipo, documento",
    [
        ("juridica", "123"),
        ("juridica", "12345678901"),  # tamanho de CPF pra pessoa juridica
        ("fisica", "12345678000199"),  # tamanho de CNPJ pra pessoa fisica
        ("fisica", "abc"),
    ],
)
def test_documento_invalido_da_422(client, tipo, documento):
    r = client.post("/doadores", json={**DOADOR, "tipo_pessoa": tipo, "documento": documento})
    assert r.status_code == 422


def test_cpf_valido_pra_pessoa_fisica(client):
    r = client.post(
        "/doadores", json={**DOADOR, "tipo_pessoa": "fisica", "documento": "123.456.789-09"}
    )
    assert r.status_code == 201


@pytest.mark.parametrize(
    "campo, valor",
    [
        ("nome", ""),
        ("nome", "   "),
        ("cidade", ""),
        ("estado", "Sao Paulo"),
        ("estado", "S"),
        ("email", "sem-arroba"),
        ("latitude", 91),
        ("longitude", -181),
        ("tipo_pessoa", "ong"),
    ],
)
def test_campos_invalidos_da_422(client, campo, valor):
    assert client.post("/doadores", json={**DOADOR, campo: valor}).status_code == 422


def test_campo_obrigatorio_faltando_da_422(client):
    sem_cidade = {k: v for k, v in DOADOR.items() if k != "cidade"}
    assert client.post("/doadores", json=sem_cidade).status_code == 422


def test_uf_vira_maiuscula(client):
    r = client.post("/doadores", json={**DOADOR, "estado": "sp"})
    assert r.json()["estado"] == "SP"


def test_update_valida_igual_ao_create(client):
    client.post("/doadores", json=DOADOR)
    assert client.put("/doadores/1", json={"estado": "Sao Paulo"}).status_code == 422
    assert client.put("/doadores/1", json={"nome": ""}).status_code == 422
    assert client.put("/doadores/1", json={"nome": None}).status_code == 422


def test_update_pode_limpar_telefone(client):
    client.post("/doadores", json={**DOADOR, "telefone": "11999999999"})
    r = client.put("/doadores/1", json={"telefone": None})
    assert r.status_code == 200
    assert r.json()["telefone"] is None


def test_update_nao_troca_documento(client):
    client.post("/doadores", json=DOADOR)
    r = client.put("/doadores/1", json={"documento": "99999999000199"})
    assert r.json()["documento"] == "12345678000199"


def test_nao_apaga_doador_com_lote(client):
    client.post("/doadores", json=DOADOR)
    client.post("/lotes", json=LOTE)
    assert client.delete("/doadores/1").status_code == 409
    assert client.get("/doadores/1").status_code == 200

    client.delete("/lotes/1")
    assert client.delete("/doadores/1").status_code == 204
