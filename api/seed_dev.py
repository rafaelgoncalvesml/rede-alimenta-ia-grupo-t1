"""Popula a API local com um doador e uma ONG de exemplo.

Com STORAGE=memory precisa rodar de novo toda vez que a API reinicia. Com
STORAGE=postgres roda uma vez so: se ja tem doador, nao faz nada.

    python -m api.seed_dev
"""
import json
import os
import urllib.request

API_URL = os.getenv("API_URL", "http://localhost:8000")

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


def _req(path, corpo=None):
    dados = json.dumps(corpo).encode() if corpo is not None else None
    req = urllib.request.Request(
        API_URL + path, data=dados, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as r:
        return json.load(r)


if __name__ == "__main__":
    if _req("/doadores"):
        print("ja tem doador cadastrado, nada a fazer")
    else:
        d = _req("/doadores", DOADOR)
        o = _req("/ongs", ONG)
        print(f"doador id={d['id']} e ong id={o['id']} criados")
