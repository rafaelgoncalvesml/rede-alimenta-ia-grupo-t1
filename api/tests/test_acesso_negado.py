"""Quem pode o que (dia 16): papel errado recebe 403, sem token recebe 401.

O mundo de cada teste: dois doadores (A e B), tres ONGs (X, Y e Z), um lote de A ja doado pra X,
um lote de B, um lote de A ainda disponivel e um doador e uma ONG sem nada ligado (C e Z,
pra DELETE dar 204). O ator e quem faz o pedido; "dono" e A, "recebe" e X.
"""
from datetime import date, timedelta

import pytest

from api.main import app

ATORES = ["anonimo", "dono", "outro_doador", "recebe", "outra_ong", "admin"]
VALIDADE = str(date.today() + timedelta(days=10))


def _doador(n):
    return {"nome": f"Doador {n}", "tipo_pessoa": "juridica", "documento": f"1234567800{n:04d}",
            "cidade": "Sao Paulo", "estado": "SP"}


def _ong(n):
    return {"nome": f"ONG {n}", "cnpj": f"9876543200{n:04d}", "endereco": "Rua A, 1",
            "cidade": "Sao Paulo", "estado": "SP", "capacidade_kg": 500,
            "necessidades": ["hortifruti"]}


LOTE = {"descricao": "tomate", "quantidade_kg": 20, "validade": VALIDADE,
        "armazenamento": "refrigerado"}


@pytest.fixture
def mundo(client, usuario_de, anonimo):
    for n in (1, 2, 3):                               # doadores A, B e C
        assert client.post("/doadores", json=_doador(n)).status_code == 201
    for n in (1, 2, 3):                               # ONGs X, Y e Z
        assert client.post("/ongs", json=_ong(n)).status_code == 201
    assert client.post("/lotes", json={**LOTE, "doador_id": 1}).status_code == 201   # lote 1 (A)
    assert client.post("/lotes", json={**LOTE, "doador_id": 2}).status_code == 201   # lote 2 (B)
    assert client.post("/lotes", json={**LOTE, "doador_id": 1}).status_code == 201   # lote 3 (A)
    assert client.post("/doacoes", json={"lote_id": 1, "ong_id": 1}).status_code == 201
    return {
        "anonimo": anonimo, "admin": client,
        "dono": usuario_de("doador", 1), "outro_doador": usuario_de("doador", 2),
        "recebe": usuario_de("ong", 1), "outra_ong": usuario_de("ong", 2),
    }


# (metodo, caminho, corpo, esperado por ator na ordem de ATORES)
# 401 = sem token, 403 = papel ou dono errado. Quando o admin tira 409 e porque passou da
# autorizacao e bateu numa regra de negocio (comentado na linha).
MATRIZ = [
    ("POST", "/usuarios", {"email": "novo@x.com", "senha": "senha-longa-123", "papel": "admin"},
     [401, 403, 403, 403, 403, 201]),
    ("GET", "/usuarios", None, [401, 403, 403, 403, 403, 200]),

    ("POST", "/doadores", _doador(9), [401, 403, 403, 403, 403, 201]),
    ("GET", "/doadores", None, [401, 403, 403, 403, 403, 200]),
    ("GET", "/doadores/1", None, [401, 200, 403, 403, 403, 200]),
    ("PUT", "/doadores/1", {"nome": "Novo nome"}, [401, 200, 403, 403, 403, 200]),
    ("DELETE", "/doadores/3", None, [401, 403, 403, 403, 403, 204]),

    ("POST", "/ongs", _ong(9), [401, 403, 403, 403, 403, 201]),
    ("GET", "/ongs", None, [401, 200, 200, 200, 200, 200]),
    ("GET", "/ongs/1", None, [401, 200, 200, 200, 200, 200]),
    ("PUT", "/ongs/1", {"nome": "Novo nome"}, [401, 403, 403, 200, 403, 200]),
    ("DELETE", "/ongs/3", None, [401, 403, 403, 403, 403, 204]),

    ("POST", "/lotes", {**LOTE, "doador_id": 1}, [401, 201, 403, 403, 403, 201]),
    ("GET", "/lotes", None, [401, 200, 200, 200, 200, 200]),
    ("GET", "/lotes/1", None, [401, 200, 403, 200, 403, 200]),
    ("PUT", "/lotes/1", {"descricao": "outra"}, [401, 200, 403, 403, 403, 200]),
    ("DELETE", "/lotes/3", None, [401, 204, 403, 403, 403, 204]),

    ("POST", "/doacoes", {"lote_id": 3, "ong_id": 1}, [401, 201, 403, 403, 403, 201]),
    ("GET", "/doacoes", None, [401, 200, 200, 200, 200, 200]),
    ("GET", "/doacoes/1", None, [401, 200, 403, 200, 403, 200]),

    ("GET", "/kpis/impacto", None, [401, 200, 200, 200, 200, 200]),
    ("GET", "/kpis/ia", None, [401, 200, 200, 200, 200, 200]),
]


