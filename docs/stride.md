# Matriz de ameacas e riscos (STRIDE) - v2

Dono: Anthony. Escrita em 13/10 e ajustada em 14/10 contra a `main` (modelo v2, CI do GitHub Actions), lendo
`api/seguranca.py`, `api/limites.py`, `api/erros.py`, `api/auditoria.py`, `api/storage.py`,
`infra/db/schema.sql`, `api/Dockerfile` e `render.yaml`. Nada aqui foi testado por teste de
intrusao: onde diz FEITO, aponto o arquivo ou o teste que sustenta.

Coluna **Estado**: `FEITO` existe no codigo, no pipeline ou na configuracao e da pra apontar onde;
`PARCIAL` parte existe, parte nao (a parte que falta esta dita); `PENDENTE` nao existe;
`ACEITO` risco conhecido que o grupo decidiu nao tratar no MVP.

## 1. Ativos

| # | Ativo | Onde vive | Por que importa |
|---|---|---|---|
| A1 | Dados pessoais do doador PF (nome, CPF, telefone, e-mail, cidade, coordenadas) e e-mail dos usuarios | Tabelas `doadores` e `usuarios` (Supabase) | LGPD, ver `docs/lgpd.md` |
| A2 | Dados de ONG (CNPJ, endereco, capacidade, necessidades) | Tabela `ongs` | Integridade do que a doacao confere (issue 9) |
| A3 | Lotes, prioridade e doacoes | Tabelas `lotes` e `doacoes` | Base dos KPIs de kg salvos e refeicoes |
| A4 | `SUPABASE_DB_URL`, `JWT_SECRET`, `ADMIN_PASSWORD` | `.env` local, painel do Render, secrets do GitHub | Acesso total aos dados e a qualquer papel |
| A5 | Modelo de prioridade (`models/prioridade_v2.joblib`) | Repositorio e imagem Docker | `joblib.load` e pickle: arquivo trocado executa codigo |
| A6 | Pipeline e secrets do GitHub Actions | `.github/workflows/`, GitHub | Quem controla o pipeline controla o que vai pra producao |
| A7 | Disponibilidade da API publica (Render free) | Render | A defesa e uma demo ao vivo |
| A8 | Hash de senha dos usuarios | Coluna `usuarios.senha_hash` | Argon2; vazar o hash facilita senha fraca |

## 2. Fronteiras de confianca

1. **Internet -> API (Render).** Tudo que chega e nao confiavel. Entra por JWT, limite de pedidos e limite de corpo.
2. **API -> Supabase.** Conexao TLS pelo pooler; a API conecta como dono das tabelas.
3. **Streamlit -> API.** O front e so mais um cliente: nao e fronteira de seguranca (e ainda nao existe no repo).
4. **Dev -> GitHub -> Render.** Codigo e segredos cruzam aqui. O CI testa e escaneia, mas nao publica: o deploy e manual pelo painel do Render.
5. **Artefato do modelo -> processo da API.** O `.joblib` e carregado como codigo.

## 3. Ameacas e mitigacoes

