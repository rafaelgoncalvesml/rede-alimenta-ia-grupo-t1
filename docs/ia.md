# IA: dataset v1, metrica, baseline, modelo e predict()

Versao v2 (rotulo revisto em 13/10, secao 4). **Todo o dataset e SIMULADO** (ver `data/README.md`): as metricas abaixo provam que o
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

- Com o rotulo revisto (v2, secao 4) as classes ficaram menos equilibradas (v1 limpo: 444 alta, 372
  media, 267 baixa; razao 1,7). Acuracia deixaria uma classe ruim passar escondida; o F1 macro pesa
  as tres igual.
- Acompanham, sem virar meta: `recall_alta` e `alta_prevista_como_baixa`, a fracao das altas que o
  modelo manda pro fim da fila. E o erro que mais custa: o lote que ia estragar espera.
- Pesos e cortes do rotulo sao premissa do grupo, nao vem de estudo de custo. Trocar a metrica por
  outra (recall da alta, por exemplo) e decisao de negocio, nao tecnica.

Split: 80/20 estratificado pela prioridade, seed 42 (866 treino, 217 teste). O modelo e escolhido
por validacao cruzada de 5 dobras so no treino; o teste e medido uma vez.

## 4. Baseline e modelo (v2, rotulo revisto em 13/10)

**Por que mudou.** Rodando o seed de demo em 12/10, marmitas prontas e pao que vencem amanha sairam
`baixa`. O modelo nao tinha errado: tinha aprendido o rotulo, e o rotulo media so a **fracao** da
vida util ja gasta. Pra um item de 1 a 4 dias de vida, "falta 1 dia" era lote recem-feito, logo pouco
urgente (preparados com 1 dia restante eram `alta` em 16% dos lotes). Pra doacao o que pesa e quanto
tempo sobra pra achar ONG, coletar e entregar.

**O que mudou.** Em `data/gerar_dataset_v0.py` a urgencia passou a ser o **maior** entre a fracao
da vida util ja gasta e o prazo absoluto, `1 - dias / 4` (`PRAZO_LOGISTICO_DIAS = 4`, premissa:
dias entre o cadastro e a comida chegar ao prato). O resto do dataset e identico (mesma seed): so
128 de 1212 rotulos mudaram, e todos pra cima (30 baixa -> alta, 53 baixa -> media, 45 media ->
alta), nunca rebaixando. Um teste (`test_perecivel_de_vida_curta_que_vence_amanha_e_alta`) estava
vermelho com a v1 e passou com a v2. O artefato virou `models/prioridade_v2.joblib`.

**Baseline** (`ml/baseline.py`): so `dias_ate_validade`, com dois cortes aprendidos no treino pra
maximizar o F1 macro. Resultado na v2: alta se vence em ate 1 dia, media ate 5, baixa depois.

**Modelos** (`ml/treinar.py`): regressao logistica e Random Forest (100 arvores, `min_samples_leaf=5`,
escolhido por CV no treino na v1; com folhas de 1 lote o artefato pesava 9 MB e a CV era pior).

| v2 | F1 macro (CV treino) | F1 macro (teste) | Acuracia (teste) | Recall alta | Alta como baixa |
|---|---|---|---|---|---|
| Baseline (dias) | 0,644 | 0,610 | 0,627 | 0,775 | 9,0% |
| Regressao logistica | 0,505 | 0,492 | 0,558 | 0,944 | 0,0% |
| **Random Forest** | **0,708** | **0,669** | **0,682** | **0,832** | **2,2%** |

- O Random Forest continua o escolhido, e o erro que mais custa (alta mandada pro fim da fila) caiu
  de 5,3% na v1 pra 2,2%. Em compensacao **o ganho sobre o baseline encolheu e ficou incerto**:
  +0,058 no teste e +0,064 na CV. Bootstrap de 2000 reamostragens do teste: Random Forest entre
  0,605 e 0,728 (IC 95%), baseline entre 0,542 e 0,673, diferenca entre -0,001 e +0,117 (o Random
  Forest ganha em 97,2% das reamostragens). Faz sentido: o prazo absoluto entrou no rotulo, e o
  baseline e justamente uma regra de prazo. **Na defesa: o modelo bate a regra simples, por pouco.**
