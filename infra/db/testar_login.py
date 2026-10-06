"""Testa auth e permissoes contra o Supabase de verdade (dia 15/16).

    python -m infra.db.testar_login      (da raiz do repo; precisa de SUPABASE_DB_URL no .env)

Usa segredo e senhas descartaveis geradas na hora, cria doadores, ONG, usuarios e um lote
marcados TESTE-AUTH / @exemplo.invalid, roda ~26 verificacoes e apaga tudo no final (confere a
contagem de linhas antes e depois). Exige que a tabela usuarios ja exista:
python infra/db/aplicar_schema.py.
"""
import logging
import os
import secrets
import sys

os.environ["STORAGE"] = "postgres"
os.environ["JWT_SECRET"] = secrets.token_urlsafe(48)
SENHA_ADMIN = secrets.token_urlsafe(14)
SENHA_USER = secrets.token_urlsafe(14)
os.environ["ADMIN_EMAIL"] = "teste-login-admin@exemplo.invalid"
os.environ["ADMIN_PASSWORD"] = SENHA_ADMIN
from datetime import date, timedelta  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

from api import seguranca  # noqa: E402
from api.main import app  # noqa: E402
from api.storage import get_storage  # noqa: E402

logging.getLogger("auditoria").setLevel(logging.CRITICAL)

db = get_storage()
antes = {t: len(db.listar(t)) for t in ("doadores", "ongs", "lotes", "doacoes", "usuarios")}
print("antes :", antes)
ok = True
def checa(rotulo, got, esperado):
    global ok
    bom = got == esperado
    ok &= bom
    print(f"{'OK  ' if bom else 'FALHA'} {rotulo}: {got}" + ("" if bom else f" (esperado {esperado})"))