| ID | Cat. | Ativo | Ameaca | Mitigacao (onde) | Estado |
|---|---|---|---|---|---|
| S1 | **S**poofing | A1-A3 | Chamar a API fingindo ser outro usuario ou papel | JWT HS256 de 30 min com papel e dono; `algorithms` fixo (token `alg: none` nao passa); `exp`, `sub` e `papel` obrigatorios; `JWT_SECRET` de 32+ caracteres ou a API nao sobe (`api/seguranca.py`); 401 sem token. Testes: `test_auth.py`, `test_seguranca.py` (token forjado, expirado, sem assinatura, papel trocado) | FEITO |
| S2 | Spoofing | A8 | Adivinhar senha por tentativa e erro; descobrir quais e-mails existem | Argon2; 5 erros por e-mail a cada 15 min, depois 429; mesma mensagem e mesmo custo para e-mail inexistente (hash falso); senha de 10 a 128 caracteres. Limite: quem erra o e-mail de outra pessoa trava o login dela por 15 min, e o contador fica na memoria do processo (`docs/auth.md`) | FEITO, com o limite aceito |
| S3 | Spoofing | A4 | Credencial vazada no repositorio | `.env` no `.gitignore` e no `.dockerignore`; `.env.example` com placeholder; Trivy `secret` no CI. O `.env.example` antigo, com o ref do Supabase e o usuario do Atlas, continua no historico do Git, mas o usuario do Atlas foi apagado em 14/10 (o cluster estava pausado e o acesso por IP restrito). Falta: `gitleaks` nao foi rodado, so `git grep` | PARCIAL |
| S4 | Spoofing | A4 | Admin com senha fraca ou conhecida | Admin so nasce de `ADMIN_EMAIL`/`ADMIN_PASSWORD` do ambiente, minimo 10 caracteres; no Render as duas variaveis sao `sync: false` (nao ficam no repo). Risco: enquanto as variaveis existirem, o admin volta a cada subida se for apagado (`docs/container.md`). A senha do Render tem que ser diferente da de teste | FEITO, com atencao no Render |
| S5 | Spoofing | A6 | Commit direto na `main` sem revisao | O repo e privado em conta free e o GitHub nega a protecao de branch (API devolve 403 pedindo plano Pro ou repo publico; conferido em 14/10). Vale so o combinado de mergear por PR. Charles subiu direto na `main` 5 vezes em 29/09 e 47 commits em 13/10 (`docs/checkpoint-rubrica.md`). O CI roda em push e em PR, mas um push direto so ve o resultado depois | ACEITO ate o grupo decidir tornar o repo publico |
| T1 | **T**ampering | A1-A3 | Payload malformado ou malicioso altera dado | Pydantic em tudo: tipos, `max_length`, `allow_inf_nan=False`, tetos de 5000 kg, 100000 kg e 730 dias; `prioridade` e `status` fora do que o cliente escreve; transicoes de status validas; `CHECK` no `schema.sql`; JSON invalido da 400; corpo acima de 64 KiB da 413 (`api/models.py`, `api/limites.py`, `api/erros.py`). Os tetos sao palpite do Rafael que o grupo ainda nao confirmou | FEITO |
| T2 | Tampering | A1-A3 | SQL injection | Consulta com `psycopg.sql` e parametros `%s`, nome de tabela e coluna so de lista fixa `COLUNAS` (`api/storage.py`); `DataError` do banco vira 422; Bandit B608 no CI. O `testar_login.py` rodou 28 verificacoes no Supabase, mas **nenhuma com texto de injecao**: isso fica por rodar (`docs/security/testes.md`) | PARCIAL |
| T3 | Tampering | A5 | `.joblib` trocado por pickle malicioso | Arquivo versionado, so muda por PR; caminho fixo em `ml/predict.py` (`# nosec B301` justificado ali); container sem root. Falta checar o hash do arquivo antes do `joblib.load` | PARCIAL |
| T4 | Tampering | A6 | Dependencia, imagem base ou Action comprometida | Pins em `api/requirements.txt` e `scikit-learn`; `pip-audit` das tres listas de dependencias no CI (0 vulnerabilidade em 14/10); Trivy na imagem e no Dockerfile no CI, pela action `aquasecurity/trivy-action`. Falta: as Actions (`checkout`, `setup-python`, `trivy-action`) estao por tag e nao por SHA; `ml/requirements.txt` fixa so o scikit-learn e `api/requirements.txt` traz `joblib` e `pandas` com `>=`; nao ha Dependabot | PARCIAL |
| R1 | **R**epudiation | A3 | Alguem altera ou apaga dado e nega | Uma linha JSON por pedido e por mudanca de dado, com `request_id`, `usuario_id` do token e IP, sem corpo nem querystring (`api/auditoria.py`); `criado_em` e `confirmado_em` no banco. No Render o IP vem do `CF-Connecting-IP` (`CONFIAR_CF_CONNECTING_IP=1`, medido em 12/10, `docs/deploy-render.md`). Limite: o log so existe no stdout do Render, sem copia nem retencao verificada | FEITO, com o limite aceito |
| R2 | Repudiation | A6 | Deploy sem rastro | `render.yaml` tem `autoDeployTrigger: "off"`: publicar e uma acao manual no painel do Render, que guarda o historico de deploys. Nao ha workflow de deploy no GitHub, entao nao existe amarra entre o CI verde e o que sobe | PARCIAL |
| I1 | **I**nformation disclosure | A1 | Um papel le dado de outro (IDOR) | Matriz de acesso: cada papel ve so o que e dele, listas filtradas por dono, 403 para recurso alheio; teste de 120 casos que **falha se aparecer rota nova sem linha na matriz** (`api/tests/test_acesso_negado.py`, `docs/auth.md`). Residual: 403 em vez de 404 revela que o id existe, e os ids sao sequenciais | FEITO |
| I2 | Information disclosure | A1, A4 | Dado pessoal, token ou segredo vazam por log ou mensagem de erro | Log sem corpo; 500 generico com `request_id`, stack so no log; 401 e 403 com texto fixo; imagem sem `.env`, teste e dado; logs do container conferidos sem JWT, senha nem URL de banco (`docs/container.md`); teste novo `test_log_nao_leva_token_documento_nem_senha` | FEITO |
| I3 | Information disclosure | A1-A3 | Leitura direta pela API REST publica do Supabase | RLS ligado nas 5 tabelas, sem policy (`infra/db/schema.sql`) | FEITO |
| I4 | Information disclosure | A1 | `GET /doadores` (admin) devolve CPF/CNPJ completo de todos | So admin e o proprio doador veem o documento. Mascarar a listagem do admin seria reforco, nao falha: ver `docs/lgpd.md` | ACEITO |
| I5 | Information disclosure | A7 | `/docs`, `/openapi.json` e `/health/db` abertos | Swagger e entregavel da rubrica; `/health/db` so diz `postgres` ou `memory` | ACEITO |
| D1 | **D**enial of service | A7 | Inundar a API de pedidos ou de corpo | 120 pedidos/min por usuario, limites menores em `POST /lotes`, `/doacoes`, `/usuarios`; 429 com `Retry-After`; 413 acima de 64 KiB (`api/limites.py`). Limites: contadores na memoria do processo (1 worker); no Render o IP do cliente vem do `CF-Connecting-IP` (medido em 12/10), mas teste de carga na URL publica nao foi feito | PARCIAL |
| D2 | Denial of service | A7 | Banco fora ou pool esgotado derruba a API | Pool de 5 conexoes com timeout e handler que devolve 503 (`api/storage.py`, `api/erros.py`); `/health` nao toca o banco | FEITO |
| D3 | Denial of service | A7 | Cold start do Render free (~22 s medidos) parece queda na defesa | Abrir a URL com folga antes da apresentacao (dia 31, roteiro em `docs/deploy-render.md`) | ACEITO |
| D4 | Denial of service | A8 | Senha gigante forca argon2 caro | `senha` com no maximo 128 caracteres, 422 antes de chamar o hash (`LoginIn`) | FEITO |
| D5 | Denial of service | A1-A3 | Supabase free pausa o projeto parado por 1 semana e nao tem backup automatico | `infra/db/reset_demo.py` guarda o estado em `backups/` antes de apagar (so quando alguem o roda) | PARCIAL |
| E1 | **E**levation of privilege | A1-A3 | Usuario comum chama rota de admin ou age sobre dado de outro | `exige(...)` por papel e checagem de dono em cada rota; `papel` vem do token assinado, nunca do corpo; 120 casos testados; Rafael verificou que o teste pega regressao tirando as checagens (`docs/auth.md`) | FEITO |
| E2 | Elevation of privilege | A7 | Falha na API vira controle do container | Usuario `app` uid 10001, `nologin`, sem `pip` na imagem final (`api/Dockerfile`); no `docker-compose.yml`, `cap_drop: ALL` e `no-new-privileges` (testado no job `compose` do CI em 14/10: a API sobe com `read_only`, `cap_drop: ALL` e `no-new-privileges` e responde em `/health` e `/docs`, com storage em memoria; nao foi exercitada com escrita nem com Postgres nesse modo) | FEITO |
| E3 | Elevation of privilege | A6 | Workflow com permissao demais ou segredo exposto a PR externo | `permissions: contents: read`; o CI usa `pull_request` (nao `pull_request_target`) e nao le segredo (o `JWT_SECRET` do teste do container e um valor descartavel escrito no proprio workflow); nao ha job de deploy | FEITO |
| E4 | Elevation of privilege | A1-A3 | Usuario apagado ou rebaixado continua valendo ate o token vencer | Token de 30 min e sem revogacao; revogar pediria consulta ao banco a cada pedido (0,6 a 2 s no Supabase). Decisao do Rafael em `docs/auth.md` | ACEITO |

## 4. Resumo

25 ameacas.

| Estado | Qtd | Quais |
|---|---|---|
| FEITO | 13 | S1, S2, S4, T1, R1, I1, I2, I3, D2, D4, E1, E2, E3 |
| PARCIAL | 7 | S3, T2, T3, T4, R2, D1, D5 |
| ACEITO | 5 | S5, I4, I5, D3, E4 |

A tabela e a fonte de verdade: ao fechar um item, trocar o estado aqui no mesmo PR.
Evidencias: `api/tests/test_seguranca.py` (token forjado, injecao, log), `.github/workflows/ci.yml`
(Bandit, pip-audit e Trivy no pipeline) e `docs/security/vulnerabilidades.md`.
