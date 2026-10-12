FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

# Trivy DS-0002: nao roda como root
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin app
USER app

# Hugging Face Spaces espera o app respondendo na porta 7860
EXPOSE 7860
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]
