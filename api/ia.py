"""Ponte entre a API e o modelo do Charles (ml/predict.py).

Contrato esperado: predict(lote: dict) -> dict com a chave "prioridade" (alta,
media ou baixa). O lote vai com descricao, quantidade_kg, validade (ISO),
armazenamento e tipo. Enquanto o ml/predict.py nao existir (ou se o modelo
falhar), o lote e cadastrado sem prioridade em vez de derrubar o POST.
"""
import logging

log = logging.getLogger(__name__)

PRIORIDADES = {"alta", "media", "baixa"}

_predict = None
_ja_tentou = False


def _carrega():
    global _predict, _ja_tentou
    if not _ja_tentou:
        _ja_tentou = True
        try:
            from ml.predict import predict

            _predict = predict
        except ImportError as e:
            log.warning("modelo indisponivel, lotes ficam sem prioridade: %s", e)
    return _predict


def prioridade_do_lote(lote: dict) -> str | None:
    predict = _carrega()
    if predict is None:
        return None
    try:
        saida = predict(lote)
    except Exception:
        # o doador nao pode perder o cadastro por causa do modelo
        log.exception("predict() falhou")
        return None
    prioridade = saida.get("prioridade") if isinstance(saida, dict) else None
    if prioridade not in PRIORIDADES:
        log.error("predict() devolveu prioridade invalida: %r", prioridade)
        return None
    return prioridade
