import base64
import json
from datetime import datetime, timedelta, timezone

import jwt
import pytest

from api import seguranca
from api.tests.conftest import SENHA

ADMIN = {"email": "admin@teste.local", "senha": "senha-do-admin-1"}
DOADOR = {"nome": "Mercado Sol", "tipo_pessoa": "juridica", "documento": "12345678000199",
          "cidade": "Sao Paulo", "estado": "SP"}


def test_login_devolve_token_com_papel(anonimo):
    r = anonimo.post("/auth/login", json=ADMIN)
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["token_type"] == "bearer" and corpo["expires_in"] == 30 * 60
    claims = jwt.decode(corpo["access_token"], seguranca.segredo(), algorithms=["HS256"])
    assert claims["papel"] == "admin" and "doador_id" not in claims


def test_senha_nunca_volta_em_resposta(client):
    client.post("/doadores", json=DOADOR)
    corpo = {"email": "d@x.com", "senha": SENHA, "papel": "doador", "doador_id": 1}
    r = client.post("/usuarios", json=corpo)
    assert r.status_code == 201
    assert "senha" not in json.dumps(r.json()) and "hash" not in json.dumps(r.json())
    assert all("senha" not in u and "senha_hash" not in u for u in client.get("/usuarios").json())


def test_senha_guardada_como_argon2(client):
    from api.storage import get_storage

    hashes = [u["senha_hash"] for u in get_storage().listar("usuarios")]
    assert hashes and all(h.startswith("$argon2") for h in hashes)
    assert "senha-do-admin-1" not in "".join(hashes)


@pytest.mark.parametrize("corpo", [
    {"email": "admin@teste.local", "senha": "errada-errada"},
    {"email": "ninguem@teste.local", "senha": "senha-do-admin-1"},
])
def test_login_errado_da_401_com_a_mesma_mensagem(anonimo, corpo):
    r = anonimo.post("/auth/login", json=corpo)
    assert r.status_code == 401
    assert r.json() == {"detail": "E-mail ou senha incorretos"}
    assert r.headers["www-authenticate"] == "Bearer"


def test_login_ignora_caixa_e_espacos_no_email(anonimo):
    r = anonimo.post("/auth/login", json={**ADMIN, "email": "  ADMIN@Teste.Local "})
    assert r.status_code == 200


def test_cinco_erros_bloqueiam_ate_a_senha_certa(anonimo):
    ruim = {**ADMIN, "senha": "errada-errada"}
    assert [anonimo.post("/auth/login", json=ruim).status_code for _ in range(5)] == [401] * 5
    r = anonimo.post("/auth/login", json=ADMIN)  # senha certa, mas ja bloqueado
    assert r.status_code == 429
    assert int(r.headers["retry-after"]) > 0


def test_bloqueio_e_por_email(anonimo):
    for _ in range(5):
        anonimo.post("/auth/login", json={**ADMIN, "senha": "errada-errada"})
    outro = anonimo.post("/auth/login", json={"email": "outro@x.com", "senha": "qualquer-coisa"})
    assert outro.status_code == 401  # outro e-mail nao herda o bloqueio


def test_acerto_zera_o_contador(anonimo):
    for _ in range(4):
        anonimo.post("/auth/login", json={**ADMIN, "senha": "errada-errada"})
    assert anonimo.post("/auth/login", json=ADMIN).status_code == 200
    for _ in range(4):
        assert anonimo.post("/auth/login", json={**ADMIN, "senha": "errada-errada"}).status_code == 401


@pytest.mark.parametrize("cabecalho", [
    None, "", "Bearer", "Bearer lixo", "Basic YWRtaW46YWRtaW4=", "Bearer a.b.c",
])
def test_sem_token_valido_da_401(anonimo, cabecalho):
    h = {"Authorization": cabecalho} if cabecalho is not None else {}
    r = anonimo.get("/lotes", headers=h)
    assert r.status_code == 401
    assert r.headers["www-authenticate"] == "Bearer"


def _token(**claims):
    base = {"sub": "1", "papel": "admin",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5)}
    return jwt.encode({**base, **claims}, seguranca.segredo(), algorithm="HS256")


def test_token_expirado_da_401(anonimo):
    t = _token(exp=datetime.now(timezone.utc) - timedelta(seconds=1))
    assert anonimo.get("/lotes", headers={"Authorization": f"Bearer {t}"}).status_code == 401


