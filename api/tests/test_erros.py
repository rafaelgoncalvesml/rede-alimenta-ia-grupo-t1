import json
import logging
from datetime import date, timedelta

import psycopg
import pytest

from api.storage import get_storage

DOADOR = {
    "nome": "Mercado Sol",
    "tipo_pessoa": "juridica",
    "documento": "12345678000199",
    "email": "contato@mercadosol.example",
    "cidade": "Sao Paulo",
    "estado": "SP",
}
ONG = {
    "nome": "Casa Esperanca", "cnpj": "11222333000144", "endereco": "Rua A, 1",
    "cidade": "Sao Paulo", "estado": "SP", "capacidade_kg": 100,
}
LOTE = {
    "doador_id": 1, "descricao": "tomate", "quantidade_kg": 20,
    "validade": str(date.today() + timedelta(days=7)), "armazenamento": "refrigerado",
}
JSON_HDR = {"content-type": "application/json"}


def linhas_de_auditoria(caplog, tipo=None):
    saida = [json.loads(r.getMessage()) for r in caplog.records if r.name == "auditoria"]
    return [l for l in saida if tipo is None or l["tipo"] == tipo]


# 400

def test_json_malformado_da_400(client):
    r = client.post("/lotes", content=b"{nao e json", headers=JSON_HDR)
    assert r.status_code == 400
    assert r.json() == {"detail": "Corpo do pedido nao e um JSON valido"}


def test_corpo_vazio_continua_422(client):
    assert client.post("/lotes").status_code == 422


# 404 e 405

def test_rota_inexistente_da_404_em_json(client):
    r = client.get("/nada")
    assert r.status_code == 404
    assert r.headers["content-type"] == "application/json"


def test_metodo_nao_permitido_da_405(client):
    assert client.delete("/doacoes").status_code == 405


@pytest.mark.parametrize("rota", ["/doadores/99", "/ongs/99", "/lotes/99", "/doacoes/99"])
def test_recurso_que_nao_existe_da_404(client, rota):
    assert client.get(rota).status_code == 404


# 422

def test_infinito_e_nan_viram_422_e_nao_500(client):
    client.post("/doadores", json=DOADOR)
    corpo_ong = '{"nome":"a","cnpj":"11222333000144","endereco":"r","cidade":"c","estado":"SP","capacidade_kg":%s}'
    corpo_lote = '{"doador_id":1,"descricao":"tomate","quantidade_kg":%s,"validade":"%s","armazenamento":"ambiente"}'
    for valor in ("NaN", "Infinity", "1e999"):
        r = client.post("/ongs", content=(corpo_ong % valor).encode(), headers=JSON_HDR)
        assert r.status_code == 422, valor
        r = client.post("/lotes", content=(corpo_lote % (valor, LOTE["validade"])).encode(), headers=JSON_HDR)
        assert r.status_code == 422, valor
    assert client.get("/ongs").json() == []


def test_texto_gigante_no_lote_da_422(client):
    client.post("/doadores", json=DOADOR)
    assert client.post("/lotes", json={**LOTE, "descricao": "x" * 501}).status_code == 422
    assert client.post("/lotes", json={**LOTE, "tipo": "x" * 51}).status_code == 422
    assert client.post("/lotes", json={**LOTE, "descricao": "x" * 500}).status_code == 201


def test_banco_recusa_valor_vira_422(client, monkeypatch):
    def estoura(*a, **k):
        raise psycopg.errors.NumericValueOutOfRange("bigint out of range")

    monkeypatch.setattr(get_storage(), "buscar", estoura)
    r = client.get("/lotes/99999999999999999999")
    assert r.status_code == 422
    assert "bigint" not in r.text


# 503

def test_banco_fora_da_503_com_request_id(client, monkeypatch):
    def cai(*a, **k):
        raise psycopg.OperationalError("connection to server at 10.0.0.5 failed")

    monkeypatch.setattr(get_storage(), "listar", cai)
    r = client.get("/lotes")
    assert r.status_code == 503
    assert r.json()["request_id"] == r.headers["X-Request-ID"]
    assert "10.0.0.5" not in r.text


