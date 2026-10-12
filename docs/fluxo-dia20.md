# Fluxo ponta a ponta e bugs (dia 20)

Rodado em 10/10 e 12/10 pelo Rafael. O fluxo rodou em tres frentes: `uvicorn` local, o
container em memoria e o container contra o Supabase. A imagem foi **reconstruida com o codigo
de hoje** (`docker build -t rede-alimenta-api -f api/Dockerfile .`, 714 MB, igual a do dia 19).

## O que rodou

`python -m api.fluxo_http` (script novo, fala HTTP com uma API que ja esta de pe):
**16 verificacoes, 0 falhas**, tanto no `uvicorn` quanto no container em memoria (`docker run`
sem `STORAGE=postgres`, admin descartavel `@exemplo.invalid`).

| Passo | Resposta |
|---|---|
| login do admin | 200 |
| `POST /doadores` (CNPJ com mascara) | 201 |
| `POST /ongs` | 201 |
| `POST /lotes` tomate, vence amanha | 201, prioridade `alta` vinda do modelo |
| `POST /doacoes` | 201, `tempo_match_s` preenchido |
| `POST /doacoes` repetida | 409 |
| `PUT /lotes/1` para `doado` | 200 |
| `GET /kpis/impacto` | 200, `kg_doados` = 20 |
| `GET /kpis/ia` | 200 |
| sem token, `GET /lotes` | 401 |

Container contra o Supabase (`STORAGE=postgres`, `API_URL=... python -m infra.db.testar_login`,
o mesmo teste do dia 19): **28 verificacoes ok, 0 falhas**, contagem de linhas igual antes e
depois. Container pronto em poucos segundos, 140 MiB depois do teste (uma amostra), usuario
uid 10001, logs sem traceback, sem URL de banco e sem JWT.

Fora do container: `pytest api ml`, 408 passaram (eram 397); `ruff check` limpo; Bandit 0 alta
e 0 media (4 baixas, as mesmas do dia 14, no gerador do dataset); `pip-audit` sem
vulnerabilidade conhecida nos tres `requirements.txt`.

**Matching e dashboard nao entraram no fluxo porque nao existem no repo** (issue 8). O passo
do meio continua sendo a escolha da ONG na mao.

## Issues fechadas

| # | Issue | O que mudou | Teste |
|---|---|---|---|
| 7 | `necessidades` x `tipo` | `POST` e `PUT /ongs` recusam (422) necessidade fora das 6 categorias do modelo. A lista e a `CATEGORIAS` de `ml/features.py`, a mesma do lote | `test_ongs.py` |
| 9 | doacao pra ONG sem capacidade ou sem a necessidade | `POST /doacoes` volta 409 se `quantidade_kg` passa da `capacidade_kg` ou se a categoria do lote nao esta nas `necessidades`. Lote com `tipo` nulo (modelo falhou no cadastro) so confere a capacidade | `test_doacoes.py` |
| 10 | cache versionado | 26 arquivos fora do indice. Quatro eram `.pyc` numa pasta `ml/tests/_pycache__` (um underscore so, nome errado) que o `.gitignore` nao pegava pelo nome | `git ls-files \| grep -c cache` da 0 |
| 11 | sem teto | 5000 kg por lote, 100000 kg de capacidade, validade ate 730 dias a frente. So na entrada | `test_lotes.py`, `test_ongs.py` |
| 12 | `.env.example` com ids reais | placeholders (`<project-ref>`, `<usuario>`, `<cluster>`) | leitura do arquivo |

Os numeros da issue 11 e a regra da 9 **sao palpite meu**, o grupo ainda nao decidiu (ver
`docs/decisoes.md`). Base dos tetos: o maior lote do dataset v1 tem 1176 kg e a maior
validade, 325 dias. Dois efeitos pra avisar o grupo:

- Quem cadastrou ONG com texto livre antes disso continua sendo lido (a checagem nao roda na
  leitura), mas nao consegue mais editar `necessidades` sem trocar pelas categorias.
- Na issue 9, ONG com `necessidades` vazias **nao recebe nada**. Se o grupo quiser "vazio
  significa aceita tudo", e uma linha em `api/routers/doacoes.py`.

**Capacidade e por doacao**, nao acumulada: a regra compara o lote com `capacidade_kg`, nao
com o que a ONG ja recebeu. Nao existe campo de estoque da ONG pra fazer diferente.

## Issues que continuam abertas

- **#8, matching e tela.** Charles (matching) e Gustavo (tela). Nao toquei: nao ha
  `ml/matching.py` nem `app/` no repo, e inventar o score aqui contradiz o dono da parte.

## O que ficou de fora

- **`docker compose up`, Trivy, pipeline.** Nao existem no repo (Anthony, dias 15 a 19). Eu nao
  instalei o Trivy: scanner de terceiro e decisao do grupo (`docs/container.md`).
- **Teste de bug e malicioso na API** (`docs/security/testes.md`) e do Anthony.
- **Outra maquina.** So testei na minha (Windows).

## Docker Desktop (nota pro grupo)

Na minha maquina o Docker Desktop 4.86 nao subia: `initializing Inference manager ... remove
...dockerInference: The file cannot be accessed by the system`, e depois o mesmo erro no
`docker-secrets-engine\engine.sock`. Eram sockets antigos que o Windows nao deixava apagar
(`del` e `fsutil` voltam erro 1920) e nem o reinicio limpou. O que resolveu, sem perder nada:
fechar o Docker e **renomear** as pastas `%LOCALAPPDATA%\Docker\run` e
`%LOCALAPPDATA%\docker-secrets-engine` (o Docker recria). Se alguem do grupo travar nisso na
hora do `docker compose up`, e esse o caminho.
