# Rede Alimenta IA

Projeto integrador de Ciberseguranca e DevSecOps (FIAP, Tecnologo em Inteligencia Artificial). A API cadastra lotes de alimentos doados, classifica a prioridade de descarte com um modelo de IA e registra a doacao do lote para uma ONG. O matching por necessidade, capacidade e distancia existe como funcao em `ml/matching.py`, mas ainda nao esta ligado a uma rota da API (ver "O que ainda nao esta no repo").

API publica: https://rede-alimenta-ia-api.onrender.com (Swagger em `/docs`). O servico esta no plano free e dorme sem trafego; ver "Producao".

## Equipe

- Charles Augusto Miranda da Silva: IA e Dados
- Rafael Fernandes de Paula Goncalves: Backend, Banco e Deploy
- Gustavo Reatti Sela: Interface e Dashboard
- Anthony Prado Pereira: DevSecOps e Seguranca

Orientacao: Prof. M.Sc Oerton Fernandes.

## Arquitetura

```mermaid
flowchart LR
    U[Cliente: Swagger /docs hoje, Streamlit planejado] -->|HTTPS + JWT| CF[Cloudflare do Render]
    CF --> API
    subgraph Container["Container Docker no Render (Python 3.12)"]
        API["FastAPI: api/main.py"]
        API --> SEG["auth, papeis, limite de pedidos, auditoria"]
        API --> IA["api/ia.py -> ml/predict.py"]
        IA --> M[(models/prioridade_v2.joblib)]
    end
    API -->|psycopg, session pooler| DB[(Postgres no Supabase)]
```

Um `POST /lotes` passa por: limite de pedidos, conferencia do token e do papel, validacao do corpo, modelo de IA (que devolve `tipo` e `prioridade`), gravacao no banco e uma linha de auditoria no stdout.

| Parte | Onde | O que faz |
|---|---|---|
| API | `api/` | FastAPI com rotas de doadores, ONGs, lotes, doacoes, usuarios, KPIs e login |
| Seguranca | `api/seguranca.py`, `limites.py`, `auditoria.py`, `erros.py` | JWT, papeis admin/doador/ong, senhas com argon2, limites, log em JSON, erros sem stack trace |
| Modelo | `ml/`, `models/` | Classifica a categoria do alimento e a prioridade (alta, media, baixa). O artefato `.joblib` vai versionado no repo e na imagem |
| Armazenamento | `api/storage.py`, `infra/db/schema.sql` | Em memoria (testes e dev rapido) ou Postgres/Supabase, escolhido por `STORAGE` |
| Deploy | `api/Dockerfile`, `render.yaml` | Imagem sem root, publicada no Render |

Tabelas: `doadores`, `ongs`, `lotes`, `doacoes`, `usuarios` e `demo_seed` (copia do seed da demo). Todas com RLS ligado e sem policy: a API REST do Supabase nao le nada, so a nossa API, que conecta como dono das tabelas.

## Estrutura do repositorio

- `api/`: backend FastAPI, testes em `api/tests/`
- `ml/`: modelo de priorizacao e testes
- `models/`: modelo treinado e `metrics.json`
- `app/`: reservado ao frontend (hoje so `.gitkeep`)
- `infra/`: schema do banco, scripts de banco e o hello world do deploy de teste
- `docs/`: decisoes tecnicas, checkpoints, auth, deploy, container e relatorios de seguranca
- `data/`: dataset simulado, gerador, historico simulado e `seed_demo.json`
- `.github/workflows/`: pipeline de CI

## Como rodar

### Local

Precisa de Python 3.11 ou mais (o scikit-learn 1.8 do modelo nao instala no 3.10).

```
python -m venv .venv
.venv\Scripts\activate          # Windows; no Linux/Mac: source .venv/bin/activate
pip install -r api/requirements-dev.txt
copy .env.example .env          # no Linux/Mac: cp .env.example .env
```

Edite o `.env`: gere o `JWT_SECRET` com `python -c "import secrets; print(secrets.token_urlsafe(48))"` (minimo 32 caracteres) e preencha `ADMIN_EMAIL` e `ADMIN_PASSWORD` (10 ou mais caracteres). O admin e criado na primeira subida. Depois:

```
uvicorn api.main:app --reload
```

Swagger em http://localhost:8000/docs e health check em `/health`. Sem `JWT_SECRET` a API nao sobe.

