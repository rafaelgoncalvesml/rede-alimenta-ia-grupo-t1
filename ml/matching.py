"""
Matching simples (issue 8): dado um lote, quais ONGs podem receber e em que ordem.

    matching(lote, doador, ongs) -> {"ranking": [...], "descartadas": [...]}

Sem peso aprendido: filtra por categoria e capacidade, ordena por distancia (haversine) e o `score`
e a distancia normalizada. Contrato e decisoes em docs/matching.md.
"""
from ml.geo import haversine_km, posicao

# PREMISSA do grupo: distancia a partir da qual a ONG ja e "longe demais" e o score trava em 1.
# O dataset cobre grande SP + Campinas, onde o par mais distante fica a ~85 km.
RAIO_REFERENCIA_KM = 100.0


def _motivo_de_descarte(lote: dict, ong: dict) -> str | None:
    # mesma regra de api/routers/doacoes.py (_confere_ong_recebe): toda ONG sugerida aqui
    # consegue confirmar a doacao. tipo vazio = o modelo falhou no cadastro, entao nao ha o que conferir
    if lote.get("tipo") and lote["tipo"] not in ong["necessidades"]:
        return "categoria"
    if lote["quantidade_kg"] > ong["capacidade_kg"]:
        return "capacidade"
    return None


def matching(lote: dict, doador: dict, ongs: list[dict]) -> dict:
    origem = posicao(doador)
    if origem is None:
        raise ValueError(
            f"doador sem coordenada valida e sem centro conhecido pra cidade {doador.get('cidade')!r}/"
            f"{doador.get('estado')!r}: nao ha como calcular distancia")
    ranking, descartadas = [], []
    for o in ongs:
        motivo = _motivo_de_descarte(lote, o)
        destino = posicao(o) if motivo is None else None
        if motivo is None and destino is None:
            motivo = "sem_coordenada"
        if motivo:
            descartadas.append({"ong_id": o["id"], "motivo": motivo})
            continue
        km = haversine_km(origem[0], origem[1], destino[0], destino[1])
        ranking.append({"ong_id": o["id"], "nome": o.get("nome"), "distancia_km": round(km, 2),
                        "score": round(min(km / RAIO_REFERENCIA_KM, 1.0), 4),
                        "geo_aproximada": origem[2] or destino[2]})
    ranking.sort(key=lambda r: (r["distancia_km"], r["ong_id"]))
    for numero, r in enumerate(ranking, start=1):
        r["posicao"] = numero
    return {"ranking": ranking, "descartadas": descartadas}
