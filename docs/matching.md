# Matching simples (issue 8)

`ml/matching.py` e `ml/geo.py`. Testes: `ml/tests/test_matching.py` (comportamento) e
`api/tests/test_contrato_matching.py` (contrato com a API). Versao simples que o Rafael sugeriu no
checkpoint da Semana 2: filtra por categoria e capacidade, ordena por distancia (haversine), `score` e
a distancia normalizada, sem peso aprendido.

## Contrato

```python
from ml.matching import matching

r = matching(lote, doador, ongs)   # tres dicts/listas de dicts, como a API devolve
```

| Entrada | Campos usados |
|---|---|
| `lote` | `quantidade_kg`, `tipo` (pode ser `None`) |
| `doador` | `latitude`, `longitude`, `cidade`, `estado` (as coordenadas podem ser `None`) |
| `ongs` | `id`, `latitude`, `longitude`, `cidade`, `estado`, `capacidade_kg`, `necessidades` |

Saida: `{"ranking": [...], "descartadas": [...]}`.

```json
{"ranking": [{"ong_id": 2, "distancia_km": 3.0, "score": 0.03, "geo_aproximada": false, "posicao": 1}],
 "descartadas": [{"ong_id": 4, "motivo": "categoria"}]}
```

| Campo | Significado |
|---|---|
| `distancia_km` | haversine entre doador e ONG, 2 casas |
| `score` | `min(distancia_km / 100, 1)`, 4 casas. **Menor e melhor.** 0 = mesmo ponto, 1 = 100 km ou mais |
| `geo_aproximada` | `true` se a coordenada do doador **ou** da ONG veio do fallback: a distancia e estimativa |
| `posicao` | 1, 2, 3... ordenado por `distancia_km` e, no empate, por `ong_id` (resultado sempre igual) |
| `motivo` | `categoria`, `capacidade` ou `sem_coordenada` |

O ranking traz tambem o `nome` da ONG. Na doacao (`POST /doacoes`) o servidor calcula `distancia_km` e
`score` com esta mesma funcao e ignora o que o cliente mandar nesses campos; ONG sem coordenada conhecida
entra com os dois nulos.

## Regras

1. **Categoria:** `lote.tipo` precisa estar em `ong.necessidades`. ONG sem `necessidades` nao recebe
   (decisao do dia 20). Lote sem `tipo` (o modelo falhou no cadastro) nao filtra por categoria.
2. **Capacidade:** `lote.quantidade_kg > ong.capacidade_kg` descarta; igual passa. Por doacao, nao
   acumulada.
3. As regras 1 e 2 sao **as mesmas de `api/routers/doacoes.py`** (`_confere_ong_recebe`): toda ONG
   sugerida consegue confirmar a doacao e nenhuma que ela aceitaria some do ranking. Um teste
   percorre as combinacoes e compara os dois lados.
4. **Ordem:** distancia crescente. A prioridade do lote **nao** entra: o ranking e por lote. Quem
   quiser atender primeiro o lote de prioridade alta ordena os lotes antes de chamar.

## Fallback de coordenada (pendente do `docs/ia.md`, agora feito)

Coordenada ausente, `0,0`, latitude e longitude trocadas ou fora do retangulo do Brasil (a mesma
regra da limpeza do dataset) conta como ausente. Ai:

- cidade com centro conhecido (as 6 do dataset: Sao Paulo, Guarulhos, Osasco, Santo Andre, Sao
  Bernardo do Campo, Campinas) usa esse centro, e `geo_aproximada` vira `true`. Acento, caixa e UF em
  minuscula nao atrapalham ("SAO PAULO", "Sao Paulo", "sp");
- ONG em cidade **sem** centro conhecido sai do ranking com `sem_coordenada`. Nao inventa;
- doador nessa situacao levanta `ValueError` (sem origem nao ha distancia): a rota devolve 422.

## Premissas e limites (pra defesa)

- **100 km e premissa** (`RAIO_REFERENCIA_KM`). Escolhi dividir por um raio fixo em vez de normalizar
  entre as candidatas (min-max) porque assim o score de uma ONG nao muda conforme quem mais esta na
  lista, e uma unica candidata nao da 0/0. Pra min-max, troque o `km / RAIO_REFERENCIA_KM` por
  `(km - menor) / (maior - menor)`; o ranking nao muda, so o numero.
- **Distancia em linha reta**, nao de rota. O erro de trajeto real fica de fora.
- **O fallback erra pelo tamanho da cidade.** O centro de Sao Paulo pode ficar a 20 km ou mais do
  endereco real (a Casa do Zezinho, no Capao Redondo, fica a ~20 km do centro). Por isso
  `geo_aproximada` existe: a tela deve mostrar "distancia aproximada" nesses casos.
- Os centros das cidades sao os mesmos de `data/gerar_dataset_v0.py` (um teste garante). Cidade
  fora dessa lista so funciona se doador e ONG tiverem coordenada propria.

## Rota (14/10)

`api/routers/matching.py`: `POST /matching/{lote_id}`, so admin e o doador dono do lote (os outros papeis
recebem 403, na matriz de `api/tests/test_acesso_negado.py`), limite de 20 pedidos por minuto. Lote que
nao existe: 404. Lote que nao esta `disponivel`: 409. Doador sem coordenada e sem centro de cidade: 422.
Testes em `api/tests/test_matching_rota.py`, incluindo a doacao gravando a distancia do servidor.

Verificado de ponta a ponta com o seed de demo (`docs/seed-demo.md`): lote, prioridade do modelo,
matching, doacao confirmada e KPI, pela API e pela tela de Matchings do Streamlit (papeis doador e ONG).
