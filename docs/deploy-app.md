# Deploy do frontend (Streamlit)

O frontend tem imagem propria (`app/Dockerfile`) e ainda nao esta no ar. A API ja esta no Render
(`docs/deploy-render.md`); o app e um segundo servico, que so conversa com a API por HTTP.

## O que a imagem faz

- Python 3.12, usuario sem root, `pip` removido no fim do build, como na imagem da API.
- Porta: usa `$PORT` (o Render passa) e cai em 8501 fora dele.
- Healthcheck em `/_stcore/health`.
- Leva o `data/historico_simulado.json` pra dentro (o mapa de calor le dele) e o
  `app/dados/seguranca.json` (o bloco de seguranca).
- `REDE_ALIMENTA_API_URL` entra so por variavel de ambiente. Sem ela a tela abre em modo
  demonstracao, sem matching, doacao nem KPI.

## Subir local em container

```
docker build -t rede-alimenta-app -f app/Dockerfile .
docker run --rm -p 8501:8501 -e REDE_ALIMENTA_API_URL=http://host.docker.internal:8000 rede-alimenta-app
```

Ou pelo compose, com a API junto: `docker compose up --build` (o servico `app` fala com `api`).

## Publicar no Render (passo manual, plano free)

1. New > Web Service, mesmo repo, branch `main`.
2. Runtime: Docker. Dockerfile path: `./app/Dockerfile`. Context: a raiz do repo.
3. Regiao Ohio, plano free, auto-deploy desligado (como o da API).
4. Variavel `REDE_ALIMENTA_API_URL` = a URL publica da API (`https://rede-alimenta-ia-api.onrender.com`).
5. Health check path: `/_stcore/health`.

Nao entrou no `render.yaml` de proposito: o Blueprint da API sincroniza sozinho e criaria o servico
sem ninguem pedir.

## Riscos

- Plano free: o app e a API dormem sem trafego. Abrir os dois uns 10 minutos antes de apresentar.
- A sessao do usuario fica na memoria do Streamlit; se o servico reinicia, todo mundo cai no login.
- Cada clique recarrega o script e chama a API de novo. O ranking do matching fica 30 s em cache
  na sessao por causa do limite de 20 pedidos por minuto da rota.
- O mapa carrega os tiles do Carto pela internet; sem rede o mapa abre sem fundo.
