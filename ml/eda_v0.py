"""
EDA inicial do dataset v0: nulos, duplicados, balanceamento, outliers e coerencia.
Rodar da raiz do repo:
    python ml/eda_v0.py
Le data/lotes_v0.csv e escreve o relatorio em ml/eda_v0.md.
"""
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
ENTRADA = RAIZ / "data" / "lotes_v0.csv"
SAIDA = RAIZ / "ml" / "eda_v0.md"
FRIO_MINIMO = {"laticinios": "refrigerado", "carnes_peixes": "refrigerado", "preparados": "refrigerado"}


def bloco(obj) -> str:
    return "```\n" + obj.to_string() + "\n```\n"


def main() -> None:
    df = pd.read_csv(ENTRADA, parse_dates=["data_cadastro", "validade"])
    df["dias_ate_validade"] = (df["validade"] - df["data_cadastro"]).dt.days

    nulos = df.isna().sum()
    nulos = nulos[nulos > 0].to_frame("nulos")
    nulos["%"] = (nulos["nulos"] / len(df) * 100).round(1)

    colunas_conteudo = [c for c in df.columns if c != "lote_id"]
    duplicados = df[df.duplicated(subset=colunas_conteudo, keep=False)]
    n_dup = int(df.duplicated(subset=colunas_conteudo).sum())

    q1, q3 = df["quantidade_kg"].quantile([0.25, 0.75])
    teto = q3 + 3 * (q3 - q1)
    outliers = df[df["quantidade_kg"] > teto]
    # comparado ao proprio setor: 100x a mediana separa erro de unidade de lote grande
    razao_setor = df["quantidade_kg"] / df.groupby("setor_doador")["quantidade_kg"].transform("median")
    erro_unidade = df[razao_setor > 100]

    vencidos = df[df["dias_ate_validade"] < 0]
    fora_do_frio = df[df.apply(
        lambda r: r["categoria"] in FRIO_MINIMO and r["armazenamento"] == "ambiente", axis=1)]

    balanco = df["prioridade"].value_counts()
    razao = balanco.max() / balanco.min()

    partes = [
        "# EDA do dataset v0 (SIMULADO)\n",
        f"Gerado por `ml/eda_v0.py` a partir de `data/lotes_v0.csv`. "
        f"{len(df)} linhas, {df.shape[1] - 1} colunas originais "
        "(+ `dias_ate_validade`, calculada aqui).\n",
        "## 1. Tipos\n", bloco(df.dtypes.to_frame("dtype")),
        "## 2. Nulos\n", bloco(nulos),
        f"## 3. Duplicados\n\n{n_dup} lotes repetidos com `lote_id` diferente "
        "(mesmo conteudo cadastrado duas vezes). Exemplo:\n",
        bloco(duplicados.sort_values(colunas_conteudo).head(4)[
            ["lote_id", "descricao", "quantidade_kg", "validade"]]),
        "## 4. Balanceamento do alvo (`prioridade`)\n", bloco(df["prioridade"].value_counts()),
        f"Razao maior/menor classe: {razao:.2f}. Desbalanceamento leve, "
        "da pra usar split estratificado sem reamostragem.\n",
        "### Categoria e perecibilidade\n", bloco(df["categoria"].value_counts()),
        bloco(df["perecivel"].value_counts()),
        "## 5. Outliers em `quantidade_kg`\n", bloco(df["quantidade_kg"].describe().round(1)),
        f"Pelo IQR global (acima de Q3 + 3*IQR = {teto:.1f} kg) sao {len(outliers)} lotes, "
        "mas a maioria e lote grande legitimo de supermercado ou industria. Comparando "
        "com a mediana do proprio setor, ha um corte claro: "
        f"{len(erro_unidade)} lotes passam de 100x a mediana do setor, e o proximo fica "
        "abaixo de 25x. Esses tem cara de gramas digitadas como kg:\n",
        bloco(erro_unidade.sort_values("quantidade_kg", ascending=False)[
            ["lote_id", "setor_doador", "descricao", "quantidade_kg"]]),
        "Limite: um erro de unidade num lote pequeno (0,5 kg virando 500 kg) cai dentro "
        "da faixa plausivel e nao e detectavel so pela quantidade. Na API, a defesa e "
        "validar no cadastro (teto por setor, confirmacao acima de X kg).\n",
        "## 6. Dias ate a validade\n", bloco(df["dias_ate_validade"].describe().round(1)),
        f"{len(vencidos)} lotes ja chegam vencidos (dias < 0). Pela regra de negocio "
        "lote vencido nao pode ser doado: sai do treino e a API deve recusar no cadastro.\n",
        "## 7. Coerencia categoria x armazenamento\n",
        bloco(pd.crosstab(df["categoria"], df["armazenamento"].fillna("(nulo)"))),
        f"{len(fora_do_frio)} lotes de categoria que exige frio registrados em ambiente. "
        "Nao e erro de cadastro: e o caso de maior risco que o modelo precisa capturar.\n",
        "## 8. Prioridade por categoria (% da linha)\n",
        bloco((pd.crosstab(df["categoria"], df["prioridade"], normalize="index") * 100)
              .round(1)[["alta", "media", "baixa"]]),
        "## 9. O que vai pra limpeza (dataset v1, dia 5)\n",
        f"- Remover os {n_dup} duplicados de conteudo.\n"
        f"- Remover os {len(vencidos)} lotes vencidos.\n"
        f"- Dividir por 1000 os {len(erro_unidade)} erros de unidade; manter os demais "
        "lotes grandes.\n"
        "- `armazenamento` nulo: imputar pela moda da categoria ou descartar; decidir no v1.\n"
        "- `descricao` vazia: manter, a categoria ja vem preenchida; so atrapalha o "
        "classificador de texto.\n"
        "- `latitude`/`longitude` nulas: nao afetam a prioridade, mas o matching precisa; "
        "geocodificar pela cidade ou excluir do matching.\n"
        "- Features pro v1: `dias_ate_validade`, `perecivel`, `categoria`, "
        "`armazenamento`, flag de fora do frio, `quantidade_kg`.\n",
    ]
    SAIDA.write_text("\n".join(partes), encoding="utf-8")
    print(f"Relatorio gravado em {SAIDA}")


if __name__ == "__main__":
    main()
