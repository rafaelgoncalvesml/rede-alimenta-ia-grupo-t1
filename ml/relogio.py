"""A data de "hoje" do negocio e a de Brasilia, nao a do servidor (o Render roda em UTC).

Com `date.today()`, depois das 21h de Brasilia um lote que vence hoje ja era lido como vencido.
"""
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

FUSO = ZoneInfo("America/Sao_Paulo")  # no Windows precisa do pacote tzdata (esta nos requirements)


def hoje(agora: datetime | None = None) -> date:
    return (agora or datetime.now(UTC)).astimezone(FUSO).date()
