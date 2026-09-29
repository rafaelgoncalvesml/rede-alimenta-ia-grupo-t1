"""
Baseline de prioridade: uma regra so por dias ate a validade.

    alta  se dias <= corte_alta
    media se dias <= corte_media
    baixa no resto

Os dois cortes sao aprendidos no treino, escolhendo o par que maximiza o F1 macro (a metrica-alvo,
ver docs/ia.md). Depois de aprendidos, so o `dias_ate_validade` entra na predicao. Qualquer modelo
que nao ganhe disso nao esta aprendendo nada alem de "vence logo, doa logo".
"""
import numpy as np
from sklearn.base import BaseEstimator, ClassifierMixin

from ml.features import PRIORIDADES


class BaselineDias(ClassifierMixin, BaseEstimator):
    def fit(self, X, y):
        dias = X["dias_ate_validade"].to_numpy()
        classe = np.array([PRIORIDADES.index(p) for p in y])
        candidatos = np.unique(dias)

        # conta[k, i] = quantos lotes da classe k tem dias <= candidatos[i]
        posicao = np.searchsorted(candidatos, dias)
        conta = np.stack([
            np.cumsum(np.bincount(posicao[classe == k], minlength=len(candidatos)))
            for k in range(len(PRIORIDADES))
        ])
        total = conta[:, -1]

        melhor, cortes = -1.0, None
        for i in range(len(candidatos)):
            for j in range(i, len(candidatos)):
                regioes = np.stack([conta[:, i], conta[:, j] - conta[:, i], total - conta[:, j]])
                acertos = np.diag(regioes)
                f1 = np.divide(2 * acertos, regioes.sum(axis=1) + total,
                               out=np.zeros(3), where=(regioes.sum(axis=1) + total) > 0)
                if f1.mean() > melhor:
                    melhor, cortes = f1.mean(), (int(candidatos[i]), int(candidatos[j]))

        self.cortes_ = cortes
        self.classes_ = np.array(PRIORIDADES)
        return self

    def predict(self, X):
        dias = X["dias_ate_validade"].to_numpy()
        corte_alta, corte_media = self.cortes_
        return np.where(dias <= corte_alta, "alta", np.where(dias <= corte_media, "media", "baixa"))
