# Decisoes travadas (dia 4)

Baseado no levantamento dos dias 2 e 3 (`docs/deploy-comparacao.md` e
`docs/db-comparacao.md`). Trava marcada pro grupo confirmar no sync de
30min, mas os dois casos ja saem praticamente decididos so pelos dados.

## Deploy: Render

O Render aceita o FastAPI de graca e sem friccao (so autorizar o repo pelo
GitHub App), build em ~42s e cold start medido de ~22s depois de idle -
aceitavel pra MVP/demo. O Hugging Face Spaces free tier bloqueia o cenario
que a gente precisa: os SDKs Gradio e Docker aparecem como "Paid" no
free tier atual, so o Static (arquivo estatico) e gratuito, e isso nao
roda uma API.

**Decisao: Render pra API.** O frontend (Streamlit) fica em aberto entre
Render ou HF Spaces mais pra frente - se o HF liberar SDK gratuito ate la,
reavalia.

## Banco: Supabase

Os dois free tiers cobrem o volume do MVP sem problema (500 MB Supabase x
512 MB Atlas, dataset simulado e bem menor que isso). O que decide e o
modelo de dados: as entidades do projeto (Doador, ONG, Lote, Doacao) tem
relacionamento claro entre si - um lote pertence a um doador, uma doacao
liga um lote a uma ONG - que e o caso de uso natural de um banco
relacional com chave estrangeira. Collections do Mongo fariam mais sentido
se os dados de lote fossem heterogeneos por tipo de alimento, o que nao e
o nosso caso.

**Decisao: Supabase (Postgres) pra tudo.** Conexao real com a API entra no
dia 10 do cronograma; ate la os CRUDs rodam com storage em memoria
(esqueleto).

## Proximos passos que dependem disso

- Rafael: modelar as tabelas em `infra/db/schema.sql` seguindo Postgres
  (feito junto com essa trava, ver `api/models.py`)
- Gustavo: pode assumir Streamlit rodando local sem se preocupar com onde
  vai hospedar ainda
- Anthony: workflow de deploy (dia 22) so precisa mirar Render, nao os dois