@pytest.mark.parametrize("ator", ATORES)
@pytest.mark.parametrize(
    "metodo,caminho,corpo,esperados", MATRIZ, ids=[f"{m} {c}" for m, c, _, _ in MATRIZ])
def test_matriz_de_acesso(mundo, ator, metodo, caminho, corpo, esperados):
    r = mundo[ator].request(metodo, caminho, json=corpo)
    assert r.status_code == esperados[ATORES.index(ator)], r.text


def test_matriz_cobre_todas_as_rotas_da_api():
    """Rota nova sem linha na matriz quebra aqui: nao da pra esquecer de pensar na permissao."""
    publicas = {("GET", "/health"), ("GET", "/health/db"), ("POST", "/auth/login")}
    na_api = {(m, r.path) for r in app.routes if hasattr(r, "methods")
              for m in r.methods if r.path.startswith(("/doadores", "/ongs", "/lotes", "/doacoes",
                                                       "/usuarios", "/auth", "/health", "/kpis"))}
    na_matriz = {(m, c.split("/")[1]) for m, c, _, _ in MATRIZ}
    for metodo, caminho in na_api - publicas - {("GET", "/auth/eu")}:
        assert (metodo, caminho.split("/")[1]) in na_matriz, f"{metodo} {caminho} sem teste de acesso"


def test_toda_rota_protegida_responde_401_sem_token(anonimo):
    # TEMPORARIO: /diagnostico/ip sai junto com a rota (chore/diagnostico-xff-temporario)
    publicas = {("GET", "/health"), ("GET", "/health/db"), ("POST", "/auth/login"),
                ("GET", "/diagnostico/ip")}
    for r in app.routes:
        if not hasattr(r, "methods") or r.path in ("/docs", "/openapi.json", "/docs/oauth2-redirect",
                                                   "/redoc"):
            continue
        for metodo in r.methods - {"HEAD", "OPTIONS"}:
            if (metodo, r.path) in publicas:
                continue
            caminho = r.path.replace("{doador_id}", "1").replace("{ong_id}", "1") \
                .replace("{lote_id}", "1").replace("{doacao_id}", "1")
            assert anonimo.request(metodo, caminho).status_code == 401, f"{metodo} {r.path}"


def test_rotas_publicas_continuam_publicas(anonimo):
    assert anonimo.get("/health").status_code == 200
    assert anonimo.get("/docs").status_code == 200
    assert anonimo.get("/openapi.json").status_code == 200


# ---- o que cada papel enxerga nas listas ----

def test_doador_lista_so_os_proprios_lotes(mundo):
    assert [l["id"] for l in mundo["dono"].get("/lotes").json()] == [1, 3]
    assert [l["id"] for l in mundo["outro_doador"].get("/lotes").json()] == [2]
    assert [l["id"] for l in mundo["admin"].get("/lotes").json()] == [1, 2, 3]


