"""
Gera o dataset v0 de lotes doados (SIMULADO). Rodar da raiz do repo:
    python data/gerar_dataset_v0.py

So stdlib, seed fixa: rodar de novo gera o mesmo CSV byte a byte.
Premissas, formula do rotulo e ruido injetado estao em data/README.md.
"""
import csv
import random
from datetime import date, timedelta
from pathlib import Path

SEED = 42
N_LOTES = 1200
SAIDA = Path(__file__).with_name("lotes_v0.csv")

# PREMISSA: faixa de vida util total (dias) por categoria e armazenamento.
# Ainda nao conferida item a item: validar contra o FoodKeeper (USDA/FSIS) na v1.
VIDA_UTIL = {
    ("hortifruti", "ambiente"): (3, 10),
    ("hortifruti", "refrigerado"): (5, 14),
    ("padaria", "ambiente"): (1, 4),
    ("padaria", "refrigerado"): (3, 7),
    ("laticinios", "refrigerado"): (5, 25),
    ("laticinios", "ambiente"): (1, 3),
    ("carnes_peixes", "refrigerado"): (1, 5),
    ("carnes_peixes", "congelado"): (30, 180),
    ("carnes_peixes", "ambiente"): (1, 1),
    ("preparados", "refrigerado"): (1, 4),
    ("preparados", "congelado"): (30, 90),
    ("preparados", "ambiente"): (1, 1),
    ("nao_pereciveis", "ambiente"): (60, 365),
}

# armazenamento mais frio que a categoria precisa: 0 ambiente, 1 refrigerado, 2 congelado
FRIO = {"ambiente": 0, "refrigerado": 1, "congelado": 2}
FRIO_MINIMO = {"laticinios": 1, "carnes_peixes": 1, "preparados": 1}

CATEGORIAS = {
    # perecivel, pesos de armazenamento, descricoes
    "hortifruti": (True, {"ambiente": 0.6, "refrigerado": 0.4}, [
        "caixa de tomate", "alface crespa", "banana prata", "cenoura", "maca fuji",
        "batata inglesa", "laranja pera", "folhas de couve", "mamao formosa", "cebola"]),
    "padaria": (True, {"ambiente": 0.9, "refrigerado": 0.1}, [
        "pao frances", "pao de forma", "bolo simples", "paes doces", "baguete", "broa de milho"]),
    "laticinios": (True, {"refrigerado": 0.85, "ambiente": 0.15}, [
        "iogurte natural", "leite pasteurizado", "queijo mussarela", "requeijao",
        "bebida lactea", "manteiga"]),
    "carnes_peixes": (True, {"refrigerado": 0.5, "congelado": 0.45, "ambiente": 0.05}, [
        "peito de frango", "carne moida", "file de tilapia", "linguica toscana",
        "coxa de frango", "patinho em cubos"]),
    "preparados": (True, {"refrigerado": 0.7, "congelado": 0.1, "ambiente": 0.2}, [
        "marmitas de arroz e feijao", "sopa de legumes", "refeicao pronta",
        "sobra de buffet", "salada pronta", "lasanha"]),
    "nao_pereciveis": (False, {"ambiente": 1.0}, [
        "arroz tipo 1", "feijao carioca", "macarrao espaguete", "oleo de soja",
        "leite em po", "enlatado de milho", "farinha de trigo", "acucar cristal"]),
}
COMPLEMENTOS = ["", "", "", " para consumo rapido", " sobra de feira", " proximo do vencimento",
                " embalagem avariada", " excedente de estoque", " lote grande"]

SETORES = {
    # setor, tipo de doador, peso, categorias mais comuns
    "supermercado": ("PJ", 0.30, list(CATEGORIAS)),
    "restaurante": ("PJ", 0.15, ["preparados", "hortifruti", "carnes_peixes"]),
    "padaria": ("PJ", 0.10, ["padaria", "laticinios"]),
    "feira": ("PF", 0.15, ["hortifruti"]),
    "industria": ("PJ", 0.10, ["nao_pereciveis", "laticinios", "carnes_peixes"]),
    "pessoa_fisica": ("PF", 0.20, ["nao_pereciveis", "hortifruti", "padaria"]),
}
QTD_MEDIANA = {"pessoa_fisica": 4, "feira": 25, "padaria": 10, "restaurante": 12,
               "supermercado": 40, "industria": 120}

