from datetime import UTC, datetime

from ml.relogio import hoje


def test_depois_das_21h_de_brasilia_ainda_e_o_mesmo_dia_aqui_mesmo_ja_sendo_amanha_em_utc():
    # 23h30 de 14/10 em Brasilia = 02h30 de 15/10 em UTC: "vence hoje" nao pode virar "ja venceu"
    assert hoje(datetime(2026, 10, 15, 2, 30, tzinfo=UTC)).isoformat() == "2026-10-14"


def test_de_manha_utc_e_brasilia_concordam():
    assert hoje(datetime(2026, 10, 15, 12, 0, tzinfo=UTC)).isoformat() == "2026-10-15"
