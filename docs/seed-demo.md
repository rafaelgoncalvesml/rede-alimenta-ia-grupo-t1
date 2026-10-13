# Seed de demo

`python -m api.seed_demo` (todo) ou `python -m api.seed_demo --so-reais`. 3 doadores, 4 ONGs e 5 lotes,
idempotente. Testes: `api/tests/test_seed_demo.py` (roda contra a API real, em memoria). Precisa de
`ADMIN_EMAIL` e `ADMIN_PASSWORD`, como o `api/seed_dev.py`. Conferido em 12/10/2026.

## O que e real e o que e simulado

| Dado | Origem |
|---|---|
| Nome, CNPJ e endereco das 2 ONGs reais | **Real.** Receita Federal, via [BrasilAPI](https://brasilapi.com.br/api/cnpj/v1/74566035000129). Situacao `ATIVA` nas duas |
| Coordenada das 2 ONGs reais | **Real, nivel de rua.** OpenStreetMap/Nominatim, (c) OpenStreetMap contributors (ODbL) |
| `capacidade_kg` e `necessidades` das ONGs reais | **SIMULADO.** As entidades nao informaram. Esta no codigo marcado com `# SIMULADO` |
| 2 ONGs com `(DEMO)` no nome, 3 doadores, 5 lotes | **SIMULADO.** Ficticios. Os CNPJs `000000000004xx` sao invalidos de proposito |

| ONG real | CNPJ | Cidade | Conferencia |
|---|---|---|---|
| Casa do Zezinho - Associacao Educacional e Assistencial | 74.566.035/0001-29 | Sao Paulo (Capao Redondo) | CNPJ no site da entidade e na Receita (ATIVA, desde 1994) |
| Banco de Alimentos - Associacao Civil | 02.736.449/0001-48 | Sao Paulo (Pacaembu) | CNPJ no site da entidade e na Receita (ATIVA, desde 1998) |

Duas coisas que mexem com a confianca nesses dados:

- **A Receita e o site divergem no numero da Casa do Zezinho** (30 contra 77). O seed usa a Receita.
- **Nao use a coordenada da API de CEP** (BrasilAPI `/cep/v2`): pras duas ONGs ela devolveu o mesmo
  ponto (-23,5475; -46,6361), que e o centro de Sao Paulo, nao o endereco. O Capao Redondo fica a ~20 km dali.

**As entidades nao foram consultadas** e nao sabem que aparecem num demo. Antes de mostrar em
publico, vale avisa-las, ou rodar so a versao `(DEMO)`.

## Por que so 2 ONGs reais

Procurei ISA (Campinas, dentro da Ceasa) e Gastromotiva, e nao achei o CNPJ em nenhuma pagina
oficial; nao vou chutar. **Mande o CNPJ de qualquer ONG e entra em minutos:** conferir em
`https://brasilapi.com.br/api/cnpj/v1/<cnpj>` (`ATIVA`, endereco), geocodificar o endereco no
Nominatim e colocar em `ONGS_REAIS` com `capacidade_kg` e `necessidades` marcadas `SIMULADO`.

## O que os 5 lotes exercitam

| Lote | Mostra |
|---|---|
| tomate, 120 kg, doador em Sao Paulo | ordem por distancia: Banco de Alimentos (3 km), Casa do Zezinho (14 km), Campinas (82 km) |
| pao, 25 kg | uma ONG sem coordenada (DEMO, Santo Andre) entra pelo fallback, `geo_aproximada=true` |
| iogurte, 60 kg, doador em Campinas | a ONG de Campinas fica em primeiro, a de Sao Paulo (81 km) em segundo |
| arroz, 400 kg, doador sem coordenada | a Casa do Zezinho (300 kg) e descartada por capacidade |
| marmitas, 40 kg | **nenhuma ONG possivel**, de proposito: so uma aceita preparados e leva 30 kg |
