# IA: dataset v1, metrica, baseline, modelo e predict()

Versao v1. **Todo o dataset e SIMULADO** (ver `data/README.md`): as metricas abaixo provam que o
pipeline funciona, nao que a prioridade reflete descarte real. Numeros em `models/metrics.json`.

## 1. Limpeza: dataset v0 -> v1

`python -m ml.limpeza` le `data/lotes_v0.csv` e grava `data/lotes_v1.csv` (1212 -> 1083 lotes).
As decisoes vem da secao 9 de `ml/eda_v0.md`. Codigo e testes: `ml/limpeza.py`, `ml/tests/test_limpeza.py`.

| Problema | Lotes | O que faz |
|---|---|---|
| Lote cadastrado duas vezes (mesmo conteudo, `lote_id` novo) | 12 | Remove |
| Vencido no cadastro (`validade` antes de `data_cadastro`) | 85 | Remove. Lote vencido nao pode ser doado. Vencer no proprio dia ainda vale |
| `armazenamento` vazio | 32 | Remove (secao 2) |
| `quantidade_kg` digitada em gramas (mais de 100x a mediana do setor) | 6 | Divide por 1000 |
| Sem coordenada, ou coordenada fora do Brasil (0,0; lat e lon trocadas) | 69 | Centro da cidade + `geo_aproximada=True` (secao 2) |

Limite conhecido: erro de unidade em lote pequeno (0,5 kg virando 500 kg) cai na faixa plausivel e
nao e detectavel so pela quantidade. Na API a defesa e validar no cadastro.
`descricao` vazia fica no dataset; so sai do treino do classificador de categoria.

### Features do modelo de prioridade

Calculadas em `ml/features.py`, o mesmo codigo no treino e no `predict()`.

| Feature | Como |
|---|---|
| `dias_ate_validade` | `validade` menos `data_cadastro` (em producao, menos a data de hoje) |
| `perecivel` | `categoria != nao_pereciveis` (vem da categoria, nao do que foi digitado) |
| `fora_do_frio` | a categoria exige frio (laticinios, carnes_peixes, preparados) e o armazenamento e mais quente que o minimo |
| `log_quantidade_kg` | `log1p(quantidade_kg)` |
| `categoria`, `armazenamento` | one-hot |

Nao entram: `setor_doador`, `cidade`, `uf`, `latitude`, `longitude`, `data_cadastro` (nao existem no
`Lote` da API ou nao afetam a prioridade) e `descricao` (so alimenta o classificador de categoria).

## 2. Armazenamento e lat/long

**Armazenamento** (`ambiente`, `refrigerado`, `congelado`): define a vida util e o rotulo. Lote sem
armazenamento e descartado do treino em vez de imputado pela moda da categoria, porque o valor
chutado entraria no treino como se fosse verdade (carnes_peixes empata entre refrigerado e
congelado). Na API o campo e obrigatorio, entao o modelo nunca ve nulo em producao. O `predict()`
recusa valor fora dos tres.

**Latitude e longitude**: o matching precisa, a prioridade nao (a formula do rotulo nao usa), entao
ficam fora do modelo e dentro do dataset. Coordenada ausente ou fora do retangulo do Brasil vira a
mediana das coordenadas conhecidas da mesma cidade, com `geo_aproximada=True`. O v1 fica com 100%
de coordenada, 69 aproximadas. O erro tipico e de ate ~4 km (o jitter do dataset simulado), bom pro
matching por distancia em escala de cidade e ruim pra rota fina. Cidade sem nenhuma coordenada
conhecida continua sem coordenada e sem a marca (nao inventa). O fallback de ONG e doador da API
(que tem latitude e longitude opcionais) esta em `ml/geo.py` e e usado pelo matching
(`docs/matching.md`).

## 3. Metrica-alvo

**F1 macro sobre `prioridade` (alta, media, baixa).** Media simples do F1 das tres classes:

- As classes sao quase equilibradas (v1: 373 alta, 364 media, 346 baixa). Acuracia deixaria uma
  classe ruim passar escondida; o F1 macro pesa as tres igual.
- Acompanham, sem virar meta: `recall_alta` e `alta_prevista_como_baixa`, a fracao das altas que o
  modelo manda pro fim da fila. E o erro que mais custa: o lote que ia estragar espera.
- Pesos e cortes do rotulo sao premissa do grupo, nao vem de estudo de custo. Trocar a metrica por
  outra (recall da alta, por exemplo) e decisao de negocio, nao tecnica.

