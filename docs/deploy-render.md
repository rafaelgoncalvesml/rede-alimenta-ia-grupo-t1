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
| `autoDeployTrigger` | `off` | O CI (`.github/workflows/ci.yml`) roda Bandit e Trivy, mas nao faz deploy. Com `commit` o Render publicaria antes de o CI terminar |
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
| `CONFIAR_CF_CONNECTING_IP` | no yaml, `1` | IP real do cliente no limite de pedidos e no log. So no Render (ver "Riscos") |

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
hello world do dia 3. O primeiro `POST /lotes` levou 9,8 s no dia 23 porque o modelo so carregava
nele. **Desde 13/10 o modelo carrega quando a API sobe** (`api/ia.py`, `pre_carregar_modelo`): o
custo foi pro acordar, e o log da subida traz o evento `modelo.carregado` com `segundos` e
`memoria_pico_mb`, a memoria que a aba Metrics do plano free nao mostra. **Ainda nao medido no
Render.** O Render tambem avisa na propria tela que o free "pode atrasar pedidos em 50 segundos ou mais".

### Plano de abertura da URL antes da defesa

1. Uns 5 minutos antes: abrir `.../health` no navegador e esperar o `{"status":"ok"}`.
2. Conferir no log do Render a linha `modelo.carregado` da subida. Se ela nao estiver la (o modelo
   falhou ao carregar), os lotes vao entrar sem prioridade: e o momento de investigar, nao a demo.
   O `POST /lotes` de aquecimento deixou de ser necessario.
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

- **Rate limit por IP atras do proxy.** `api/limites.py` conta pedido sem token por `request.client.host`.
  No Render isso e o IP do proxy interno (`10.x`), nao o do cliente: medi com uma rota temporaria
  (12/10, ja removida) e o `client_host` variou entre `10.24.x` e `10.25.x` de um pedido pro outro.
  O balde anonimo fica dividido entre os proxies, nao por cliente. O login tem limite proprio
  por e-mail e nao sofre; autenticado conta por usuario.

  **O que o teste mostrou (uma maquina, uma rodada):**

  | Cabecalho | O que chegou na API |
  |---|---|
  | `X-Forwarded-For` | `<o que o cliente mandou>, <IP real>, <IP do Cloudflare 162.159.x>, <proxy 10.x>`. O valor forjado vem **primeiro** (esquerda): quem confia na primeira entrada e enganado. O IP real e a **terceira de tras pra frente** |
  | `CF-Connecting-IP` | sempre o IP real (conferi com `api.ipify.org`). Mandei `True-Client-IP: 9.9.9.9` forjado e voltou o IP real: o Cloudflare sobrescreve, o cliente nao forja |
  | `True-Client-IP` | igual ao `CF-Connecting-IP` |
  | `X-Real-IP`, `Forwarded`, `Via` | ausentes |

  **Decisao (12/10): opcao 1, implementada.** `api/auditoria.py::ip_do_cliente` usa o
  `CF-Connecting-IP` so quando `CONFIAR_CF_CONNECTING_IP=1` (ligada no `render.yaml`); sem a
  variavel, ou com valor que nao seja um IP, volta pro `client.host`. O mesmo IP alimenta o limite
  de pedidos e o campo `ip` do log. Testes em `api/tests/test_limites.py`. **Falta confirmar em
  producao depois do deploy** (o campo `ip` do log do Render deve mostrar o IP real, nao `10.x`).
  A fragilidade da opcao 1 continua: o Render nao documenta o Cloudflare. As outras duas ficam
  aqui como registro.

  **Opcoes consideradas:**
  1. Usar `CF-Connecting-IP` quando existir, e cair no `client.host` quando nao. Mais
     robusto que contar saltos. Fragilidade: o Render nao documenta que fica atras do
     Cloudflare; se isso mudar, o cabecalho some (cai pro proxy, seguro) ou, pior, passa a vir
     do cliente sem filtro (forjavel). Ligar so com uma variavel de ambiente
     (`CONFIAR_CF_CONNECTING_IP=1`) deixa isso explicito.
  2. Pegar a terceira entrada de tras pra frente do `X-Forwarded-For`. Quebra se o numero de
     saltos mudar.
  3. Deixar como esta e registrar como limitacao do plano free. Pro MVP e defesa o risco e
     baixo: ninguem vai estourar 120 pedidos por minuto na demo.

  `FORWARDED_ALLOW_IPS=*` continua **fora**: deixaria a primeira entrada (forjavel) valer.
- **Memoria.** Free tier tem 512 MB. No container deu ~136 MiB depois de carregar o modelo
  (uma amostra). Conferir no Render e item do Charles no dia 22.
- **Limite em memoria.** Contadores de rate limit e de login ficam no processo; funciona com
  um worker, que e o que a imagem sobe.
- **Admin recriado.** Enquanto `ADMIN_EMAIL` e `ADMIN_PASSWORD` existirem, o admin volta a
  cada subida se tiver sido apagado.