Por padrao a API guarda tudo em memoria e perde os dados quando reinicia. Pra usar o banco, ponha `STORAGE=postgres` e `SUPABASE_DB_URL` no `.env` e crie as tabelas uma vez com `python infra/db/aplicar_schema.py` (pode repetir sem problema). `GET /health/db` mostra qual storage esta ativo e, no Postgres, testa a conexao.

Pra ter dados de exemplo com a API de pe, `python -m api.seed_dev` cadastra um doador e uma ONG (nao duplica se ja houver doador). O fluxo completo da demo em memoria, sem subir a API, roda com `python -m api.demo_checkpoint`.

### Docker

Da raiz do repo:

```
docker build -t rede-alimenta-api -f api/Dockerfile .
docker run -d --name rede-api -p 8000:8000 \
  -e STORAGE=postgres -e SUPABASE_DB_URL -e JWT_SECRET -e ADMIN_EMAIL -e ADMIN_PASSWORD \
  rede-alimenta-api
```

`-e VAR` sem valor copia a variavel do shell, entao a senha do banco nao aparece no comando. Sem `STORAGE=postgres` a API sobe em memoria. A imagem usa Python 3.12, roda com um usuario sem root e traz um healthcheck em `/health`. O `.dockerignore` deixa o `.env` de fora.

O `docker-compose.yml` sobe so a API (`docker compose up --build`, com `JWT_SECRET` no `.env`); o servico do Streamlit esta comentado ate o frontend existir. Ele so foi testado no job `compose` do CI, nao na maquina de ninguem. Medidas, o que foi e o que nao foi testado em `docs/container.md`; achados do Trivy em `docs/security/trivy-imagem.md`.

### Producao

A API roda no Render (plano free, regiao Ohio, a mesma do Supabase), criada pelo Blueprint do `render.yaml` a partir da `main`. O deploy automatico esta desligado (`autoDeployTrigger: "off"`): publicar e uma acao manual no painel do Render.

1. New > Blueprint, apontando pro repo, branch `main`.
2. Preencher `SUPABASE_DB_URL`, `ADMIN_EMAIL` e `ADMIN_PASSWORD`. Na primeira vez o Render nao perguntou e o servico subiu sem elas: `/health` deu 200 mas o login dava 500. Depois de qualquer deploy, confira na aba Environment que as tres continuam la. `/health` sozinho nao prova que o banco esta ligado, use `/health/db`.
3. Aplicar o schema no Supabase com `python infra/db/aplicar_schema.py`.
4. Conferir com `python -m infra.db.testar_producao`, que roda o fluxo ponta a ponta contra a URL publica e apaga o que criou.

Antes de uma apresentacao: o servico dorme depois de uns 15 minutos sem trafego e o primeiro pedido leva cerca de 22 s (medido uma vez). O primeiro `POST /lotes` leva mais uns 10 s porque carrega o modelo. Abra `/health` uns 5 minutos antes e faca um `POST /lotes` de aquecimento. Detalhes, riscos e o plano B em `docs/deploy-render.md`.

## Variaveis de ambiente

A lista completa, com placeholders, esta em `.env.example`. O `.env` fica fora do git. No Render elas entram pelo painel ou pelo `render.yaml`; nunca vao pra imagem.

| Variavel | Padrao | Pra que serve |
|---|---|---|
| `STORAGE` | `memory` | `memory` ou `postgres`. Em producao tem que ser `postgres`; em memoria a API sobe sem reclamar e perde tudo a cada deploy |
| `SUPABASE_DB_URL` | sem padrao | Conexao do Supabase (session pooler, IPv4). Obrigatoria com `STORAGE=postgres` e nos scripts de `infra/db/`. Senha com caractere especial precisa de percent-encode |
| `JWT_SECRET` | sem padrao | Assina os tokens. Minimo 32 caracteres; sem ele a API nao sobe. No Render e gerado pelo Blueprint |
| `TOKEN_MINUTOS` | `30` | Validade do token |
| `ADMIN_EMAIL`, `ADMIN_PASSWORD` | vazios | Admin criado na subida se o e-mail ainda nao existir. Sem as duas a API nao cria admin |
| `MAX_BODY_BYTES` | `65536` | Maior corpo de pedido aceito (acima disso volta 413) |
| `CONFIAR_CF_CONNECTING_IP` | desligada | Com `1`, o IP do cliente (limite de pedidos e log) vem do `CF-Connecting-IP`. Ligar so no Render: fora de um proxy que sobrescreva o cabecalho, qualquer cliente forja o IP |
| `KG_POR_REFEICAO` | `0.5` | Fator dos KPIs de impacto. Premissa do grupo, sem fonte ainda (`docs/kpis.md`) |
| `PORT` | `8000` | So no `render.yaml`, pra bater com a porta do Dockerfile |
| `API_URL` | `http://localhost:8000` | So nos scripts que falam com a API por HTTP (`api/seed_dev.py`, `infra/db/testar_login.py`, `infra/db/testar_producao.py`) |
| `MONGODB_URI` | sem padrao | So pro `infra/db/test_connections.py` (comparacao de bancos do dia 3). A API nao usa |

