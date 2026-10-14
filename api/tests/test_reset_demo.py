import json
from pathlib import Path

import pytest

from infra.db.reset_demo import montar

SEED = json.loads((Path(__file__).resolve().parents[2] / "data" / "seed_demo.json").read_text(encoding="utf-8"))


def test_seed_passa_nas_regras_da_api():
    doadores, ongs, lotes = montar(SEED)
    assert (len(doadores), len(ongs), len(lotes)) == (3, 4, 5)
    assert all("(DEMO)" in x["nome"] for x in doadores + ongs)
    assert all(l["prioridade"] in ("alta", "media", "baixa") for l in lotes)


def test_seed_entra_pela_api(client):
    doadores, ongs, lotes = montar(SEED)
    ids = {}
    for d in doadores:
        r = client.post("/doadores", json=d)
        assert r.status_code == 201, r.text
        ids[d["nome"]] = r.json()["id"]
    for o in ongs:
        assert client.post("/ongs", json=o).status_code == 201
    for l in lotes:
        corpo = {**l, "doador_id": ids[l["doador"]]}
        assert client.post("/lotes", json=corpo).status_code == 201


def test_lote_de_doador_fora_do_seed_e_recusado():
    ruim = {**SEED, "lotes": [{**SEED["lotes"][0], "doador": "Fantasma"}]}
    with pytest.raises(SystemExit):
        montar(ruim)
