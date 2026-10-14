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
- app/ - reservado ao frontend (hoje so tem um `.gitkeep`)
- infra/ - schema do banco, scripts de banco e o hello world do deploy de teste
- docs/ - decisoes tecnicas, STRIDE, LGPD e relatorios de seguranca
- .github/workflows/ - pipeline de CI
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

A API **nao sobe sem `JWT_SECRET`** (minimo 32 caracteres). Pro uso local, copie
`.env.example` pra `.env`, gere o segredo com
`python -c "import secrets; print(secrets.token_urlsafe(48))"` e preencha tambem
`ADMIN_EMAIL` e `ADMIN_PASSWORD` (10+ caracteres): o admin e criado na primeira
subida. Veja a secao "Autenticacao" abaixo.

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

### Em container

`api/Dockerfile` (Python 3.12, usuario sem root) e `.dockerignore` na raiz. Da raiz do repo:
`docker build -t rede-alimenta-api -f api/Dockerfile .` e depois `docker run` com as variaveis
de ambiente (passo a passo, medidas e o que nao foi testado em `docs/container.md`). Sem
`STORAGE=postgres` a API sobe em memoria.

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
- `capacidade_kg` entre 0 e 100000. `necessidades` vira minuscula, sem repetido e sem vazio, e
  so aceita as 6 categorias do modelo (`hortifruti`, `padaria`, `laticinios`,
  `carnes_peixes`, `preparados`, `nao_pereciveis`); outra volta 422.

Lote:
- Nao aceita `validade` anterior a hoje nem mais de 730 dias a frente (422), nem
  `quantidade_kg` acima de 5000. A checagem e so na entrada. Os tetos sao premissa do dia 20
  (`docs/decisoes.md`).
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
- Falha do modelo (arquivo `models/prioridade_v2.joblib` ausente, versao errada do
  scikit-learn) ou saida fora de alta/media/baixa: o lote e cadastrado com
  `prioridade` e `tipo` nulos e o erro vai pro log. O doador nao perde o cadastro.
- O `PUT` nao recalcula a prioridade.

Doacao (dia 12): `POST /doacoes` confirma o match. Corpo: `lote_id`, `ong_id` e,
opcionais, `distancia_km` e `score` (o que o `/matching` devolveu; por enquanto
informativos, o servidor nao recalcula). Status e timestamps sao sempre do servidor.

- Reserva o lote (`disponivel` -> `reservado`) e grava a doacao como `confirmada` no
  mesmo passo. Lote ou ONG que nao existe volta 404; lote que nao esta `disponivel`
  (inclusive confirmado por outro pedido ao mesmo tempo) volta 409. Tambem volta 409
  se o lote passa da `capacidade_kg` da ONG ou se a categoria dele nao esta nas
  `necessidades` dela (lote sem `tipo` so confere a capacidade).
- `confirmado_em` e `tempo_match_s` (confirmacao menos o `criado_em` do lote) ficam
  gravados: o tempo medio de match e um `avg(tempo_match_s)`.
- Nao existe `PUT` nem `DELETE` de doacao. Se a reserva cai (`PUT /lotes/{id}` de
  `reservado` para `disponivel` ou `descartado`), a doacao vira `cancelada` e o lote
  pode ser doado a outra ONG. `reservado` -> `doado` (entrega) mantem a confirmada.
- Lote e ONG com doacao registrada nao podem ser apagados (409). `GET /doacoes`
  aceita `lote_id`, `ong_id` e `status`.
- A tabela nova esta em `infra/db/schema.sql`; no Supabase, rode
  `python infra/db/aplicar_schema.py` (seguro repetir).

## Autenticacao e papeis (dias 15 e 16)

Todo endpoint, menos `/health`, `/docs` e `POST /auth/login`, pede token. Detalhes e
decisoes em `docs/auth.md`.

1. `POST /auth/login` com `{"email": ..., "senha": ...}` devolve `access_token` (JWT, vale
   30 min). Erro de login volta 401 sempre com a mesma mensagem; 5 erros no mesmo e-mail em
   15 min voltam 429 com `Retry-After`.
2. Nas demais chamadas: `Authorization: Bearer <token>`. No Swagger, botao "Authorize".
3. Quem cria usuario e o admin (`POST /usuarios`); nao existe cadastro aberto.

| Papel | Pode |
|---|---|
| `admin` | tudo |
| `doador` | ler e editar o proprio cadastro; criar, ver, editar e apagar os proprios lotes; confirmar doacao dos proprios lotes; listar as ONGs |
| `ong` | listar as ONGs e editar a propria; ver os lotes e doacoes que recebeu |

Sem token valido volta 401; papel ou dono errado volta 403. A matriz completa esta em
`api/tests/test_acesso_negado.py`.

Erros e auditoria (dia 13): todo erro volta como JSON `{"detail": ...}`.

| Codigo | Quando |
|---|---|
| 400 | corpo do pedido que nao e JSON |
| 404 | rota ou registro que nao existe (405 se o metodo nao existe na rota) |
| 409 | conflito: documento repetido, status que nao pode andar, lote que nao esta disponivel |
| 422 | JSON valido com campo errado. `detail` e uma lista de `{type, loc, msg}`, sem o valor recebido |
| 500 | erro nosso. Corpo generico `{"detail": "Erro interno do servidor", "request_id": ...}`; o stack trace fica so no log |
| 503 | banco fora do ar (mesmo `request_id`) |