- A regressao logistica continua sem ganhar do baseline. Acerta quase todas as altas (84 de 89), mas
  chama de alta 48 de 75 medias e 17 de 53 baixas.
- Por categoria (teste, 21 a 78 lotes por grupo, numero ruidoso): melhor em preparados (0,71, n=23) e
  padaria (0,70, n=42), os de vida curta que motivaram a mudanca; pior em carnes_peixes (0,38, n=21) e
  nao_pereciveis (0,39, n=30). Nao da pra comparar categoria a categoria com a v1 de forma justa,
  porque o rotulo e os lotes do teste mudaram.
- Uma feature candidata continua sendo dias divididos pela vida util tipica da categoria, mas ela
  copiaria as faixas que o proprio gerador usa: so vale com faixas conferidas no FoodKeeper (USDA).

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
| `modelo_versao` | `"v2"` |

Exemplo real (`iogurte natural`, 20 kg, vence em 2 dias, em ambiente; na v1 saia `media`):

```json
{"categoria": "laticinios", "categoria_origem": "modelo", "categoria_confianca": 0.841,
 "perecivel": true, "prioridade": "alta",
 "probabilidades": {"alta": 0.612, "media": 0.312, "baixa": 0.076},
 "dias_ate_validade": 2, "fora_do_frio": true, "modelo_versao": "v2"}
```

Entrada invalida, inclusive campo ausente, levanta `ValueError` com a mensagem pronta pra virar 422.
A tela deve mostrar as `probabilidades` quando a decisao for apertada.

**Carga.** A API carrega o modelo quando sobe (`api/ia.py`, `pre_carregar_modelo`), nao no primeiro
`POST /lotes`, que levou 9,8 s em producao no dia 23. A subida registra no log o evento
`modelo.carregado` com `segundos` e `memoria_pico_mb` (pico de memoria do processo, lido do sistema
operacional: o numero que a aba Metrics do plano free do Render nao mostra). Se carregar falhar, a API
sobe do mesmo jeito e o lote entra sem prioridade, como antes. Localmente (Windows, Python 3.14)
carregar leva 0,7 s e a primeira predicao depois disso, 9 ms. **Nao medi no Render.**

## 6. Limitacoes (pra defesa)

- **O modelo aprende a nossa formula, nao o mundo.** O rotulo e `score` de pesos escolhidos pelo grupo
  mais ruido (`data/README.md`). Com dado real de um banco de alimentos, so troca o CSV e re-treina.
- O prazo logistico de 4 dias e premissa, como os pesos. Mudou o numero, roda o gerador, a limpeza e
  o treino de novo (secao 7) e o teste de pereciveis de vida curta diz se o efeito continua.
- Descricoes simuladas: o classificador de categoria esta otimista (secao 4).
- So grande SP e Campinas, sem sazonalidade. Coordenada aproximada por cidade, ate ~4 km de erro.
- Categorias com poucos lotes no teste dao metrica por categoria ruidosa.
- `predict()` usa a data do servidor (`date.today()`, UTC no Render), igual a validacao `LoteCreate`.
  Perto da meia-noite de Brasilia, um lote que vence "hoje" pode ser lido como vencido.

## 7. Reproduzir e operar

```
pip install -r ml/requirements.txt pytest
python data/gerar_dataset_v0.py   # data/lotes_v0.csv (rotulo v2)
python -m ml.limpeza     # data/lotes_v1.csv
python -m ml.treinar     # models/prioridade_v2.joblib + models/metrics.json (~1 MB, seed fixa)
pytest ml
```

- **Python 3.11 ou maior.** scikit-learn 1.8, pandas 3 e numpy 2.4 exigem 3.11+. O Dockerfile
  planejado com `python:3.10-slim` nao instala isto: usar `3.11-slim` ou maior.
- `scikit-learn` esta fixado em `ml/requirements.txt`: o `.joblib` so carrega na versao que o treinou.
  Mudou a versao, roda `python -m ml.treinar` de novo e commita o artefato.
- `.joblib` e pickle: carregar arquivo de fora executa codigo. Este e gerado aqui e versionado no
  repo, e o `joblib.load` em `ml/predict.py` tem um comentario explicando (com `# nosec B301` por
  precaucao). Se o Bandit apontar, registrar como risco aceito com essa justificativa, sem esconder.