Split: 80/20 estratificado pela prioridade, seed 42 (866 treino, 217 teste). O modelo e escolhido
por validacao cruzada de 5 dobras so no treino; o teste e medido uma vez.

## 4. Baseline e primeiro modelo

**Baseline** (`ml/baseline.py`): so `dias_ate_validade`, com dois cortes aprendidos no treino pra
maximizar o F1 macro. Resultado: alta se vence em 0 dias, media ate 5, baixa depois.

**Modelos** (`ml/treinar.py`): regressao logistica e Random Forest (100 arvores, `min_samples_leaf=5`,
escolhido por CV no treino entre 6 combinacoes; com folhas de 1 lote o artefato pesava 9 MB e a CV era pior).

| | F1 macro (CV treino) | F1 macro (teste) | Acuracia (teste) | Recall alta | Alta como baixa |
|---|---|---|---|---|---|
| Baseline (dias) | 0,582 | 0,539 | 0,525 | 0,440 | 5,3% |
| Regressao logistica | 0,472 | 0,522 | 0,558 | 0,947 | 2,7% |
| **Random Forest** | **0,655** | **0,654** | **0,650** | 0,760 | 5,3% |

- O Random Forest ganha do baseline em F1 macro (+0,116 no teste, +0,074 na CV) e foi o escolhido.
  Com 217 lotes no teste a margem e larga. Bootstrap de 2000 reamostragens do teste: F1 do Random
  Forest entre 0,594 e 0,715 (IC 95%), baseline entre 0,470 e 0,603, e a diferenca entre +0,037 e
  +0,197 (o Random Forest ganha em 99,8% das reamostragens). O ganho e real, mas de tamanho incerto.
- A regressao logistica **nao** ganha do baseline em F1 macro. Ela e linear em `dias`, e a urgencia
  depende dos dias **em relacao a vida util da categoria**. Em compensacao acerta quase todas as
  altas (0,947), ao custo de chamar de alta boa parte das medias e baixas: 37 de 73 medias e 22 de 69
  baixas viram alta.
- Por categoria (teste, poucos lotes por grupo, numero ruidoso): melhor em nao_pereciveis (0,80, n=34),
  pior em laticinios (0,46, n=31) e preparados (0,49, n=16). Os pereciveis de vida util curta sao o
  ponto fraco, e sao justamente os que mais importam.
- **O piso de 58% citado em `data/README.md` estava inflado**: a regra 0/5 dias acerta 75% dos lotes
  vencidos, e a limpeza os remove. No v1 limpo o piso e ~56% (52,5% no teste).
- Proximo passo do modelo (dia 9): validacao cruzada completa e matriz de confusao. Uma feature
  candidata e dias divididos pela vida util tipica da categoria, mas ela copiaria as faixas de vida
  util que o proprio gerador do dataset usa: so vale com faixas conferidas no FoodKeeper (USDA).

### Classificador de categoria

TF-IDF de n-gramas de caractere + regressao logistica sobre a `descricao`, treinado no mesmo split.
Acuracia no teste: 1,00. **Nao vale como evidencia**: as descricoes simuladas saem de listas fixas de
palavras por categoria. Com texto real de doador ele vai errar mais, e a `categoria_confianca` do
contrato existe pra a interface poder sinalizar categoria incerta.

## 5. Contrato do `predict()`

`ml/predict.py`. A API chama ao cadastrar o lote (`POST /lotes`).

```python
from ml.predict import predict

try:
    r = predict(lote.model_dump(mode="json"))   # chaves extras (doador_id, status...) sao ignoradas
except ValueError as erro:
    raise HTTPException(status_code=422, detail=str(erro))
# grava r["categoria"] em Lote.tipo e r["prioridade"] em Lote.prioridade
```

**Entrada**

| Campo | Regra |
|---|---|
| `descricao` | texto; obrigatorio se `tipo` nao vier |
| `quantidade_kg` | numero maior que zero (nao aceita texto, booleano, NaN nem infinito) |
| `validade` | `date` ou texto `AAAA-MM-DD`; nao pode estar vencida (vencer hoje vale) |
| `armazenamento` | `ambiente`, `refrigerado` ou `congelado` |
| `tipo` | opcional; se vier, uma das 6 categorias e a IA nao reclassifica |

**Saida**

