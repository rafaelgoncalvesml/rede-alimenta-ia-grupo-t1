# Supabase vs MongoDB Atlas - free tier

Levantamento pra apoiar a decisao Supabase x Atlas (trava marcada pro dia 4,
`docs/decisoes.md`). Dados de setembro/2026, direto das paginas oficiais de
pricing e da doc de limites do Atlas - conferir de novo antes da trava porque
os dois mudam plano com frequencia.

## Supabase (free plan)

- 500 MB de banco (Postgres dedicado) por projeto
- Limite de 2 projetos ativos por conta
- Projeto pausa depois de 1 semana sem uso (precisa reativar manual)
- 5 GB de egress/mes, 5 GB de egress cacheado
- 1 GB de file storage
- 50.000 usuarios ativos/mes (auth)
- Requisicoes de API ilimitadas
- CPU e RAM compartilhados (sem numero fixo divulgado)
- Sem backup automatico no free (so no Pro, $25/mes)
- Suporte só via comunidade

## MongoDB Atlas (cluster M0 / free tier)

- 512 MB de storage por cluster, 1 cluster free por projeto
- RAM e vCPU compartilhados
- Maximo de 500 conexoes simultaneas
- Maximo de 100 databases e 500 collections no total
- Transferencia de dados: 10 GB de entrada + 10 GB de saida por janela de 7 dias corridos (passando disso o Atlas throttla a rede do cluster)
- Sem backup automatico (só mongodump/mongorestore manual)
- Sem failover/outage test, sem peering de rede, sem private endpoint
- Atlas pode desligar cluster free por inatividade prolongada
- MongoDB 8.0 fixo, sem controle de versao

## Leitura rapida

Pro nosso caso (lotes de doacao + matching, volume baixo no MVP), os dois
free tiers cobrem o projeto sem problema - 500 MB / 512 MB e bem mais que
suficiente pro dataset simulado. A diferenca que pesa mais e o modelo de
dados: Supabase e Postgres relacional (schema fixo, bom pra tabelas tipo
lote/doador/ONG com relacionamento claro), Atlas e documento (schema livre,
melhor se os dados de lote ficarem heterogeneos por tipo de alimento).

## Como testar

1. Copiar `.env.example` pra `.env` na raiz do repo
2. Criar um projeto free no [Supabase](https://supabase.com) e um cluster M0 no [MongoDB Atlas](https://www.mongodb.com/atlas) (login manual, nao automatizado)
3. Preencher `SUPABASE_DB_URL` e `MONGODB_URI` no `.env`
4. `python -m pip install -r infra/db/requirements.txt`
5. `python infra/db/test_connections.py`
