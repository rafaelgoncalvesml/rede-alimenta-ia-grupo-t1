# Checkpoint contra a rubrica (13/10, atualizado em 14/10; entrega e defesa em 15/10)

A entrega e a defesa foram adiantadas pra 15/10. Este arquivo cruza cada entregavel do PDF do
professor com o que existe no repo hoje.

Hoje (13/10) o usuario `CharlotteDxD` (Charles) subiu 47 commits direto na `main`, pela interface
web ("Add files via upload" e "Delete ..."). Entraram matching, modelo v2, historico simulado,
`seed_demo.py` e docs. Os numeros da secao abaixo vem de um clone limpo dessa `main` (commit
`8cc4be4`), antes dos PRs de CI/LGPD e dos dias 24 e 25 (reset da demo e README completo, que
depende do primeiro).

O Render roda a versao de antes de tudo isso (o deploy e manual).

Atualizacao de 14/10: a branch `feat/frontend-matching-relogio` (ainda sem PR) acrescenta a rota
`POST /matching/{lote_id}`, o frontend em Streamlit e a data de hoje no fuso de Brasilia. Onde a
tabela abaixo fala do estado da `main` e a branch muda a resposta, a linha traz os dois.

## O que rodou agora

### Branch `feat/frontend-matching-relogio` (14/10)

| Verificacao | Resultado |
|---|---|
| `pytest api` / `pytest ml` | 436 / 65 passaram, 0 falhas (501 no total) |
| `ruff check .` | sem achados |
| `bandit -r api ml infra` (sem os testes) | 0 achados |
| `pip-audit` em `api`, `ml`, `app` e `infra/db` | 0 vulnerabilidades nas quatro listas |
| Segredos nos arquivos alterados | nenhum; `.env` e `backups/` seguem no `.gitignore` |

Streamlit testado a mao em 14/10 contra a API local em memoria (seed da demo, usuarios de teste):
login como doador e como ONG, cadastro de lote (a IA classificou `alface americana` como
hortifruti), ranking do `/matching` com distancia e score do servidor, confirmacao da doacao
(gravada com 8,17 km e score 0,0817; um score forjado no corpo foi ignorado) e Relatorios com os KPIs
de impacto e IA. Nao rodei `docker build` nem Trivy (so no CI), nao testei contra o banco em nuvem
nem a producao, e o CI do GitHub ainda nao rodou nesta branch.

Dois defeitos achados nesse teste e corrigidos em `app/services/api_client.py`: a tela pedia o
ranking ao `/matching` a cada clique (a rota aceita 20 pedidos por minuto, entao a tela cairia na
triagem local), e a URL `localhost` custava cerca de 2 s por chamada no Windows (o `requests` tenta
`::1` antes de `127.0.0.1`), o que deixava cada clique em mais de 10 s. O ranking agora fica em cache
na sessao por 30 s e o `localhost` vira `127.0.0.1`. Pendente: pra ONG, a tela de inicio ainda diz
"Quero doar alimentos".

### `origin/main` em 13/10

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
| Impacto social (30%) | relevancia, utilidade, empatia | API, `/kpis/impacto`, seed de demo com 4 ONGs reais, reset da demo. Na branch, o Streamlit mostra o impacto em Relatorios | na `main` nao ha tela (so JSON e Swagger); a tela nao esta publicada e nao mostra o impacto por regiao |
| Qualidade da IA (20%) | eficacia do modelo, dados abertos, bibliotecas gratis | Random Forest v2, F1 macro 0,669 contra 0,610 da regra por dias; 63 testes em `ml`; `ml/matching.py` pronto (haversine, filtro por categoria e capacidade); a rota `POST /matching/{lote_id}` entra pela branch | dados 100% simulados; na `main` so existe a funcao, sem rota; o README de Charles diz que a diferenca pro baseline vai de -0,001 a +0,117 de F1 (IC 95%) |
| DevSecOps (30%) | pipeline CI/CD, SAST, container | Dockerfile sem root, Trivy corrigido, auth, limites, auditoria, deploy no Render, `ci.yml` verde no GitHub, `docker-compose.yml` da API, `docs/lgpd.md`, `docs/stride.md`, 29 testes de ataque | sem protecao de branch na `main` (indisponivel em repo privado free); deploy manual |
| Engenharia e defesa (20%) | codigo, README, pitch | README, 487 testes na `main` (501 na branch), docs por tema | o README da `main` de 13/10 era o da semana 3; o PR dos dias 24 e 25 trouxe a versao completa; roteiro do pitch ainda e rascunho |

