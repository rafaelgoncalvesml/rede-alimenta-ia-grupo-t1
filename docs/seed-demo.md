# Seed de demo

`python -m api.seed_demo`: 3 doadores, 4 ONGs e 5 lotes, idempotente (rodar de novo nao duplica).
Testes: `api/tests/test_seed_demo.py` (roda contra a API real, em memoria). Precisa de `ADMIN_EMAIL`
e `ADMIN_PASSWORD`, como o `api/seed_dev.py`. Conferido em 12 e 13/10/2026.

## O que e real e o que e simulado

| Dado | Origem |
|---|---|
| Nome, CNPJ e endereco das 4 ONGs | **Real.** Cadastro da Receita Federal (situacao `ATIVA` nas quatro) |
| Coordenada das 4 ONGs | **Real, nivel de rua.** OpenStreetMap/Nominatim, (c) OpenStreetMap contributors (ODbL) |
| `capacidade_kg` e `necessidades` das ONGs | **SIMULADO.** As entidades nao informaram. No codigo, marcado `# SIMULADO` |
| 3 doadores e 5 lotes | **SIMULADO.** Ficticios, com `(DEMO)` no nome do doador. CNPJs `000000000001xx` invalidos de proposito |

| ONG | CNPJ | Cidade | De onde veio o CNPJ | Conferido na Receita via |
|---|---|---|---|---|
| Casa do Zezinho - Associacao Educacional e Assistencial | 74.566.035/0001-29 | Sao Paulo (Capao Redondo) | site da entidade | BrasilAPI |
| Banco de Alimentos - Associacao Civil | 02.736.449/0001-48 | Sao Paulo (Pacaembu) | site da entidade | BrasilAPI |
| Fundacao FEAC - Federacao das Entidades Assistenciais de Campinas | 46.002.176/0001-83 | Campinas (Vila Brandina) | Mapa das OSCs (IPEA) | CNPJ.ws |
| Arsenal da Esperanca - Associacao Assindes Sermig | 62.459.409/0001-28 | Sao Paulo (Bras/Mooca) | lista de projetos da Justica Federal de SP (2018) | CNPJ.ws |

A FEAC e o Arsenal foram conferidos no CNPJ.ws (mesmos dados abertos da Receita) porque a BrasilAPI
devolveu erro 500 em 13/10.

Cuidados com esses dados:

- **A Receita e o site divergem** no numero da Casa do Zezinho (30 contra 77) e no bairro do Arsenal
  (Bras contra Mooca). O seed usa a Receita.
- **Nao use a coordenada da API de CEP** (BrasilAPI `/cep/v2`): pras ONGs de Sao Paulo ela devolveu o
  centro da cidade, nao o endereco. O Capao Redondo fica a ~20 km dali.
- Na FEAC e no Arsenal o OpenStreetMap achou a rua com o CEP certo, mas nao o numero: a coordenada
  e da rua, a poucas centenas de metros do predio.
- A FEAC coordena uma rede de entidades de Campinas; aqui ela aparece como receptora, o que e uma
  simplificacao do demo.
- **As entidades nao foram consultadas** e nao sabem que aparecem num demo. Antes de mostrar em
  publico, vale avisa-las.

Pra trocar ou acrescentar uma ONG: conferir o CNPJ (`ATIVA`, endereco) na Receita, geocodificar o
endereco no Nominatim e colocar em `ONGS_REAIS`, com `capacidade_kg` e `necessidades` marcadas `SIMULADO`.

## O que os 5 lotes mostram (modelo v2)

| Lote | Prioridade | Mostra |
|---|---|---|
| tomate, 120 kg, doador em Sao Paulo | alta | ordem por distancia: Banco de Alimentos (3 km), Arsenal (8 km), Casa do Zezinho (14 km), FEAC (81 km) |
| pao, 25 kg, vence amanha | alta | na v1 saia `baixa`; foi o caso que motivou o rotulo v2 (`docs/ia.md`, secao 4) |
| iogurte, 60 kg, doador em Campinas | media | a FEAC (3 km) em primeiro, o Banco de Alimentos (81 km) em segundo |
| arroz, 400 kg, doador sem coordenada | baixa | fallback (centro de Santo Andre, `geo_aproximada=true`) e a Casa do Zezinho (300 kg) descartada por capacidade |
| marmitas, 40 kg, vencem amanha | alta | so o Arsenal, que serve refeicoes, aceita preparados |
