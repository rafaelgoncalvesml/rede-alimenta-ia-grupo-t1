"""Seed de demo (roadmap, dia 21): 3 doadores, 4 ONGs e 5 lotes. Fontes e rotulos em docs/seed-demo.md.

    python -m api.seed_demo               # tudo
    python -m api.seed_demo --so-reais    # so as ONGs verificadas na Receita, sem as ficticias

O que e REAL: nome, CNPJ, endereco e coordenada das duas ONGs reais (dados publicos, conferidos em
12/10/2026). O que e SIMULADO: `capacidade_kg` e `necessidades` delas (as entidades nao informaram
isso), os 3 doadores, as 2 ONGs com (DEMO) no nome e os 5 lotes. Nada aqui e dado de operacao.

Idempotente: rodar de novo nao duplica. Precisa de ADMIN_EMAIL e ADMIN_PASSWORD, como o seed_dev.
"""
import os
import sys
from datetime import date, timedelta

from api.seed_dev import _req as _http

# Fonte: Receita Federal via BrasilAPI (situacao ATIVA em 12/10/2026; endereco como no cadastro da
# Receita). Coordenada: OpenStreetMap/Nominatim, (c) OpenStreetMap contributors, nivel de rua.
# NAO usar a coordenada que a API de CEP devolve: pras duas ONGs ela volta o centro de Sao Paulo.
ONGS_REAIS = [
    {
        "nome": "Casa do Zezinho - Associação Educacional e Assistencial",
        "cnpj": "74566035000129",
        "endereco": "Rua Anália Dolácio Albino, 30 - Parque Maria Helena",  # o site diz 77; vale a Receita
        "cidade": "São Paulo", "estado": "SP",
        "latitude": -23.66114, "longitude": -46.76214,
        "capacidade_kg": 300,  # SIMULADO
        "necessidades": ["hortifruti", "padaria", "nao_pereciveis"],  # SIMULADO
    },
    {
        "nome": "Banco de Alimentos - Associação Civil",
        "cnpj": "02736449000148",
        "endereco": "Rua Atibaia, 218 - Pacaembu",
        "cidade": "São Paulo", "estado": "SP",
        "latitude": -23.53959, "longitude": -46.66820,
        "capacidade_kg": 2000,  # SIMULADO
        "necessidades": ["hortifruti", "padaria", "laticinios", "nao_pereciveis"],  # SIMULADO
    },
]

# Ficticias, com CNPJ de preenchimento (invalido de proposito: nao e de ninguem).
ONGS_DEMO = [
    {
        "nome": "ONG Prato Cheio Campinas (DEMO)", "cnpj": "00000000000400",
        "endereco": "Rua Exemplo, 100 (DEMO)", "cidade": "Campinas", "estado": "SP",
        "latitude": -22.8968, "longitude": -47.0449,
        "capacidade_kg": 800, "necessidades": ["hortifruti", "laticinios", "padaria"],
    },
    {  # sem coordenada de proposito: o matching cai no centro de Santo Andre (fallback)
        "nome": "ONG Mesa Farta Santo André (DEMO)", "cnpj": "00000000000500",
        "endereco": "Rua Exemplo, 200 (DEMO)", "cidade": "Santo André", "estado": "SP",
        "capacidade_kg": 30, "necessidades": ["preparados", "padaria"],
    },
]

DOADORES = [
    {"nome": "Supermercado Vila Madalena (DEMO)", "tipo_pessoa": "juridica", "documento": "00000000000100",
     "cidade": "São Paulo", "estado": "SP", "latitude": -23.5568, "longitude": -46.6911},
    {"nome": "Padaria Santo André (DEMO)", "tipo_pessoa": "juridica", "documento": "00000000000200",
     "cidade": "Santo André", "estado": "SP"},  # sem coordenada: fallback
    {"nome": "Restaurante Cambuí (DEMO)", "tipo_pessoa": "juridica", "documento": "00000000000300",
     "cidade": "Campinas", "estado": "SP", "latitude": -22.8985, "longitude": -47.0498},
]

# (documento do doador, descricao, kg, dias ate vencer, armazenamento). Pensados pra exercitar o matching:
# o 4 passa da capacidade de uma ONG, o 5 nao tem ONG possivel (a unica que aceita preparados so leva 30 kg).
LOTES = [
    ("00000000000100", "caixa de tomate", 120, 2, "refrigerado"),
    ("00000000000100", "pao frances do dia", 25, 1, "ambiente"),
    ("00000000000300", "iogurte natural", 60, 4, "refrigerado"),
    ("00000000000200", "arroz tipo 1 saco 5kg", 400, 180, "ambiente"),
    ("00000000000100", "marmitas prontas de arroz e feijao", 40, 1, "refrigerado"),
]


def popular(req, hoje: date | None = None, so_reais: bool = False) -> dict:
    """`req(metodo, caminho, corpo=None)` devolve o JSON da resposta e levanta se a API recusar."""
    hoje = hoje or date.today()
    criados = {"doadores": 0, "ongs": 0, "lotes": 0}

    doadores = {d["documento"]: d for d in req("GET", "/doadores")}
    for corpo in DOADORES:
        if corpo["documento"] not in doadores:
            doadores[corpo["documento"]] = req("POST", "/doadores", corpo)
            criados["doadores"] += 1

    ongs = {o["cnpj"]: o for o in req("GET", "/ongs")}
    for corpo in ONGS_REAIS + ([] if so_reais else ONGS_DEMO):
        if corpo["cnpj"] not in ongs:
            ongs[corpo["cnpj"]] = req("POST", "/ongs", corpo)
            criados["ongs"] += 1

    ja_tem = {(l["doador_id"], l["descricao"]) for l in req("GET", "/lotes")}
    for documento, descricao, kg, dias, armazenamento in LOTES:
        doador_id = doadores[documento]["id"]
        if (doador_id, descricao) not in ja_tem:
            req("POST", "/lotes", {"doador_id": doador_id, "descricao": descricao, "quantidade_kg": kg,
                                   "validade": (hoje + timedelta(days=dias)).isoformat(),
                                   "armazenamento": armazenamento})
            criados["lotes"] += 1
    return criados


if __name__ == "__main__":
    login = {"email": os.getenv("ADMIN_EMAIL", ""), "senha": os.getenv("ADMIN_PASSWORD", "")}
    if not all(login.values()):
        raise SystemExit("defina ADMIN_EMAIL e ADMIN_PASSWORD (no .env ou no ambiente)")
    token = _http("/auth/login", login)["access_token"]
    resumo = popular(lambda metodo, caminho, corpo=None: _http(caminho, corpo, token),
                     so_reais="--so-reais" in sys.argv)
    print(f"criados: {resumo}")
    print("SIMULADO: capacidade_kg e necessidades das ONGs reais, doadores, ONGs (DEMO) e lotes.")
