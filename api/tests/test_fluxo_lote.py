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
    "validade": "2026-10-05",
    "armazenamento": "refrigerado",
}


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_cadastra_lote_e_lista(client):
    assert client.post("/doadores", json=DOADOR).status_code == 201
    r = client.post("/lotes", json=LOTE)
    assert r.status_code == 201
    lote = r.json()
    assert lote["status"] == "disponivel"
    assert lote["prioridade"] is None  # so o modelo preenche

    listados = client.get("/lotes").json()
    assert [l["id"] for l in listados] == [lote["id"]]


def test_lote_sem_doador_da_404(client):
    assert client.post("/lotes", json=LOTE).status_code == 404


def test_lote_nao_aceita_prioridade_do_cliente(client):
    client.post("/doadores", json=DOADOR)
    r = client.post("/lotes", json={**LOTE, "prioridade": "alta", "status": "doado"})
    assert r.json()["prioridade"] is None
    assert r.json()["status"] == "disponivel"


def test_lote_rejeita_quantidade_invalida(client):
    client.post("/doadores", json=DOADOR)
    for qtd in (0, -5):
        r = client.post("/lotes", json={**LOTE, "quantidade_kg": qtd})
        assert r.status_code == 422


def test_lote_rejeita_descricao_vazia(client):
    client.post("/doadores", json=DOADOR)
    assert client.post("/lotes", json={**LOTE, "descricao": ""}).status_code == 422


def test_lote_rejeita_armazenamento_fora_do_dominio(client):
    client.post("/doadores", json=DOADOR)
    r = client.post("/lotes", json={**LOTE, "armazenamento": "quente"})
    assert r.status_code == 422
