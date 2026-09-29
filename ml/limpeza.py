"""
Limpeza do dataset v0 -> v1. As decisoes vem da secao 9 de ml/eda_v0.md.
Rodar da raiz do repo:
    python -m ml.limpeza
"""
from pathlib import Path

import pandas as pd

from ml.features import adicionar_features

RAIZ = Path(__file__).resolve().parents[1]
ENTRADA = RAIZ / "data" / "lotes_v0.csv"
SAIDA = RAIZ / "data" / "lotes_v1.csv"

# acima de 100x a mediana do proprio setor ha um corte claro no dataset v0 (ml/eda_v0.md, secao 5):
# o proximo lote fica abaixo de 25x, entao isso separa erro de unidade de lote grande de verdade
LIMITE_ERRO_UNIDADE = 100

# retangulo que contem o Brasil (aproximado). Pega 0,0 (coordenada zerada) e latitude/longitude
# trocadas, que passam num teste de intervalo -90..90 mas cairiam no oceano
LATITUDE_BRASIL = (-33.75, 5.27)
LONGITUDE_BRASIL = (-73.99, -28.85)


def carregar(caminho: Path = ENTRADA) -> pd.DataFrame:
    return pd.read_csv(caminho, parse_dates=["data_cadastro", "validade"])


def limpar(df: pd.DataFrame) -> pd.DataFrame:
    """Devolve o dataset v1. O que foi tratado por motivo fica em `resultado.attrs["relatorio"]`."""
    relatorio = {"linhas_entrada": len(df)}

    colunas_conteudo = [c for c in df.columns if c != "lote_id"]
    n = len(df)
    df = df.drop_duplicates(subset=colunas_conteudo).copy()
    relatorio["duplicados"], n = n - len(df), len(df)

    # lote vencido nao pode ser doado (regra de negocio); vencer no proprio dia ainda pode
    df = df[df["validade"] >= df["data_cadastro"]].copy()
    relatorio["vencidos"], n = n - len(df), len(df)

    # armazenamento define a vida util e o rotulo; imputar pela moda da categoria injetaria
    # rotulo errado no treino (carnes_peixes empata entre refrigerado e congelado). Na API o
    # campo e obrigatorio, entao o modelo nunca ve nulo em producao: descartar e o mais honesto.
    df = df[df["armazenamento"].notna()].copy()
    relatorio["sem_armazenamento"] = n - len(df)

    mediana_do_setor = df.groupby("setor_doador")["quantidade_kg"].transform("median")
    gramas = df["quantidade_kg"] > LIMITE_ERRO_UNIDADE * mediana_do_setor
    df.loc[gramas, "quantidade_kg"] = (df.loc[gramas, "quantidade_kg"] / 1000).round(1)
    relatorio["erro_de_unidade_corrigido"] = int(gramas.sum())

    # o matching precisa de coordenada, a prioridade nao: em vez de descartar, usa o centro da cidade
    geo_ok = df["latitude"].between(*LATITUDE_BRASIL) & df["longitude"].between(*LONGITUDE_BRASIL)
    df.loc[~geo_ok, ["latitude", "longitude"]] = float("nan")
    centro = df.groupby("cidade")[["latitude", "longitude"]].transform("median").round(5)
    imputar = ~geo_ok & centro["latitude"].notna()
    df.loc[imputar, ["latitude", "longitude"]] = centro[imputar]
    df["geo_aproximada"] = imputar
    relatorio["coordenada_aproximada"] = int(imputar.sum())

    limpo = adicionar_features(df).reset_index(drop=True)
    relatorio["linhas_saida"] = len(limpo)
    limpo.attrs["relatorio"] = relatorio
    return limpo


def main() -> None:
    v1 = limpar(carregar())
    v1.to_csv(SAIDA, index=False)
    print(f"{SAIDA.relative_to(RAIZ)} gravado")
    for motivo, n in v1.attrs["relatorio"].items():
        print(f"  {motivo}: {n}")


if __name__ == "__main__":
    main()