Checkpoint 3 do PDF (URL publica, banco em nuvem, README, pitch): URL e banco estao no ar, o README
esta completo na `main` e o pitch e rascunho. A URL publica serve a API antiga; o frontend nao tem URL.

## Dashboard (o PDF pede tres blocos de KPI)

| Bloco do PDF | Backend | Tela |
|---|---|---|
| Impacto social: kg salvos e refeicoes por regiao | `/kpis/impacto` (`por_estado`, `por_dia`) | na branch: cards de impacto em Relatorios, sem recorte por regiao |
| Seguranca (SAST): saude do pipeline, vulnerabilidades, security gates | `/kpis/seguranca` nao existe | nao existe |
| IA insights: acuracia e tempo medio de match | `/kpis/ia` e `tempo_medio_match_s` | na branch: `/kpis/ia` e tempo medio de match em Relatorios |
| Mapa de calor | `historico_simulado.json` tem coordenadas, sem endpoint agregado | nao existe |

Na `main`, `app/` so tem `.gitkeep`; o Streamlit esta na branch. O bloco de seguranca e o mapa de
calor seguem sem tela, e a defesa deve dizer isso. Plano B: demo no Swagger em `/docs`.

## Decisoes pro grupo (14/10)

Com o congelamento valendo, e escolher entre fazer e declarar como "nao entrou". Do menor custo
pro maior:

1. Seed da defesa: um so, `data/seed_demo.json` com o conteudo de Charles (4 ONGs reais), carregado
   pelo `reset_demo.py` do Rafael. Um teste mantem o JSON igual a `api/seed_demo.py`.
2. Limpar a `main`: `.ruff_cache/` e a linha solta do README. Feito neste PR.
3. `docs/lgpd.md` e `docs/stride.md`: feitos neste PR como rascunho. Anthony le e corrige.
4. Relatorio Bandit: o job do CI guarda `bandit.txt` como artefato a cada execucao. Falta copiar um
   resultado pra `docs/security/` se a banca pedir o arquivo no repo.
5. Workflow de GitHub Actions: feito e verde no GitHub em 14/10. A protecao da `main` nao existe no
   plano free de repo privado (a API do GitHub devolve 403); resta o combinado do grupo de mergear
   so por PR, ou tornar o repo publico.
6. `docker-compose.yml` so da API: entrou com os testes de Anthony; o job `compose` do CI o sobe
   com `read_only` e confere `/health`.
7. Ligar `POST /matching/{lote_id}`: feito na branch `feat/frontend-matching-relogio`, com 20 pedidos
   por minuto, dono do lote ou admin, e o `POST /doacoes` gravando distancia e score calculados no
   servidor. Falta o aval do grupo pra furar o congelamento e o merge.
8. Tela minima (Streamlit chamando `/kpis/impacto` e `/kpis/ia`): feita na branch, testada a mao em 14/10
   contra a API local com os papeis doador e ONG (ver acima). Falta o merge e decidir se vai ao ar.
9. Redeploy no Render com a versao final, ja que o deploy e manual e o que esta no ar e antigo.
   Segue aberto e so faz sentido depois do merge dos itens 7 e 8.

Os itens 2 a 6 nao sao feature de produto e cabem no congelamento.

## O que os PRs #26 e #27 mudaram

PR #26 (`chore/lgpd-ci-ajustes`) e PR #27 (dias 24 e 25), ja na `main`.

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

## O que o PR de seguranca muda (14/10)

Junta o que ha de aproveitavel no PR #28 de Anthony, sem o README dele (que era o da semana 3 e
sobrescreveria o atual) e sem a pasta `upload-github/`.

