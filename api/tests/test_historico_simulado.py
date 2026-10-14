"""O historico simulado alimenta o dashboard: tem que passar pelo mesmo calculo de KPI que a API usa,
estar rotulado SIMULADO em toda linha e nao contradizer a regra de negocio (capacidade, categoria)."""
import json
from collections import Counter

import pytest

from api import kpis
from data.gerar_historico_simulado import SAIDA, carregar_historico, gerar


@pytest.fixture(scope="module")
def historico():
    return gerar()


def test_toda_linha_vem_rotulada_simulado(historico):
    assert historico["origem"] == "SIMULADO"
    for tabela in ("ongs", "lotes", "doacoes"):
        assert historico[tabela] and all(l["origem"] == "SIMULADO" for l in historico[tabela]), tabela
    assert all("SIMULAD" in o["nome"].upper() for o in historico["ongs"])


def test_o_calculo_de_kpi_da_api_aceita_o_historico_e_fecha_as_contas(historico):
    h = carregar_historico(historico)

    r = kpis.calcula_impacto(h["lotes"], h["doacoes"], h["ongs"], fator=0.5)

    assert r["kg_doados"] > 0 and r["ongs_atendidas"] > 3
    assert r["refeicoes_geradas"] == round(r["kg_doados"] / 0.5, 1)
    assert sum(r["lotes_por_status"].values()) == len(h["lotes"])
    assert r["tempo_medio_match_s"] > 0
    assert round(sum(d["kg_doados"] for d in r["por_dia"]), 1) == pytest.approx(r["kg_doados"], abs=1.0)


def test_cada_doacao_respeita_a_regra_da_doacao_da_api(historico):
    lotes = {l["id"]: l for l in historico["lotes"]}
    ongs = {o["id"]: o for o in historico["ongs"]}
    for d in historico["doacoes"]:
        lote, ong = lotes[d["lote_id"]], ongs[d["ong_id"]]
        assert lote["quantidade_kg"] <= ong["capacidade_kg"]
        assert lote["tipo"] in ong["necessidades"]
        assert d["tempo_match_s"] > 0 and d["confirmado_em"] > lote["criado_em"]


def test_lote_doado_tem_exatamente_uma_doacao_confirmada_e_descartado_nenhuma(historico):
    confirmadas = Counter(d["lote_id"] for d in historico["doacoes"] if d["status"] == "confirmada")
    for l in historico["lotes"]:
        esperado = 1 if l["status"] in ("doado", "reservado") else 0
        assert confirmadas[l["id"]] == esperado, (l["id"], l["status"])


def test_a_mesma_semente_gera_exatamente_o_mesmo_historico():
    assert json.dumps(gerar(), sort_keys=True) == json.dumps(gerar(), sort_keys=True)
    assert json.dumps(gerar(semente=1), sort_keys=True) != json.dumps(gerar(semente=2), sort_keys=True)


def test_o_arquivo_versionado_e_o_que_o_gerador_produz_hoje():
    assert json.loads(SAIDA.read_text(encoding="utf-8")) == json.loads(json.dumps(gerar()))
