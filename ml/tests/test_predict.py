from datetime import date, timedelta

import pytest

from ml.limpeza import carregar, limpar
from ml.predict import predict
from ml.treinar import treinar

HOJE = date(2026, 9, 29)
CATEGORIAS = {"hortifruti", "padaria", "laticinios", "carnes_peixes", "preparados", "nao_pereciveis"}
CHAVES = {"categoria", "categoria_origem", "categoria_confianca", "perecivel", "prioridade",
          "probabilidades", "dias_ate_validade", "fora_do_frio", "modelo_versao"}


@pytest.fixture(scope="module")
def modelo():
    return treinar(limpar(carregar()))


def entrada(**mudancas) -> dict:
    base = dict(descricao="iogurte natural", quantidade_kg=20.0,
                validade=HOJE + timedelta(days=3), armazenamento="refrigerado")
    return {**base, **mudancas}


def test_tipo_informado_vale_e_a_ia_nao_reclassifica(modelo):
    # descricao de laticinio, mas o doador disse que e carne: quem manda e o `tipo`
    saida = predict(entrada(tipo="carnes_peixes"), hoje=HOJE, modelo=modelo)

    assert saida["categoria"] == "carnes_peixes"
    assert saida["categoria_origem"] == "informada"
    assert saida["categoria_confianca"] is None


def test_lote_vencido_e_recusado_mas_o_que_vence_hoje_ainda_vale(modelo):
    with pytest.raises(ValueError, match="vencido"):
        predict(entrada(validade=HOJE - timedelta(days=1)), hoje=HOJE, modelo=modelo)

    assert predict(entrada(validade=HOJE), hoje=HOJE, modelo=modelo)["dias_ate_validade"] == 0


@pytest.mark.parametrize("quantidade", [0, -5, float("nan"), float("inf"), "20", True, None])
def test_quantidade_que_nao_e_numero_positivo_e_recusada(modelo, quantidade):
    with pytest.raises(ValueError, match="quantidade_kg"):
        predict(entrada(quantidade_kg=quantidade), hoje=HOJE, modelo=modelo)


@pytest.mark.parametrize("campo, valor", [
    ("armazenamento", "geladeira"), ("armazenamento", None), ("armazenamento", "Ambiente"),
    ("tipo", "bebidas"), ("tipo", ""),
])
def test_armazenamento_e_tipo_fora_do_dominio_sao_recusados(modelo, campo, valor):
    with pytest.raises(ValueError, match=campo):
        predict(entrada(**{campo: valor}), hoje=HOJE, modelo=modelo)


@pytest.mark.parametrize("descricao", ["", "   ", None])
def test_sem_tipo_e_sem_descricao_nao_ha_como_classificar(modelo, descricao):
    with pytest.raises(ValueError, match="descricao"):
        predict(entrada(descricao=descricao), hoje=HOJE, modelo=modelo)


def test_com_tipo_informado_a_descricao_pode_faltar(modelo):
    assert predict(entrada(descricao="", tipo="padaria"), hoje=HOJE, modelo=modelo)["categoria"] == "padaria"


def test_aceita_o_lote_como_a_api_manda_validade_em_texto_e_campos_extras(modelo):
    lote_da_api = {"doador_id": 7, "id": 1, "status": "disponivel", "tipo": None, "descricao": "pao frances",
                   "quantidade_kg": 12, "validade": (HOJE + timedelta(days=2)).isoformat(),
                   "armazenamento": "ambiente"}

    saida = predict(lote_da_api, hoje=HOJE, modelo=modelo)

    assert saida["categoria"] == "padaria" and saida["dias_ate_validade"] == 2


@pytest.mark.parametrize("validade", ["29/09/2026", "amanha", None, 20260929])
def test_validade_que_nao_e_data_e_recusada(modelo, validade):
    with pytest.raises(ValueError, match="validade"):
        predict(entrada(validade=validade), hoje=HOJE, modelo=modelo)


@pytest.mark.parametrize("campo", ["validade", "quantidade_kg", "armazenamento"])
def test_campo_obrigatorio_ausente_vira_value_error_e_nao_key_error(modelo, campo):
    lote = entrada()
    del lote[campo]

    with pytest.raises(ValueError, match=campo):
        predict(lote, hoje=HOJE, modelo=modelo)


