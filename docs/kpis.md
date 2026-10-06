# KPIs (dia 17): `GET /kpis/impacto` e `GET /kpis/ia`

Qualquer usuario logado chama os dois, mas cada papel soma so o que e dele: admin tudo,
doador os proprios lotes e as doacoes deles, ONG as doacoes que recebeu e os lotes
correspondentes. O calculo esta em `api/kpis.py` (funcoes puras, testadas em
`api/tests/test_kpis.py`).

## O que o Charles ainda precisa fechar

O roadmap (dia 15) pediu pro Charles as formulas e o fator kg por refeicao, **com fonte ou
marcado como premissa**. Nada disso chegou ao repo, entao implementei o que o resto do grupo
precisa pra ligar o dashboard e deixei o fator como premissa explicita:

- `1 refeicao = 0,5 kg` e **premissa nossa, sem fonte**. Nao pesquisei nem citei referencia.
- Vem de `KG_POR_REFEICAO` (padrao 0,5), volta em toda resposta como `fator_kg_por_refeicao` e
  na lista `premissas`. Quando o Charles fechar o valor com a fonte, e so trocar a variavel e
  citar a fonte aqui.
- Se as formulas dele forem diferentes das de baixo, a mudanca e em `api/kpis.py`.

## `/kpis/impacto`

| Campo | Formula |
|---|---|
| `kg_doados` | soma de `quantidade_kg` dos lotes com status `doado` e doacao `confirmada` |
| `kg_em_andamento` | o mesmo pros lotes ainda `reservado` (a ONG ainda nao recebeu) |
| `refeicoes_geradas` | `kg_doados / fator` |
| `doacoes_confirmadas`, `doacoes_canceladas` | contagem por status da doacao |
| `ongs_atendidas` | ONGs distintas com pelo menos uma doacao entregue |
| `tempo_medio_match_s` | media de `tempo_match_s` das doacoes confirmadas (`null` se nao ha) |
| `lotes_por_status` | contagem dos lotes |
| `por_estado` | `kg_doados`, `doacoes` e `refeicoes_geradas` agrupados pela UF da **ONG** |
| `por_dia` | `kg_doados` e `refeicoes_geradas` por data de `confirmado_em` (UTC) |

Escolhas que mudam o numero e valem discutir no grupo:

- **"Salvo" so conta depois da entrega.** Lote `reservado` nao entra em `kg_doados`.
- **`por_dia` usa a data da confirmacao**, nao a da entrega, porque a entrega nao tem
  timestamp proprio (`PUT /lotes` com `doado` nao grava hora). Se o grafico precisar da data
  de entrega, falta uma coluna.
- **Doacao cancelada nao conta**, e um lote com doacao cancelada seguida de outra confirmada
  nao e somado duas vezes.

## `/kpis/ia`

- `modelo`: vem de `models/metrics.json`, o mesmo arquivo do Charles (versao, modelo escolhido,
  F1 macro do teste e do baseline, ganho sobre o baseline, acuracia, recall da classe alta e
  fracao de altas mandadas pro fim da fila). `null` se o arquivo nao existir.
- `operacao`: calculada sobre os lotes do banco. `classificados` sao os que tem `prioridade`;
  `sem_prioridade` sao os cadastrados quando o modelo falhou (a API cadastra mesmo assim).
  Tambem `por_prioridade` e `por_tipo`.
- `avisos`: **o rotulo de simulado nao some**. Enquanto o dataset for `SIMULADO`, toda resposta
  diz que as metricas provam o pipeline e nao a qualidade em dado real. Um teste garante isso.

## Limites

- **Real vs. simulado nos dados do banco.** O roadmap quer o dashboard rotulando o que e real e
  o que e simulado. A API nao sabe a diferenca: nao ha coluna pra isso, e o script de historico
  simulado do Charles (dia 16) tambem nao chegou. Decisao do grupo: uma coluna `origem` em
  `lotes` e `doacoes`, ou um banco separado pra demo.
- **Sem cache.** Cada chamada le lotes, doacoes e ONGs inteiros. Em memoria e instantaneo; no
  Supabase sao tres consultas de ~0,6 a 2 s. Pro dashboard pedir de tempos em tempos funciona;
  se ficar lento, o proximo passo e agregar no SQL ou guardar o resultado por alguns segundos.
- **`/kpis/seguranca`** esta no desenho de endpoints do roadmap e e do Anthony; nao fiz.
