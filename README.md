# Rede Alimenta IA

Projeto integrador de Ciberseguranca e DevSecOps (FIAP, Tecnologo em Inteligencia Artificial). Sistema que cadastra lotes de alimentos doados, classifica a prioridade de descarte com um modelo de IA e faz o matching com ONGs por necessidade, capacidade e distancia.

## Equipe

- Charles Augusto Miranda da Silva - IA e Dados
- Rafael Fernandes de Paula Goncalves - Backend, Banco e Deploy
- Gustavo Reatti Sela - Interface e Dashboard
- Anthony Prado Pereira - DevSecOps e Seguranca

Orientacao: Prof. M.Sc Oerton Fernandes.

## Estrutura do repositorio

- api/ - backend em FastAPI
- ml/ - modelo de priorizacao e matching
- app/ - frontend em Streamlit
- infra/ - Docker, Compose e configuracao de deploy
- docs/ - decisoes tecnicas, STRIDE, LGPD e relatorios de seguranca
- data/ - dataset e scripts de dados

## Como rodar a API (local)

Da raiz do repo, com Python 3.10+:

```
python -m venv .venv
.venv\Scripts\activate          # Windows; no Linux/Mac: source .venv/bin/activate
pip install -r api/requirements-dev.txt
uvicorn api.main:app --reload
```

Swagger em http://localhost:8000/docs e health check em `/health`.

O storage ainda e em memoria, entao tudo some quando a API reinicia. Com a API
de pe, `python -m api.seed_dev` cadastra um doador e uma ONG de exemplo (o lote
precisa de um `doador_id` que exista).

Testes: `pytest api`.

## Contrato pro Streamlit

O frontend le a URL da API da variavel `API_URL` (padrao `http://localhost:8000`).
Fluxo do dia 6: `POST /lotes` e depois `GET /lotes`.

```json
{
  "doador_id": 1,
  "descricao": "alface",
  "quantidade_kg": 12.5,
  "validade": "2026-10-01",
  "armazenamento": "refrigerado"
}
```

`armazenamento` aceita `ambiente`, `refrigerado` ou `congelado`. `quantidade_kg`
tem que ser maior que zero e `descricao` nao pode ser vazia (422 caso contrario).
`status`, `prioridade` e `id` voltam preenchidos pela API; o cliente nao consegue
setar `prioridade` (so o modelo vai escrever isso).

## Status

Semana 1 de producao. Ver `docs/checkpoint-semana1.md`.
