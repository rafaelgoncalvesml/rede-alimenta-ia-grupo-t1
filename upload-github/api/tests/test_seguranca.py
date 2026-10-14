import base64
import json
import os
from datetime import date, datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient

from api.main import app

DOADOR = {"nome": "Mercado Sol", "tipo_pessoa": "juridica", "documento": "12345678000199",
          "cidade": "Sao Paulo", "estado": "SP"}


def _lote(**extra):
    return {"doador_id": 1, "descricao": "tomate", "quantidade_kg": 5,
            "armazenamento": "refrigerado",
            "validade": str(date.today() + timedelta(days=10)), **extra}


def _claims(**mudancas):
    agora = datetime.now(timezone.utc)
    base = {"sub": "1", "papel": "admin", "iat": agora, "exp": agora + timedelta(minutes=10)}
    return {**base, **mudancas}


def _com_token(token: str) -> TestClient:
    c = TestClient(app)
    c.headers["Authorization"] = f"Bearer {token}"
    return c


# ---------- token forjado (S1, E1) ----------

def test_controle_token_assinado_com_o_segredo_certo_passa():
    # sem este controle, os testes abaixo poderiam dar 401 por erro do proprio teste
    token = jwt.encode(_claims(), os.environ["JWT_SECRET"], algorithm="HS256")
    assert _com_token(token).get("/usuarios").status_code == 200


@pytest.mark.parametrize("como", ["alg_none", "segredo_errado", "expirado", "sem_exp",
                                  "sem_papel", "papel_inexistente"])
def test_token_forjado_ou_invalido_vira_401(como):
    segredo = os.environ["JWT_SECRET"]
    claims = _claims()
    if como == "alg_none":
        token = jwt.encode(claims, None, algorithm="none")
    elif como == "segredo_errado":
        token = jwt.encode(claims, "outro-segredo-" + "x" * 32, algorithm="HS256")
    elif como == "expirado":
        claims["exp"] = datetime.now(timezone.utc) - timedelta(minutes=1)
        token = jwt.encode(claims, segredo, algorithm="HS256")
    elif como == "sem_exp":
        del claims["exp"]
        token = jwt.encode(claims, segredo, algorithm="HS256")
    elif como == "sem_papel":
        del claims["papel"]
        token = jwt.encode(claims, segredo, algorithm="HS256")
    else:
        claims["papel"] = "superadmin"
        token = jwt.encode(claims, segredo, algorithm="HS256")
    assert _com_token(token).get("/usuarios").status_code == 401


@pytest.mark.parametrize("token", ["abc", "a.b.c", "e30.e30.e30"])
def test_lixo_no_lugar_do_token_vira_401(token):
    assert _com_token(token).get("/usuarios").status_code == 401


def test_esquema_basic_no_lugar_de_bearer_vira_401():
    c = TestClient(app)
    c.headers["Authorization"] = "Basic YWRtaW46c2VuaGE="
    assert c.get("/usuarios").status_code == 401


def test_trocar_o_papel_no_token_sem_reassinar_da_401(client, usuario_de):
    assert client.post("/doadores", json=DOADOR).status_code == 201
    doador = usuario_de("doador", 1)
    assert doador.get("/usuarios").status_code == 403  # controle: o doador de verdade e barrado
    cabecalho, carga, assinatura = doador.headers["Authorization"].split()[1].split(".")
    dados = json.loads(base64.urlsafe_b64decode(carga + "=" * (-len(carga) % 4)))
    dados["papel"] = "admin"
    nova = base64.urlsafe_b64encode(json.dumps(dados).encode()).rstrip(b"=").decode()
    assert _com_token(f"{cabecalho}.{nova}.{assinatura}").get("/usuarios").status_code == 401


# ---------- injecao em campo, filtro, login e id (T1, T2) ----------

@pytest.mark.parametrize("veneno", ["'; DROP TABLE lotes; --", "' OR '1'='1",
                                    "1; SELECT pg_sleep(10)", "<script>alert(1)</script>"])
def test_texto_de_ataque_e_guardado_como_texto(client, veneno):
    assert client.post("/doadores", json=DOADOR).status_code == 201
    r = client.post("/lotes", json=_lote(descricao=veneno))
    assert r.status_code == 201
    assert client.get(f"/lotes/{r.json()['id']}").json()["descricao"] == veneno
    assert len(client.get("/lotes").json()) == 1  # a "tabela" continua la


@pytest.mark.parametrize("filtro", [("status", "' OR 1=1 --"), ("status", "disponivel;DROP TABLE lotes"),
                                    ("doador_id", "1 OR 1=1"), ("doador_id", "abc")])
def test_filtro_com_injecao_vira_422(client, filtro):
    nome, valor = filtro
    assert client.get("/lotes", params={nome: valor}).status_code == 422


@pytest.mark.parametrize("caminho", ["/lotes/abc", "/doadores/1;DROP", "/ongs/' OR 1=1", "/doacoes/1.5"])
def test_id_que_nao_e_inteiro_vira_422(client, caminho):
    assert client.get(caminho).status_code == 422


def test_id_negativo_ou_gigante_nao_vira_200_nem_500(client):
    assert client.get("/lotes/-1").status_code == 404
    # em memoria o id gigante e 404; no Postgres o handler de DataError devolve 422
    assert client.get("/lotes/99999999999999999999").status_code in (404, 422)


@pytest.mark.parametrize("email", ["' OR '1'='1", "admin@teste.local' --"])
def test_login_com_injecao_vira_401(anonimo, email):
    r = anonimo.post("/auth/login", json={"email": email, "senha": "' OR '1'='1"})
    assert r.status_code == 401
    assert r.json() == {"detail": "E-mail ou senha incorretos"}


def test_login_com_senha_ou_email_gigante_vira_422_antes_de_gastar_argon2(anonimo):
    assert anonimo.post("/auth/login", json={"email": "admin@teste.local",
                                             "senha": "A" * 129}).status_code == 422
    assert anonimo.post("/auth/login", json={"email": "a" * 201 + "@x.com",
                                             "senha": "qualquer-coisa"}).status_code == 422


# ---------- o que nao pode parar no log (I2, LGPD) ----------

def test_log_nao_leva_token_documento_nem_senha(client, anonimo, caplog):
    caplog.set_level("INFO", logger="auditoria")
    caplog.clear()
    assert client.post("/doadores", json=DOADOR).status_code == 201
    r = anonimo.post("/auth/login", json={"email": "admin@teste.local", "senha": "senha-do-admin-1"})
    token = r.json()["access_token"]
    assert anonimo.get("/auth/eu", headers={"Authorization": f"Bearer {token}"}).status_code == 200
    texto = " ".join(x.getMessage() for x in caplog.records)
    assert texto  # o log existe
    assert token not in texto
    assert DOADOR["documento"] not in texto
    assert "senha-do-admin-1" not in texto