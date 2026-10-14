# Checkpoint contra a rubrica (13/10, entrega e defesa em 15/10)

A entrega e a defesa foram adiantadas pra 15/10. Este arquivo cruza cada entregavel do PDF do
professor com o que existe no repo hoje.

Existem duas versoes do repo e elas nao batem:

- A `main` do GitHub (`origin/main`, commit `8cc4be4`). Hoje (13/10) o usuario `CharlotteDxD`
  (Charles) subiu 47 commits direto nela, pela interface web ("Add files via upload" e "Delete ...").
  Entraram matching, modelo v2, historico simulado, `seed_demo.py` e docs. A secao abaixo descreve
  um clone limpo dessa `main`.
- A branch local do Rafael (`feat/dia24-25-reset-demo-readme`), que parte da `main` de ontem e tem
  mudancas nao commitadas (README, `api/main.py`, `schema.sql`, `reset_demo.py`,
  `data/seed_demo.json`). Ela nao tem nada do que Charles subiu e mexe nos mesmos arquivos
  (`README.md`, `api/main.py`), entao vai dar conflito ao juntar.

O Render roda a versao de antes das duas (o deploy e manual).

## O que rodou agora

Clone limpo da `origin/main` num diretorio novo, venv novo, `pip install -r api/requirements-dev.txt`:

| Verificacao | Resultado |
|---|---|
| Instalacao do zero (Python 3.14.3 do Windows) | sem erro |
| `pytest api` / `pytest ml` | 392 / 63 passaram, 0 falhas (455 no total) |
| `ruff check .` | sem achados |
| `bandit -r api ml infra` (sem os testes) | 0 achados (baixa, media e alta) |
| Segredos no que o git rastreia | so placeholders em `.env.example`; `.env` e `backups/` estao no `.gitignore` |
| `GET /health` na URL publica | 200, 0,28 s |
| `GET /health/db` na URL publica | 200, `storage: postgres`, 0,30 s |

O `pip-audit` tambem rodou em `api/requirements.txt` e `ml/requirements.txt`: 0 vulnerabilidades.

Nao rodei o `testar_producao.py` nem nada que escreva no banco em nuvem. Na maquina os testes
rodaram no Python 3.14. O `docker build` e o Trivy so rodaram no CI do GitHub (secao "O que este PR muda").

## Rubrica, eixo por eixo (estado da `origin/main`)

| Eixo (peso) | Pede | Estado | Lacuna |
|---|---|---|---|
| Impacto social (30%) | relevancia, utilidade, empatia | API, `/kpis/impacto`, seed de demo com 4 ONGs reais, reset da demo | nao ha tela: o impacto so aparece em JSON e no Swagger |
| Qualidade da IA (20%) | eficacia do modelo, dados abertos, bibliotecas gratis | Random Forest v2, F1 macro 0,669 contra 0,610 da regra por dias; 63 testes em `ml`; `ml/matching.py` pronto (haversine, filtro por categoria e capacidade) | dados 100% simulados; a rota `POST /matching/{lote_id}` nao existe, so a funcao; o README de Charles diz que a diferenca pro baseline vai de -0,001 a +0,117 de F1 (IC 95%) |
| DevSecOps (30%) | pipeline CI/CD, SAST, container | Dockerfile sem root, Trivy corrigido, auth, limites, auditoria, deploy no Render; nesta branch: `ci.yml`, `docs/lgpd.md`, `docs/stride.md` | sem docker-compose; sem protecao de branch na `main` (o workflow passou no GitHub em 14/10) |
| Engenharia e defesa (20%) | codigo, README, pitch | README, 455 testes, docs por tema | o README da `main` e o da semana 3 (sem a parte de producao, reset e variaveis, que esta na branch local do Rafael); roteiro do pitch e rascunho |

Checkpoint 3 do PDF (URL publica, banco em nuvem, README, pitch): URL e banco estao no ar, o README
existe mas esta desatualizado na `main`, e o pitch e rascunho.

## Dashboard (o PDF pede tres blocos de KPI)

| Bloco do PDF | Backend | Tela |
|---|---|---|
| Impacto social: kg salvos e refeicoes por regiao | `/kpis/impacto` (`por_estado`, `por_dia`) | nao existe |
| Seguranca (SAST): saude do pipeline, vulnerabilidades, security gates | `/kpis/seguranca` nao existe | nao existe |
| IA insights: acuracia e tempo medio de match | `/kpis/ia` e `tempo_medio_match_s` | nao existe |
| Mapa de calor | `historico_simulado.json` tem coordenadas, sem endpoint agregado | nao existe |

`app/` continua so com `.gitkeep`. Plano B ja documentado: demo no Swagger em `/docs`.

## Decisoes pro grupo (14/10)

Com o congelamento valendo, e escolher entre fazer e declarar como "nao entrou". Do menor custo
pro maior:

1. Juntar o trabalho do Rafael com a `main` (README e `api/main.py` conflitam; o `seed_demo.py` de
   Charles e o `reset_demo.py` com `seed_demo.json` do Rafael fazem coisas parecidas). Decidir
   qual seed fica.
2. Limpar a `main`: `.ruff_cache/` e a linha solta do README. Feito neste PR.
3. `docs/lgpd.md` e `docs/stride.md`: feitos neste PR como rascunho. Anthony le e corrige.
4. Relatorio Bandit: o job do CI guarda `bandit.txt` como artefato a cada execucao. Falta copiar um
   resultado pra `docs/security/` se a banca pedir o arquivo no repo.
