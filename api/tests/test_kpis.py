from datetime import date, datetime, timedelta, timezone

import pytest

from api import kpis

HOJE = date.today()
VALIDADE = str(HOJE + timedelta(days=10))


def _lote(id_, kg, status, doador_id=1, prioridade="media", tipo="hortifruti"):
    return {"id": id_, "doador_id": doador_id, "quantidade_kg": kg, "status": status,
            "prioridade": prioridade, "tipo": tipo}


def _doacao(id_, lote_id, ong_id, status="confirmada", tempo=60.0, dia=(2026, 10, 6)):
    return {"id": id_, "lote_id": lote_id, "ong_id": ong_id, "status": status,
            "tempo_match_s": tempo, "confirmado_em": datetime(*dia, 12, 0, tzinfo=timezone.utc)}


ONGS = [{"id": 1, "estado": "SP"}, {"id": 2, "estado": "RJ"}]


# ---- calculo puro ----

def test_impacto_soma_so_o_que_foi_entregue():
    lotes = [_lote(1, 100, "doado"), _lote(2, 40, "reservado"), _lote(3, 10, "disponivel")]
    doacoes = [_doacao(1, 1, 1), _doacao(2, 2, 2)]
    r = kpis.calcula_impacto(lotes, doacoes, ONGS, fator=0.5)
    assert r["kg_doados"] == 100
    assert r["kg_em_andamento"] == 40            # reservado nao conta como salvo
    assert r["refeicoes_geradas"] == 200         # 100 kg / 0,5
    assert r["doacoes_confirmadas"] == 2
    assert r["ongs_atendidas"] == 1              # so a ONG 1 recebeu de fato
    assert r["lotes_por_status"] == {"doado": 1, "reservado": 1, "disponivel": 1}


def test_impacto_ignora_doacao_cancelada():
    lotes = [_lote(1, 100, "doado")]
    doacoes = [_doacao(1, 1, 1, status="cancelada"), _doacao(2, 1, 2)]
    r = kpis.calcula_impacto(lotes, doacoes, ONGS, fator=0.5)
    assert r["kg_doados"] == 100                 # o lote nao e contado duas vezes
    assert r["doacoes_canceladas"] == 1 and r["doacoes_confirmadas"] == 1


def test_impacto_tempo_medio_e_por_estado_e_por_dia():
    lotes = [_lote(1, 10, "doado"), _lote(2, 30, "doado"), _lote(3, 20, "doado")]
    doacoes = [_doacao(1, 1, 1, tempo=30, dia=(2026, 10, 5)),
               _doacao(2, 2, 1, tempo=90, dia=(2026, 10, 6)),
               _doacao(3, 3, 2, tempo=60, dia=(2026, 10, 6))]
    r = kpis.calcula_impacto(lotes, doacoes, ONGS, fator=1)
    assert r["tempo_medio_match_s"] == 60
    assert r["por_estado"] == [
        {"estado": "RJ", "doacoes": 1, "kg_doados": 20, "refeicoes_geradas": 20},
        {"estado": "SP", "doacoes": 2, "kg_doados": 40, "refeicoes_geradas": 40},
    ]
    assert r["por_dia"] == [
        {"data": "2026-10-05", "kg_doados": 10, "refeicoes_geradas": 10},
        {"data": "2026-10-06", "kg_doados": 50, "refeicoes_geradas": 50},
    ]


def test_impacto_sem_dados_nao_quebra():
    r = kpis.calcula_impacto([], [], [], fator=0.5)
    assert r["kg_doados"] == 0 and r["refeicoes_geradas"] == 0
    assert r["tempo_medio_match_s"] is None      # media de nada nao e zero
    assert r["por_estado"] == [] and r["por_dia"] == []


def test_impacto_leva_a_premissa_do_fator_na_resposta():
    r = kpis.calcula_impacto([], [], [], fator=0.4)
    assert r["fator_kg_por_refeicao"] == 0.4
    assert any("PREMISSA" in p and "0.4" in p for p in r["premissas"])


def test_ia_conta_classificados_e_sem_prioridade():
    lotes = [_lote(1, 1, "disponivel", prioridade="alta"),
             _lote(2, 1, "disponivel", prioridade="alta"),
             _lote(3, 1, "disponivel", prioridade="baixa", tipo="padaria"),
             _lote(4, 1, "disponivel", prioridade=None, tipo=None)]
    r = kpis.calcula_ia(lotes, None)["operacao"]
    assert r["lotes_total"] == 4 and r["classificados"] == 3 and r["sem_prioridade"] == 1
    assert r["taxa_classificacao"] == 0.75
    assert r["por_prioridade"] == {"alta": 2, "baixa": 1}
    assert r["por_tipo"] == {"hortifruti": 2, "padaria": 1}


def test_ia_sem_lotes_e_sem_metricas():
    r = kpis.calcula_ia([], None)
    assert r["modelo"] is None and r["operacao"]["taxa_classificacao"] is None
    assert any("metrics.json" in a for a in r["avisos"])