## Reset da demo

`infra/db/reset_demo.py` devolve o banco em nuvem ao estado inicial da demo. O seed fica em `data/seed_demo.json`: 3 doadores (DEMO) e 5 lotes simulados e 4 ONGs reais (dados publicos da Receita e do OpenStreetMap, com `capacidade_kg` e `necessidades` simuladas). E o mesmo conteudo de `api/seed_demo.py`, de Charles (`docs/seed-demo.md`), e um teste falha se os dois se afastarem. Use `reset_demo` pra voltar o banco ao estado da demo; use `api.seed_demo` pra popular uma API de pe sem apagar nada. A validade dos lotes e contada em dias a partir do dia do reset, entao nenhum lote nasce vencido.

```
python -m infra.db.reset_demo backup             # guarda o seed na tabela demo_seed
python -m infra.db.reset_demo reset              # so mostra o que seria apagado
python -m infra.db.reset_demo reset --aplicar    # apaga e recarrega o seed
python -m infra.db.reset_demo reset --aplicar --seed-do-banco   # usa a copia do banco
```

O reset apaga doacoes, lotes, doadores, ONGs e usuarios que nao sejam admin, zera os ids (o primeiro lote volta a ser o 1) e recarrega o seed pelas mesmas regras da API, com a prioridade vinda do modelo. Os admins ficam. Tudo roda numa transacao. Antes de apagar, as linhas que existiam vao pra `backups/` (fora do git, sem o hash das senhas). A tabela `demo_seed` vem do `schema.sql`, entao rode `aplicar_schema.py` antes do primeiro `backup`.

Nao rode `api.fluxo_http` contra a URL publica: ele cria doacoes, que nao tem DELETE na API e ficam no banco de producao. Se rodar, o reset limpa.

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

## Testes e qualidade

```
pytest api        # sempre em memoria, nunca toca o banco
pytest ml
ruff check .
```

Em 14/10: 424 testes em `api` (29 deles de ataque, em `api/tests/test_seguranca.py`) e 63 em `ml`, todos passando, e o ruff sem achados. O fluxo em producao tem seu proprio script (`infra.db.testar_producao`, 17 verificacoes no dia 23). O CI esta em `.github/workflows/ci.yml` (ruff, pytest, Bandit, pip-audit das tres listas de dependencias, build e Trivy da imagem, `/health` do container e `docker compose`); passou nos tres jobs no GitHub em 14/10, depois de dois ajustes (`python -m pytest` e a tag da action do Trivy).

## Referencia da API

### Autenticacao e papeis

Todo endpoint, menos `/health`, `/docs` e `POST /auth/login`, pede token. Decisoes em `docs/auth.md`.

1. `POST /auth/login` com `{"email": ..., "senha": ...}` devolve `access_token` (JWT, vale 30 min). Erro de login volta 401 sempre com a mesma mensagem; 5 erros no mesmo e-mail em 15 min voltam 429 com `Retry-After`.
2. Nas demais chamadas: `Authorization: Bearer <token>`. No Swagger, botao "Authorize".
3. Quem cria usuario e o admin (`POST /usuarios`); nao existe cadastro aberto.

| Papel | Pode |
|---|---|
| `admin` | tudo |
| `doador` | ler e editar o proprio cadastro; criar, ver, editar e apagar os proprios lotes; confirmar doacao dos proprios lotes; listar as ONGs |
| `ong` | listar as ONGs e editar a propria; ver os lotes e doacoes que recebeu |

Sem token valido volta 401; papel ou dono errado volta 403. A matriz completa esta em `api/tests/test_acesso_negado.py`.

### Lote: contrato

O frontend le a URL da API da variavel `API_URL` (padrao `http://localhost:8000`). Fluxo: `POST /lotes` e depois `GET /lotes`.

