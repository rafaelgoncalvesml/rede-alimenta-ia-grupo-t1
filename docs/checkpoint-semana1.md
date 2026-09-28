# Checkpoint da Semana 1 (dia 7, 28/09)

Conferencia do checklist da semana contra o que esta no repo. Onde eu (Rafael)
nao consigo ver o estado real, marquei "confirmar" com o dono.

## Checklist

| Item | Estado | Dono | Observacao |
|---|---|---|---|
| Repo com pastas, `.gitignore`, `.env.example` | feito | Rafael / Anthony | |
| Main protegida (PR obrigatorio) | confirmar | Anthony | O historico tem commits direto na main depois do dia 5, inclusive meus. Conferir em Settings > Branches |
| Decisoes travadas (Render, Supabase) | feito | Rafael | `docs/decisoes.md`. Falta o grupo confirmar no sync que o arquivo diz que foi combinado |
| Dataset v0 versionado, com fonte e real vs. simulado | feito | Charles | `data/README.md`, EDA em `ml/eda_v0.md` |
| STRIDE v1 | nao esta no repo | Anthony | Dia 6 pedia fechar revisando com Charles e Rafael |
| Wireframe das telas | nao esta no repo | Gustavo | |
| API esqueleto (`/health` + CRUD) | feito | Rafael | Doador, ONG e Lote, storage em memoria, 7 testes passando |
| Streamlit conversando com a API | nao esta no repo | Gustavo | `app/` so tem `.gitkeep`. Contrato pronto no README |
| CI com ruff e pytest | nao esta no repo | Anthony | `pytest api` ja funciona pra ele plugar |

## Dia 6: o que rodou

Subi a API local, cadastrei doador e ONG, criei um lote e listei. Funcionou.
Na rodada apareceram tres problemas:

- Lote aceitava `quantidade_kg` negativa ou zero e `descricao` vazia, o que o
  `schema.sql` recusa. Corrigido em `api/models.py` (agora 422).
- Doador com `documento` repetido volta 201, mas o schema tem `unique`. Fica pro
  dia 8 (validacao e codigos HTTP), deve virar 409.
- Apagar um doador que tem lote deixa o lote orfao; no Postgres seria erro de
  chave estrangeira. Tambem dia 8.

Como o storage e em memoria, o `--reload` apaga os dados a cada salvamento e o
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
  (`POST /doacoes`), mas o desenho pode sair antes, no dia 10, quando a API
  ligar no Supabase.
- Dia 8 pra mim ficou maior: validacao do Doador, 409 de duplicado, bloqueio de
  delete com lote. Nao da pra deixar pra depois porque o Gustavo consome no dia 8.
- Python: rodei local no 3.14 e o Dockerfile planejado usa 3.10-slim. Vale o
  Anthony rodar os testes em 3.10 no CI pra pegar diferenca cedo.
