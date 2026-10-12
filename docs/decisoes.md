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
dia 10 do cronograma e ja esta feita (`api/storage.py`, variavel `STORAGE`);
os testes continuam em memoria.

## Proximos passos que dependem disso

- Rafael: modelar as tabelas em `infra/db/schema.sql` seguindo Postgres
  (feito junto com essa trava, ver `api/models.py`)
- Gustavo: pode assumir Streamlit rodando local sem se preocupar com onde
  vai hospedar ainda
- Anthony: workflow de deploy (dia 22) so precisa mirar Render, nao os dois

# Premissas do dia 20 (Rafael, aguardam o grupo)

Fechei cinco issues sem a decisao do grupo, porque cada uma pedia um numero ou uma regra e
deixar aberta bloqueava o dia 21. Tudo abaixo e **premissa**: troca com uma constante.

- **Teto de lote: 5000 kg.** O maior lote do dataset v1 tem 1176 kg. `QUANTIDADE_MAX_KG` em
  `api/models.py`.
- **Teto de capacidade da ONG: 100000 kg.** Sem fonte; so barra erro de digitacao.
  `CAPACIDADE_MAX_KG`.
- **Validade ate 730 dias a frente.** A maior do dataset e 325. `VALIDADE_MAX_DIAS`.
- **A doacao confere capacidade e categoria** (issue 9), alem do matching. Capacidade e por
  doacao, nao acumulada. ONG sem `necessidades` nao recebe.
- **`necessidades` da ONG so aceita as 6 categorias do modelo** (issue 7). Mexer nessa lista
  e mexer em `ml/features.py`.

