# Imagem do frontend (Streamlit). Construir da raiz do repo:
#   docker build -t rede-alimenta-app -f app/Dockerfile .
#   docker run -p 8501:8501 -e REDE_ALIMENTA_API_URL=https://rede-alimenta-ia-api.onrender.com rede-alimenta-app
# Sem REDE_ALIMENTA_API_URL a tela abre em modo demonstracao.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HOME=/tmp

WORKDIR /srv

RUN apt-get update \
    && apt-get upgrade -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

COPY app/requirements.txt requirements.txt
RUN pip install --upgrade "pip>=26.2.0" \
    && pip install -r requirements.txt \
    && pip uninstall -y pip

# o .streamlit/config.toml so vale se o cwd for a pasta do app
COPY app .
# o mapa de calor le o historico simulado daqui (no repo ele fica em data/)
COPY data/historico_simulado.json dados/historico_simulado.json

RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin app
USER app

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8501/_stcore/health', timeout=4).status == 200 else 1)"]

# o Render passa a porta em $PORT; local cai no 8501
CMD ["sh", "-c", "exec streamlit run dashboard.py --server.address 0.0.0.0 --server.port ${PORT:-8501} --server.headless true --browser.gatherUsageStats false"]