| Campo | Valores |
|---|---|
| `categoria` | `hortifruti`, `padaria`, `laticinios`, `carnes_peixes`, `preparados`, `nao_pereciveis` |
| `categoria_origem` | `informada` (veio em `tipo`) ou `modelo` (classificada pela descricao) |
| `categoria_confianca` | probabilidade da categoria (0 a 1) quando `modelo`; `null` quando `informada` |
| `perecivel` | `true` para todas menos `nao_pereciveis` |
| `prioridade` | `alta`, `media` ou `baixa` |
| `probabilidades` | `{"alta": p, "media": p, "baixa": p}`, soma 1; `prioridade` e a maior |
| `dias_ate_validade` | inteiro, contado a partir de hoje |
| `fora_do_frio` | `true` se a categoria exige frio e o armazenamento e `ambiente` |
| `modelo_versao` | `"v1"` |

Exemplo real (`iogurte natural`, 20 kg, vence em 2 dias, em ambiente):

```json
{"categoria": "laticinios", "categoria_origem": "modelo", "categoria_confianca": 0.829,
 "perecivel": true, "prioridade": "media",
 "probabilidades": {"alta": 0.362, "media": 0.451, "baixa": 0.187},
 "dias_ate_validade": 2, "fora_do_frio": true, "modelo_versao": "v1"}
```

Entrada invalida, inclusive campo ausente, levanta `ValueError` com a mensagem pronta pra virar 422.
A tela deve mostrar as `probabilidades` quando a decisao for apertada, como neste exemplo.

## 6. Limitacoes (pra defesa)

- **O modelo aprende a nossa formula, nao o mundo.** O rotulo e `score` de pesos escolhidos pelo grupo
  mais ruido (`data/README.md`). Com dado real de um banco de alimentos, so troca o CSV e re-treina.
- Descricoes simuladas: o classificador de categoria esta otimista (secao 4).
- So grande SP e Campinas, sem sazonalidade. Coordenada aproximada por cidade, ate ~4 km de erro.
- Categorias com poucos lotes no teste (preparados: 16) dao metrica por categoria ruidosa.
- **Pereciveis de vida curta: a prioridade contraria a intuicao (achado de 12/10, rodando o seed de
  demo).** Marmitas prontas (preparados, refrigerado) que vencem amanha saem `baixa`
  (alta 0,28 / media 0,32 / baixa 0,40); pao em ambiente vencendo amanha tambem. **O modelo nao
  errou: aprendeu o rotulo.** No dataset v1, preparados com 1 dia restante sao `alta` em 16% dos
  lotes e `baixa` em 34% (padaria: 22% e 36%), porque o rotulo mede a **fracao** da vida util ja
  gasta, e pra um item de 1 a 4 dias de vida "falta 1 dia" costuma ser lote recem-feito. Pra
  logistica de doacao o que pesa e o prazo absoluto. Corrigir e mudar a premissa do rotulo
  (`data/gerar_dataset_v0.py`, funcao `prioridade`), regenerar o dataset e re-treinar: decisao do
  grupo, porque troca o numero da defesa e o artefato que a API ja usa. Enquanto isso, a tela
  deve mostrar as `probabilidades`: nesses casos o modelo ja diz que esta em duvida.
- `predict()` usa a data do servidor (`date.today()`, UTC no Render), igual a validacao `LoteCreate`.
  Perto da meia-noite de Brasilia, um lote que vence "hoje" pode ser lido como vencido.

## 7. Reproduzir e operar

```
pip install -r ml/requirements.txt pytest
python -m ml.limpeza     # data/lotes_v1.csv
python -m ml.treinar     # models/prioridade_v1.joblib + models/metrics.json (~1 MB, seed fixa)
pytest ml
```

- **Python 3.11 ou maior.** scikit-learn 1.8, pandas 3 e numpy 2.4 exigem 3.11+. O Dockerfile
  planejado com `python:3.10-slim` nao instala isto: usar `3.11-slim` ou maior.
- `scikit-learn` esta fixado em `ml/requirements.txt`: o `.joblib` so carrega na versao que o treinou.
  Mudou a versao, roda `python -m ml.treinar` de novo e commita o artefato.
- `.joblib` e pickle: carregar arquivo de fora executa codigo. Este e gerado aqui e versionado no
  repo, e o `joblib.load` em `ml/predict.py` tem um comentario explicando (com `# nosec B301` por
  precaucao). Se o Bandit apontar, registrar como risco aceito com essa justificativa, sem esconder.
