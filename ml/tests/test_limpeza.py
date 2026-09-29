import pandas as pd

from ml.limpeza import limpar


def lote(**mudancas) -> dict:
    base = dict(
        lote_id=1, data_cadastro="2026-09-01", setor_doador="supermercado", tipo_doador="PJ",
        cidade="Sao Paulo", uf="SP", latitude=-23.55, longitude=-46.63,
        descricao="caixa de tomate", categoria="hortifruti", perecivel=True,
        armazenamento="refrigerado", quantidade_kg=20.0, validade="2026-09-05", prioridade="alta",
    )
    return {**base, **mudancas}


def df_de(*linhas: dict) -> pd.DataFrame:
    df = pd.DataFrame(linhas)
    df["data_cadastro"] = pd.to_datetime(df["data_cadastro"])
    df["validade"] = pd.to_datetime(df["validade"])
    return df


def test_lote_vencido_no_cadastro_sai_mas_o_que_vence_no_proprio_dia_fica():
    sujo = df_de(
        lote(lote_id=1, validade="2026-08-30"),
        lote(lote_id=2, validade="2026-09-01", descricao="alface crespa"),
    )

    limpo = limpar(sujo)

    assert list(limpo["lote_id"]) == [2]


def test_gramas_digitadas_como_kg_voltam_pra_kg_e_lote_grande_de_verdade_fica():
    normais = [lote(lote_id=i, descricao=f"caixa {i}", quantidade_kg=20.0) for i in range(1, 6)]
    sujo = df_de(
        *normais,
        lote(lote_id=6, descricao="gramas", quantidade_kg=30000.0),
        lote(lote_id=7, descricao="lote grande", quantidade_kg=400.0),
    )

    limpo = limpar(sujo).set_index("lote_id")

    assert limpo.loc[6, "quantidade_kg"] == 30.0
    assert limpo.loc[7, "quantidade_kg"] == 400.0


def test_lote_sem_armazenamento_sai_em_vez_de_ganhar_um_valor_chutado():
    sujo = df_de(
        lote(lote_id=1, armazenamento=None),
        lote(lote_id=2, armazenamento="ambiente", descricao="cenoura"),
    )

    limpo = limpar(sujo)

    assert list(limpo["lote_id"]) == [2]


def test_coordenada_ausente_vira_o_centro_da_propria_cidade_e_fica_marcada_como_aproximada():
    sujo = df_de(
        lote(lote_id=1, descricao="a", latitude=-23.50, longitude=-46.60),
        lote(lote_id=2, descricao="b", latitude=-23.60, longitude=-46.70),
        lote(lote_id=3, descricao="c", latitude=-23.55, longitude=-46.65),
        lote(lote_id=4, descricao="d", latitude=None, longitude=None),
        lote(lote_id=5, descricao="e", cidade="Campinas", latitude=-22.90, longitude=-47.06),
    )

    limpo = limpar(sujo).set_index("lote_id")

    assert (limpo.loc[4, "latitude"], limpo.loc[4, "longitude"]) == (-23.55, -46.65)
    assert limpo["geo_aproximada"].to_dict() == {1: False, 2: False, 3: False, 4: True, 5: False}
    assert limpo.loc[5, "latitude"] == -22.90


def test_coordenada_fora_do_brasil_zerada_ou_com_lat_e_lon_trocadas_conta_como_ausente():
    sujo = df_de(
        lote(lote_id=1, descricao="a", latitude=-23.50, longitude=-46.60),
        lote(lote_id=2, descricao="b", latitude=-23.60, longitude=-46.70),
        lote(lote_id=3, descricao="zerada", latitude=0.0, longitude=0.0),
        lote(lote_id=4, descricao="trocada", latitude=-46.63, longitude=-23.55),
    )

    limpo = limpar(sujo).set_index("lote_id")

    assert limpo["geo_aproximada"].to_dict() == {1: False, 2: False, 3: True, 4: True}
    assert (limpo.loc[3, "latitude"], limpo.loc[3, "longitude"]) == (-23.55, -46.65)
    assert (limpo.loc[4, "latitude"], limpo.loc[4, "longitude"]) == (-23.55, -46.65)


def test_cidade_sem_nenhuma_coordenada_conhecida_continua_sem_coordenada_e_nao_finge():
    sujo = df_de(lote(lote_id=1, latitude=None, longitude=None))

    limpo = limpar(sujo)

    assert limpo["latitude"].isna().all() and limpo["longitude"].isna().all()
    assert not limpo["geo_aproximada"].any()


def test_features_dias_ate_validade_perecivel_e_fora_do_frio():
    sujo = df_de(
        lote(lote_id=1, descricao="a", categoria="hortifruti", armazenamento="refrigerado",
             data_cadastro="2026-09-01", validade="2026-09-05"),
        lote(lote_id=2, descricao="b", categoria="laticinios", armazenamento="ambiente"),
        lote(lote_id=3, descricao="c", categoria="nao_pereciveis", armazenamento="ambiente",
             perecivel=True),
        lote(lote_id=4, descricao="d", categoria="carnes_peixes", armazenamento="congelado"),
    )

    limpo = limpar(sujo).set_index("lote_id")

    assert limpo.loc[1, "dias_ate_validade"] == 4
    assert limpo["fora_do_frio"].to_dict() == {1: False, 2: True, 3: False, 4: False}
    # perecivel vem da categoria, nao do que veio digitado
    assert limpo["perecivel"].to_dict() == {1: True, 2: True, 3: False, 4: True}


def test_relatorio_conta_o_que_foi_tratado_por_motivo():
    normais = [lote(lote_id=i, descricao=f"caixa {i}", quantidade_kg=20.0) for i in range(1, 6)]
    sujo = df_de(
        *normais,
        lote(lote_id=6, descricao="caixa 1", quantidade_kg=20.0),
        lote(lote_id=7, descricao="vencido", validade="2026-08-01"),
        lote(lote_id=8, descricao="sem armazenamento", armazenamento=None),
        lote(lote_id=9, descricao="gramas", quantidade_kg=30000.0),
        lote(lote_id=10, descricao="sem geo", latitude=None, longitude=None),
    )

    limpo = limpar(sujo)

    assert limpo.attrs["relatorio"] == {
        "linhas_entrada": 10, "duplicados": 1, "vencidos": 1, "sem_armazenamento": 1,
        "erro_de_unidade_corrigido": 1, "coordenada_aproximada": 1, "linhas_saida": 7,
    }


def test_lote_cadastrado_duas_vezes_com_lote_id_novo_fica_so_uma_vez():
    sujo = df_de(lote(lote_id=1), lote(lote_id=2), lote(lote_id=3, descricao="alface crespa"))

    limpo = limpar(sujo)

    assert sorted(limpo["lote_id"]) == [1, 3]
