import pytest

from ml.matching import matching

SE = (-23.5505, -46.6333)  # centro de Sao Paulo


def doador(**mudancas) -> dict:
    return {"cidade": "Sao Paulo", "estado": "SP", "latitude": SE[0], "longitude": SE[1], **mudancas}


def ong(id, lat=SE[0], lon=SE[1], **mudancas) -> dict:
    base = {"id": id, "nome": f"ONG {id}", "cidade": "Sao Paulo", "estado": "SP",
            "latitude": lat, "longitude": lon, "capacidade_kg": 500.0,
            "necessidades": ["hortifruti", "padaria"]}
    return {**base, **mudancas}


def lote(**mudancas) -> dict:
    return {"quantidade_kg": 100.0, "tipo": "hortifruti", **mudancas}


def test_descarta_ong_que_nao_aceita_a_categoria_ou_nao_aguenta_o_peso_e_diz_o_motivo():
    ongs = [
        ong(1),
        ong(2, necessidades=["padaria"]),
        ong(3, capacidade_kg=99.9),
        ong(4, capacidade_kg=100.0),  # exatamente o peso do lote: aguenta (a doacao so recusa se passar)
        ong(5, necessidades=[]),      # ONG sem necessidades nao recebe nada (decisao do dia 20)
    ]

    resultado = matching(lote(quantidade_kg=100.0, tipo="hortifruti"), doador(), ongs)

    assert {r["ong_id"] for r in resultado["ranking"]} == {1, 4}
    assert resultado["descartadas"] == [
        {"ong_id": 2, "motivo": "categoria"},
        {"ong_id": 3, "motivo": "capacidade"},
        {"ong_id": 5, "motivo": "categoria"},
    ]


def test_lote_sem_tipo_nao_filtra_por_categoria_porque_o_modelo_pode_ter_falhado():
    ongs = [ong(1, necessidades=["padaria"]), ong(2, necessidades=[])]

    resultado = matching(lote(tipo=None), doador(), ongs)

    assert [r["ong_id"] for r in resultado["ranking"]] == [1, 2]
    assert resultado["descartadas"] == []


def test_ordena_da_mais_perto_pra_mais_longe_desempata_pelo_id_e_numera_a_posicao():
    ongs = [
        ong(1, lat=-22.9099, lon=-47.0626),   # Campinas, ~84 km
        ong(2, lat=-23.5614, lon=-46.6559),   # a ~2,5 km
        ong(3, lat=-23.4543, lon=-46.5337),   # Guarulhos, ~14 km
        ong(4, lat=-23.5614, lon=-46.6559),   # mesma coordenada da 2: empata, perde pelo id
    ]

    ranking = matching(lote(), doador(), ongs)["ranking"]

    assert [r["ong_id"] for r in ranking] == [2, 4, 3, 1]
    assert [r["posicao"] for r in ranking] == [1, 2, 3, 4]
    assert ranking[0]["distancia_km"] < ranking[2]["distancia_km"] < ranking[3]["distancia_km"]


def test_score_e_a_distancia_dividida_pelo_raio_de_referencia_de_100_km_limitado_a_1():
    ongs = [
        ong(1, lat=-23.0, lon=-46.0),    # no mesmo ponto do doador: 0 km
        ong(2, lat=-23.5, lon=-46.0),    # meio grau de latitude: 55,5975 km
        ong(3, lat=-24.0, lon=-46.0),    # 111,195 km: passa do raio, o score trava em 1
    ]

    ranking = matching(lote(), doador(latitude=-23.0, longitude=-46.0), ongs)["ranking"]

    assert [r["score"] for r in ranking] == [0.0, 0.556, 1.0]


def test_score_de_uma_ong_nao_muda_com_as_outras_candidatas():
    sozinha = matching(lote(), doador(), [ong(1, lat=-23.5614, lon=-46.6559)])["ranking"][0]["score"]
    junto = matching(lote(), doador(), [ong(1, lat=-23.5614, lon=-46.6559),
                                        ong(2, lat=-22.9099, lon=-47.0626)])["ranking"][0]["score"]

    assert sozinha == junto > 0


def test_ong_sem_coordenada_usa_o_centro_da_cidade_e_fica_marcada_como_aproximada():
    # cidade escrita como a Receita escreve (maiuscula, com acento) e UF em minuscula: tem que casar
    sem_coord = ong(2, lat=None, lon=None, cidade="SÃO PAULO", estado="sp")

    ranking = matching(lote(), doador(), [ong(1, lat=-23.5614, lon=-46.6559), sem_coord])["ranking"]

    por_id = {r["ong_id"]: r for r in ranking}
    assert por_id[2]["geo_aproximada"] is True and por_id[2]["distancia_km"] == 0.0
    assert por_id[1]["geo_aproximada"] is False


@pytest.mark.parametrize("lat, lon", [(0.0, 0.0), (-46.63, -23.55), (40.7, -74.0)])
def test_coordenada_fora_do_brasil_zerada_ou_trocada_conta_como_ausente(lat, lon):
    # 0,0 (placeholder), latitude e longitude trocadas e Nova York: a mesma regra da limpeza do dataset
    ranking = matching(lote(), doador(), [ong(1, lat=lat, lon=lon)])["ranking"]

    assert ranking[0]["geo_aproximada"] is True
    assert ranking[0]["distancia_km"] == 0.0


def test_ong_sem_coordenada_em_cidade_sem_centro_conhecido_e_descartada_em_vez_de_inventada():
    ongs = [ong(1), ong(2, lat=None, lon=None, cidade="Santos", estado="SP")]

    resultado = matching(lote(), doador(), ongs)

    assert [r["ong_id"] for r in resultado["ranking"]] == [1]
    assert resultado["descartadas"] == [{"ong_id": 2, "motivo": "sem_coordenada"}]


def test_doador_sem_coordenada_usa_o_centro_da_cidade_e_marca_todas_as_distancias_como_aproximadas():
    ranking = matching(lote(), doador(latitude=None, longitude=None), [ong(1)])["ranking"]

    assert ranking[0]["geo_aproximada"] is True
    assert ranking[0]["distancia_km"] == 0.0  # a ONG esta no centro de Sao Paulo, o mesmo ponto do fallback


def test_doador_sem_coordenada_e_sem_centro_conhecido_nao_tem_como_calcular_distancia():
    with pytest.raises(ValueError, match="doador"):
        matching(lote(), doador(latitude=None, longitude=None, cidade="Santos"), [ong(1)])


def test_centros_do_fallback_batem_com_as_cidades_que_o_gerador_do_dataset_usa():
    from data.gerar_dataset_v0 import CIDADES
    from ml.geo import CENTROS_CIDADES, _chave_cidade

    do_gerador = {_chave_cidade(nome, uf): (lat, lon) for nome, uf, lat, lon, _peso in CIDADES}

    assert CENTROS_CIDADES == do_gerador


def test_distancia_e_haversine_um_grau_de_latitude_sao_111_195_km():
    # valor analitico: arco de meridiano de 1 grau = raio medio (6371,0088 km) * pi / 180
    resultado = matching(lote(), doador(latitude=-23.0, longitude=-46.0), [ong(1, lat=-24.0, lon=-46.0)])

    assert resultado["ranking"][0]["distancia_km"] == pytest.approx(111.195, abs=0.01)
