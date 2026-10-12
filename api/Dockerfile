# Imagem da API. Construir da raiz do repo:
#   docker build -t rede-alimenta-api -f api/Dockerfile .
#
# Python 3.12 e nao o 3.10 do roadmap: o scikit-learn 1.8 e o pandas 3 pedem 3.11 ou mais.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# as dependencias primeiro: mexer no codigo nao refaz esta camada
COPY api/requirements.txt api/requirements.txt
RUN pip install -r api/requirements.txt

# a API importa ml.predict e le models/ (o .dockerignore deixa de fora testes, dados e docs)
COPY api api
COPY ml ml
COPY models models

# sem root: se alguem escapar da API, nao e dono do container
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin app
USER app

EXPOSE 8000

# JWT_SECRET, SUPABASE_DB_URL etc. entram por variavel de ambiente na hora do run, nunca na imagem
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health', timeout=4).status == 200 else 1)"]

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
