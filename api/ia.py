"""Ponte entre a API e o modelo do Charles (ml/predict.py). Contrato em docs/ia.md, secao 5."""
import logging

from ml.predict import predict

log = logging.getLogger(__name__)

PRIORIDADES = {"alta", "media", "baixa"}


def classificar_lote(lote: dict) -> dict:
    """Devolve {"tipo", "prioridade"} pra gravar no lote, ou {} se o modelo nao respondeu.

    ValueError do predict() e entrada que o modelo recusa (tipo fora das 6 categorias,
    descricao em branco sem tipo...): sobe pra rota responder 422. Qualquer outra falha
    (joblib sumiu, versao do scikit-learn trocou) e problema nosso, nao do doador, entao
    o lote entra sem prioridade e o erro fica no log.
    """
    try:
        saida = predict(lote)
    except ValueError:
        raise
    except Exception:
        log.exception("predict() falhou, lote segue sem prioridade")
        return {}
    prioridade = saida.get("prioridade") if isinstance(saida, dict) else None
    if prioridade not in PRIORIDADES:
        log.error("predict() devolveu prioridade invalida: %r", prioridade)
        return {}
    return {"tipo": saida.get("categoria"), "prioridade": prioridade}
