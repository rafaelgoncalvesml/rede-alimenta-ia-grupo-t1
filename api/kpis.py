"""Calculo dos KPIs. Funcoes puras sobre listas de dicts, sem tocar o banco, pra testar de
cabeca. Definicoes e premissas em docs/kpis.md."""
import json
import os
from collections import Counter, defaultdict
from pathlib import Path

METRICAS = Path(__file__).resolve().parent.parent / "models" / "metrics.json"

# PREMISSA do grupo, sem fonte brasileira (docs/kpis.md). Vai marcada como premissa em toda
# resposta que a usa. A unica referencia achada (Feeding America, EUA) da ~0,544 kg.
KG_POR_REFEICAO_PADRAO = 0.5


def kg_por_refeicao() -> float:
    valor = float(os.getenv("KG_POR_REFEICAO", KG_POR_REFEICAO_PADRAO))
    if valor <= 0:
        raise RuntimeError("KG_POR_REFEICAO precisa ser maior que zero")
    return valor


def _refeicoes(kg: float, fator: float) -> float:
    return round(kg / fator, 1)


def calcula_impacto(lotes: list[dict], doacoes: list[dict], ongs: list[dict], fator: float) -> dict:
    """kg salvos = lotes `doado` com doacao confirmada. Lote so `reservado` ainda nao chegou:
    entra em kg_em_andamento, nao em kg_doados."""
    lote_por_id = {l["id"]: l for l in lotes}
    ong_por_id = {o["id"]: o for o in ongs}
    confirmadas = [d for d in doacoes if d["status"] == "confirmada" and d["lote_id"] in lote_por_id]

    entregues = [d for d in confirmadas if lote_por_id[d["lote_id"]]["status"] == "doado"]
    em_andamento = [d for d in confirmadas if lote_por_id[d["lote_id"]]["status"] == "reservado"]

    def kg(ds):
        return sum(lote_por_id[d["lote_id"]]["quantidade_kg"] for d in ds)

    kg_doados = kg(entregues)

    por_estado: dict[str, dict] = defaultdict(lambda: {"doacoes": 0, "kg_doados": 0.0})
    for d in entregues:
        uf = (ong_por_id.get(d["ong_id"]) or {}).get("estado", "?")
        por_estado[uf]["doacoes"] += 1
        por_estado[uf]["kg_doados"] += lote_por_id[d["lote_id"]]["quantidade_kg"]

    por_dia: dict[str, float] = defaultdict(float)
    for d in entregues:
        por_dia[d["confirmado_em"].date().isoformat()] += lote_por_id[d["lote_id"]]["quantidade_kg"]

    tempos = [d["tempo_match_s"] for d in confirmadas]
    return {
        "kg_doados": round(kg_doados, 2),
        "kg_em_andamento": round(kg(em_andamento), 2),
        "refeicoes_geradas": _refeicoes(kg_doados, fator),
        "doacoes_confirmadas": len(confirmadas),
        "doacoes_canceladas": sum(1 for d in doacoes if d["status"] == "cancelada"),
        "ongs_atendidas": len({d["ong_id"] for d in entregues}),
        "tempo_medio_match_s": round(sum(tempos) / len(tempos), 2) if tempos else None,
        "lotes_por_status": dict(Counter(l["status"] for l in lotes)),
        "por_estado": [
            {"estado": uf, "doacoes": v["doacoes"], "kg_doados": round(v["kg_doados"], 2),
             "refeicoes_geradas": _refeicoes(v["kg_doados"], fator)}
            for uf, v in sorted(por_estado.items())
        ],
        "por_dia": [
            {"data": dia, "kg_doados": round(kg_dia, 2), "refeicoes_geradas": _refeicoes(kg_dia, fator)}
            for dia, kg_dia in sorted(por_dia.items())
        ],
        "fator_kg_por_refeicao": fator,
        "premissas": [
            f"1 refeicao = {fator} kg: PREMISSA do grupo (KG_POR_REFEICAO). Unica referencia achada, "
            "de outro pais: Feeding America usa 1,2 lb (~0,544 kg) por refeicao (docs/kpis.md)",
            "kg doados = lotes com status doado e doacao confirmada; reservado fica em kg_em_andamento",
            "por_estado agrupa pela UF da ONG que recebeu; por_dia pela data de confirmacao (UTC)",
        ],
    }


def le_metricas() -> dict | None:
    try:
        return json.loads(METRICAS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def calcula_ia(lotes: list[dict], metricas: dict | None) -> dict:
    classificados = [l for l in lotes if l.get("prioridade")]
    modelo = None
    avisos = []
    if metricas:
        escolhido = metricas["modelo_escolhido"]
        teste = metricas["teste"][escolhido]
        base = metricas["teste"]["baseline_dias"]
        cat = metricas.get("classificador_de_categoria", {})
        modelo = {
            "versao": metricas["versao"],
            "modelo": escolhido,
            "dataset": metricas["dataset"],
            "metrica_alvo": metricas["metrica_alvo"],
            "n_treino": metricas["n_treino"],
            "n_teste": metricas["n_teste"],
            "f1_macro_teste": teste["f1_macro"],
            "f1_macro_baseline": base["f1_macro"],
            "ganho_sobre_baseline": round(teste["f1_macro"] - base["f1_macro"], 4),
            "acuracia_teste": teste["acuracia"],
            "recall_alta": teste["recall_alta"],
            "alta_prevista_como_baixa": teste["alta_prevista_como_baixa"],
            "acuracia_classificador_de_categoria": cat.get("acuracia_teste"),
        }
        if "SIMULADO" in metricas["dataset"]:
            avisos.append("metricas de modelo calculadas sobre dataset SIMULADO: provam o pipeline, "
                          "nao a qualidade em dado real")
        if cat.get("aviso"):
            avisos.append(cat["aviso"])
    else:
        avisos.append("models/metrics.json nao encontrado: sem metricas do modelo")
    return {
        "modelo": modelo,
        "operacao": {
            "lotes_total": len(lotes),
            "classificados": len(classificados),
            "sem_prioridade": len(lotes) - len(classificados),
            "taxa_classificacao": round(len(classificados) / len(lotes), 4) if lotes else None,
            "por_prioridade": dict(Counter(l["prioridade"] for l in classificados)),
            "por_tipo": dict(Counter(l["tipo"] for l in classificados if l.get("tipo"))),
        },
        "avisos": avisos,
    }