def test_doador_nao_ve_lote_de_outro_nem_com_filtro(mundo):
    assert mundo["outro_doador"].get("/lotes", params={"doador_id": 1}).status_code == 403
    r = mundo["outro_doador"].get("/lotes", params={"doador_id": 2})
    assert [l["id"] for l in r.json()] == [2]


def test_ong_so_enxerga_lote_que_recebeu(mundo):
    assert [l["id"] for l in mundo["recebe"].get("/lotes").json()] == [1]
    assert mundo["outra_ong"].get("/lotes").json() == []


def test_doacao_cancelada_tira_o_lote_da_ong(mundo):
    mundo["admin"].put("/lotes/1", json={"status": "disponivel"})  # a reserva cai
    assert mundo["recebe"].get("/lotes").json() == []
    assert mundo["recebe"].get("/lotes/1").status_code == 403


def test_doacoes_cada_um_ve_as_suas(mundo):
    assert [d["id"] for d in mundo["recebe"].get("/doacoes").json()] == [1]
    assert [d["id"] for d in mundo["dono"].get("/doacoes").json()] == [1]
    assert mundo["outro_doador"].get("/doacoes").json() == []
    assert mundo["outra_ong"].get("/doacoes").json() == []


def test_ong_nao_pede_doacoes_de_outra(mundo):
    assert mundo["outra_ong"].get("/doacoes", params={"ong_id": 1}).status_code == 403
    assert mundo["outro_doador"].get("/doacoes", params={"lote_id": 1}).status_code == 403


# ---- tentativas de driblar a regra ----

def test_doador_nao_cria_lote_em_nome_de_outro(mundo):
    r = mundo["outro_doador"].post("/lotes", json={**LOTE, "doador_id": 1})
    assert r.status_code == 403
    assert len(mundo["admin"].get("/lotes").json()) == 3  # nada foi gravado


def test_doador_nao_doa_lote_de_outro(mundo):
    r = mundo["outro_doador"].post("/doacoes", json={"lote_id": 3, "ong_id": 2})
    assert r.status_code == 403
    assert mundo["admin"].get("/lotes/3").json()["status"] == "disponivel"


def test_ong_nao_confirma_doacao_nem_cria_lote(mundo):
    assert mundo["recebe"].post("/doacoes", json={"lote_id": 3, "ong_id": 1}).status_code == 403
    assert mundo["recebe"].post("/lotes", json={**LOTE, "doador_id": 1}).status_code == 403


def test_negado_nao_altera_o_dado(mundo):
    mundo["outro_doador"].put("/lotes/1", json={"descricao": "invadido"})
    mundo["outro_doador"].delete("/lotes/3")
    mundo["outra_ong"].put("/ongs/1", json={"nome": "invadida"})
    mundo["outro_doador"].put("/doadores/1", json={"nome": "invadido"})
    admin = mundo["admin"]
    assert admin.get("/lotes/1").json()["descricao"] == "tomate"
    assert admin.get("/lotes/3").status_code == 200
    assert admin.get("/ongs/1").json()["nome"] == "ONG 1"
    assert admin.get("/doadores/1").json()["nome"] == "Doador 1"


def test_doador_nao_vira_admin_pelo_corpo_do_pedido(mundo):
    # campos que o cliente nao deveria controlar ficam de fora do contrato
    r = mundo["outro_doador"].put("/doadores/2", json={"nome": "Ok", "papel": "admin"})
    assert r.status_code == 200
    assert mundo["outro_doador"].get("/usuarios").status_code == 403
    assert mundo["outro_doador"].get("/auth/eu").json()["papel"] == "doador"


def test_negado_e_registrado_no_log(mundo, caplog):
    caplog.set_level("INFO", logger="auditoria")
    caplog.clear()
    mundo["outro_doador"].get("/lotes/1")
    mensagens = [r.getMessage() for r in caplog.records]
    assert any('"acao": "acesso.negado"' in m and '"papel": "doador"' in m for m in mensagens)