# centro aproximado das cidades (grande SP + Campinas), com jitter por lote
CIDADES = [
    ("Sao Paulo", "SP", -23.5505, -46.6333, 0.45),
    ("Guarulhos", "SP", -23.4543, -46.5337, 0.10),
    ("Osasco", "SP", -23.5325, -46.7917, 0.08),
    ("Santo Andre", "SP", -23.6737, -46.5432, 0.08),
    ("Sao Bernardo do Campo", "SP", -23.6914, -46.5646, 0.09),
    ("Campinas", "SP", -22.9099, -47.0626, 0.20),
]

INICIO = date(2026, 6, 1)
JANELA_DIAS = 112  # ate 20/09/2026


def escolher(rng, pesos: dict):
    return rng.choices(list(pesos), weights=list(pesos.values()))[0]


def prioridade(categoria, armazenamento, dias, vida_total, qtd, rng) -> str:
    perecivel = CATEGORIAS[categoria][0]
    urgencia = 1.0 - min(max(dias / vida_total, 0.0), 1.0)
    fora_do_frio = FRIO[armazenamento] < FRIO_MINIMO.get(categoria, 0)
    score = (0.55 * urgencia + 0.20 * perecivel + 0.15 * fora_do_frio
             + 0.10 * min(qtd / 200, 1.0) + rng.gauss(0, 0.08))
    if score >= 0.60:
        return "alta"
    if score >= 0.38:
        return "media"
    return "baixa"


def gerar_lote(rng, lote_id: int) -> dict:
    setor = escolher(rng, {s: v[1] for s, v in SETORES.items()})
    tipo_doador, _, cats = SETORES[setor]
    categoria = rng.choice(cats)
    perecivel, pesos_arm, descricoes = CATEGORIAS[categoria]
    armazenamento = escolher(rng, pesos_arm)

    lo, hi = VIDA_UTIL[(categoria, armazenamento)]
    vida_total = rng.randint(lo, hi)
    # doacao costuma chegar com parte da vida util ja gasta; alguns ja vencidos
    dias = round(vida_total * rng.uniform(-0.15, 1.0))

    qtd = round(rng.lognormvariate(0, 0.9) * QTD_MEDIANA[setor], 1) or 0.1
    cadastro = INICIO + timedelta(days=rng.randrange(JANELA_DIAS))
    cidade, uf, lat, lon, _ = rng.choices(CIDADES, weights=[c[4] for c in CIDADES])[0]

    return {
        "lote_id": lote_id,
        "data_cadastro": cadastro.isoformat(),
        "setor_doador": setor,
        "tipo_doador": tipo_doador,
        "cidade": cidade,
        "uf": uf,
        "latitude": round(lat + rng.uniform(-0.04, 0.04), 5),
        "longitude": round(lon + rng.uniform(-0.04, 0.04), 5),
        "descricao": rng.choice(descricoes) + rng.choice(COMPLEMENTOS),
        "categoria": categoria,
        "perecivel": perecivel,
        "armazenamento": armazenamento,
        "quantidade_kg": qtd,
        "validade": (cadastro + timedelta(days=dias)).isoformat(),
        "prioridade": prioridade(categoria, armazenamento, dias, vida_total, qtd, rng),
    }


def sujar(rng, lotes: list[dict]) -> list[dict]:
    """Ruido de cadastro real, de proposito, pra limpeza do dia 5 ter o que tratar."""
    for lote in lotes:
        r = rng.random()
        if r < 0.02:
            lote["descricao"] = ""
        elif r < 0.05:
            lote["armazenamento"] = ""
        elif r < 0.10:
            lote["latitude"] = lote["longitude"] = ""  # endereco nao geocodificado
        elif r < 0.11:
            lote["quantidade_kg"] = round(lote["quantidade_kg"] * 1000, 1)  # digitou gramas
    duplicados = [dict(l) for l in rng.sample(lotes, k=len(lotes) // 100)]
    for i, dup in enumerate(duplicados, start=len(lotes) + 1):
        dup["lote_id"] = i  # mesmo lote cadastrado duas vezes
    return lotes + duplicados


def main() -> None:
    rng = random.Random(SEED)
    lotes = sujar(rng, [gerar_lote(rng, i) for i in range(1, N_LOTES + 1)])

    assert len(lotes) == N_LOTES + N_LOTES // 100
    assert {l["prioridade"] for l in lotes} == {"alta", "media", "baixa"}
    assert len({l["lote_id"] for l in lotes}) == len(lotes)

    with SAIDA.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(lotes[0]))
        writer.writeheader()
        writer.writerows(lotes)
    print(f"{len(lotes)} lotes gravados em {SAIDA}")


if __name__ == "__main__":
    main()
