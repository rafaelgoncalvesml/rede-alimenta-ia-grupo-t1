# Dados - dataset v0

`lotes_v0.csv`: 1212 lotes de alimentos doados. **Todo o dataset e SIMULADO**,
gerado por `gerar_dataset_v0.py` com seed fixa. Nenhum lote, doador ou desfecho
aqui aconteceu de verdade.

## Por que simulado

Nao encontramos base aberta brasileira no nivel que o modelo precisa: lote a
lote, com validade, armazenamento e o que aconteceu com ele (doado ou
descartado). As bases abertas sobre desperdicio sao agregadas (por pais, elo da
cadeia ou domicilio), boas pra contextualizar o problema e calibrar premissas,
nao pra treinar um classificador de lote.

## Fontes abertas levantadas

| Fonte | O que da | Uso aqui |
|---|---|---|
| [FoodKeeper (USDA/FSIS)](https://catalog.data.gov/dataset/fsis-foodkeeper-data) | Vida util por alimento e forma de armazenamento (tem versao em portugues), dominio publico | Referencia pras faixas de `VIDA_UTIL`. Na v0 as faixas sao premissa; conferir item a item na v1 |
| FAO - Food Loss and Waste Database | Perdas e desperdicio por pais, produto e elo da cadeia | Contexto do problema no pitch |
| UNEP - Food Waste Index Report | Desperdicio por pais e setor (domicilio, varejo, food service) | Contexto do problema no pitch |
| Lei 14.016/2020 | Autoriza a doacao de excedentes de alimentos proprios pro consumo | Base legal da regra de negocio: so doa o que esta dentro da validade |

Nenhum numero dessas fontes foi copiado pro dataset. Quando um numero delas
entrar em KPI ou slide, vai com a fonte do lado.

## O que e real e o que e simulado

| Coluna | Tipo | Origem |
|---|---|---|
| `lote_id` | int | Sequencial |
| `data_cadastro` | data | SIMULADO, uniforme entre 01/06 e 20/09/2026 |
| `setor_doador` | texto | SIMULADO: supermercado, restaurante, padaria, feira, industria, pessoa_fisica. Mix e premissa |
| `tipo_doador` | PF/PJ | Derivado do setor |
| `cidade`, `uf` | texto | Cidades reais (grande SP e Campinas), peso de cada uma e premissa |
| `latitude`, `longitude` | float | Centro aproximado real da cidade + ruido de ate ~4 km (SIMULADO) |
| `descricao` | texto | SIMULADO, texto livre montado de listas de alimentos por categoria |
| `categoria` | texto | SIMULADO. Alvo do classificador de tipo: hortifruti, padaria, laticinios, carnes_peixes, preparados, nao_pereciveis |
| `perecivel` | bool | Derivado da categoria (so `nao_pereciveis` e False) |
| `armazenamento` | texto | SIMULADO, mesmo dominio da API: ambiente, refrigerado, congelado |
| `quantidade_kg` | float | SIMULADO, lognormal com mediana por setor (premissa) |
| `validade` | data | SIMULADO: `data_cadastro` + parte da vida util restante |
| `prioridade` | texto | **Rotulo alvo**, SIMULADO pela formula abaixo: alta, media, baixa |

Nao ha dado pessoal: sem nome, documento, telefone ou endereco de doador.
O dataset pode ficar publico no repo sem questao de LGPD.

## Como o rotulo `prioridade` e gerado

```
relativa     = 1 - (dias ate a validade / vida util total), limitado entre 0 e 1
absoluta     = 1 - (dias ate a validade / 4), limitado entre 0 e 1
urgencia     = maior entre relativa e absoluta
fora_do_frio = 1 se a categoria exige frio (laticinios, carnes_peixes, preparados)
               e o lote esta em ambiente, senao 0
score = 0.55*urgencia + 0.20*perecivel + 0.15*fora_do_frio
      + 0.10*min(quantidade_kg/200, 1) + ruido normal (desvio 0.08)

alta se score >= 0.60, media se >= 0.38, baixa no resto
```

Os pesos e o prazo de 4 dias (`PRAZO_LOGISTICO_DIAS`: cadastro, achar ONG, coletar, entregar) sao
premissa do grupo, nao vem de estudo. **O termo `absoluta` entrou em 13/10** (rotulo v2): antes so
existia a fracao da vida util, e uma marmita recem-feita que vence amanha saia `baixa`. A mudanca
alterou 128 de 1212 rotulos, todos pra cima; o resto do CSV e identico (mesma seed). Motivo e
efeito no modelo em `docs/ia.md`, secao 4.

O ruido existe pra que nenhuma regra simples acerte tudo: so olhando os dias ate a validade, a
melhor regra de corte (alta ate 1 dia, media ate 5) acerta 62,7% no teste do v1 (`models/metrics.json`).

## Ruido injetado de proposito

Pra EDA e limpeza terem o que tratar, como num cadastro real:

- ~2% `descricao` vazia, ~3% `armazenamento` vazio
- ~5% sem `latitude`/`longitude` (endereco nao geocodificado)
- ~1% com `quantidade_kg` multiplicada por 1000 (gramas digitadas como kg)
- 12 lotes duplicados com `lote_id` novo
- Lotes ja vencidos no cadastro (validade antes de `data_cadastro`)

O rotulo e calculado antes do ruido, com os valores corretos.

## Como regenerar

Da raiz do repo:

```
python data/gerar_dataset_v0.py
```

So usa a biblioteca padrao. A seed e fixa, entao o CSV sai identico.

## Historico simulado (`historico_simulado.json`)

Pra alimentar o dashboard (dia 16). **Tudo SIMULADO**, cada linha leva `origem: "SIMULADO"` e as
premissas ficam na chave `premissas` do arquivo. `python -m data.gerar_historico_simulado` gera: parte dos
1083 lotes do v1, usa o `ml.matching` pra escolher a ONG e descarta o lote se nao ha ONG possivel
ou se o tempo de match estoura a validade. 12 ONGs inventadas (2 por cidade), nenhuma real. Mesmo
formato da API (`lotes`, `doacoes`, `ongs`): `api.kpis.calcula_impacto` calcula em cima, via
`carregar_historico()`. Saida atual: 1037 doados, 17 reservados, 29 descartados, 1054 doacoes
confirmadas. **Os numeros saem das premissas, nao de dado**: a taxa de doacao de ~96% e otimista
(premissas simples) e nao pode ir pro pitch como resultado.

## Dataset v1 (`lotes_v1.csv`)

1083 lotes, gerado do v0 por `python -m ml.limpeza` (duplicados, vencidos, lotes sem armazenamento
e erros de unidade tratados; coordenadas ausentes preenchidas). Continua **SIMULADO**. Tem as
colunas do v0 mais `dias_ate_validade`, `fora_do_frio` e `geo_aproximada` (`True` quando a
latitude e a longitude sao o centro da cidade, nao o endereco). Detalhes e o que cada tratamento
faz em `docs/ia.md`.

## Limitacoes (pra defesa)

- **O modelo vai aprender a nossa formula**, nao o mundo real. O v0 prova o
  pipeline (dado, treino, predicao na API), nao que a prioridade reflete descarte
  real. Com dado real de um banco de alimentos, so troca o CSV.
- Faixas de vida util, pesos do score, mix de setores e quantidades sao premissas.
- So cobre grande SP e Campinas: o matching por distancia nao foi testado em
  outras regioes.
- Sem sazonalidade: cadastro uniforme no tempo.
- Vies: categorias com mais lotes (hortifruti) vao pesar mais no treino; usar
  split estratificado e olhar metrica por categoria, nao so a geral.
