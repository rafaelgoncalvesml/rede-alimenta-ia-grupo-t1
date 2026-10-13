"""
Historico simulado de doacoes pro dashboard (roadmap, dia 16). **Tudo SIMULADO.** Da raiz do repo:

    python -m data.gerar_historico_simulado      # grava data/historico_simulado.json

Parte dos lotes do dataset v1 (`data/lotes_v1.csv`, ele mesmo simulado) e usa o `ml.matching` de
verdade pra escolher a ONG de cada lote. Um lote so e descartado se nao existe ONG que o receba
ou se o tempo de match estoura a validade. Seed fixa: roda de novo e sai o mesmo arquivo.

O formato e o da API (lotes, doacoes, ongs), pra o mesmo `api.kpis.calcula_impacto` calcular em cima.
Toda linha leva `origem: "SIMULADO"`; as premissas vao dentro do arquivo, na chave `premissas`.
As ONGs daqui sao inventadas de proposito: nenhuma entidade real recebe volume simulado.
"""
import csv
import json
import math
import random
from datetime import datetime, time, timedelta, timezone
from pathlib import Path

from ml.features import CATEGORIAS
from ml.geo import CENTROS_CIDADES
from ml.matching import matching

RAIZ = Path(__file__).resolve().parents[1]
ENTRADA = RAIZ / "data" / "lotes_v1.csv"
SAIDA = RAIZ / "data" / "historico_simulado.json"
SEMENTE = 2026

# PREMISSAS do grupo (nenhuma tem fonte). Ficam aqui e saem em `premissas` no JSON.
ONGS_POR_CIDADE = 2
CAPACIDADE_MEDIANA_KG, CAPACIDADE_SIGMA, CAPACIDADE_MIN_KG, CAPACIDADE_MAX_KG = 600, 0.6, 100, 5000
CATEGORIAS_POR_ONG = 4  # cada ONG aceita 4 das 6 categorias, em rodizio: toda categoria tem ONG
TEMPO_MATCH_MEDIANO_S, TEMPO_MATCH_SIGMA = 4 * 3600, 0.9  # lognormal: mediana de 4 h
PESO_DA_1A_2A_3A_ONG = (0.60, 0.25, 0.15)  # o doador nem sempre escolhe a mais perto
P_CANCELADA = 0.04  # doacao confirmada e cancelada antes da entrega; o lote volta pro matching
DIAS_EM_ANDAMENTO, P_EM_ANDAMENTO = 2, 0.5  # lotes dos ultimos dias que ainda nao foram entregues

PREMISSAS = [
    "TUDO SIMULADO: nenhum lote, doador, ONG ou doacao aqui aconteceu de verdade",
    f"{ONGS_POR_CIDADE} ONGs inventadas por cidade; capacidade lognormal (mediana {CAPACIDADE_MEDIANA_KG} kg, "
    f"entre {CAPACIDADE_MIN_KG} e {CAPACIDADE_MAX_KG}); cada uma aceita {CATEGORIAS_POR_ONG} das 6 categorias",
    f"tempo de match lognormal (mediana {TEMPO_MATCH_MEDIANO_S // 3600} h, sigma {TEMPO_MATCH_SIGMA}); "
    "o lote e descartado se o match passa do fim do dia da validade",
    f"o doador escolhe a 1a, 2a ou 3a ONG do matching com pesos {PESO_DA_1A_2A_3A_ONG}",
    f"{P_CANCELADA:.0%} das doacoes sao canceladas e refeitas; nos ultimos {DIAS_EM_ANDAMENTO} dias "
    f"{P_EM_ANDAMENTO:.0%} dos lotes ficam reservados (kg em andamento)",
    "prioridade do lote = o rotulo simulado do dataset v1 (data/README.md)",
]


def _ongs(rng: random.Random) -> list[dict]:
    ongs = []
    for (cidade, uf), (lat, lon) in CENTROS_CIDADES.items():
        for _ in range(ONGS_POR_CIDADE):
            i = len(ongs) + 1
            capacidade = rng.lognormvariate(math.log(CAPACIDADE_MEDIANA_KG), CAPACIDADE_SIGMA)
            ongs.append({
                "id": i, "nome": f"ONG Simulada {i:02d} {cidade.title()} (SIMULADO)",
                "cidade": cidade.title(), "estado": uf,
                "latitude": round(lat + rng.uniform(-0.02, 0.02), 5),
                "longitude": round(lon + rng.uniform(-0.02, 0.02), 5),
                "capacidade_kg": round(min(max(capacidade, CAPACIDADE_MIN_KG), CAPACIDADE_MAX_KG), 1),
                "necessidades": [CATEGORIAS[(i + k) % len(CATEGORIAS)] for k in range(CATEGORIAS_POR_ONG)],
                "origem": "SIMULADO",
            })
    return ongs


