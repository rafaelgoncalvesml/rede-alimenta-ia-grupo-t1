# Matriz de ameacas STRIDE (rascunho de 13/10)

O checkpoint 1 do enunciado pede esta matriz e ela nunca chegou ao repo (`docs/checkpoint-semana1.md` e
`docs/checkpoint-semana2.md` registram isso). Esta versao foi escrita a partir do codigo e dos docs
que existem hoje, nao de uma revisao feita pelo Anthony, que e o dono do tema. Serve de base pra ele
corrigir. "Mitigacao" so lista o que existe no repo; "Lacuna" e o que falta ou nao foi testado.

Fluxo: cliente (Swagger hoje) por HTTPS e JWT, Cloudflare e Render, API FastAPI em container,
Postgres no Supabase. O modelo (`.joblib`) vai dentro da imagem. Ver o diagrama no README.

## Ativos

Dados pessoais de doadores (`docs/lgpd.md`), contas e hashes de senha, lotes e doacoes (o registro
do que cada ONG recebeu), `JWT_SECRET`, `SUPABASE_DB_URL`, o modelo e a disponibilidade da API.

## Matriz

| # | Ativo ou fronteira | Cat. | Ameaca | Mitigacao no repo | Lacuna |
|---|---|---|---|---|---|
| 1 | Login | S | Adivinhar senha de um usuario | 5 erros em 15 min voltam 429; senha argon2, 10 a 128 caracteres; erro de login sempre com a mesma mensagem (`docs/auth.md`) | Contagem na memoria do processo (so vale com um worker); quem erra 5 vezes o e-mail de outro trava o login dele por 15 min |
| 2 | Token JWT | S | Roubo ou forja de token | HS256, 30 min, `JWT_SECRET` com 32+ caracteres (a API nao sobe sem ele); HTTPS pelo Render | Token nao e revogavel; sem refresh nem logout |
| 3 | IP do cliente | S | Forjar `X-Forwarded-For` pra fugir do limite | So `CF-Connecting-IP`, e so com `CONFIAR_CF_CONNECTING_IP=1` (medido em 12/10, `docs/deploy-render.md`) | Valido so atras do Cloudflare do Render; fora dele a variavel tem que ficar desligada |
| 4 | Rotas da API | T | Doador alterar lote ou doacao de outro | Dono e papel checados em toda rota; 120 casos em `api/tests/test_acesso_negado.py`, mais um teste que falha se aparecer rota nova sem linha na matriz | Teste so em memoria; 403 em vez de 404 deixa descobrir que um id existe |
| 5 | Corpo dos pedidos | T | Injecao, valor absurdo, NaN | Pydantic nos modelos, tetos de quantidade e validade, consultas parametrizadas no psycopg, corpo maximo de 64 KB (413) | Documento (CPF/CNPJ) so confere quantidade de digitos, nao o digito verificador |
| 6 | Status do lote | T | Pular etapa do fluxo (`disponivel` direto pra `doado`) | Maquina de estados no `PUT /lotes`; `doado` e `descartado` sao finais (409) | Entrega nao grava timestamp proprio |
| 7 | Prioridade do lote | T | Cliente escolher a propria prioridade | O campo nao existe no corpo de entrada; so o modelo escreve | Se o modelo falhar o lote entra sem prioridade e fica fora da ordenacao |
| 8 | Doacao | R | Negar que uma ONG recebeu um lote | Doacao nao tem PUT nem DELETE; cancelar vira status; `confirmado_em` e `tempo_match_s` gravados pelo servidor | Sem assinatura nem comprovante externo; o historico so vale tanto quanto o banco |
| 9 | Acoes no sistema | R | Ninguem sabe quem mudou o que | Log de auditoria em JSON (um por pedido e um por mudanca de dado), `request_id` em toda resposta | O log fica no stdout do Render, sem retencao verificada nem copia fora dele |
| 10 | Respostas de erro | I | Vazar stack trace, SQL ou valor enviado | 500 generico com `request_id`; 422 sem o valor recebido; stack so no log | Nao ha teste de fuzzing |
| 11 | Dados pessoais | I | Ler CPF, e-mail e telefone de outro doador | Cada papel le so o dele; ONG nao le doador; log sem corpo nem querystring; RLS ligado, sem policy, na API REST do Supabase | Sem criptografia de coluna (so o que o Supabase aplicar em disco, nao verificado); detalhes em `docs/lgpd.md` |
| 12 | Segredos | I | `.env` ou chave no git ou na imagem | `.env` no `.gitignore` e no `.dockerignore`; `.env.example` so com placeholders; Trivy com scanner de segredo; conferido em 13/10 | O usuario antigo do Atlas continua no historico do git e precisa ser rotacionado |
| 13 | Imagem Docker | I, E | Vulnerabilidade no sistema ou nas bibliotecas | Base `python:3.12-slim`, usuario sem root, pip removido da imagem final, Trivy sem achado critico e sem achado em pacote Python (`docs/security/trivy-imagem.md`); gate no CI | 44 HIGH do Debian sem correcao publicada; a leitura de que a API nao alcanca esses pacotes e nossa, sem teste de exploracao |
| 14 | Dependencias | T | Pacote com CVE ou trocado | `fastapi`, `psycopg`, `PyJWT`, `argon2-cffi` e `scikit-learn` com versao exata; `pip-audit` sem achado em 13/10; job no CI | `joblib` e `pandas` entram com `>=`; sem pin por hash nem SBOM |
| 15 | Codigo | T, E | Padroes inseguros no Python | Bandit sem achados em `api`, `ml` e `infra`; job no CI | Bandit so olha o Python |
| 16 | Disponibilidade | D | Inundar a API de pedidos | Limite por rota e por usuario ou IP (120/min; 30 em `POST /lotes` e `/doacoes`; 10 em `POST /usuarios`); corpo maximo | Limite na memoria do processo; plano free do Render nao tem protecao propria; teste de carga nao foi feito |
| 17 | Disponibilidade | D | Servico dormindo no plano free | Plano de abertura da URL (`docs/deploy-render.md`) | Cold start de ~22 s medido uma vez |
| 18 | Banco | D | Supabase free pausa o projeto parado por 1 semana; sem backup automatico | `reset_demo.py` guarda o estado antes de apagar, mas so quando alguem o roda | Nao ha rotina de backup no repo |
| 19 | Privilegios | E | Doador virar admin | `papel` vem do token assinado; o corpo nao aceita `papel` (testado em `test_acesso_negado.py`); so o admin cria usuario | O primeiro admin nasce de `ADMIN_EMAIL` e `ADMIN_PASSWORD` no ambiente; se sumirem do Render a API sobe sem admin |
| 20 | Container | E | Escapar da API pro host | Usuario `app` (uid 10001) sem shell, `.env` fora da imagem | Nao rodamos teste de escape; o Render isola o container por conta propria |
| 21 | Modelo | T | Trocar o `.joblib` por um malicioso (pickle executa codigo ao carregar) | Arquivo versionado no repo e copiado na build; sem upload nem download em runtime | Quem tem permissao de merge na `main` controla o modelo; hoje qualquer integrante empurra direto, sem revisao |
| 22 | CI e repositorio | T, E | Alguem alterar a `main` sem passar pelos testes | O workflow roda em push e em pull request | Nao ha protecao de branch na `main` (nao conferi nas configuracoes do GitHub, so pelo historico): em 13/10 entraram 47 commits pela web direto nela. Ligar "exigir pull request e checks" em Settings, Branches |

## Fora do escopo desta versao

Ameacas ao frontend (nao existe), ao Cloudflare e ao Supabase como servicos (dependemos deles),
engenharia social contra o grupo e ataques fisicos.

## Pro Anthony

Confirmar ou corrigir cada linha, dar nota de risco (probabilidade e impacto) e decidir quais lacunas
entram como aceitas e quais viram tarefa. As linhas 18, 21 e 22 sao as mais baratas de fechar antes da
defesa.
