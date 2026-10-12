# Checkpoint da Semana 3 (dia 21)

Conferido em 10/10 contra o GitHub (`origin/main` e as 9 branches abertas) e rodando o que
existe na minha maquina. Mesma regra das semanas anteriores: o que nao aparece no repo vai como
"nao esta no repo", porque pode estar so na maquina de alguem. Nao existe nenhuma branch do
Anthony, do Gustavo ou do Charles alem dos uploads do Charles na `main` de 29/09.

## Checklist

| Item | Estado | Dono | Observacao |
|---|---|---|---|
| Dockerfile da API | feito | Rafael | `api/Dockerfile`, testado em 06/10 contra o Supabase (`docs/container.md`). Rebuildado e testado em 12/10 com o codigo desta semana, em memoria e contra o Supabase (`docs/fluxo-dia20.md`) |
| `docker-compose.yml` subindo tudo | **nao esta no repo** | Anthony | Sem ele nao ha "um comando" e nao ha frontend pra subir junto |
| Pipeline (ruff, pytest, Bandit, Trivy, build) | **nao esta no repo** | Anthony | Nao existe `.github/`. Rodei ruff, pytest, Bandit e Trivy na mao (dias 14, 20 e 21); nada disso roda em CI ainda |
| Autenticacao e papeis (RBAC) | feito | Rafael | JWT, 3 papeis, matriz de acesso negado testada. 28 verificacoes contra o Supabase hoje |
| Endpoints de KPI | feito | Rafael | `/kpis/impacto` e `/kpis/ia`. **Nada os consome**: nao ha dashboard no repo |
| Rate limit e validacao de entrada | feito | Rafael | Limite por rota e de corpo (dia 18). Hoje entraram os tetos de quantidade, capacidade e validade |
| Relatorios SAST v1 em `docs/security/` | **parcial** | Anthony | A pasta passou a existir com `trivy-imagem.md` (rodado por mim, saida real). Falta o Bandit no mesmo formato (o do dia 14 esta em `docs/checkpoint-semana2.md`) e o `testes.md` do Anthony |
| Dashboard v1 | **nao esta no repo** | Gustavo | `app/` so tem `.gitkeep` desde o dia 7 |
| Matching | **nao esta no repo** | Charles | Issue 8 |
| Seed de demo (3 doadores, 4 ONGs, 5 lotes) | **nao esta no repo** | Charles | O `api/seed_dev.py` e meu e cria 1 doador e 1 ONG |

Das seis linhas do checklist oficial da semana, **tres fecham** (RBAC, KPIs como endpoint,
rate limit e validacao) e **tres nao** (compose, pipeline, SAST em `docs/security/`). O marco
"dashboard v1" tambem esta aberto.

## O que rodou (10 e 12/10)

- `pytest api ml`: **408 passaram**, 0 falhas. Em memoria, Python 3.14.
- `ruff check .`: limpo.
- Bandit 1.9.4 em `api ml infra data` (2247 linhas, sem os testes): **0 alta, 0 media**, 4
  baixas (as mesmas do dia 14, no gerador do dataset).
- `pip-audit` 2.10.1 nos tres `requirements.txt`: sem vulnerabilidade conhecida.
- Container (imagem reconstruida) com `python -m api.fluxo_http`: 16 verificacoes ok.
- Container contra o Supabase com `python -m infra.db.testar_login`: 28 ok, banco igual antes e
  depois.
- Trivy 0.75.0 (imagem oficial `aquasec/trivy`) na imagem e no repo: **0 critica**, 0 achado nos
  pacotes Python, 44 HIGH do sistema Debian **sem correcao publicada**. `--ignore-unfixed` com
  HIGH e CRITICAL passa. O Trivy achou 4 coisas que consertei (pip da imagem base, `liblzma5`, pip
  embutido com `urllib3` velho e o `infra/deploy-test` rodando como root); detalhes em
  `docs/security/trivy-imagem.md`.
- **Nao rodou:** `docker compose` (nao existe), nada em CI e qualquer teste em outra maquina.

## Issues

Fechadas no codigo (PR a abrir): 7, 9, 10, 11 e 12, detalhes em `docs/fluxo-dia20.md`. Segue
aberta a 8 (matching e tela). Os tetos da 11 e a regra da 9 sao palpite meu e **precisam do
aval do grupo** (`docs/decisoes.md`).

## PRs

Nove PRs meus abertos e empilhados (5, 6 e 13 a 19), **nenhum na `main`**, mais o de hoje por abrir. A `main` nao
tem modelo na API, doacao, auth, KPIs, limites nem a imagem. O Render faz deploy da `main`:
sem esses merges, o dia 22 publicaria uma API velha. Ordem: 5, 6, 13, 14, 15, 16, 17, 18, 19,
depois o de hoje. Cada merge pede pipeline verde pela regra do grupo, e o pipeline nao existe.

## Preparo do deploy (dia 21)

`render.yaml` agora descreve a API (Docker, regiao `ohio`, `/health`, deploy manual) e
`.env.example` lista todas as variaveis. Passo a passo, o que e do Render e o que depende de
conta: `docs/deploy-render.md`. Nao validei o arquivo no Render.

## Pra decidir no sync de segunda

1. Aceita os tetos (5000 kg, 100000 kg, 730 dias) e a regra da doacao (issue 9)?
2. ONG sem `necessidades` recebe tudo ou nada? Hoje, nada.
3. Rate limit por IP no Render: medir o que chega no `X-Forwarded-For` depois do deploy (`docs/deploy-render.md`).
4. Quem faz o compose e o pipeline antes do dia 22, que e quando o deploy depende deles.

## Nao conferido

- O `gitleaks` continua nao instalado; a busca de segredos foi por `git grep` (nada achado em
  arquivos versionados; o `.env` real esta fora do git).
- Nao consegui ver se Anthony, Gustavo e Charles tem trabalho local nao enviado.
- O `.env.example` antigo ficou no historico do git com o ref do Supabase e o usuario do Atlas.
  Nao e senha; decidir se vale rotacionar o usuario do Atlas.
