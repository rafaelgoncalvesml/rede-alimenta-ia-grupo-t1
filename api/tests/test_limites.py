from datetime import date, timedelta

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from api import limites

LOTE = {"descricao": "tomate", "quantidade_kg": 5, "armazenamento": "refrigerado",
        "validade": str(date.today() + timedelta(days=10))}
DOADOR = {"nome": "Mercado Sol", "tipo_pessoa": "juridica", "documento": "12345678000199",
          "cidade": "Sao Paulo", "estado": "SP"}


# ---- limite por rota ----

def test_post_lotes_estoura_no_limite_e_avisa_quando_voltar(client):
    client.post("/doadores", json=DOADOR)
    for _ in range(limites.LOTES):
        assert client.post("/lotes", json={**LOTE, "doador_id": 1}).status_code == 201
    r = client.post("/lotes", json={**LOTE, "doador_id": 1})
    assert r.status_code == 429
    assert 1 <= int(r.headers["retry-after"]) <= limites.JANELA_S
    assert r.json() == {"detail": "Muitos pedidos. Tente de novo em instantes."}
    assert len(client.get("/lotes").json()) == limites.LOTES  # o pedido barrado nao gravou nada


def test_estourar_uma_rota_nao_trava_as_outras(client):
    client.post("/doadores", json=DOADOR)
    for _ in range(limites.LOTES + 1):
        client.post("/lotes", json={**LOTE, "doador_id": 1})
    assert client.get("/lotes").status_code == 200
    assert client.get("/doadores").status_code == 200


def test_cada_usuario_tem_o_seu_contador(client, usuario_de):
    client.post("/doadores", json=DOADOR)
    client.post("/doadores", json={**DOADOR, "documento": "12345678000270"})
    a, b = usuario_de("doador", 1), usuario_de("doador", 2)
    for _ in range(limites.LOTES):
        assert a.post("/lotes", json={**LOTE, "doador_id": 1}).status_code == 201
    assert a.post("/lotes", json={**LOTE, "doador_id": 1}).status_code == 429
    assert b.post("/lotes", json={**LOTE, "doador_id": 2}).status_code == 201


def test_libera_depois_da_janela(client, monkeypatch):
    agora = [1000.0]
    monkeypatch.setattr(limites, "_agora", lambda: agora[0])
    client.post("/doadores", json=DOADOR)
    for _ in range(limites.LOTES):
        client.post("/lotes", json={**LOTE, "doador_id": 1})
    assert client.post("/lotes", json={**LOTE, "doador_id": 1}).status_code == 429
    agora[0] += limites.JANELA_S - 1
    assert client.post("/lotes", json={**LOTE, "doador_id": 1}).status_code == 429
    agora[0] += 2
    assert client.post("/lotes", json={**LOTE, "doador_id": 1}).status_code == 201


def test_criar_usuario_tem_limite_mais_apertado(client):
    codigos = [client.post("/usuarios", json={"email": f"u{i}@x.com", "senha": "senha-longa-123",
                                              "papel": "admin"}).status_code
               for i in range(limites.USUARIOS + 1)]
    assert codigos == [201] * limites.USUARIOS + [429]


def test_limite_vale_pra_nao_autenticado_por_ip(anonimo):
    # sem token valido a chave e o IP; os 401 contam, entao inundar de pedido ruim tambem trava
    codigos = {anonimo.post("/lotes", json={}, headers={"Authorization": "Bearer lixo"}).status_code
               for _ in range(limites.LOTES + 5)}
    assert codigos == {401, 429}


def test_limite_estourado_vai_pro_log(client, caplog):
    caplog.set_level("INFO", logger="auditoria")
    client.post("/doadores", json=DOADOR)
    for _ in range(limites.LOTES + 1):
        client.post("/lotes", json={**LOTE, "doador_id": 1})
    assert any('"acao": "limite.estourado"' in r.getMessage() and '"rota": "lotes"' in r.getMessage()
               for r in caplog.records)


# ---- limite geral ----

def test_limite_geral_trava_quem_passa_de_120_por_minuto(client):
    codigos = [client.get("/lotes").status_code for _ in range(limites.GERAL + 1)]
    assert codigos[:limites.GERAL] == [200] * limites.GERAL and codigos[-1] == 429


def test_health_e_login_ficam_fora_do_limite_geral(anonimo):
    assert {anonimo.get("/health").status_code for _ in range(limites.GERAL + 20)} == {200}
    corpo = {"email": "admin@teste.local", "senha": "senha-do-admin-1"}
    assert {anonimo.post("/auth/login", json=corpo).status_code
            for _ in range(limites.GERAL + 5)} == {200}


# ---- pronto pro matching ----

def test_limita_pronto_pra_rota_do_matching():
    """POST /matching ainda nao existe. Quando existir basta
    `dependencies=[Depends(limites.limita("matching", limites.MATCHING))]` na rota."""
    app = FastAPI()

    @app.post("/matching/{lote_id}", dependencies=[Depends(limites.limita("matching", limites.MATCHING))])
    def matching(lote_id: int):
        return {"lote_id": lote_id}

    c = TestClient(app)
    codigos = [c.post("/matching/1").status_code for _ in range(limites.MATCHING + 1)]
    assert codigos == [200] * limites.MATCHING + [429]


