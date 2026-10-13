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


def test_as_4_ongs_sao_as_reais_verificadas_na_receita_e_nenhuma_e_ficticia(client):
    popular(_req(client))

    ongs = client.get("/ongs").json()
    assert {o["cnpj"] for o in ongs} == {o["cnpj"] for o in ONGS_REAIS} and len(ONGS_REAIS) == 4
    assert not any("DEMO" in o["nome"] for o in ongs)
    assert all(len(o["cnpj"]) == 14 and o["cnpj"].isdigit() for o in ONGS_REAIS)


def test_os_doadores_sao_ficticios_e_dizem_demo_no_nome(client):
    popular(_req(client))

    assert all("DEMO" in d["nome"] for d in client.get("/doadores").json())


def test_matching_sobre_o_seed_mostra_distancia_capacidade_e_fallback(client):
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
    assert [nomes[r["ong_id"]].split(" - ")[0] for r in arroz["ranking"]] == ["Arsenal da Esperança",
                                                                             "Banco de Alimentos"]
    assert {d["motivo"] for d in arroz["descartadas"]} >= {"capacidade"}
    assert arroz["ranking"][0]["geo_aproximada"] is True  # doador sem coordenada: centro de Santo Andre

    marmita, nomes = rodar("marmita")  # so o Arsenal, que serve refeicoes, aceita preparados
    assert [nomes[r["ong_id"]].split(" - ")[0] for r in marmita["ranking"]] == ["Arsenal da Esperança"]