def test_ia_usa_as_metricas_reais_do_arquivo():
    metricas = kpis.le_metricas()
    assert metricas is not None, "models/metrics.json sumiu"
    r = kpis.calcula_ia([], metricas)
    escolhido = metricas["modelo_escolhido"]
    assert r["modelo"]["f1_macro_teste"] == metricas["teste"][escolhido]["f1_macro"]
    esperado = metricas["teste"][escolhido]["f1_macro"] - metricas["teste"]["baseline_dias"]["f1_macro"]
    assert r["modelo"]["ganho_sobre_baseline"] == pytest.approx(esperado, abs=1e-4)
    assert any("SIMULADO" in a for a in r["avisos"])  # o rotulo de simulado nao pode sumir


@pytest.mark.parametrize("valor", ["0", "-1"])
def test_fator_invalido_barra(monkeypatch, valor):
    monkeypatch.setenv("KG_POR_REFEICAO", valor)
    with pytest.raises(RuntimeError, match="KG_POR_REFEICAO"):
        kpis.kg_por_refeicao()


def test_fator_vem_do_ambiente(monkeypatch):
    monkeypatch.delenv("KG_POR_REFEICAO", raising=False)
    assert kpis.kg_por_refeicao() == kpis.KG_POR_REFEICAO_PADRAO
    monkeypatch.setenv("KG_POR_REFEICAO", "0.4")
    assert kpis.kg_por_refeicao() == 0.4


# ---- pela API, com cada papel enxergando so o que e dele ----

@pytest.fixture
def mundo(client, usuario_de, monkeypatch):
    monkeypatch.delenv("KG_POR_REFEICAO", raising=False)

    def doador(n):
        return {"nome": f"D{n}", "tipo_pessoa": "juridica", "documento": f"1234567800{n:04d}",
                "cidade": "X", "estado": "SP"}

    def ong(n, uf):
        return {"nome": f"O{n}", "cnpj": f"9876543200{n:04d}", "endereco": "R", "cidade": "X",
                "estado": uf, "capacidade_kg": 500, "necessidades": []}

    for n in (1, 2):
        client.post("/doadores", json=doador(n))
    client.post("/ongs", json=ong(1, "SP"))
    client.post("/ongs", json=ong(2, "RJ"))
    lote = {"descricao": "tomate", "quantidade_kg": 20, "validade": VALIDADE,
            "armazenamento": "refrigerado"}
    client.post("/lotes", json={**lote, "doador_id": 1})                        # 1 -> ONG 1, entregue
    client.post("/lotes", json={**lote, "doador_id": 2, "quantidade_kg": 50})   # 2 -> ONG 2, entregue
    client.post("/lotes", json={**lote, "doador_id": 1, "quantidade_kg": 5})    # 3 -> ONG 1, reservado
    client.post("/lotes", json={**lote, "doador_id": 2})                        # 4 disponivel
    for lote_id, ong_id in ((1, 1), (2, 2), (3, 1)):
        client.post("/doacoes", json={"lote_id": lote_id, "ong_id": ong_id})
    client.put("/lotes/1", json={"status": "doado"})
    client.put("/lotes/2", json={"status": "doado"})
    return {"admin": client, "doador1": usuario_de("doador", 1), "ong2": usuario_de("ong", 2)}


def test_api_admin_ve_tudo(mundo):
    r = mundo["admin"].get("/kpis/impacto").json()
    assert r["kg_doados"] == 70 and r["kg_em_andamento"] == 5
    assert r["refeicoes_geradas"] == 140          # fator padrao 0,5
    assert [e["estado"] for e in r["por_estado"]] == ["RJ", "SP"]
    assert r["lotes_por_status"] == {"doado": 2, "reservado": 1, "disponivel": 1}
    assert r["tempo_medio_match_s"] is not None and r["tempo_medio_match_s"] >= 0


def test_api_doador_so_soma_os_proprios_lotes(mundo):
    r = mundo["doador1"].get("/kpis/impacto").json()
    assert r["kg_doados"] == 20 and r["kg_em_andamento"] == 5
    assert r["lotes_por_status"] == {"doado": 1, "reservado": 1}


def test_api_ong_so_soma_o_que_recebeu(mundo):
    r = mundo["ong2"].get("/kpis/impacto").json()
    assert r["kg_doados"] == 50 and r["ongs_atendidas"] == 1
    assert [e["estado"] for e in r["por_estado"]] == ["RJ"]


def test_api_fator_do_ambiente_muda_as_refeicoes(mundo, monkeypatch):
    monkeypatch.setenv("KG_POR_REFEICAO", "1")
    assert mundo["admin"].get("/kpis/impacto").json()["refeicoes_geradas"] == 70


def test_api_kpis_ia(mundo):
    r = mundo["admin"].get("/kpis/ia").json()
    op = r["operacao"]
    assert r["modelo"]["modelo"] == "random_forest"
    assert op["lotes_total"] == 4
    assert sum(op["por_prioridade"].values()) == op["classificados"]
    assert op["lotes_total"] == op["classificados"] + op["sem_prioridade"]
    # doador ve as metricas do modelo (globais), mas a operacao so dos lotes dele
    d = mundo["doador1"].get("/kpis/ia").json()
    assert d["modelo"] == r["modelo"] and d["operacao"]["lotes_total"] == 2