Toda resposta traz o header `X-Request-ID`. Com ele se acha a linha no log.
`quantidade_kg` e `capacidade_kg` nao aceitam NaN nem infinito; `descricao` vai ate 500
caracteres e `tipo` ate 50.

O log de auditoria sai no stdout, uma linha JSON por pedido (`tipo: requisicao`: metodo,
path, status, ms, ip) e uma por mudanca de dado (`tipo: evento`: `lote.criado`,
`lote.atualizado` com `status_de`/`status_para`, `doacao.confirmada`, `doacao.cancelada`,
`doador.criado`...). Nao grava corpo nem querystring, entao CPF, CNPJ, e-mail e telefone
nao aparecem. Sem login ainda, "quem" e so o IP (atras do proxy do Render e o do proxy).
Codigo em `api/erros.py` e `api/auditoria.py`.

## Dados e IA

**Tudo que e dado de lote e SIMULADO.** Nao achamos base aberta brasileira lote a lote (validade,
armazenamento, destino); as bases publicas de desperdicio sao agregadas. Detalhes e premissas em
`data/README.md`; numeros do modelo em `models/metrics.json`; decisoes em `docs/ia.md`.

| Peca | Onde | O que faz |
|---|---|---|
| Dataset | `data/gerar_dataset_v0.py` -> `lotes_v0.csv` (1212 lotes) | Gerador com seed fixa. Rotulo `prioridade` por formula de urgencia (fracao da vida util **ou** prazo absoluto, o maior), frio, perecibilidade e quantidade, mais ruido |
| Limpeza | `ml/limpeza.py` -> `lotes_v1.csv` (1083) | Tira duplicados, vencidos e lote sem armazenamento; corrige grama digitada como kg; preenche coordenada ausente com o centro da cidade |
| Modelo | `ml/treinar.py` -> `models/prioridade_v2.joblib` | Random Forest. F1 macro 0,669 no teste contra 0,610 da regra so por dias; o lote urgente mandado pro fim da fila caiu pra 2,2% |
| Categoria | mesmo pacote | Classifica a descricao numa das 6 categorias (acuracia 1,00, otimista: texto simulado) |
| `predict()` | `ml/predict.py` | Chamado no `POST /lotes`. Contrato em `docs/ia.md`, secao 5 |
| Matching | `ml/matching.py`, `ml/geo.py` | Filtra ONG por categoria e capacidade (a mesma regra da doacao), ordena por distancia (haversine) e devolve `score` = distancia / 100 km. ONG ou doador sem coordenada usa o centro da cidade e sai marcado `geo_aproximada`. Contrato em `docs/matching.md` |
| KPIs | `api/kpis.py` | `kg doados / 0,5` = refeicoes. O 0,5 kg e **premissa**; a unica referencia achada (EUA) da 0,544 kg (`docs/kpis.md`) |
| Historico | `data/gerar_historico_simulado.py` -> `historico_simulado.json` | 1083 lotes e 1090 doacoes **SIMULADAS** pro dashboard, no formato da API, com 12 ONGs inventadas |
| Seed de demo | `api/seed_demo.py` | 4 ONGs **reais** (CNPJ ativo na Receita, coordenada do OpenStreetMap), 3 doadores e 5 lotes ficticios. Capacidade e necessidades das ONGs sao simuladas (`docs/seed-demo.md`) |

O modelo carrega quando a API sobe, nao no primeiro lote; o log registra `modelo.carregado` com o
tempo e o pico de memoria. Reproduzir tudo:

```
python data/gerar_dataset_v0.py
python -m ml.limpeza
python -m ml.treinar
python -m data.gerar_historico_simulado
pytest ml api
```

Limites pra defesa: o modelo aprende a nossa formula, nao o mundo real, e ganha da regra simples por
pouco (diferenca de -0,001 a +0,117 no F1, IC 95%). A rota `POST /matching/{lote_id}` ainda nao esta na
API; a funcao esta pronta e o trecho da rota esta em `docs/matching.md`.

## Deploy

`render.yaml` sobe a API pela imagem Docker. Variaveis, passo a passo e riscos em
`docs/deploy-render.md`; a lista completa esta em `.env.example`.

## Qualidade e seguranca

`.github/workflows/ci.yml` roda em todo push na `main` e em todo pull request: `ruff` e `pytest`
(Python 3.12), Bandit e `pip-audit`, e depois o build da imagem com Trivy (HIGH e CRITICAL com
correcao publicada derrubam o job) e uma subida do container conferindo `/health`. O deploy no
Render continua manual. Relatorio do Trivy em `docs/security/trivy-imagem.md`, ameacas em
`docs/stride.md` e dados pessoais em `docs/lgpd.md` (rascunho, sem revisao juridica).

Ainda nao existe `docker-compose.yml`.

## Status

Fim da Semana 3. Ver `docs/checkpoint-semana3.md` (o que fechou e o que nao esta no repo).