def _le_lotes(caminho: Path) -> list[dict]:
    with caminho.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _registra(doacoes: list, lote: dict, criado: datetime, ong: dict, segundos: float, status: str) -> None:
    confirmado = criado + timedelta(seconds=segundos)
    doacoes.append({
        "id": len(doacoes) + 1, "lote_id": lote["id"], "ong_id": ong["ong_id"],
        "distancia_km": ong["distancia_km"], "score": ong["score"], "status": status,
        "criado_em": confirmado.isoformat(), "confirmado_em": confirmado.isoformat(),
        "tempo_match_s": round(segundos, 1), "origem": "SIMULADO",
    })


def gerar(semente: int = SEMENTE, caminho: Path = ENTRADA) -> dict:
    rng = random.Random(semente)
    ongs = _ongs(rng)
    linhas = _le_lotes(caminho)
    ultimo_dia = max(l["data_cadastro"] for l in linhas)
    corte_em_andamento = (datetime.fromisoformat(ultimo_dia) - timedelta(days=DIAS_EM_ANDAMENTO)).date().isoformat()

    lotes, doacoes = [], []
    for l in linhas:
        criado = datetime.combine(datetime.fromisoformat(l["data_cadastro"]).date(), time(rng.randint(7, 19),
                                  rng.randint(0, 59)), tzinfo=timezone.utc)
        lote = {
            "id": int(l["lote_id"]), "descricao": l["descricao"], "quantidade_kg": float(l["quantidade_kg"]),
            "validade": l["validade"], "armazenamento": l["armazenamento"], "tipo": l["categoria"],
            "prioridade": l["prioridade"], "status": "descartado", "criado_em": criado.isoformat(),
            "latitude": float(l["latitude"]), "longitude": float(l["longitude"]),
            "cidade": l["cidade"], "estado": l["uf"], "origem": "SIMULADO",
        }
        lotes.append(lote)

        candidatas = matching(lote, lote, ongs)["ranking"]
        if not candidatas:
            continue
        tempo_s = rng.lognormvariate(math.log(TEMPO_MATCH_MEDIANO_S), TEMPO_MATCH_SIGMA)
        fim_da_validade = datetime.combine(datetime.fromisoformat(l["validade"]).date() + timedelta(days=1),
                                           time(0, 0), tzinfo=timezone.utc)
        if criado + timedelta(seconds=tempo_s) > fim_da_validade:
            continue

        pesos = PESO_DA_1A_2A_3A_ONG[:len(candidatas[:3])]
        escolhida = rng.choices(candidatas[:3], weights=pesos)[0]

        if rng.random() < P_CANCELADA:
            _registra(doacoes, lote, criado, escolhida, tempo_s * 0.5, "cancelada")
        _registra(doacoes, lote, criado, escolhida, tempo_s, "confirmada")
        em_andamento = l["data_cadastro"] >= corte_em_andamento and rng.random() < P_EM_ANDAMENTO
        lote["status"] = "reservado" if em_andamento else "doado"

    return {
        "origem": "SIMULADO", "gerado_por": "data/gerar_historico_simulado.py", "semente": semente,
        "periodo": {"inicio": min(l["data_cadastro"] for l in linhas), "fim": ultimo_dia},
        "premissas": PREMISSAS, "ongs": ongs, "lotes": lotes, "doacoes": doacoes,
    }


def carregar_historico(historico: dict) -> dict:
    """O JSON guarda datas como texto; o `api.kpis` espera datetime em `confirmado_em`."""
    return {
        **historico,
        "lotes": [{**l, "criado_em": datetime.fromisoformat(l["criado_em"])} for l in historico["lotes"]],
        "doacoes": [{**d, "criado_em": datetime.fromisoformat(d["criado_em"]),
                     "confirmado_em": datetime.fromisoformat(d["confirmado_em"])} for d in historico["doacoes"]],
    }


def main() -> None:
    h = gerar()
    SAIDA.write_text(json.dumps(h, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    por_status = {}
    for l in h["lotes"]:
        por_status[l["status"]] = por_status.get(l["status"], 0) + 1
    print(f"{SAIDA.relative_to(RAIZ)}: {len(h['lotes'])} lotes {por_status}, {len(h['doacoes'])} doacoes, "
          f"{len(h['ongs'])} ONGs (tudo SIMULADO)")


if __name__ == "__main__":
    main()
