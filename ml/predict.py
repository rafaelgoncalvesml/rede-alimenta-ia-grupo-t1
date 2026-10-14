"""
predict(): o que a API chama ao cadastrar um lote (POST /lotes).

Entrada (dict, aceita os campos do Lote da API; chaves extras sao ignoradas):
    descricao      str    texto livre; obrigatorio se `tipo` nao vier
    quantidade_kg  float  > 0
    validade       date ou "AAAA-MM-DD"; nao pode estar vencida
    armazenamento  "ambiente" | "refrigerado" | "congelado"
    tipo           opcional; uma das 6 categorias. Se vier, a IA nao reclassifica

Saida (dict):
    categoria            uma das 6: hortifruti, padaria, laticinios, carnes_peixes, preparados, nao_pereciveis
    categoria_origem     "informada" (veio em `tipo`) ou "modelo" (classificada pela descricao)
    categoria_confianca  probabilidade da categoria quando "modelo"; None quando "informada"
    perecivel            bool, derivado da categoria
    prioridade           "alta" | "media" | "baixa"
    probabilidades       {"alta": p, "media": p, "baixa": p}, soma 1
    dias_ate_validade    int, contado a partir de `hoje`
    fora_do_frio         bool: a categoria exige frio e o armazenamento e ambiente
    modelo_versao        str

Entrada invalida (inclusive campo ausente) levanta ValueError com a mensagem pronta pra virar 422.
"""
import functools
import math
import re
from datetime import date, datetime
from pathlib import Path

import joblib
import pandas as pd

from ml.features import (
    ARMAZENAMENTOS,
    CATEGORIAS,
    PRIORIDADES,
    adicionar_features,
    matriz_do_modelo,
)

# quem le define o caminho e o treino (ml/treinar.py) importa daqui: a API nao carrega codigo de treino
MODELO = Path(__file__).resolve().parents[1] / "models" / "prioridade_v2.joblib"

DATA_ISO = re.compile(r"\d{4}-\d{2}-\d{2}")


@functools.lru_cache(maxsize=1)
def carregar_modelo(caminho=MODELO) -> dict:
    # joblib e pickle: carregar arquivo de fonte desconhecida executa codigo. Aqui o arquivo e
    # gerado por ml/treinar.py e versionado no proprio repo; nunca apontar isto pra .joblib de fora.
    return joblib.load(caminho)  # nosec B301


def _validade(valor) -> date:
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    # so AAAA-MM-DD: date.fromisoformat aceitaria tambem "20260929" e "2026-W40-2" desde o Python 3.11
    if isinstance(valor, str) and DATA_ISO.fullmatch(valor):
        try:
            return date.fromisoformat(valor)
        except ValueError:
            pass
    raise ValueError(f"validade deve ser uma data AAAA-MM-DD valida, recebi {valor!r}")


def _quantidade(valor) -> float:
    if isinstance(valor, bool) or not isinstance(valor, (int, float)) or not 0 < valor < math.inf:
        raise ValueError(f"quantidade_kg deve ser um numero maior que zero, recebi {valor!r}")
    return float(valor)


def predict(lote: dict, hoje: date | None = None, modelo: dict | None = None) -> dict:
    hoje = hoje or date.today()
    modelo = modelo or carregar_modelo()

    validade = _validade(lote.get("validade"))
    if validade < hoje:
        raise ValueError(f"lote vencido: validade {validade.isoformat()} e anterior a {hoje.isoformat()}")
    quantidade = _quantidade(lote.get("quantidade_kg"))
    armazenamento = lote.get("armazenamento")
    if armazenamento not in ARMAZENAMENTOS:
        raise ValueError(f"armazenamento deve ser um de {ARMAZENAMENTOS}, recebi {armazenamento!r}")
    tipo = lote.get("tipo")
    if tipo is not None and tipo not in CATEGORIAS:
        raise ValueError(f"tipo deve ser um de {CATEGORIAS} ou ficar vazio, recebi {tipo!r}")
    descricao = lote.get("descricao")
    if tipo is None and not (isinstance(descricao, str) and descricao.strip()):
        raise ValueError("descricao e obrigatoria quando tipo nao e informado: sem ela nao ha como classificar")

    if tipo is not None:
        categoria, origem, confianca = tipo, "informada", None
    else:
        categoria = modelo["categoria"].predict([descricao])[0]
        origem = "modelo"
        confianca = float(modelo["categoria"].predict_proba([descricao])[0].max())

    features = adicionar_features(pd.DataFrame([{
        "data_cadastro": pd.Timestamp(hoje), "validade": pd.Timestamp(validade),
        "categoria": categoria, "armazenamento": armazenamento, "quantidade_kg": quantidade,
    }]))
    pipeline = modelo["prioridade"]
    proba = dict(
        zip(pipeline.classes_, pipeline.predict_proba(matriz_do_modelo(features))[0], strict=True)
    )
    probabilidades = {p: float(proba[p]) for p in PRIORIDADES}

    return {
        "categoria": categoria,
        "categoria_origem": origem,
        "categoria_confianca": confianca,
        "perecivel": bool(features.loc[0, "perecivel"]),
        "prioridade": max(probabilidades, key=probabilidades.get),
        "probabilidades": probabilidades,
        "dias_ate_validade": int(features.loc[0, "dias_ate_validade"]),
        "fora_do_frio": bool(features.loc[0, "fora_do_frio"]),
        "modelo_versao": modelo["versao"],
    }