def test_token_assinado_com_outra_chave_da_401(anonimo):
    t = jwt.encode({"sub": "1", "papel": "admin",
                    "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
                   "outra-chave-" + "z" * 40, algorithm="HS256")
    assert anonimo.get("/lotes", headers={"Authorization": f"Bearer {t}"}).status_code == 401


def test_token_sem_exp_da_401(anonimo):
    t = jwt.encode({"sub": "1", "papel": "admin"}, seguranca.segredo(), algorithm="HS256")
    assert anonimo.get("/lotes", headers={"Authorization": f"Bearer {t}"}).status_code == 401


def test_token_com_papel_inventado_da_401(anonimo):
    t = _token(papel="superusuario")
    assert anonimo.get("/lotes", headers={"Authorization": f"Bearer {t}"}).status_code == 401


def test_token_alg_none_da_401(anonimo):
    def b64(d):
        return base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()
    exp = int((datetime.now(timezone.utc) + timedelta(minutes=5)).timestamp())
    t = f"{b64({'alg': 'none', 'typ': 'JWT'})}.{b64({'sub': '1', 'papel': 'admin', 'exp': exp})}."
    assert anonimo.get("/lotes", headers={"Authorization": f"Bearer {t}"}).status_code == 401


def test_token_com_payload_trocado_da_401(anonimo, usuario_de, client):
    client.post("/doadores", json=DOADOR)
    doador = usuario_de("doador", 1)
    cab, corpo, assinatura = doador.headers["Authorization"].split(" ")[1].split(".")
    pad = "=" * (-len(corpo) % 4)
    claims = json.loads(base64.urlsafe_b64decode(corpo + pad))
    claims["papel"] = "admin"  # tenta virar admin sem a chave
    falso = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=").decode()
    r = anonimo.get("/usuarios", headers={"Authorization": f"Bearer {cab}.{falso}.{assinatura}"})
    assert r.status_code == 401


def test_eu_devolve_papel_e_entidade(client, usuario_de):
    client.post("/doadores", json=DOADOR)
    assert client.get("/auth/eu").json()["papel"] == "admin"
    eu = usuario_de("doador", 1).get("/auth/eu").json()
    assert eu["papel"] == "doador" and eu["doador_id"] == 1 and eu["ong_id"] is None


# ---- criacao de usuario ----

def test_usuario_com_email_repetido_da_409(client):
    r = client.post("/usuarios", json={"email": "ADMIN@teste.local", "senha": SENHA,
                                       "papel": "admin"})
    assert r.status_code == 409


@pytest.mark.parametrize("corpo", [
    {"papel": "doador"},                            # doador sem doador_id
    {"papel": "doador", "doador_id": 1, "ong_id": 1},
    {"papel": "ong", "doador_id": 1},               # ong com doador_id
    {"papel": "admin", "doador_id": 1},             # admin nao aponta pra entidade
    {"papel": "dono"},                              # papel que nao existe
])
def test_usuario_com_papel_e_entidade_incoerentes_da_422(client, corpo):
    client.post("/doadores", json=DOADOR)
    r = client.post("/usuarios", json={"email": "u@x.com", "senha": SENHA, **corpo})
    assert r.status_code == 422


def test_usuario_aponta_pra_entidade_que_nao_existe_da_404(client):
    r = client.post("/usuarios", json={"email": "u@x.com", "senha": SENHA, "papel": "ong",
                                       "ong_id": 99})
    assert r.status_code == 404


@pytest.mark.parametrize("senha", ["curta", "x" * 129])
def test_senha_fora_do_tamanho_da_422(client, senha):
    r = client.post("/usuarios", json={"email": "u@x.com", "senha": senha, "papel": "admin"})
    assert r.status_code == 422


def test_entidade_com_usuario_nao_pode_ser_apagada(client, usuario_de):
    client.post("/doadores", json=DOADOR)
    usuario_de("doador", 1)
    assert client.delete("/doadores/1").status_code == 409


# ---- configuracao ----

def test_api_nao_sobe_sem_segredo(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "curto")
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        seguranca.valida_config()
    monkeypatch.delenv("JWT_SECRET")
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        seguranca.valida_config()


def test_admin_nao_e_criado_duas_vezes():
    from api.storage import get_storage

    seguranca.garantir_admin()
    seguranca.garantir_admin()
    assert len(get_storage().listar("usuarios")) == 1


def test_senha_de_admin_curta_barra_a_subida(monkeypatch):
    monkeypatch.setenv("ADMIN_PASSWORD", "curta")
    with pytest.raises(RuntimeError, match="ADMIN_PASSWORD"):
        seguranca.garantir_admin()


def test_log_de_auditoria_leva_o_usuario_e_nunca_a_senha(client, caplog):
    caplog.set_level("INFO", logger="auditoria")
    caplog.clear()
    client.post("/doadores", json=DOADOR)
    linhas = [json.loads(r.getMessage()) for r in caplog.records if r.name == "auditoria"]
    pedido = next(x for x in linhas if x.get("path") == "/doadores" and x["metodo"] == "POST")
    assert pedido["usuario_id"] == 1
    assert "senha-do-admin-1" not in " ".join(r.getMessage() for r in caplog.records)