# ---- tamanho do corpo ----

def test_corpo_acima_do_limite_da_413_sem_ler(client, monkeypatch):
    monkeypatch.setenv("MAX_BODY_BYTES", "1000")
    r = client.post("/doadores", content=b"x" * 1001, headers={"Content-Type": "application/json"})
    assert r.status_code == 413
    assert r.json() == {"detail": "Corpo do pedido grande demais", "limite_bytes": 1000}
    assert "x-request-id" in r.headers  # passou pela auditoria, entao ficou no log


def test_corpo_no_limite_exato_passa(client, monkeypatch):
    monkeypatch.setenv("MAX_BODY_BYTES", "1000")
    r = client.post("/doadores", content=b"{" + b" " * 998 + b"}",
                    headers={"Content-Type": "application/json"})
    assert r.status_code == 422  # chegou na validacao (falta campo), nao foi barrado


def test_corpo_em_pedacos_sem_content_length_tambem_da_413(client, monkeypatch):
    monkeypatch.setenv("MAX_BODY_BYTES", "1000")

    def pedacos():
        for _ in range(20):
            yield b" " * 100

    r = client.post("/doadores", content=pedacos(), headers={"Content-Type": "application/json"})
    assert r.status_code == 413


def test_texto_enorme_no_lote_vira_413_e_o_gigante_moderado_continua_422(client):
    client.post("/doadores", json=DOADOR)
    assert client.post("/lotes", json={**LOTE, "doador_id": 1, "descricao": "x" * 70_000}
                       ).status_code == 413          # passa dos 64 KiB padrao
    assert client.post("/lotes", json={**LOTE, "doador_id": 1, "descricao": "x" * 5_000}
                       ).status_code == 422          # cabe no corpo, o Pydantic recusa
    assert client.get("/lotes").json() == []


def test_413_vem_antes_de_olhar_o_token(anonimo):
    # barato de recusar: nao gasta decode de token nem consulta ao banco
    r = anonimo.post("/lotes", content=b"x" * 70_000, headers={"Content-Type": "application/json"})
    assert r.status_code == 413


def test_limite_padrao_e_64_kib(monkeypatch):
    monkeypatch.delenv("MAX_BODY_BYTES", raising=False)
    assert limites.max_corpo() == 65536


def test_pedido_sem_corpo_nao_e_afetado(client, monkeypatch):
    monkeypatch.setenv("MAX_BODY_BYTES", "10")
    assert client.get("/lotes").status_code == 200


# ---- IP do cliente atras do Render (CF-Connecting-IP) ----

def _inunda(c, ip, n):
    cab = {"Authorization": "Bearer lixo", "CF-Connecting-IP": ip}
    return [c.post("/lotes", json={}, headers=cab).status_code for _ in range(n)]


def test_com_a_variavel_ligada_cada_ip_tem_o_seu_balde(anonimo, monkeypatch):
    monkeypatch.setenv("CONFIAR_CF_CONNECTING_IP", "1")
    assert 429 in _inunda(anonimo, "203.0.113.7", limites.LOTES + 5)
    assert set(_inunda(anonimo, "198.51.100.9", 3)) == {401}  # outro cliente nao paga pelo primeiro


def test_com_a_variavel_desligada_o_cabecalho_e_ignorado(anonimo, monkeypatch):
    # fora do Render qualquer cliente poderia forjar o cabecalho pra escapar do limite
    monkeypatch.delenv("CONFIAR_CF_CONNECTING_IP", raising=False)
    codigos = _inunda(anonimo, "203.0.113.7", limites.LOTES + 5)
    codigos += _inunda(anonimo, "198.51.100.9", 3)
    assert set(codigos[-3:]) == {429}  # mesmo balde, o do client.host


def test_cabecalho_que_nao_e_ip_cai_no_client_host(anonimo, monkeypatch):
    monkeypatch.setenv("CONFIAR_CF_CONNECTING_IP", "1")
    cab = {"Authorization": "Bearer lixo", "CF-Connecting-IP": "isto-nao-e-ip"}
    codigos = {anonimo.post("/lotes", json={}, headers=cab).status_code for _ in range(limites.LOTES + 5)}
    assert codigos == {401, 429}


def test_ip_do_cabecalho_vai_pro_log_de_auditoria(anonimo, monkeypatch, caplog):
    import json
    import logging
    monkeypatch.setenv("CONFIAR_CF_CONNECTING_IP", "1")
    with caplog.at_level(logging.INFO, logger="auditoria"):
        anonimo.get("/health", headers={"CF-Connecting-IP": "203.0.113.7"})
    ips = [json.loads(r.getMessage()).get("ip") for r in caplog.records if r.name == "auditoria"]
    assert "203.0.113.7" in ips
