"""Ponte entre a API e o modelo do Charles (ml/predict.py). Contrato em docs/ia.md, secao 5."""
import logging
import time

from api import auditoria
from ml.predict import carregar_modelo, predict

log = logging.getLogger(__name__)


def _memoria_pico_mb() -> float | None:
    # pico de memoria do processo: o plano free do Render nao mostra memoria, o log mostra.
    # `resource` so existe em Linux/macOS (o container); no Windows volta None.
    try:
        import resource
    except ImportError:
        return None
    return round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)  # Linux da em KB


def pre_carregar_modelo() -> None:
    """Chamado quando a API sobe: tira do primeiro POST /lotes o tempo de carregar o joblib (9,8 s
    em producao, docs/checkpoint-dia23.md). Falhar aqui nao derruba a API: o POST /lotes tenta de
    novo e, se falhar de novo, o lote entra sem prioridade, como ja era."""
    inicio = time.perf_counter()
    try:
        carregar_modelo()
    except Exception:
        log.exception("modelo nao carregou na subida; o POST /lotes tenta de novo")
        return
    auditoria.registrar("modelo.carregado", segundos=round(time.perf_counter() - inicio, 2),
                        memoria_pico_mb=_memoria_pico_mb())

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
