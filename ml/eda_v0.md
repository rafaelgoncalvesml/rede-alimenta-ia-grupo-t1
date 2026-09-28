# EDA do dataset v0 (SIMULADO)

Gerado por `ml/eda_v0.py` a partir de `data/lotes_v0.csv`. 1212 linhas, 15 colunas originais (+ `dias_ate_validade`, calculada aqui).

## 1. Tipos

```
                            dtype
lote_id                     int64
data_cadastro      datetime64[us]
setor_doador                  str
tipo_doador                   str
cidade                        str
uf                            str
latitude                  float64
longitude                 float64
descricao                     str
categoria                     str
perecivel                    bool
armazenamento                 str
quantidade_kg             float64
validade           datetime64[us]
prioridade                    str
dias_ate_validade           int64
```

## 2. Nulos

```
               nulos    %
latitude          76  6.3
longitude         76  6.3
descricao         28  2.3
armazenamento     34  2.8
```

## 3. Duplicados

12 lotes repetidos com `lote_id` diferente (mesmo conteudo cadastrado duas vezes). Exemplo:

```
      lote_id                            descricao  quantidade_kg   validade
406       407                    enlatado de milho           27.7 2026-06-05
1207     1208                    enlatado de milho           27.7 2026-06-05
71         72  patinho em cubos embalagem avariada           30.2 2026-06-11
1206     1207  patinho em cubos embalagem avariada           30.2 2026-06-11
```

## 4. Balanceamento do alvo (`prioridade`)

```
prioridade
alta     451
media    401
baixa    360
```

Razao maior/menor classe: 1.25. Desbalanceamento leve, da pra usar split estratificado sem reamostragem.

### Categoria e perecibilidade

```
categoria
hortifruti        394
padaria           206
nao_pereciveis    196
carnes_peixes     156
laticinios        150
preparados        110
```

```
perecivel
True     1016
False     196
```

## 5. Outliers em `quantidade_kg`

```
count      1212.0
mean        276.6
std        4051.0
min           0.1
25%           6.8
50%          19.6
75%          51.2
max      116500.0
```

Pelo IQR global (acima de Q3 + 3*IQR = 184.5 kg) sao 69 lotes, mas a maioria e lote grande legitimo de supermercado ou industria. Comparando com a mediana do proprio setor, ha um corte claro: 8 lotes passam de 100x a mediana do setor, e o proximo fica abaixo de 25x. Esses tem cara de gramas digitadas como kg:

```
     lote_id   setor_doador                               descricao  quantidade_kg
878      879   supermercado                maca fuji sobra de feira       116500.0
584      585    restaurante                        patinho em cubos        64800.0
317      318        padaria                pao de forma lote grande        29800.0
224      225   supermercado  farinha de trigo proximo do vencimento        26100.0
735      736          feira            cebola proximo do vencimento        20100.0
593      594          feira     folhas de couve para consumo rapido        11800.0
472      473        padaria          manteiga proximo do vencimento         6900.0
27        28  pessoa_fisica    farinha de trigo para consumo rapido         5000.0
```

Limite: um erro de unidade num lote pequeno (0,5 kg virando 500 kg) cai dentro da faixa plausivel e nao e detectavel so pela quantidade. Na API, a defesa e validar no cadastro (teto por setor, confirmacao acima de X kg).

## 6. Dias ate a validade

```
count    1212.0
mean       17.6
std        43.3
min       -34.0
25%         1.0
50%         2.0
75%         7.0
max       325.0
```

87 lotes ja chegam vencidos (dias < 0). Pela regra de negocio lote vencido nao pode ser doado: sai do treino e a API deve recusar no cadastro.

## 7. Coerencia categoria x armazenamento

```
armazenamento   (nulo)  ambiente  congelado  refrigerado
categoria                                               
carnes_peixes        3         5         76           72
hortifruti          17       216          0          161
laticinios           4        22          0          124
nao_pereciveis       4       192          0            0
padaria              5       181          0           20
preparados           1        20         12           77
```

47 lotes de categoria que exige frio registrados em ambiente. Nao e erro de cadastro: e o caso de maior risco que o modelo precisa capturar.

## 8. Prioridade por categoria (% da linha)

```
prioridade      alta  media  baixa
categoria                         
carnes_peixes   46.2   31.4   22.4
hortifruti      43.9   32.0   24.1
laticinios      44.7   36.0   19.3
nao_pereciveis   6.6   40.3   53.1
padaria         40.3   29.1   30.6
preparados      39.1   30.0   30.9
```

## 9. O que vai pra limpeza (dataset v1, dia 5)

- Remover os 12 duplicados de conteudo.
- Remover os 87 lotes vencidos.
- Dividir por 1000 os 8 erros de unidade; manter os demais lotes grandes.
- `armazenamento` nulo: imputar pela moda da categoria ou descartar; decidir no v1.
- `descricao` vazia: manter, a categoria ja vem preenchida; so atrapalha o classificador de texto.
- `latitude`/`longitude` nulas: nao afetam a prioridade, mas o matching precisa; geocodificar pela cidade ou excluir do matching.
- Features pro v1: `dias_ate_validade`, `perecivel`, `categoria`, `armazenamento`, flag de fora do frio, `quantidade_kg`.
