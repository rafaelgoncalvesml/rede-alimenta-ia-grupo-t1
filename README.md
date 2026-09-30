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

Da raiz do repo, com Python 3.11+ (o scikit-learn 1.8 do modelo nao instala no 3.10):

```
python -m venv .venv
.venv\Scripts\activate          # Windows; no Linux/Mac: source .venv/bin/activate
pip install -r api/requirements-dev.txt
uvicorn api.main:app --reload
```

Swagger em http://localhost:8000/docs e health check em `/health`.

### Onde os dados ficam

A variavel `STORAGE` escolhe:

- `memory` (padrao): sem banco, tudo some quando a API reinicia. E o que os
  testes usam e o que roda sem configurar nada.
- `postgres`: Supabase, via `SUPABASE_DB_URL` (copie `.env.example` pra `.env` e
  preencha; o `.env` nunca vai pro repo). No PowerShell:
  `$env:STORAGE="postgres"; uvicorn api.main:app`.

Na primeira vez no banco, crie as tabelas com
`python infra/db/aplicar_schema.py` (pode rodar de novo sem problema).
`GET /health/db` mostra qual storage esta ativo e, no Postgres, testa a conexao.

Com a API de pe, `python -m api.seed_dev` cadastra um doador e uma ONG de exemplo
(o lote precisa de um `doador_id` que exista). Ele nao duplica se ja tiver doador.

Testes: `pytest api` (sempre em memoria, nunca tocam o banco).

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

## Doador: regras e codigos HTTP

- `documento` aceita com ou sem mascara, mas precisa ter 11 digitos (`fisica`)
  ou 14 (`juridica`); a API guarda so os digitos. Nao valida digito verificador.
- `estado` e a sigla com 2 letras (vira maiuscula). `email`, se vier, precisa ter
  formato de e-mail. Latitude entre -90 e 90, longitude entre -180 e 180.
- `PUT /doadores/{id}` e atualizacao parcial; documento e tipo de pessoa nao mudam.
- 201 criou, 204 apagou, 404 nao achou, 409 documento repetido ou doador com
  lotes, 422 dado invalido.

## ONG e Lote: regras

ONG:
- `cnpj` com ou sem mascara, 14 digitos, guardado sem mascara. CNPJ repetido
  volta 409. Nao muda depois de criada.
- `capacidade_kg` >= 0. `necessidades` vira minuscula, sem repetido e sem vazio.

Lote:
- Nao aceita `validade` anterior a hoje (422). A checagem e so na entrada.
- `GET /lotes` aceita `?status=` e `?doador_id=` (pro painel da ONG listar so os
  disponiveis).
- Status so anda assim: `disponivel` -> `reservado` ou `descartado`;
  `reservado` -> `disponivel`, `doado` ou `descartado`. `doado` e `descartado`
  sao finais: qualquer edicao volta 409, e `disponivel` nao pula direto pra `doado`.
- So apaga lote `disponivel` ou `descartado`; `reservado` e `doado` voltam 409.
- `doador_id` nao muda; `prioridade` so o modelo escreve.

Prioridade (dia 11): o `POST /lotes` chama `predict()` de `ml/predict.py` (contrato em
`docs/ia.md`, secao 5) e grava `prioridade` (`alta`, `media` ou `baixa`) e a categoria
em `tipo`. Se o doador ja mandou `tipo`, a IA nao reclassifica.

- Entrada que o modelo recusa (`tipo` fora das 6 categorias, `descricao` em branco
  sem `tipo`) volta 422 com a mensagem do modelo e o lote nao e cadastrado.
- Falha do modelo (arquivo `models/prioridade_v1.joblib` ausente, versao errada do
  scikit-learn) ou saida fora de alta/media/baixa: o lote e cadastrado com
  `prioridade` e `tipo` nulos e o erro vai pro log. O doador nao perde o cadastro.
- O `PUT` nao recalcula a prioridade.

Doacao (dia 12): `POST /doacoes` confirma o match. Corpo: `lote_id`, `ong_id` e,
opcionais, `distancia_km` e `score` (o que o `/matching` devolveu; por enquanto
informativos, o servidor nao recalcula). Status e timestamps sao sempre do servidor.

- Reserva o lote (`disponivel` -> `reservado`) e grava a doacao como `confirmada` no
  mesmo passo. Lote ou ONG que nao existe volta 404; lote que nao esta `disponivel`
  (inclusive confirmado por outro pedido ao mesmo tempo) volta 409.
- `confirmado_em` e `tempo_match_s` (confirmacao menos o `criado_em` do lote) ficam
  gravados: o tempo medio de match e um `avg(tempo_match_s)`.
- Nao existe `PUT` nem `DELETE` de doacao. Se a reserva cai (`PUT /lotes/{id}` de
  `reservado` para `disponivel` ou `descartado`), a doacao vira `cancelada` e o lote
  pode ser doado a outra ONG. `reservado` -> `doado` (entrega) mantem a confirmada.
- Lote e ONG com doacao registrada nao podem ser apagados (409). `GET /doacoes`
  aceita `lote_id`, `ong_id` e `status`.
- A tabela nova esta em `infra/db/schema.sql`; no Supabase, rode
  `python infra/db/aplicar_schema.py` (seguro repetir).

## Status

Semana 1 de producao. Ver `docs/checkpoint-semana1.md`.
