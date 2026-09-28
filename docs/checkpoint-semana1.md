# Checkpoint da Semana 1 (dia 7, 28/09)

Conferencia do checklist da semana contra o que esta no GitHub (main e
branches, conferido em 28/09). O que nao aparece la marquei como "nao esta no
repo": pode existir so na maquina de alguem, entao vale cobrar no sync.

## Checklist

| Item | Estado | Dono | Observacao |
|---|---|---|---|
| Repo com pastas, `.gitignore`, `.env.example` | feito | Rafael / Anthony | |
| Main protegida (PR obrigatorio) | nao aplicavel hoje | Rafael (dono do repo) | Ver "GitHub" abaixo: o repo e privado em conta gratuita, entao o GitHub nao aplica regra de protecao. Por enquanto e so combinado entre a gente |
| Decisoes travadas (Render, Supabase) | feito | Rafael | `docs/decisoes.md`. Falta o grupo confirmar no sync que o arquivo diz que foi combinado |
| Dataset v0 versionado, com fonte e real vs. simulado | feito | Charles | `data/README.md`, EDA em `ml/eda_v0.md` |
| STRIDE v1 | nao esta no repo | Anthony | Dia 6 pedia fechar revisando com Charles e Rafael |
| Wireframe das telas | nao esta no repo | Gustavo | |
| API esqueleto (`/health` + CRUD) | feito | Rafael | Doador, ONG e Lote. CRUD fechado com validacao e 409 nos dias 8 e 9, 68 testes passando |
| Streamlit conversando com a API | nao esta no repo | Gustavo | `app/` so tem `.gitkeep`. Contrato pronto no README |
| CI com ruff e pytest | nao esta no repo | Anthony | Nenhum workflow em `.github/` e a aba Actions esta vazia. `pytest api` ja funciona pra ele plugar |

## GitHub (conferido em 28/09)

- **Protecao da main:** nao existe e nao da pra aplicar. Tanto a regra classica
  quanto o ruleset avisam que nao valem em repo privado sem GitHub Team. Sem
  isso, qualquer colaborador com push consegue subir direto na main: o Charles
  fez isso em 27/09 (upload pela web). Opcoes: tornar o repo publico (a protecao
  passa a valer de graca; antes disso tirar do `.env.example` o host do Supabase
  e o usuario do Atlas) ou manter privado e seguir a regra so por combinado.
  Decisao do grupo.
- **Pull requests:** nenhum aberto ou fechado ate agora.
- **Actions:** nenhum workflow.
- **Branches:** alem da main, `feat/dia6-7-integracao-checkpoint`,
  `feat/dia8-crud-doador-validacao` e `feat/dia9-crud-ong-lote`, empilhadas
  nessa ordem. Merge na mesma ordem.
- **Colaboradores:** nao consegui conferir (a pagina pede confirmacao no app do
  GitHub). Rafael confere se Anthony e Gustavo foram convidados.

## Dia 6: o que rodou

Subi a API local, cadastrei doador e ONG, criei um lote e listei. Funcionou.
Na rodada apareceram tres problemas:

- Lote aceitava `quantidade_kg` negativa ou zero e `descricao` vazia, o que o
  `schema.sql` recusa. Corrigido em `api/models.py` (agora 422).
- Doador com `documento` repetido voltava 201, mas o schema tem `unique`. Virou
  409 no dia 8.
- Apagar um doador que tinha lote deixava o lote orfao; no Postgres seria erro de
  chave estrangeira. Virou 409 no dia 8.

Com o storage em memoria (situacao do dia 6), o `--reload` apaga os dados a cada salvamento e o
Streamlit passa a receber 404 no `doador_id`. Por isso o `api/seed_dev.py`.

Nao consegui testar o lado do Streamlit porque o formulario do Gustavo nao
chegou na main. Assim que chegar, a checagem e cadastrar um lote pela tela e
ve-lo em `GET /lotes`.

## Ajustes pra Semana 2

- O `tipo` do lote (API) e a `categoria` do dataset sao a mesma coisa: hortifruti,
  padaria, laticinios, carnes_peixes, preparados, nao_pereciveis. Combinar com o
  Charles que `predict()` devolve exatamente esses valores e a prioridade sai
  como `alta`, `media` ou `baixa`. Hoje a API guarda os dois como texto livre;
  vale virar enum quando o modelo estiver pronto.
- O dataset tem 76 lotes sem latitude/longitude, 34 sem armazenamento e 28 sem
  descricao. Na API `armazenamento` e obrigatorio, entao o Charles precisa
  decidir o que fazer com esses nulos antes do dia 11.
- Falta a tabela `doacoes` no `schema.sql`. Entra junto com o dia 12
  (`POST /doacoes`).
- Os problemas do CRUD (documento repetido, delete com lote, validacao) sairam
  nos dias 8 e 9. Codigos: 201 criou, 404 nao achou, 409 conflito (documento ou
  CNPJ repetido, doador com lote, status invalido), 422 dado invalido.
- Python: rodei local no 3.14 e o Dockerfile planejado usa 3.10-slim. Vale o
  Anthony rodar os testes em 3.10 no CI pra pegar diferenca cedo.

## Dia 10: banco em nuvem

A API agora fala com o Supabase. O `api/storage.py` tem dois backends com a
mesma interface, escolhidos pela variavel `STORAGE` (`memory` por padrao,
`postgres` pra usar o banco). Os testes ficam sempre em memoria.

- Schema aplicado com `infra/db/aplicar_schema.py`, com RLS ligado nas tres
  tabelas (o Supabase expoe o schema `public` numa API REST propria; sem RLS ela
  ficaria aberta pra quem tiver a chave publica. A nossa API conecta como
  `postgres`, que ignora o RLS).
- Testei o fluxo inteiro contra o banco (CRUD, 409, filtros, transicao de
  status) e a persistencia depois de reiniciar a API. Cada chamada leva uns 2
  segundos porque o pooler fica em us-east-2. Vale lembrar disso na demo e ver
  se compensa recriar o projeto numa regiao mais perto.
- O seed (`python -m api.seed_dev`) rodou no banco: 1 doador e 1 ONG rotulados
  DEMO. O seed maior de demo (3 doadores, 4 ONGs, 5 lotes) e do Charles, dia 21.
- Erros de banco viram resposta limpa: violacao de unique ou FK vira 409 e banco
  fora do ar vira 503.
- Ponto de atencao: o free tier do Supabase pausa o projeto depois de 1 semana
  sem uso. Antes da defesa, abrir o painel e conferir que esta ativo.
- Nao ha pytest contra o Postgres de verdade (so tem um banco, e seria o de
  demo). Se der tempo, montar um schema separado so pra teste.
