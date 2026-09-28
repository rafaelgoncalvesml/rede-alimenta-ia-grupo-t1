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
urgencia     = 1 - (dias ate a validade / vida util total), limitado entre 0 e 1
fora_do_frio = 1 se a categoria exige frio (laticinios, carnes_peixes, preparados)
               e o lote esta em ambiente, senao 0
score = 0.55*urgencia + 0.20*perecivel + 0.15*fora_do_frio
      + 0.10*min(quantidade_kg/200, 1) + ruido normal (desvio 0.08)

alta se score >= 0.60, media se >= 0.38, baixa no resto
```

Os pesos sao premissa do grupo, nao vem de estudo. O ruido existe pra que nenhuma
regra simples acerte tudo: so olhando os dias ate a validade, a melhor regra de
corte (alta ate 0 dias, media ate 5) acerta cerca de 58%. Esse e o piso que o modelo precisa superar.

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
