# Imagem do Streamlit (Gustavo). Contexto de build = raiz do repo:
#   docker build -f app/Dockerfile -t rede-alimenta-app .
# PREMISSA: o frontend tem app/requirements.txt e o arquivo de entrada e app/main.py.
# Se o Gustavo usar outro nome, so trocar APP_ENTRY no CMD.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    API_URL=http://api:8000

WORKDIR /app
RUN useradd --system --create-home --uid 10001 appuser

COPY app/requirements.txt requirements.txt
RUN pip install -r requirements.txt

COPY app ./app

USER appuser
EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8501/_stcore/health', timeout=4).status == 200 else 1)"

CMD ["streamlit", "run", "app/main.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true"]