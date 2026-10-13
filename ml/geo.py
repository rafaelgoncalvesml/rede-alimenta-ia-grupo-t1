"""Geografia do matching: distancia e o que fazer quando a coordenada falta. Sem dependencias."""
import unicodedata
from math import asin, cos, radians, sin, sqrt

RAIO_TERRA_KM = 6371.0088  # raio medio

# Retangulo que contem o Brasil (aproximado). Pega 0,0 (coordenada zerada) e latitude/longitude
# trocadas, que passam num teste de intervalo -90..90 mas cairiam no oceano. Mesma regra da limpeza.
LATITUDE_BRASIL = (-33.75, 5.27)
LONGITUDE_BRASIL = (-73.99, -28.85)

# Centro aproximado das cidades do dataset (grande SP + Campinas): as mesmas coordenadas de
# CIDADES em data/gerar_dataset_v0.py (um teste garante que as duas listas nao se separem).
# PREMISSA: serve de fallback quando ONG ou doador nao tem coordenada; o erro e o tamanho da cidade.
CENTROS_CIDADES = {
    ("sao paulo", "SP"): (-23.5505, -46.6333),
    ("guarulhos", "SP"): (-23.4543, -46.5337),
    ("osasco", "SP"): (-23.5325, -46.7917),
    ("santo andre", "SP"): (-23.6737, -46.5432),
    ("sao bernardo do campo", "SP"): (-23.6914, -46.5646),
    ("campinas", "SP"): (-22.9099, -47.0626),
}


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    dlat, dlon = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * RAIO_TERRA_KM * asin(sqrt(a))


def _chave_cidade(cidade: str, estado: str) -> tuple[str, str]:
    sem_acento = unicodedata.normalize("NFKD", cidade).encode("ascii", "ignore").decode()
    return " ".join(sem_acento.lower().split()), estado.strip().upper()


def coordenada_valida(lat, lon) -> bool:
    return (isinstance(lat, (int, float)) and isinstance(lon, (int, float))
            and LATITUDE_BRASIL[0] <= lat <= LATITUDE_BRASIL[1]
            and LONGITUDE_BRASIL[0] <= lon <= LONGITUDE_BRASIL[1])


def posicao(entidade: dict) -> tuple[float, float, bool] | None:
    """(latitude, longitude, aproximada) de uma ONG ou doador. Coordenada ausente ou fora do Brasil
    cai no centro da cidade (aproximada=True). Cidade sem centro conhecido devolve None: nao inventa."""
    lat, lon = entidade.get("latitude"), entidade.get("longitude")
    if coordenada_valida(lat, lon):
        return lat, lon, False
    centro = CENTROS_CIDADES.get(_chave_cidade(entidade.get("cidade") or "", entidade.get("estado") or ""))
    return (*centro, True) if centro else None