| Mudanca | Arquivo |
|---|---|
| 29 testes de ataque: JWT forjado, injecao em campo, filtro, id e login, e log sem token, documento e senha | `api/tests/test_seguranca.py` |
| `pytest` sem `python -m` | `pytest.ini` |
| Compose so da API, com `read_only` e sem capabilities; o servico do Streamlit fica comentado | `docker-compose.yml` |
| STRIDE v2 de Anthony (25 ameacas, com estado e evidencia), ajustada pro CI e o modelo v2 reais | `docs/stride.md` |
| LGPD fundindo as duas versoes, com propostas de schema, mascaramento e checklist | `docs/lgpd.md` |
| Testes de ataque e achados do Bandit, pip-audit e Trivy | `docs/security/testes.md`, `docs/security/vulnerabilidades.md` |
| Job `compose` no CI; `pip-audit` das tres listas de dependencias | `.github/workflows/ci.yml` |

Ficaram de fora: o `run_sast.py` (o CI ja guarda o Bandit como artefato e o import de `subprocess`
derrubaria o nosso gate), o `bandit-report.json` e o `resumo.md` (caminhos de Windows, ficam velhos) e
o `app/Dockerfile` (nao ha frontend).

## Bugs e pontos fracos conhecidos

Nenhum teste falha e o Bandit nao achou nada. Os itens abaixo vem de ler o repo e rodar em 13/10.

| # | Ponto | Gravidade | Sugestao de dono |
|---|---|---|---|
| 1 | README da `main` comecava com uma linha de link solta, resto do upload pela web | media | corrigido neste PR |
| 2 | `.ruff_cache/` (14 arquivos) foi commitado na `main` pelo upload | baixa | corrigido neste PR (`git rm --cached`; o `.gitignore` ja ignorava) |
| 3 | Producao roda o modelo v1; a `main` apagou `prioridade_v1.joblib` e tem so o v2. Deploy manual: quem apertar o botao muda o modelo (e as metricas) em producao | alta se redeploy for feito sem teste | Rafael: redeployar na quarta, nao na quinta de manha, e rodar `testar_producao.py` |
| 4 | Cold start de 22 s e primeiro lote de 10 s no Render free. A `main` agora carrega o modelo na subida (`pre_carregar_modelo`), o que deve tirar os 10 s do primeiro lote; nao medi em producao | alta na defesa | Rafael: medir depois do redeploy |
| 5 | Variaveis do Render (`SUPABASE_DB_URL`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`) ja sumiram uma vez num deploy; `/health` nao detecta | alta | Rafael: `/health/db` e login depois de cada deploy |
| 6 | Trabalho dos dias 24 e 25 (reset da demo, README) estava so na maquina do Rafael | media | resolvido pelo PR dos dias 24 e 25 |
| 7 | `KG_POR_REFEICAO = 0,5` e premissa; Charles achou uma referencia (EUA, 0,544 kg) em `docs/kpis.md`, ainda nao e fonte brasileira | media | Charles: dizer "premissa" na defesa |
| 8 | Tetos de lote e de ONG (5000 kg, 100000 kg) sem aval do grupo | baixa | grupo |
| 9 | Usuario do Atlas antigo segue no historico do git | media | Rafael: rotacionar no Atlas |
| 10 | Modelo ganha do baseline por pouco (IC 95% encosta em zero) e todos os dados sao simulados | media na defesa | Charles: dizer antes que a banca pergunte |
| 11 | Historico simulado tem 12 ONGs inventadas; seed de demo tem 4 reais com capacidade simulada | baixa | Charles: rotular na tela e no pitch |

## Divisao proposta (ajustar em 14/10)

| Quem | Fica com |
|---|---|
| Rafael | itens 1, 2 e 9 das decisoes; bugs 3, 5, 6 e 9; conferir URL e variaveis do Render |
| Anthony | revisar `docs/lgpd.md` e `docs/stride.md` (estados e riscos), decidir o que fazer da protecao da `main` |
| Gustavo | tela minima, se o grupo decidir que entra; senao, preparar o Swagger como demo |
| Charles | bugs 1, 7, 10 e 11; texto sobre limites do modelo pro pitch; rota de matching se o grupo aprovar |