criados = {"lotes": [], "usuarios": [], "doadores": [], "ongs": []}
try:
    seguranca.garantir_admin()
    admin_row = db.listar("usuarios", email=os.environ["ADMIN_EMAIL"])
    checa("admin criado no Postgres", len(admin_row), 1)
    criados["usuarios"].append(admin_row[0]["id"])
    checa("senha guardada como argon2", admin_row[0]["senha_hash"].startswith("$argon2"), True)

    anon = TestClient(app)
    checa("GET /lotes sem token", anon.get("/lotes").status_code, 401)
    r = anon.post("/auth/login", json={"email": os.environ["ADMIN_EMAIL"], "senha": SENHA_ADMIN})
    checa("login admin", r.status_code, 200)
    adm = TestClient(app)
    adm.headers["Authorization"] = "Bearer " + r.json()["access_token"]
    checa("GET /auth/eu (admin)", adm.get("/auth/eu").json()["papel"], "admin")
    checa("GET /lotes admin", adm.get("/lotes").status_code, 200)

    d1 = adm.post("/doadores", json={"nome": "TESTE-AUTH doador 1", "tipo_pessoa": "juridica",
            "documento": "99999999000191", "cidade": "Sao Paulo", "estado": "SP"})
    d2 = adm.post("/doadores", json={"nome": "TESTE-AUTH doador 2", "tipo_pessoa": "juridica",
            "documento": "99999999000272", "cidade": "Sao Paulo", "estado": "SP"})
    o1 = adm.post("/ongs", json={"nome": "TESTE-AUTH ong", "cnpj": "99999999000353", "endereco": "Rua X, 1",
            "cidade": "Sao Paulo", "estado": "SP", "capacidade_kg": 100, "necessidades": ["hortifruti"]})
    checa("cria doadores e ong", (d1.status_code, d2.status_code, o1.status_code), (201, 201, 201))
    for r_, t in ((d1, "doadores"), (d2, "doadores"), (o1, "ongs")):
        criados[t].append(r_.json()["id"])
    id1, id2, ido = d1.json()["id"], d2.json()["id"], o1.json()["id"]

    u1 = adm.post("/usuarios", json={"email": "teste-doador1@exemplo.invalid", "senha": SENHA_USER, "papel": "doador", "doador_id": id1})
    u2 = adm.post("/usuarios", json={"email": "teste-doador2@exemplo.invalid", "senha": SENHA_USER, "papel": "doador", "doador_id": id2})
    u3 = adm.post("/usuarios", json={"email": "teste-ong@exemplo.invalid", "senha": SENHA_USER, "papel": "ong", "ong_id": ido})
    checa("cria 3 usuarios (FK + check do schema)", (u1.status_code, u2.status_code, u3.status_code), (201, 201, 201))
    for r_ in (u1, u2, u3):
        criados["usuarios"].append(r_.json()["id"])
    checa("e-mail repetido", adm.post("/usuarios", json={"email": "TESTE-doador1@exemplo.invalid", "senha": SENHA_USER, "papel": "admin"}).status_code, 409)
    checa("apagar doador com usuario", adm.delete(f"/doadores/{id1}").status_code, 409)

    def entra(email):
        c = TestClient(app)
        r = c.post("/auth/login", json={"email": email, "senha": SENHA_USER})
        c.headers["Authorization"] = "Bearer " + r.json()["access_token"]
        return c, r.status_code
    c1, s1 = entra("teste-doador1@exemplo.invalid")
    c2, _ = entra("teste-doador2@exemplo.invalid")
    co, _ = entra("teste-ong@exemplo.invalid")
    checa("login doador 1", s1, 200)
    checa("doador 1 le o proprio cadastro", c1.get(f"/doadores/{id1}").status_code, 200)
    checa("doador 1 le o doador 2", c1.get(f"/doadores/{id2}").status_code, 403)
    checa("doador 1 lista doadores", c1.get("/doadores").status_code, 403)
    lote = {"doador_id": id1, "descricao": "tomate", "quantidade_kg": 5, "validade": str(date.today() + timedelta(days=5)), "armazenamento": "refrigerado"}
    r = c1.post("/lotes", json=lote)
    checa("doador 1 cria lote proprio", r.status_code, 201)
    lid = r.json()["id"]
    criados["lotes"].append(lid)
    checa("doador 2 cria lote em nome do 1", c2.post("/lotes", json=lote).status_code, 403)
    checa("doador 2 le lote do 1", c2.get(f"/lotes/{lid}").status_code, 403)
    checa("doador 2 lista lotes (so os dele)", c2.get("/lotes").json(), [])
    checa("ong le o lote antes da doacao", co.get(f"/lotes/{lid}").status_code, 403)
    r = c1.post("/doacoes", json={"lote_id": lid, "ong_id": ido})
    checa("doador 1 confirma doacao", r.status_code, 201)
    did = r.json()["id"]
    checa("ong passa a ver o lote", co.get(f"/lotes/{lid}").status_code, 200)
    checa("ong le a doacao", co.get(f"/doacoes/{did}").status_code, 200)
    checa("doador 2 le a doacao", c2.get(f"/doacoes/{did}").status_code, 403)
    checa("ong cria lote", co.post("/lotes", json=lote).status_code, 403)

    for _ in range(5):
        anon.post("/auth/login", json={"email": "teste-ong@exemplo.invalid", "senha": "errada-errada"})
    checa("6a tentativa apos 5 erros", anon.post("/auth/login", json={"email": "teste-ong@exemplo.invalid", "senha": SENHA_USER}).status_code, 429)

    # o check do schema recusa papel/entidade incoerente mesmo sem a validacao da API
    import psycopg
    try:
        db.criar("usuarios", {"email": "incoerente@exemplo.invalid", "senha_hash": "x", "papel": "admin", "doador_id": id1, "ong_id": None})
        checa("check do schema (admin com doador_id)", "aceitou", "recusou")
        criados["usuarios"].append(db.listar("usuarios", email="incoerente@exemplo.invalid")[0]["id"])
    except psycopg.errors.CheckViolation:
        checa("check do schema (admin com doador_id)", "recusou", "recusou")
finally:
    # limpeza, na ordem das chaves estrangeiras
    for d in db.listar("doacoes"):
        if d["lote_id"] in criados["lotes"]:
            db._rodar("delete from doacoes where id = %s returning id", [d["id"]])
    for t in ("lotes", "usuarios", "doadores", "ongs"):
        for i in criados[t]:
            db.apagar(t, i)
    depois = {t: len(db.listar(t)) for t in antes}
    print("depois:", depois)
    checa("banco voltou ao que era", depois, antes)
sys.exit(0 if ok else 1)
