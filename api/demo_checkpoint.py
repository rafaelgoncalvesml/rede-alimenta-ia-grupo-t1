"""Demo do checkpoint da Semana 2 (dia 14): doador -> lote com prioridade -> doacao -> entrega.

Roda em memoria pelo TestClient, sem subir a API e sem tocar o Supabase:
    python -m api.demo_checkpoint

O passo de matching ainda nao existe na API; aqui a ONG e escolhida na mao e a
linha fica marcada pra entrar quando o POST /matching chegar.
"""
import os

os.environ["STORAGE"] = "memory"
# so pra demo local: segredo e admin descartaveis, a API em memoria some quando o script acaba
os.environ.setdefault("JWT_SECRET", "demo-" + "x" * 40)
os.environ.setdefault("ADMIN_EMAIL", "admin@demo.local")
os.environ.setdefault("ADMIN_PASSWORD", "senha-da-demo-1")

import logging  # noqa: E402
from datetime import date, timedelta  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

from api import seguranca  # noqa: E402
from api.main import app  # noqa: E402
from api.storage import get_storage  # noqa: E402

get_storage().reset()
seguranca.garantir_admin()
c = TestClient(app)
c.headers["Authorization"] = "Bearer " + c.post("/auth/login", json={
    "email": os.environ["ADMIN_EMAIL"], "senha": os.environ["ADMIN_PASSWORD"]}).json()["access_token"]
logging.getLogger("auditoria").setLevel(logging.CRITICAL)  # a demo ja imprime cada passo
hoje = date.today()


def passo(titulo, resp, campos=()):
    extra = " ".join(f"{k}={resp.json().get(k)}" for k in campos)
    print(f"{resp.status_code}  {titulo:<42} {extra}")
    return resp.json()


doador = passo("POST /doadores", c.post("/doadores", json={
    "nome": "Mercado Sol", "tipo_pessoa": "juridica", "documento": "12.345.678/0001-99",
    "cidade": "Sao Paulo", "estado": "SP"}), ("id", "documento"))
ong = passo("POST /ongs", c.post("/ongs", json={
    "nome": "Casa do Pao", "cnpj": "98765432000155", "endereco": "Rua das Flores, 100",
    "cidade": "Sao Paulo", "estado": "SP", "capacidade_kg": 500,
    "necessidades": ["hortifruti"]}), ("id",))

lotes = [
    ("tomate, vence em 1 dia", 20, 1, "refrigerado"),
    ("iogurte, vence em 6 dias", 40, 6, "refrigerado"),
    ("arroz integral, vence em 120 dias", 80, 120, "ambiente"),
]
ids = []
for desc, kg, dias, arm in lotes:
    l = passo(f"POST /lotes  ({desc})", c.post("/lotes", json={
        "doador_id": doador["id"], "descricao": desc.split(",")[0], "quantidade_kg": kg,
        "validade": str(hoje + timedelta(days=dias)), "armazenamento": arm}),
        ("id", "tipo", "prioridade"))
    ids.append(l["id"])

print("\nGET /lotes (ordem de cadastro):")
for l in c.get("/lotes").json():
    print(f"   lote {l['id']}: {l['descricao']:<8} {l['prioridade']}")

print("\n[matching] POST /matching/{lote_id}: NAO EXISTE ainda, ONG escolhida na mao")
d = passo("POST /doacoes", c.post("/doacoes", json={"lote_id": ids[0], "ong_id": ong["id"]}),
          ("id", "status", "tempo_match_s"))
passo("POST /doacoes (repetida)", c.post("/doacoes", json={"lote_id": ids[0], "ong_id": ong["id"]}))
passo("PUT /lotes/{id} status=doado", c.put(f"/lotes/{ids[0]}", json={"status": "doado"}), ("status",))
print("\nrestam disponiveis:", [l["id"] for l in c.get("/lotes", params={"status": "disponivel"}).json()])