@pytest.mark.parametrize("descricao, esperada", [
    ("iogurtes naturais", "laticinios"),
    ("Filé de Tilápia congelado", "carnes_peixes"),
    ("tomates maduros", "hortifruti"),
    ("PAO FRANCES", "padaria"),
    ("arroz tipo 1 saco 5kg", "nao_pereciveis"),
    ("marmitas prontas de arroz e feijao", "preparados"),
])
def test_a_categoria_sai_da_descricao_mesmo_com_plural_acento_e_caixa_alta(modelo, descricao, esperada):
    saida = predict(entrada(descricao=descricao), hoje=HOJE, modelo=modelo)

    assert saida["categoria"] == esperada
    assert saida["categoria_origem"] == "modelo"
    assert 0.0 < saida["categoria_confianca"] <= 1.0


def test_lote_perecivel_que_vence_amanha_e_alta_e_arroz_com_meses_de_validade_e_baixa(modelo):
    urgente = predict(entrada(descricao="iogurte natural", validade=HOJE + timedelta(days=1)),
                      hoje=HOJE, modelo=modelo)
    tranquilo = predict(entrada(descricao="arroz tipo 1", armazenamento="ambiente", quantidade_kg=10,
                                validade=HOJE + timedelta(days=200)), hoje=HOJE, modelo=modelo)

    assert urgente["prioridade"] == "alta" and urgente["perecivel"] is True
    assert tranquilo["prioridade"] == "baixa" and tranquilo["perecivel"] is False


@pytest.mark.parametrize("descricao, tipo, armazenamento", [
    ("marmitas prontas de arroz e feijao", "preparados", "refrigerado"),
    ("pao frances do dia", "padaria", "ambiente"),
])
def test_perecivel_de_vida_curta_que_vence_amanha_e_alta(modelo, descricao, tipo, armazenamento):
    # o prazo absoluto pesa: falta 1 dia pra achar ONG, coletar e entregar (rotulo revisto em 13/10)
    saida = predict(entrada(descricao=descricao, tipo=tipo, armazenamento=armazenamento, quantidade_kg=30,
                            validade=HOJE + timedelta(days=1)), hoje=HOJE, modelo=modelo)

    assert saida["prioridade"] == "alta"


def test_perecivel_fora_do_frio_e_sinalizado_e_com_mais_dias_a_chance_de_alta_cai(modelo):
    quente = predict(entrada(descricao="leite pasteurizado", armazenamento="ambiente"), hoje=HOJE, modelo=modelo)
    frio = predict(entrada(descricao="leite pasteurizado", armazenamento="refrigerado"), hoje=HOJE, modelo=modelo)
    perto = predict(entrada(validade=HOJE + timedelta(days=1)), hoje=HOJE, modelo=modelo)
    longe = predict(entrada(validade=HOJE + timedelta(days=20)), hoje=HOJE, modelo=modelo)

    assert quente["fora_do_frio"] is True and frio["fora_do_frio"] is False
    assert perto["probabilidades"]["alta"] > longe["probabilidades"]["alta"]


def test_sem_passar_modelo_carrega_o_artefato_versionado_em_models():
    # e assim que a API chama: predict(lote). Precisa de `python -m ml.treinar` rodado e models/ commitado
    saida = predict(entrada(), hoje=HOJE)

    assert set(saida) == CHAVES
    assert saida["modelo_versao"] == "v2"


def test_contrato_de_saida_tem_as_chaves_e_so_valores_permitidos(modelo):
    saida = predict(entrada(), hoje=HOJE, modelo=modelo)

    assert set(saida) == CHAVES
    assert saida["categoria"] in CATEGORIAS
    assert saida["prioridade"] in {"alta", "media", "baixa"}
    assert set(saida["probabilidades"]) == {"alta", "media", "baixa"}
    assert sum(saida["probabilidades"].values()) == pytest.approx(1.0, abs=1e-6)
    assert saida["probabilidades"][saida["prioridade"]] == max(saida["probabilidades"].values())
    assert saida["dias_ate_validade"] == 3
    assert saida["modelo_versao"] == "v2"
