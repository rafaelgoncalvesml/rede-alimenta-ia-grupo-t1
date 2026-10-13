"""Fluxo ponta a ponta contra a API publica, com o banco de producao (dia 23).

    API_URL=https://rede-alimenta-ia-api.onrender.com SUPABASE_DB_URL=... \
        python -m infra.db.testar_producao

Cria direto no banco um admin descartavel (@exemplo.invalid, senha aleatoria), faz o fluxo por
HTTP (login, doador, ONG, lote, doacao, entrega, KPIs e as recusas) e no fim apaga tudo que
criou, conferindo a contagem de linhas antes e depois. O admin real da producao nao e tocado e
a senha dele nunca passa por aqui. Doacao nao tem DELETE na API, por isso a limpeza e pelo banco.

Mede o tempo do primeiro POST /lotes (carrega o modelo) e dos seguintes.
"""
import os
import secrets
import sys
import time
from datetime import date, timedelta

import httpx

URL = os.getenv("API_URL", "").rstrip("/")
if not URL.startswith("https://"):
    sys.exit("defina API_URL com a URL publica (https://...)")
os.environ["STORAGE"] = "postgres"
os.environ.setdefault("JWT_SECRET", "x" * 40)  # so pra importar a api; o token vem da API real

from api import seguranca  # noqa: E402
from api.storage import get_storage  # noqa: E402

db = get_storage()
TABELAS = ("doadores", "ongs", "lotes", "doacoes", "usuarios")
antes = {t: len(db.listar(t)) for t in TABELAS}
print("antes :", antes)

ok = True


def checa(rotulo, got, esperado, extra=""):
    global ok
    bom = got == esperado
    ok &= bom
    print(f"{'OK   ' if bom else 'FALHA'} {rotulo}: {got}{extra}" + ("" if bom else f" (esperado {esperado})"))


def cronometra(fn):
    t0 = time.perf_counter()
    r = fn()
    return r, time.perf_counter() - t0


email = f"teste-prod-{secrets.token_hex(4)}@exemplo.invalid"
senha = secrets.token_urlsafe(14)
criados = {"usuarios": [], "doadores": [], "ongs": [], "lotes": []}
sufixo = int(time.time()) % 10**6  # documentos unicos pra nao esbarrar em dado real
try:
    adm_row = db.criar("usuarios", {"email": email, "senha_hash": seguranca.hasher.hash(senha),
                                    "papel": "admin", "doador_id": None, "ong_id": None})
    criados["usuarios"].append(adm_row["id"])

    anon = httpx.Client(base_url=URL, timeout=90)
    checa("GET /lotes sem token", anon.get("/lotes").status_code, 401)
    checa("login com senha errada", anon.post("/auth/login", json={"email": email, "senha": "errada-errada"}).status_code, 401)
    r = anon.post("/auth/login", json={"email": email, "senha": senha})
    checa("login do admin de teste", r.status_code, 200)
    if r.status_code != 200:
        raise SystemExit(1)
    c = httpx.Client(base_url=URL, timeout=90, headers={"Authorization": "Bearer " + r.json()["access_token"]})

    d = c.post("/doadores", json={"nome": "TESTE-PROD Doador", "tipo_pessoa": "juridica",
                                  "documento": f"98{sufixo:06d}000101", "cidade": "Sao Paulo", "estado": "SP"})
    checa("POST /doadores", d.status_code, 201)
    criados["doadores"].append(d.json()["id"])
    o = c.post("/ongs", json={"nome": "TESTE-PROD ONG", "cnpj": f"97{sufixo:06d}000102", "endereco": "Rua A, 1",
                              "cidade": "Sao Paulo", "estado": "SP", "capacidade_kg": 100,
                              "necessidades": ["hortifruti"]})
    checa("POST /ongs", o.status_code, 201)
    criados["ongs"].append(o.json()["id"])

    lote = {"doador_id": d.json()["id"], "descricao": "tomate", "quantidade_kg": 20,
            "validade": str(date.today() + timedelta(days=1)), "armazenamento": "refrigerado"}
    l1, t1 = cronometra(lambda: c.post("/lotes", json=lote))
    checa("1o POST /lotes (carrega o modelo)", l1.status_code, 201, f" em {t1:.2f}s, prioridade={l1.json().get('prioridade')}")
    criados["lotes"].append(l1.json()["id"])
    l2, t2 = cronometra(lambda: c.post("/lotes", json=lote))
    checa("2o POST /lotes", l2.status_code, 201, f" em {t2:.2f}s")
    criados["lotes"].append(l2.json()["id"])
    checa("prioridade veio do modelo", l1.json().get("prioridade") in ("alta", "media", "baixa"), True)

    do = {"lote_id": l1.json()["id"], "ong_id": o.json()["id"]}
    checa("POST /doacoes", c.post("/doacoes", json=do).status_code, 201)
    checa("POST /doacoes repetida", c.post("/doacoes", json=do).status_code, 409)
    checa("PUT /lotes -> doado", c.put(f"/lotes/{l1.json()['id']}", json={"status": "doado"}).status_code, 200)
    k = c.get("/kpis/impacto")
    checa("GET /kpis/impacto", k.status_code, 200)
    checa("GET /kpis/ia", c.get("/kpis/ia").status_code, 200)
    checa("quantidade acima do teto", c.post("/lotes", json={**lote, "quantidade_kg": 1e308}).status_code, 422)
    checa("ONG com necessidade fora das categorias",
          c.post("/ongs", json={"nome": "x", "cnpj": f"96{sufixo:06d}000103", "endereco": "r", "cidade": "c",
                                "estado": "SP", "capacidade_kg": 1, "necessidades": ["graos"]}).status_code, 422)
    checa("2a doacao (outro lote, mesma ONG)", c.post("/doacoes", json={
        "lote_id": l2.json()["id"], "ong_id": o.json()["id"]}).status_code, 201)
    checa("health/db", anon.get("/health/db").json(), {"status": "ok", "storage": "postgres"})
finally:
    # limpeza na ordem das chaves estrangeiras (doacao nao tem DELETE na API)
    for dc in db.listar("doacoes"):
        if dc["lote_id"] in criados["lotes"]:
            db._rodar("delete from doacoes where id = %s returning id", [dc["id"]])
    for t in ("lotes", "usuarios", "doadores", "ongs"):
        for i in criados[t]:
            db.apagar(t, i)
    depois = {t: len(db.listar(t)) for t in TABELAS}
    print("depois:", depois)
    checa("banco voltou ao que era", depois, antes)
sys.exit(0 if ok else 1)
