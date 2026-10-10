"""Fluxo completo por HTTP contra uma API que ja esta de pe (dia 20).

    API_URL=http://localhost:8000 ADMIN_EMAIL=... ADMIN_PASSWORD=... python -m api.fluxo_http

Serve pro container em memoria (docker run sem STORAGE=postgres) e pro uvicorn local. NAO
apontar pro Supabase: doacao nao tem DELETE, entao o que este script cria fica la. Pro banco
em nuvem existe o infra/db/testar_login.py, que limpa depois.

Passos: doador, ONG, lote (prioridade vem do modelo), doacao, repeticao, entrega, KPIs e as
recusas novas (categoria fora da lista, ONG sem capacidade, teto de quantidade). Matching e
dashboard nao existem no repo e por isso nao aparecem aqui.
"""
import os
import sys
from datetime import date, timedelta

import httpx

URL = os.getenv("API_URL", "http://localhost:8000").rstrip("/")
falhas = 0


def confere(rotulo, resp, esperado, campo=None):
    global falhas
    ok = resp.status_code == esperado
    falhas += not ok
    extra = f"  {campo}={resp.json().get(campo)}" if campo and ok else ""
    print(f"{'OK   ' if ok else 'FALHA'} {resp.status_code}  {rotulo}{extra}")
    if not ok:
        print("      esperado", esperado, "->", resp.text[:200])
    return resp


c = httpx.Client(base_url=URL, timeout=30)
r = c.post("/auth/login", json={"email": os.environ["ADMIN_EMAIL"], "senha": os.environ["ADMIN_PASSWORD"]})
confere("login do admin", r, 200)
if r.status_code != 200:
    sys.exit(1)
c.headers["Authorization"] = "Bearer " + r.json()["access_token"]

# o primeiro lote carrega o modelo (~1 s); o resto fica em ms
doador = {"nome": "Mercado Fluxo", "tipo_pessoa": "juridica", "documento": "11.222.333/0001-81",
          "cidade": "Sao Paulo", "estado": "SP"}
ong = {"nome": "ONG Fluxo", "cnpj": "55.666.777/0001-90", "endereco": "Rua A, 1",
       "cidade": "Sao Paulo", "estado": "SP", "capacidade_kg": 100, "necessidades": ["hortifruti"]}
amanha = str(date.today() + timedelta(days=1))
lote = {"doador_id": 1, "descricao": "tomate", "quantidade_kg": 20, "validade": amanha,
        "armazenamento": "refrigerado"}

confere("POST /doadores", c.post("/doadores", json=doador), 201, "id")
confere("POST /ongs", c.post("/ongs", json=ong), 201, "id")
confere("POST /lotes (prioridade pelo modelo)", c.post("/lotes", json=lote), 201, "prioridade")
confere("POST /doacoes", c.post("/doacoes", json={"lote_id": 1, "ong_id": 1}), 201, "tempo_match_s")
confere("POST /doacoes repetida", c.post("/doacoes", json={"lote_id": 1, "ong_id": 1}), 409)
confere("PUT /lotes/1 -> doado", c.put("/lotes/1", json={"status": "doado"}), 200, "status")
k = confere("GET /kpis/impacto", c.get("/kpis/impacto"), 200, "kg_doados")
if k.status_code == 200 and k.json()["kg_doados"] != 20:
    falhas += 1
    print("FALHA kg_doados deveria ser 20")
confere("GET /kpis/ia", c.get("/kpis/ia"), 200)

print("--- recusas")
confere("ONG com necessidade fora das categorias",
        c.post("/ongs", json={**ong, "cnpj": "55666777000191", "necessidades": ["graos"]}), 422)
confere("quantidade acima do teto",
        c.post("/lotes", json={**lote, "quantidade_kg": 1e308}), 422)
confere("validade em 9999", c.post("/lotes", json={**lote, "validade": "9999-12-31"}), 422)
c.post("/ongs", json={**ong, "cnpj": "55666777000192", "capacidade_kg": 5, "necessidades": ["hortifruti"]})
c.post("/lotes", json=lote)
confere("doacao maior que a capacidade da ONG",
        c.post("/doacoes", json={"lote_id": 2, "ong_id": 2}), 409)
c.post("/ongs", json={**ong, "cnpj": "55666777000193", "necessidades": ["padaria"]})
confere("doacao pra ONG que nao aceita a categoria",
        c.post("/doacoes", json={"lote_id": 2, "ong_id": 3}), 409)
confere("sem token", httpx.get(URL + "/lotes"), 401)
confere("health", httpx.get(URL + "/health"), 200)

print("\nFALHAS:", falhas)
sys.exit(1 if falhas else 0)