# 500

def test_erro_inesperado_da_500_generico_e_stack_so_no_log(client, monkeypatch, caplog):
    def explode(*a, **k):
        raise RuntimeError("senha do banco = hunter2")

    monkeypatch.setattr(get_storage(), "listar", explode)
    with caplog.at_level(logging.INFO):
        r = client.get("/lotes")
    assert r.status_code == 500
    assert r.headers["content-type"] == "application/json"
    corpo = r.json()
    assert corpo["detail"] == "Erro interno do servidor"
    assert corpo["request_id"] == r.headers["X-Request-ID"]
    assert "hunter2" not in r.text and "Traceback" not in r.text

    erro = [x for x in caplog.records if x.name == "api.erros"]
    assert erro and erro[0].exc_info and "hunter2" in str(erro[0].exc_info[1])
    [req] = linhas_de_auditoria(caplog, "requisicao")
    assert req["status"] == 500 and req["request_id"] == corpo["request_id"]


# auditoria

def test_toda_resposta_tem_request_id_diferente(client):
    a = client.get("/health").headers["X-Request-ID"]
    b = client.get("/health").headers["X-Request-ID"]
    assert a and b and a != b


def test_auditoria_registra_o_pedido_sem_dado_pessoal(client, caplog):
    with caplog.at_level(logging.INFO):
        r = client.post("/doadores", json=DOADOR)
    assert r.status_code == 201
    [req] = linhas_de_auditoria(caplog, "requisicao")
    assert (req["metodo"], req["path"], req["status"], req["mutacao"]) == ("POST", "/doadores", 201, True)
    assert req["request_id"] == r.headers["X-Request-ID"]
    todo_o_log = " ".join(x.getMessage() for x in caplog.records)
    for sensivel in (DOADOR["documento"], DOADOR["email"], "Mercado Sol"):
        assert sensivel not in todo_o_log


def test_auditoria_registra_o_evento_de_negocio(client, caplog):
    client.post("/doadores", json=DOADOR)
    client.post("/ongs", json=ONG)
    client.post("/lotes", json=LOTE)
    caplog.clear()
    with caplog.at_level(logging.INFO):
        r = client.post("/doacoes", json={"lote_id": 1, "ong_id": 1})
    [ev] = linhas_de_auditoria(caplog, "evento")
    assert ev["acao"] == "doacao.confirmada"
    assert (ev["lote_id"], ev["ong_id"], ev["doacao_id"]) == (1, 1, 1)
    assert ev["request_id"] == r.headers["X-Request-ID"]


def test_auditoria_registra_reserva_que_caiu(client, caplog):
    client.post("/doadores", json=DOADOR)
    client.post("/ongs", json=ONG)
    client.post("/lotes", json=LOTE)
    client.post("/doacoes", json={"lote_id": 1, "ong_id": 1})
    caplog.clear()
    with caplog.at_level(logging.INFO):
        client.put("/lotes/1", json={"status": "disponivel"})
    acoes = [e["acao"] for e in linhas_de_auditoria(caplog, "evento")]
    assert acoes == ["doacao.cancelada", "lote.atualizado"]
    lote = linhas_de_auditoria(caplog, "evento")[1]
    assert (lote["status_de"], lote["status_para"]) == ("reservado", "disponivel")


def test_erro_de_cliente_sai_como_warning(client, caplog):
    with caplog.at_level(logging.INFO):
        client.get("/lotes/99")
    [rec] = [r for r in caplog.records if r.name == "auditoria"]
    assert rec.levelno == logging.WARNING
    assert json.loads(rec.getMessage())["status"] == 404


def test_path_forjado_nao_cria_linha_falsa_no_log(client, caplog):
    with caplog.at_level(logging.INFO):
        client.get("/x%0A%7B%22tipo%22:%22evento%22%7D")
    [rec] = [r for r in caplog.records if r.name == "auditoria"]
    assert "\n" not in rec.getMessage()
    assert json.loads(rec.getMessage())["tipo"] == "requisicao"
