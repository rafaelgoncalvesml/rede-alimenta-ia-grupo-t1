"""O seed de demo roda contra a API de verdade (em memoria): se um registro nao passar nos modelos
da API ou o modelo de prioridade falhar, o teste quebra aqui e nao na hora da apresentacao."""
from api.seed_demo import ONGS_REAIS, popular
from ml.matching import matching


def _req(client):
    def req(metodo, caminho, corpo=None):
        r = client.request(metodo, caminho, json=corpo)
        assert r.status_code < 300, f"{metodo} {caminho}: {r.status_code} {r.text}"
        return r.json()
    return req


def test_popula_3_doadores_4_ongs_5_lotes_e_cada_lote_ganha_prioridade_do_modelo(client):
    popular(_req(client))

    assert len(client.get("/doadores").json()) == 3
    assert len(client.get("/ongs").json()) == 4
    lotes = client.get("/lotes").json()
    assert len(lotes) == 5
    assert all(l["prioridade"] in {"alta", "media", "baixa"} for l in lotes)
    assert all(l["tipo"] for l in lotes)


def test_rodar_duas_vezes_nao_duplica_nada(client):
    popular(_req(client))
    popular(_req(client))

    assert (len(client.get("/doadores").json()), len(client.get("/ongs").json()),
            len(client.get("/lotes").json())) == (3, 4, 5)


def test_so_reais_cadastra_apenas_as_ongs_verificadas_na_receita(client):
    popular(_req(client), so_reais=True)

    ongs = client.get("/ongs").json()
    assert {o["cnpj"] for o in ongs} == {o["cnpj"] for o in ONGS_REAIS}
    assert not any("DEMO" in o["nome"] for o in ongs)


def test_o_que_e_ficticio_diz_demo_no_nome_e_o_que_e_real_tem_cnpj_de_14_digitos(client):
    popular(_req(client))

    reais = {o["cnpj"] for o in ONGS_REAIS}
    for o in client.get("/ongs").json():
        assert (o["cnpj"] in reais) != ("DEMO" in o["nome"]), o["nome"]
    assert all(len(c) == 14 and c.isdigit() for c in reais)
    assert all("DEMO" in d["nome"] for d in client.get("/doadores").json())


def test_matching_sobre_o_seed_mostra_distancia_fallback_e_o_lote_sem_ong_possivel(client):
    popular(_req(client))
    doadores = {d["id"]: d for d in client.get("/doadores").json()}
    ongs = client.get("/ongs").json()
    por_descricao = {l["descricao"]: l for l in client.get("/lotes").json()}

    def rodar(trecho):
        lote = next(l for d, l in por_descricao.items() if trecho in d)
        return matching(lote, doadores[lote["doador_id"]], ongs), {o["id"]: o["nome"] for o in ongs}

    tomate, nomes = rodar("tomate")
    assert nomes[tomate["ranking"][0]["ong_id"]].startswith("Banco de Alimentos")  # Pacaembu, a ~3 km

    arroz, nomes = rodar("arroz")  # 400 kg: a Casa do Zezinho (300 kg) nao aguenta
    assert [nomes[r["ong_id"]] for r in arroz["ranking"]] == ["Banco de Alimentos - Associação Civil"]
    assert {d["motivo"] for d in arroz["descartadas"]} >= {"capacidade"}
    assert arroz["ranking"][0]["geo_aproximada"] is True  # doador sem coordenada: centro de Santo Andre

    marmita, _ = rodar("marmita")
    assert marmita["ranking"] == [] and "capacidade" in {d["motivo"] for d in marmita["descartadas"]}
