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

## O que precisa de voce (Rafael) no dia 22

1. No Render, **New > Blueprint** apontando pro repo, branch `main`. Preencher
   `SUPABASE_DB_URL`, `ADMIN_EMAIL` e `ADMIN_PASSWORD` quando ele perguntar.
2. Antes disso, **os PRs 5, 6, 13 a 19 e o deste dia tem que estar na `main`** (ordem de
   numero). Hoje a `main` nao tem auth, doacao nem KPIs: o Render faz deploy da `main`.
3. Se o servico `rede-alimenta-ia-deploy-test` do dia 2 ainda existir na conta, apagar. O
   blueprint novo nao o remove.
4. `python infra/db/aplicar_schema.py` ja foi aplicado no Supabase (tabela `usuarios`
   inclusa, dia 16). Conferir com `GET /health/db` depois do deploy.
5. Plano free: o servico dorme depois de um tempo sem trafego e o primeiro pedido paga o
   cold start. **Medir e definir o plano de abertura da URL e tarefa do dia 23.**

## Riscos que ja deu pra ver

- **Rate limit por IP atras do proxy.** `api/limites.py` conta pedido sem token por IP. No
  Render o `request.client.host` e o do proxy, entao todo pedido anonimo cai no mesmo balde
  (o login tem limite proprio por e-mail, esse nao sofre). Autenticado conta por usuario e
  nao muda. Ligar `FORWARDED_ALLOW_IPS=*` no uvicorn resolveria, mas deixaria o cliente
  forjar o `X-Forwarded-For`; por isso **nao liguei** e deixo a decisao pro grupo.
- **Memoria.** Free tier tem 512 MB. No container deu ~136 MiB depois de carregar o modelo
  (uma amostra). Conferir no Render e item do Charles no dia 22.
- **Limite em memoria.** Contadores de rate limit e de login ficam no processo; funciona com
  um worker, que e o que a imagem sobe.
- **Admin recriado.** Enquanto `ADMIN_EMAIL` e `ADMIN_PASSWORD` existirem, o admin volta a
  cada subida se tiver sido apagado.
