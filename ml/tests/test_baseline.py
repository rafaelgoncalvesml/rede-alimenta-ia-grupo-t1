import pandas as pd

from ml.baseline import BaselineDias


def treino_separavel():
    # 0 e 1 dia: alta | 2 a 5 dias: media | 6 a 12 dias: baixa
    dias = list(range(0, 13)) * 3
    y = ["alta" if d <= 1 else "media" if d <= 5 else "baixa" for d in dias]
    return pd.DataFrame({"dias_ate_validade": dias}), pd.Series(y)


def test_aprende_os_cortes_do_treino_e_aplica_em_dias_que_nunca_viu():
    X, y = treino_separavel()

    baseline = BaselineDias().fit(X, y)

    assert baseline.cortes_ == (1, 5)
    novos = pd.DataFrame({"dias_ate_validade": [0, 3, 30, 400]})
    assert list(baseline.predict(novos)) == ["alta", "media", "baixa", "baixa"]


def test_so_olha_dias_ate_validade_e_ignora_qualquer_outra_coluna():
    X, y = treino_separavel()
    X["quantidade_kg"] = 999.0

    baseline = BaselineDias().fit(X, y)

    outra = pd.DataFrame({"dias_ate_validade": [1], "quantidade_kg": [0.1], "categoria": ["padaria"]})
    assert list(baseline.predict(outra)) == ["alta"]
