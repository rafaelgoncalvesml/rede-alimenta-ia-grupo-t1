"""
Regras de feature usadas no treino (ml/limpeza.py, ml/treinar.py) e em producao (ml/predict.py).
Fica num lugar so pra o modelo nunca ver, em producao, uma feature calculada diferente do treino.
"""
import numpy as np
import pandas as pd

CATEGORIAS = ("hortifruti", "padaria", "laticinios", "carnes_peixes", "preparados", "nao_pereciveis")
ARMAZENAMENTOS = ("ambiente", "refrigerado", "congelado")
PRIORIDADES = ("alta", "media", "baixa")

# mesmo criterio do gerador do dataset (data/gerar_dataset_v0.py): 0 ambiente, 1 refrigerado, 2 congelado
FRIO = {"ambiente": 0, "refrigerado": 1, "congelado": 2}
FRIO_MINIMO = {"laticinios": 1, "carnes_peixes": 1, "preparados": 1}

COLUNAS_NUMERICAS = ["dias_ate_validade", "perecivel", "fora_do_frio", "log_quantidade_kg"]
COLUNAS_CATEGORICAS = ["categoria", "armazenamento"]


def adicionar_features(df: pd.DataFrame) -> pd.DataFrame:
    """Precisa de data_cadastro, validade, categoria e armazenamento. Nao altera o df de entrada."""
    df = df.copy()
    df["dias_ate_validade"] = (df["validade"] - df["data_cadastro"]).dt.days
    df["perecivel"] = df["categoria"] != "nao_pereciveis"
    df["fora_do_frio"] = df["armazenamento"].map(FRIO) < df["categoria"].map(FRIO_MINIMO).fillna(0)
    return df


def matriz_do_modelo(df: pd.DataFrame) -> pd.DataFrame:
    """Colunas que o modelo de prioridade enxerga, a partir de um df ja com adicionar_features."""
    X = df[["dias_ate_validade", "perecivel", "fora_do_frio", "categoria", "armazenamento"]].copy()
    X[["perecivel", "fora_do_frio"]] = X[["perecivel", "fora_do_frio"]].astype(int)
    X["log_quantidade_kg"] = np.log1p(df["quantidade_kg"])
    return X[COLUNAS_NUMERICAS + COLUNAS_CATEGORICAS]