```json
{
  "doador_id": 1,
  "descricao": "alface",
  "quantidade_kg": 12.5,
  "validade": "2026-10-01",
  "armazenamento": "refrigerado"
}
```

`armazenamento` aceita `ambiente`, `refrigerado` ou `congelado`. `quantidade_kg` tem que ser maior que zero e `descricao` nao pode ser vazia (422 caso contrario). `status`, `prioridade` e `id` voltam preenchidos pela API; o cliente nao consegue setar `prioridade`.

### Doador

- `documento` aceita com ou sem mascara, mas precisa ter 11 digitos (`fisica`) ou 14 (`juridica`); a API guarda so os digitos. Nao valida digito verificador.
- `estado` e a sigla com 2 letras (vira maiuscula). `email`, se vier, precisa ter formato de e-mail. Latitude entre -90 e 90, longitude entre -180 e 180.
- `PUT /doadores/{id}` e atualizacao parcial; documento e tipo de pessoa nao mudam.
- 201 criou, 204 apagou, 404 nao achou, 409 documento repetido ou doador com lotes, 422 dado invalido.

### ONG e lote: regras

ONG:
- `cnpj` com ou sem mascara, 14 digitos, guardado sem mascara. CNPJ repetido volta 409. Nao muda depois de criada.
- `capacidade_kg` entre 0 e 100000. `necessidades` vira minuscula, sem repetido e sem vazio, e so aceita as 6 categorias do modelo (`hortifruti`, `padaria`, `laticinios`, `carnes_peixes`, `preparados`, `nao_pereciveis`); outra volta 422.

Lote:
- Nao aceita `validade` anterior a hoje nem mais de 730 dias a frente (422), nem `quantidade_kg` acima de 5000. A checagem e so na entrada. Os tetos sao premissa do dia 20 (`docs/decisoes.md`).
- `GET /lotes` aceita `?status=` e `?doador_id=`.
- Status so anda assim: `disponivel` -> `reservado` ou `descartado`; `reservado` -> `disponivel`, `doado` ou `descartado`. `doado` e `descartado` sao finais: qualquer edicao volta 409, e `disponivel` nao pula direto pra `doado`.
- So apaga lote `disponivel` ou `descartado`; `reservado` e `doado` voltam 409.
- `doador_id` nao muda; `prioridade` so o modelo escreve.

Prioridade: o `POST /lotes` chama `predict()` de `ml/predict.py` (contrato em `docs/ia.md`, secao 5) e grava `prioridade` (`alta`, `media` ou `baixa`) e a categoria em `tipo`. Se o doador ja mandou `tipo`, a IA nao reclassifica.

- Entrada que o modelo recusa (`tipo` fora das 6 categorias, `descricao` em branco sem `tipo`) volta 422 com a mensagem do modelo e o lote nao e cadastrado.
- Falha do modelo (arquivo `models/prioridade_v2.joblib` ausente, versao errada do scikit-learn) ou saida fora de alta/media/baixa: o lote e cadastrado com `prioridade` e `tipo` nulos e o erro vai pro log. O doador nao perde o cadastro.
- O `PUT` nao recalcula a prioridade.

### Doacao

`POST /doacoes` confirma o match. Corpo: `lote_id`, `ong_id` e, opcionais, `distancia_km` e `score` (informativos, o servidor nao recalcula). Status e timestamps sao sempre do servidor.

- Reserva o lote (`disponivel` -> `reservado`) e grava a doacao como `confirmada` no mesmo passo. Lote ou ONG que nao existe volta 404; lote que nao esta `disponivel` (inclusive confirmado por outro pedido ao mesmo tempo) volta 409. Tambem volta 409 se o lote passa da `capacidade_kg` da ONG ou se a categoria dele nao esta nas `necessidades` dela (lote sem `tipo` so confere a capacidade).
- `confirmado_em` e `tempo_match_s` (confirmacao menos o `criado_em` do lote) ficam gravados: o tempo medio de match e um `avg(tempo_match_s)`.
- Nao existe `PUT` nem `DELETE` de doacao. Se a reserva cai (`PUT /lotes/{id}` de `reservado` para `disponivel` ou `descartado`), a doacao vira `cancelada` e o lote pode ser doado a outra ONG. `reservado` -> `doado` (entrega) mantem a confirmada.
- Lote e ONG com doacao registrada nao podem ser apagados (409). `GET /doacoes` aceita `lote_id`, `ong_id` e `status`.

