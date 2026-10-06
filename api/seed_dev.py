"""Popula a API local com um doador e uma ONG de exemplo.

Precisa de ADMIN_EMAIL e ADMIN_PASSWORD (as mesmas que a API usa pra criar o admin).

Com STORAGE=memory precisa rodar de novo toda vez que a API reinicia. Com
STORAGE=postgres roda uma vez so: se ja tem doador, nao faz nada.

    python -m api.seed_dev
"""
import json
import os
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
API_URL = os.getenv("API_URL", "http://localhost:8000")
if not API_URL.startswith(("http://", "https://")):
    raise SystemExit("API_URL precisa comecar com http:// ou https://")

DOADOR = {
    "nome": "Mercado Bom Preco (DEMO)",
    "tipo_pessoa": "juridica",
    "documento": "11222333000181",
    "cidade": "Sao Paulo",
    "estado": "SP",
    "latitude": -23.5505,
    "longitude": -46.6333,
}
ONG = {
    "nome": "ONG Mesa Cheia (DEMO)",
    "cnpj": "44555666000102",
    "endereco": "Rua Exemplo, 100",
    "cidade": "Sao Paulo",
    "estado": "SP",
    "latitude": -23.5614,
    "longitude": -46.6559,
    "capacidade_kg": 500,
    "necessidades": ["hortifruti", "padaria"],
}


def _req(path, corpo=None, token=None):
    dados = json.dumps(corpo).encode() if corpo is not None else None
    cabecalhos = {"Content-Type": "application/json"}
    if token:
        cabecalhos["Authorization"] = "Bearer " + token
    req = urllib.request.Request(API_URL + path, data=dados, headers=cabecalhos)
    with urllib.request.urlopen(req) as r:  # nosec B310: esquema validado acima
        return json.load(r)


if __name__ == "__main__":
    login = {"email": os.getenv("ADMIN_EMAIL", ""), "senha": os.getenv("ADMIN_PASSWORD", "")}
    if not all(login.values()):
        raise SystemExit("defina ADMIN_EMAIL e ADMIN_PASSWORD (no .env ou no ambiente)")
    token = _req("/auth/login", login)["access_token"]
    if _req("/doadores", token=token):
        print("ja tem doador cadastrado, nada a fazer")
    else:
        d = _req("/doadores", DOADOR, token)
        o = _req("/ongs", ONG, token)
        print(f"doador id={d['id']} e ong id={o['id']} criados")
