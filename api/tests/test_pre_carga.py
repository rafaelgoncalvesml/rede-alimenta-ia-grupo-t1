"""O modelo carrega quando a API sobe, nao no primeiro POST /lotes (9,8 s em producao no dia 23).
Se carregar falhar, a API sobe do mesmo jeito: o lote entra sem prioridade, como ja era."""
import logging

from fastapi.testclient import TestClient

from api import ia
from api.main import app
from ml.predict import carregar_modelo


def test_o_modelo_ja_esta_carregado_quando_a_api_termina_de_subir():
    carregar_modelo.cache_clear()

    with TestClient(app):
        assert carregar_modelo.cache_info().currsize == 1


def test_a_subida_registra_quanto_tempo_o_modelo_levou_pra_carregar(caplog):
    carregar_modelo.cache_clear()

    with caplog.at_level(logging.INFO), TestClient(app):
        pass

    assert any("modelo.carregado" in r.getMessage() and "segundos" in r.getMessage() for r in caplog.records)


def test_se_o_modelo_nao_carrega_a_api_sobe_mesmo_assim_e_o_erro_fica_no_log(monkeypatch, caplog):
    def quebra():
        raise FileNotFoundError("models/prioridade_v2.joblib")

    monkeypatch.setattr(ia, "carregar_modelo", quebra)

    with caplog.at_level(logging.ERROR), TestClient(app) as cliente:
        assert cliente.get("/health").status_code == 200

    assert any("modelo nao carregou na subida" in r.getMessage() for r in caplog.records)