5. Workflow de GitHub Actions: feito neste PR (`.github/workflows/ci.yml`) e verde no GitHub em
   14/10. Falta ligar a protecao da `main` (exigir PR e checks).
6. `docker-compose.yml` so da API: nao feito.
7. Ligar `POST /matching/{lote_id}`: `docs/matching.md` ja traz o trecho da rota. E feature, entao
   precisa do aval do grupo pra furar o congelamento; sem ela, a defesa tem que dizer que a ONG
   da doacao ainda e escolhida por quem chama a API.
8. Tela minima (Streamlit chamando `/kpis/impacto` e `/kpis/ia`). Maior risco de prazo.
9. Redeploy no Render com a versao final, ja que o deploy e manual e o que esta no ar e antigo.

Os itens 2 a 6 nao sao feature de produto e cabem no congelamento.

## O que este PR muda

Branch `chore/lgpd-ci-ajustes`, criada de `origin/main`, sem tocar na branch local do Rafael.

| Mudanca | Arquivo |
|---|---|
| Mapeamento de dados pessoais (rascunho) | `docs/lgpd.md` |
| Matriz STRIDE (rascunho, estava faltando desde o checkpoint 1) | `docs/stride.md` |
| Pipeline: ruff, pytest, Bandit, pip-audit, build, Trivy, `/health` do container | `.github/workflows/ci.yml` |
| Linha solta do README e afirmacoes falsas ("Compose", "frontend em Streamlit") corrigidas; secao do CI | `README.md` |
| `.ruff_cache/` fora do git | indice do git |
| Comentarios que apontavam pro modelo v1 e pro "workflow do dia 22" que nao existia | `api/requirements.txt`, `ml/requirements.txt`, `render.yaml` |
| Estes tres documentos de defesa | `docs/checkpoint-rubrica.md`, `docs/pitch-roteiro.md`, `docs/arquitetura-perguntas.md` |

Na maquina, os comandos do workflow (`ruff`, `pytest api ml`, `bandit`, `pip-audit`) passaram no
Python 3.14 (455 testes). No GitHub (14/10) o workflow passou nos tres jobs: ruff e pytest no Python
3.12, Bandit e pip-audit, e build da imagem com Trivy e `/health` do container. Antes disso falhou duas
vezes por erro nosso: o `pytest` sem `python -m` nao achava o pacote `api`, e a tag da action do
Trivy estava errada (`0.28.0` em vez de `v0.28.0`; ficou a `v0.36.0`).

## Bugs e pontos fracos conhecidos

Nenhum teste falha e o Bandit nao achou nada. Os itens abaixo vem de ler o repo e rodar em 13/10.

| # | Ponto | Gravidade | Sugestao de dono |
|---|---|---|---|
| 1 | README da `main` comecava com uma linha de link solta, resto do upload pela web | media | corrigido neste PR |
| 2 | `.ruff_cache/` (14 arquivos) foi commitado na `main` pelo upload | baixa | corrigido neste PR (`git rm --cached`; o `.gitignore` ja ignorava) |
| 3 | Producao roda o modelo v1; a `main` apagou `prioridade_v1.joblib` e tem so o v2. Deploy manual: quem apertar o botao muda o modelo (e as metricas) em producao | alta se redeploy for feito sem teste | Rafael: redeployar na quarta, nao na quinta de manha, e rodar `testar_producao.py` |
| 4 | Cold start de 22 s e primeiro lote de 10 s no Render free. A `main` agora carrega o modelo na subida (`pre_carregar_modelo`), o que deve tirar os 10 s do primeiro lote; nao medi em producao | alta na defesa | Rafael: medir depois do redeploy |
| 5 | Variaveis do Render (`SUPABASE_DB_URL`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`) ja sumiram uma vez num deploy; `/health` nao detecta | alta | Rafael: `/health/db` e login depois de cada deploy |
| 6 | Branch local com mudancas nao commitadas que conflitam com a `main` | media | Rafael |
| 7 | `KG_POR_REFEICAO = 0,5` e premissa; Charles achou uma referencia (EUA, 0,544 kg) em `docs/kpis.md`, ainda nao e fonte brasileira | media | Charles: dizer "premissa" na defesa |
| 8 | Tetos de lote e de ONG (5000 kg, 100000 kg) sem aval do grupo | baixa | grupo |
| 9 | Usuario do Atlas antigo segue no historico do git | media | Rafael: rotacionar no Atlas |
| 10 | Modelo ganha do baseline por pouco (IC 95% encosta em zero) e todos os dados sao simulados | media na defesa | Charles: dizer antes que a banca pergunte |
| 11 | Historico simulado tem 12 ONGs inventadas; seed de demo tem 4 reais com capacidade simulada | baixa | Charles: rotular na tela e no pitch |

## Divisao proposta (ajustar em 14/10)

| Quem | Fica com |
|---|---|
| Rafael | itens 1, 2 e 9 das decisoes; bugs 3, 5, 6 e 9; conferir URL e variaveis do Render |
| Anthony | revisar `docs/lgpd.md` e `docs/stride.md`, ver o CI rodar, proteger a `main`, compose |
| Gustavo | tela minima, se o grupo decidir que entra; senao, preparar o Swagger como demo |
| Charles | bugs 1, 7, 10 e 11; texto sobre limites do modelo pro pitch; rota de matching se o grupo aprovar |