### KPIs

`GET /kpis/impacto` e `GET /kpis/ia`, abertos a qualquer usuario logado; cada papel soma so o que e dele. Formulas e premissas em `docs/kpis.md`.

### Erros, limites e auditoria

Todo erro volta como JSON `{"detail": ...}`.

| Codigo | Quando |
|---|---|
| 400 | corpo do pedido que nao e JSON |
| 404 | rota ou registro que nao existe (405 se o metodo nao existe na rota) |
| 409 | conflito: documento repetido, status que nao pode andar, lote que nao esta disponivel |
| 413 | corpo maior que `MAX_BODY_BYTES` |
| 422 | JSON valido com campo errado. `detail` e uma lista de `{type, loc, msg}`, sem o valor recebido |
| 429 | limite de pedidos estourado (120 por minuto por rota e por usuario ou IP; 30 em `POST /lotes` e `POST /doacoes`; 10 em `POST /usuarios`). Veja `docs/limites.md` |
| 500 | erro nosso. Corpo generico `{"detail": "Erro interno do servidor", "request_id": ...}`; o stack trace fica so no log |
| 503 | banco fora do ar (mesmo `request_id`) |

Toda resposta traz o header `X-Request-ID`; com ele se acha a linha no log. `quantidade_kg` e `capacidade_kg` nao aceitam NaN nem infinito; `descricao` vai ate 500 caracteres e `tipo` ate 50.

O log de auditoria sai no stdout, uma linha JSON por pedido (`tipo: requisicao`: metodo, path, status, ms, ip) e uma por mudanca de dado (`tipo: evento`: `lote.criado`, `lote.atualizado` com `status_de` e `status_para`, `doacao.confirmada`, `doacao.cancelada`, `doador.criado`...). Nao grava corpo nem querystring, entao CPF, CNPJ, e-mail e telefone nao aparecem. Codigo em `api/erros.py` e `api/auditoria.py`.

## Documentacao

| Arquivo | Assunto |
|---|---|
| `docs/decisoes.md` | decisoes tecnicas e premissas (tetos, regra da doacao) |
| `docs/auth.md` | JWT, papeis, senhas |
| `docs/limites.md` | limite de pedidos e de corpo |
| `docs/ia.md` | modelo e contrato do `predict()` |
| `docs/kpis.md` | formulas dos KPIs |
| `docs/container.md` | imagem Docker, medidas e o que nao foi testado |
| `docs/deploy-render.md` | deploy, cold start, IP do cliente atras do Render |
| `docs/security/trivy-imagem.md` | Trivy na imagem e no repo |
| `docs/lgpd.md`, `docs/stride.md` | dados pessoais e matriz de ameacas (rascunhos, sem revisao) |
| `docs/security/testes.md`, `docs/security/vulnerabilidades.md` | testes de ataque e achados do Bandit, pip-audit e Trivy com a decisao de cada um |
| `docs/matching.md`, `docs/seed-demo.md` | matching e seed de demo com ONGs reais |
| `docs/checkpoint-rubrica.md`, `docs/pitch-roteiro.md`, `docs/arquitetura-perguntas.md` | preparo da defesa |
| `docs/db-comparacao.md`, `docs/deploy-comparacao.md` | comparacoes que levaram ao Supabase e ao Render |
| `docs/checkpoint-*.md` | o que fechou e o que nao esta no repo, por semana |

## O que ainda nao esta no repo

Conferido em 13/10 contra a `main` do GitHub:

- Rota de matching (`POST /matching/{lote_id}`). A funcao `ml/matching.py` esta pronta e testada, e o trecho da rota esta em `docs/matching.md`. Hoje a ONG de cada doacao e escolhida por quem chama a API.
- Frontend e dashboard: `app/` so tem `.gitkeep`. Sem eles a demo visual e o Swagger em `/docs`.
- Teste do `docker compose up` na maquina de alguem: so o CI o rodou.
- Protecao de branch na `main`: o plano free do GitHub nao oferece em repo privado.
- Relatorio do Bandit em `docs/security/`. O CI guarda o resultado como artefato a cada execucao.
- Revisao de `docs/lgpd.md` e `docs/stride.md`, que sao rascunhos.

## Status

Semana 4, dias 24 e 25: reset da demo e README. Ver `docs/checkpoint-dia23.md` pro estado da producao e `docs/checkpoint-rubrica.md` pra comparacao com a rubrica.
