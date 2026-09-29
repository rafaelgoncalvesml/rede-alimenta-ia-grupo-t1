"""
Treina o baseline, a regressao logistica e o Random Forest de prioridade, escolhe entre os dois
modelos por validacao cruzada no treino e mede tudo uma unica vez no teste. Treina tambem o
classificador de categoria (a partir da descricao). Grava models/prioridade_v1.joblib e
models/metrics.json. Rodar da raiz do repo:
    python -m ml.treinar

Metrica-alvo: F1 macro sobre a prioridade (justificativa em docs/ia.md). Tudo SIMULADO: o dataset
v0 e simulado, entao as metricas dizem que o pipeline funciona, nao que a prioridade reflete descarte real.
"""
import json
from pathlib import Path

import joblib
import numpy as np
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, recall_score
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from ml.baseline import BaselineDias
from ml.features import COLUNAS_CATEGORICAS, COLUNAS_NUMERICAS, PRIORIDADES, matriz_do_modelo
from ml.limpeza import carregar, limpar

RAIZ = Path(__file__).resolve().parents[1]
MODELO = RAIZ / "models" / "prioridade_v1.joblib"
METRICAS = RAIZ / "models" / "metrics.json"

VERSAO = "v1"
SEED = 42
TAMANHO_TESTE = 0.2
DOBRAS_CV = 5


def _pre_processamento() -> ColumnTransformer:
    return ColumnTransformer([
        ("num", StandardScaler(), COLUNAS_NUMERICAS),
        ("cat", OneHotEncoder(handle_unknown="ignore"), COLUNAS_CATEGORICAS),
    ])


def _candidatos() -> dict:
    return {
        "regressao_logistica": Pipeline([
            ("pre", _pre_processamento()), ("clf", LogisticRegression(max_iter=1000))]),
        "random_forest": Pipeline([
            ("pre", _pre_processamento()),
            # min_samples_leaf=5 e 100 arvores: escolhido por validacao cruzada no treino entre 6
            # combinacoes (F1 macro 0,655 contra 0,625 com folhas de 1 lote) e o artefato cai de 9 MB pra ~1 MB
            ("clf", RandomForestClassifier(n_estimators=100, min_samples_leaf=5, random_state=SEED))]),
    }


def avaliar(y_true, y_pred) -> dict:
    y_true, y_pred = np.asarray(y_true), np.asarray(y_pred)
    alta = y_true == "alta"
    return {
        "f1_macro": round(f1_score(y_true, y_pred, average="macro"), 4),
        "acuracia": round(accuracy_score(y_true, y_pred), 4),
        "recall_alta": round(recall_score(y_true, y_pred, labels=["alta"], average=None)[0], 4),
        # o erro que mais custa: lote que ia estragar e o modelo manda pro fim da fila
        "alta_prevista_como_baixa": round(float((y_pred[alta] == "baixa").mean()), 4),
        "matriz_confusao": {
            "ordem": list(PRIORIDADES),
            "linhas_real_colunas_previsto": confusion_matrix(y_true, y_pred, labels=PRIORIDADES).tolist(),
        },
    }


def _classificador_de_categoria() -> Pipeline:
    # n-gramas de caractere aguentam plural, erro de digitacao e palavra que nao viu inteira
    return Pipeline([
        ("tfidf", TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), strip_accents="unicode")),
        ("clf", LogisticRegression(max_iter=1000)),
    ])


def treinar(v1) -> dict:
    """Recebe o dataset v1 (saida de limpar) e devolve o pacote que o predict() usa."""
    treino, teste = train_test_split(
        v1, test_size=TAMANHO_TESTE, stratify=v1["prioridade"], random_state=SEED)
    X_treino, y_treino = matriz_do_modelo(treino), treino["prioridade"]
    X_teste, y_teste = matriz_do_modelo(teste), teste["prioridade"]

    cv = StratifiedKFold(DOBRAS_CV, shuffle=True, random_state=SEED)
    candidatos = {"baseline_dias": BaselineDias(), **_candidatos()}
    cv_f1 = {
        nome: round(float(cross_val_score(m, X_treino, y_treino, cv=cv, scoring="f1_macro").mean()), 4)
        for nome, m in candidatos.items()
    }

    # o baseline nao entra na escolha: nao tem predict_proba e existe pra ser superado
    escolhido = max(_candidatos(), key=lambda nome: cv_f1[nome])
    for m in candidatos.values():
        m.fit(X_treino, y_treino)

    previsto = {nome: m.predict(X_teste) for nome, m in candidatos.items()}
    modelo = candidatos[escolhido]

    por_categoria = {
        cat: {"n": int(len(grupo)),
              "f1_macro": round(f1_score(grupo["prioridade"], modelo.predict(matriz_do_modelo(grupo)),
                                         average="macro"), 4)}
        for cat, grupo in teste.groupby("categoria")
    }

    com_texto_treino = treino[treino["descricao"].fillna("").str.strip() != ""]
    com_texto_teste = teste[teste["descricao"].fillna("").str.strip() != ""]
    classificador = _classificador_de_categoria().fit(com_texto_treino["descricao"], com_texto_treino["categoria"])
    acerto_categoria = accuracy_score(com_texto_teste["categoria"],
                                      classificador.predict(com_texto_teste["descricao"]))

    metricas = {
        "versao": VERSAO,
        "dataset": "data/lotes_v1.csv (SIMULADO)",
        "metrica_alvo": "f1_macro sobre prioridade (alta, media, baixa)",
        "n_treino": int(len(treino)),
        "n_teste": int(len(teste)),
        "seed": SEED,
        "cortes_do_baseline": list(candidatos["baseline_dias"].cortes_),
        "validacao_cruzada_f1_macro": cv_f1,
        "modelo_escolhido": escolhido,
        "teste": {nome: avaliar(y_teste, p) for nome, p in previsto.items()},
        "por_categoria_no_teste": por_categoria,
        "classificador_de_categoria": {
            "acuracia_teste": round(float(acerto_categoria), 4),
            "n_treino": int(len(com_texto_treino)),
            "n_teste": int(len(com_texto_teste)),
            "aviso": "SIMULADO: as descricoes saem de listas fixas de palavras por categoria, "
                     "entao esse numero e otimista e nao vale como evidencia de texto real",
        },
    }
    return {"versao": VERSAO, "prioridade": modelo, "categoria": classificador, "metricas": metricas}


def main() -> None:
    pacote = treinar(limpar(carregar()))
    MODELO.parent.mkdir(exist_ok=True)
    joblib.dump(pacote, MODELO)
    METRICAS.write_text(json.dumps(pacote["metricas"], indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    m = pacote["metricas"]
    print(f"modelo escolhido: {m['modelo_escolhido']} | cortes do baseline: {m['cortes_do_baseline']}")
    print("F1 macro (validacao cruzada no treino):", m["validacao_cruzada_f1_macro"])
    for nome, r in m["teste"].items():
        print(f"  teste {nome:20s} f1_macro={r['f1_macro']}  acuracia={r['acuracia']}  "
              f"recall_alta={r['recall_alta']}  alta->baixa={r['alta_prevista_como_baixa']}")
    print("classificador de categoria:", m["classificador_de_categoria"]["acuracia_teste"])
    print(f"gravado: {MODELO.relative_to(RAIZ)} e {METRICAS.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
