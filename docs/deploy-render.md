# Deploy da API no Render (preparo do dia 21)

O deploy em si e do dia 22. Aqui fica o que o repo ja entrega pronto e o que so a conta do
Render resolve. O `render.yaml` da raiz agora descreve a API de verdade (antes apontava pro
hello world de `infra/deploy-test`, que fica so como registro do teste do dia 2).

## O que o render.yaml faz

| Campo | Valor | Por que |
|---|---|---|
| `runtime` | `docker`, `api/Dockerfile`, contexto na raiz | E a mesma imagem testada no dia 19 contra o Supabase |
| `region` | `ohio` | O Supabase esta em `us-east-2`. No dia 19 cada consulta levou ~0,63 s de uma maquina no Brasil; na mesma regiao deve cair, mas **nao medi** |
| `healthCheckPath` | `/health` | Responde sem tocar o banco, entao o Render nao derruba o servico se o Supabase estiver lento |
| `autoDeployTrigger` | `off` | O dia 22 traz o workflow que so faz deploy se Bandit e Trivy passarem. Com `commit` o Render publicaria antes do gate |
| `PORT` | `8000` | O Dockerfile fixa a 8000. O Render documenta 10000 como padrao e diz que costuma detectar outra porta; deixei explicito pra nao depender disso |

Nao conferi o arquivo contra o Render: nao tenho conta nem CLI aqui. Conferi o YAML (le
sem erro, chaves existem na especificacao do blueprint) e a imagem (`docker build` com o
mesmo Dockerfile, ver `docs/container.md`).

## Variaveis

Todas estao listadas em `.env.example`, com placeholder.

| Variavel | No Render | Observacao |
|---|---|---|
| `STORAGE` | no yaml, `postgres` | Em `memory` a API sobe sem erro e perde tudo a cada deploy |
| `SUPABASE_DB_URL` | `sync: false`, o Render pergunta ao criar o blueprint | Session pooler (IPv4). Senha com caractere especial precisa de percent-encode |
| `JWT_SECRET` | `generateValue: true` | O Render gera um valor base64 de 256 bits (44 caracteres, acima do minimo de 32 da API). Nao precisa colar nada |
| `ADMIN_EMAIL`, `ADMIN_PASSWORD` | `sync: false` | O admin e criado na primeira subida. Senha com 10+ caracteres e **diferente** da de teste |
| `TOKEN_MINUTOS`, `MAX_BODY_BYTES`, `KG_POR_REFEICAO` | no yaml | Iguais ao padrao do codigo; o fator de refeicao continua premissa (`docs/kpis.md`) |

`MONGODB_URI` nao entra: a API nao usa (decisao do dia 4, Supabase pra tudo).

## Em producao (12/10)

