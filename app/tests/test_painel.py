from app.services import painel

ONGS = [
    {"id": 1, "nome": "ONG A", "cidade": "Sao Paulo", "estado": "SP", "latitude": -23.5, "longitude": -46.6},
    {"id": 2, "nome": "ONG B", "cidade": "Osasco", "estado": "SP", "latitude": -23.53, "longitude": -46.79},
    {"id": 3, "nome": "ONG sem coordenada", "cidade": "Campinas", "estado": "SP", "latitude": None, "longitude": None},
]
LOTES = [
    {"id": 1, "quantidade_kg": 10.0, "status": "doado"},
    {"id": 2, "quantidade_kg": 5.5, "status": "doado"},
    {"id": 3, "quantidade_kg": 100.0, "status": "reservado"},
    {"id": 4, "quantidade_kg": 7.0, "status": "doado"},
]


def doacao(lote_id, ong_id, status="confirmada"):
    return {"lote_id": lote_id, "ong_id": ong_id, "status": status}


def test_so_soma_lote_entregue_com_doacao_confirmada():
    doacoes = [doacao(1, 1), doacao(2, 1), doacao(3, 1), doacao(4, 2, "cancelada")]
    pontos = painel.kg_entregue_por_ong(ONGS, LOTES, doacoes)
    assert [(p["ong"], p["kg"], p["doacoes"]) for p in pontos] == [("ONG A", 15.5, 2)]


def test_ong_sem_coordenada_fica_fora_do_mapa():
    pontos = painel.kg_entregue_por_ong(ONGS, LOTES, [doacao(1, 3)])
    assert pontos == []


def test_kg_por_cidade_junta_ongs_da_mesma_cidade_e_ordena():
    pontos = [
        {"cidade": "Osasco", "estado": "SP", "kg": 3.0, "doacoes": 1},
        {"cidade": "Sao Paulo", "estado": "SP", "kg": 10.0, "doacoes": 2},
        {"cidade": "Sao Paulo", "estado": "SP", "kg": 5.0, "doacoes": 1},
    ]
    assert painel.kg_por_cidade(pontos) == [
        {"cidade": "Sao Paulo", "estado": "SP", "kg": 15.0, "doacoes": 3},
        {"cidade": "Osasco", "estado": "SP", "kg": 3.0, "doacoes": 1},
    ]


def test_historico_do_repo_fecha_com_a_soma_dos_lotes():
    historico = painel.carrega_historico()
    assert historico is not None
    pontos = painel.kg_entregue_por_ong(historico["ongs"], historico["lotes"], historico["doacoes"])
    lote_por_id = {lote["id"]: lote for lote in historico["lotes"]}
    esperado = sum(
        lote_por_id[d["lote_id"]]["quantidade_kg"]
        for d in historico["doacoes"]
        if d["status"] == "confirmada" and lote_por_id[d["lote_id"]]["status"] == "doado"
    )
    assert abs(sum(p["kg"] for p in pontos) - esperado) < 1


def test_resumo_seguranca_conta_do_proprio_json():
    dados = {
        "gates": [{"status": "passou"}, {"status": "falhou"}, {"status": "passou"}],
        "mitigadas": [{"achados": 3}, {"achados": 4}],
        "aceitos": [{}, {}],
    }
    assert painel.resumo_seguranca(dados) == {"gates_total": 3, "gates_ok": 2, "mitigadas": 7, "aceitos": 2}


def test_seguranca_json_versionado_tem_as_secoes_que_a_tela_le():
    dados = painel.carrega_seguranca()
    assert dados is not None
    for chave in ("medido_agora", "gates", "mitigadas", "aceitos", "gerado_em"):
        assert chave in dados
    assert {"bandit", "pip_audit", "ruff", "testes"} <= set(dados["medido_agora"])


def test_arquivo_ausente_devolve_none(tmp_path):
    assert painel.carrega_seguranca(tmp_path / "nao_existe.json") is None
    assert painel.carrega_historico([tmp_path / "nao_existe.json"]) is None
