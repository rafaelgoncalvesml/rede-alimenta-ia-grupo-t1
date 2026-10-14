"""Dados dos dois blocos do dashboard que o PDF pede e que nao vem da API: mapa de calor e seguranca.

Sem streamlit aqui de proposito: o que da pra testar sem abrir a tela fica nesse arquivo.
"""
import json
from collections import defaultdict
from pathlib import Path

RAIZ_APP = Path(__file__).resolve().parent.parent
CAMINHOS_HISTORICO = [
    RAIZ_APP / "dados" / "historico_simulado.json",  # dentro da imagem do app
    RAIZ_APP.parent / "data" / "historico_simulado.json",  # no repo
]
CAMINHO_SEGURANCA = RAIZ_APP / "dados" / "seguranca.json"


def _le_json(caminhos):
    for caminho in caminhos:
        try:
            return json.loads(Path(caminho).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
    return None


def carrega_historico(caminhos=None):
    return _le_json(caminhos or CAMINHOS_HISTORICO)


def carrega_seguranca(caminho=None):
    return _le_json([caminho or CAMINHO_SEGURANCA])


def kg_entregue_por_ong(ongs, lotes, doacoes):
    """kg de lotes `doado` com doacao confirmada, somados por ONG que recebeu.

    Serve pro historico simulado e pros dados da API (mesmo formato). ONG sem coordenada
    fica de fora porque nao tem onde aparecer no mapa.
    """
    lote_por_id = {lote["id"]: lote for lote in lotes}
    ong_por_id = {ong["id"]: ong for ong in ongs}
    soma = defaultdict(lambda: {"kg": 0.0, "doacoes": 0})
    for doacao in doacoes:
        lote = lote_por_id.get(doacao["lote_id"])
        if doacao.get("status") != "confirmada" or lote is None or lote.get("status") != "doado":
            continue
        soma[doacao["ong_id"]]["kg"] += float(lote["quantidade_kg"])
        soma[doacao["ong_id"]]["doacoes"] += 1

    pontos = []
    for ong_id, valores in soma.items():
        ong = ong_por_id.get(ong_id)
        if not ong or ong.get("latitude") is None or ong.get("longitude") is None:
            continue
        pontos.append({
            "ong": ong.get("nome"),
            "cidade": ong.get("cidade"),
            "estado": ong.get("estado"),
            "latitude": float(ong["latitude"]),
            "longitude": float(ong["longitude"]),
            "kg": round(valores["kg"], 1),
            "doacoes": valores["doacoes"],
        })
    return sorted(pontos, key=lambda p: -p["kg"])


def kg_por_cidade(pontos):
    soma = defaultdict(lambda: {"kg": 0.0, "doacoes": 0})
    for ponto in pontos:
        chave = (ponto["cidade"], ponto["estado"])
        soma[chave]["kg"] += ponto["kg"]
        soma[chave]["doacoes"] += ponto["doacoes"]
    linhas = [
        {"cidade": cidade, "estado": estado, "kg": round(v["kg"], 1), "doacoes": v["doacoes"]}
        for (cidade, estado), v in soma.items()
    ]
    return sorted(linhas, key=lambda linha: -linha["kg"])


def resumo_seguranca(dados):
    """Numeros do cabecalho do bloco de seguranca, tirados do proprio JSON pra nao divergirem."""
    gates = dados.get("gates", [])
    mitigadas = dados.get("mitigadas", [])
    return {
        "gates_total": len(gates),
        "gates_ok": sum(1 for gate in gates if gate.get("status") == "passou"),
        "mitigadas": sum(item.get("achados", 0) for item in mitigadas),
        "aceitos": len(dados.get("aceitos", [])),
    }