URL publica: `https://rede-alimenta-ia-api.onrender.com`. Deploy feito pelo Blueprint a
partir da `main` (todos os PRs ate o #20 ja estavam nela).

**Um tropeco que vale lembrar:** o Blueprint criou o servico sem `SUPABASE_DB_URL`,
`ADMIN_EMAIL` e `ADMIN_PASSWORD` (as tres com `sync: false`; o Render nao perguntou). A API
subiu, `/health` deu 200, mas `/health/db` e o login davam 500 com
`KeyError: 'SUPABASE_DB_URL'` no log. Foram adicionadas na aba Environment. **Depois de qualquer
deploy novo, conferir que as tres continuam la.** `/health` sozinho nao prova que o banco
esta ligado.

Conferido depois da correcao:

| Teste | Resultado |
|---|---|
| `GET /health/db` | 200, `{"status":"ok","storage":"postgres"}` em 0,28 s |
| `POST /auth/login` com senha errada | 401 |
| `POST /auth/login` do admin (pelo `/docs`) | 200, `expires_in` 1800 |
| `GET /lotes` e `GET /kpis/impacto` sem token | 401 |

### Cold start (medido em 12/10)

Servico do plano free, 18 minutos sem nenhum acesso, depois um `curl` no `/health`:

| Pedido | Tempo |
|---|---|
| Primeiro, depois de 18 min parado | **22,4 s** (conexao em 0,05 s; o resto foi a API acordar) |
| Seguinte | 0,25 s |
| `/health/db` logo depois | 0,28 s |

Uma medida so, num dia so: serve de ordem de grandeza, nao de garantia. Bate com os ~22 s do
hello world do dia 3. O modelo so carrega no primeiro `POST /lotes` (cerca de 1 s a mais
localmente); **isso nao medi no Render.** O Render tambem avisa na propria tela que o free
"pode atrasar pedidos em 50 segundos ou mais".

### Plano de abertura da URL antes da defesa

1. Uns 5 minutos antes: abrir `.../health` no navegador e esperar o `{"status":"ok"}`.
2. Entrar no `/docs`, logar com o admin e fazer **um `POST /lotes` de aquecimento** (carrega o
   modelo). Depois pode apagar o lote, se estiver `disponivel`.
3. Deixar uma aba com `/health/db` e outra com o dashboard abertas (quando ele existir). O servico dorme de novo
   com ~15 min sem trafego; se a apresentacao tiver pausa longa, repetir o passo 1.
4. Plano B se a URL cair ou demorar: o container local (`docs/container.md`) com o mesmo
   Supabase, e o roteiro de `python -m api.demo_checkpoint` em memoria.
5. Nao usar o `api.fluxo_http` contra a URL publica: ele cria doacoes, e doacao nao tem
   DELETE, entao ficam no Supabase de producao.

## Passo a passo do deploy (como foi feito)

1. No Render, **New > Blueprint** apontando pro repo, branch `main`. Preencher
   `SUPABASE_DB_URL`, `ADMIN_EMAIL` e `ADMIN_PASSWORD` quando ele perguntar.
2. Antes disso, os PRs 5, 6 e 13 a 20 tinham que estar na `main` (o Render faz deploy dela).
   Estavam: foram mergeados em ordem em 12/10.
3. Se o servico `rede-alimenta-ia-deploy-test` do dia 2 ainda existir na conta, apagar. O
   blueprint novo nao o remove.
4. `python infra/db/aplicar_schema.py` ja foi aplicado no Supabase (tabela `usuarios`
   inclusa, dia 16). Conferir com `GET /health/db` depois do deploy.
5. Plano free: o servico dorme depois de um tempo sem trafego e o primeiro pedido paga o
   cold start. Medido e com plano de abertura na secao acima.

## Riscos que ja deu pra ver

- **Rate limit por IP atras do proxy.** `api/limites.py` conta pedido sem token por IP. No
  Render o `request.client.host` e o do proxy, entao todo pedido anonimo cai no mesmo balde
  (o login tem limite proprio por e-mail, esse nao sofre). Autenticado conta por usuario e
  nao muda. Ligar `FORWARDED_ALLOW_IPS=*` no uvicorn resolveria, mas deixaria o cliente
  forjar o `X-Forwarded-For`; por isso **nao liguei**. Procurei como o Render expoe o IP real
  e nao ha pagina oficial; so relatos em foruns (o Render acrescentaria ao cabecalho sem
  limpar o que o cliente mandou, e o numero de saltos nao esta garantido). Entao o certo e
  **medir no dia 23**: mandar um `X-Forwarded-For` falso pra URL publica e ver o que chega em
  `request.headers` antes de escolher qual entrada da lista usar.
- **Memoria.** Free tier tem 512 MB. No container deu ~136 MiB depois de carregar o modelo
  (uma amostra). Conferir no Render e item do Charles no dia 22.
- **Limite em memoria.** Contadores de rate limit e de login ficam no processo; funciona com
  um worker, que e o que a imagem sobe.
- **Admin recriado.** Enquanto `ADMIN_EMAIL` e `ADMIN_PASSWORD` existirem, o admin volta a
  cada subida se tiver sido apagado.
