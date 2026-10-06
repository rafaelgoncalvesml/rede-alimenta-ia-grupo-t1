# Checkpoint da Semana 2 (dia 14)

Conferido em 06/10 contra o GitHub (`origin/main` e as branches abertas) e rodando
o que existe na minha maquina. Mesma regra da Semana 1: o que nao aparece no repo
vai como "nao esta no repo", porque pode estar so na maquina de alguem.

## Checklist

| Item | Estado | Dono | Observacao |
|---|---|---|---|
| Modelo treinado e salvo, com metricas reais | feito | Charles | `models/prioridade_v1.joblib` e `models/metrics.json`. Random Forest, F1 macro 0,654 no teste (baseline 0,539). Dataset todo simulado, dito em `docs/ia.md` |
| Matching funcionando e ligado a API | **nao esta no repo** | Charles / Rafael | Nao existe `ml/matching.py` nem `POST /matching`. So aparece em docs. E o buraco principal do checkpoint |
| CRUD completo com Swagger | feito | Rafael | Doador, ONG, lote e doacao. `/docs` no ar |
| Banco em nuvem conectado | feito | Rafael | Conferi hoje: `GET /health/db` volta `postgres` em 1,7 s e `GET /lotes` em 0,6 s. O banco esta vazio (0 lotes) |
| Frontend consumindo a API real | **nao esta no repo** | Gustavo | `app/` continua so com `.gitkeep`, igual ao dia 7 |
| STRIDE v2 com mitigacao | **nao esta no repo** | Anthony | A v1 tambem nunca apareceu. A unica mencao a STRIDE nos arquivos e o checkpoint da Semana 1 |
| Bandit rodado local | feito | Rafael / Anthony | `bandit -r api ml infra data -x "*/tests/*"` em 1409 linhas: 0 alta, 0 media, 4 baixa (ver abaixo). Rodei eu, o roadmap dava isso ao Anthony no dia 11 e nao ha nada dele no repo; o relatorio versionado em `docs/security/` continua com ele na Semana 3 |

Fora do checklist: tambem nao existe `.github/` (CI com ruff e pytest, pedido na Semana 1).

## O que rodou hoje

- `pytest api ml`: **181 passaram**, 0 falhas (eram 68 na Semana 1). Em memoria, Python 3.14.
- `python -m api.demo_checkpoint` (script novo, roda em memoria sem subir a API): doador,
  ONG, tres lotes, doacao, doacao repetida e entrega.

| Passo | Resposta |
|---|---|
| `POST /doadores` (CNPJ com mascara) | 201, documento guardado sem mascara |
| `POST /ongs` | 201 |
| `POST /lotes` tomate, vence em 1 dia | 201, `hortifruti`, prioridade **alta** |
| `POST /lotes` iogurte, vence em 6 dias | 201, `laticinios`, prioridade **media** |
| `POST /lotes` arroz, vence em 120 dias | 201, `nao_pereciveis`, prioridade **baixa** |
| `POST /doacoes` | 201, `confirmada`, `tempo_match_s` preenchido |
| `POST /doacoes` repetida | 409 |
| `PUT /lotes/{id}` com `doado` | 200 |

O primeiro `POST /lotes` leva ~1,1 s porque carrega o modelo; os seguintes ficam em ~16 ms.
Na demo, fazer um cadastro de aquecimento antes.

## Bandit (rodado hoje, bandit 1.9.4)

Escopo: `api`, `ml`, `infra` e `data`, sem os testes. Nos testes o Bandit acusa 269 `assert`
(B101), que e ruido do pytest e nao vale tratar.

| Achado | Severidade | Onde | O que fiz |
|---|---|---|---|
| B310, `urlopen` aceita qualquer esquema | media | `api/seed_dev.py` | **Corrigido.** `API_URL` vem de variavel de ambiente e aceitaria `file://`. Agora o script recusa o que nao comeca com `http://` ou `https://` (testado com `file:///etc/passwd`) |
| B311, `random` nao e criptografico | baixa | `data/gerar_dataset_v0.py` | Deixei. E o gerador do dataset simulado, com seed fixa de proposito |
| B101 x3, `assert` | baixa | `data/gerar_dataset_v0.py` | Deixei. Sao conferencias do dataset gerado, script que roda so na mao |

Sobrou 0 alta e 0 media, entao o item do checklist fecha. O Bandit nao olha dependencia nem
imagem: `pip-audit` e Trivy ficam pra Semana 3.

## Ruff (rodado hoje, ruff 0.16.10)

Sem configuracao, o conjunto padrao do 0.16 acusa 44 itens, quase todos estilo. Fixei no
`ruff.toml` o conjunto `E4, E7, E9, F, B, I` com linha de 100 colunas (`E741` fora: o `l` de
"lote" em comprehension nao esconde bug). Achados reais, todos corrigidos:

- `api/routers/lotes.py`: `raise ... from None` dentro do `except` (B904). Mesmo 422.
- `ml/predict.py`: `zip(..., strict=True)` entre as classes do modelo e as probabilidades
  (B905), e imports reordenados.

`ruff check` passa limpo e os 181 testes seguem verdes. **Nao apliquei `ruff format`**: ele
reformataria 30 dos 47 arquivos, entao fica pra decisao do grupo. Os 15 `date.today()` sem fuso
(DTZ011) ficam como pendencia pra olhar antes do deploy.

## O que a demo mostra e o que nao mostra

Mostra: lote, prioridade vinda do modelo e doacao, de ponta a ponta, com erros tratados.
**Nao mostra matching nem tela.** O roteiro do dia 14 pede "lote, prioridade, matching,
doacao". Hoje o passo do meio nao existe, entao a ONG da doacao e escolhida na mao. Nao
vale apresentar isso como matching.

## GitHub (conferido em 06/10)

- **PRs abertos:** #5 (dia 11), #6 (dia 12) e #13 (dia 13). Os tres estao empilhados e
  **nenhum entrou na main**. A main tem o modelo do Charles, mas nao tem
  `POST /lotes` chamando o `predict()`, `POST /doacoes` nem o tratamento de erros. Merge na
  ordem 5, 6, 13.
- **Commits do Charles direto na main:** cinco uploads pela web em 29/09, a regra de
  protecao continua so de combinado (ver checkpoint da Semana 1).
- **`__pycache__` e `.pytest_cache` versionados:** 26 arquivos, continua aberto (issue 4 do
  `docs/fluxo-dia13.md`).
- **Issues do dia 13:** o rascunho das 6 issues continua sem criar no GitHub.

## Cortes e ordem pra Semana 3

Semana 3 e pesada (Docker, pipeline com Bandit e Trivy, auth, KPIs, rate limit). Sugestao:

1. **Matching entra, mas simples.** Filtra ONG por categoria aceita e capacidade, ordena por
   distancia (haversine), `score` e a distancia normalizada. Sem peso aprendido. Charles faz
   a funcao em `ml/`, eu exponho `POST /matching/{lote_id}`. Antes disso, decidir a issue 1
   do dia 13 (`necessidades` contra as 6 categorias), senao o filtro volta vazio.
2. **Streamlit com 3 telas e mais nada:** cadastrar lote, listar ordenado por prioridade,
   confirmar doacao. Fica pra depois: mapa, filtros, dashboard (esse e da Semana 3 mesmo).
3. **STRIDE v2 como tabela** (ativo, ameaca, mitigacao). Sem diagrama bonito.
4. **Bandit no pipeline** (workflow do Anthony): ja roda limpo, so falta plugar com `-ll`.
5. **Auth (dia 15) so depois do matching.** Se o matching escorregar, o dashboard v1 da
   Semana 3 perde o dado que ele precisa.

O que eu cortaria sem dor se apertar: teto de negocio em `quantidade_kg` e `validade` (issue 5)
e o teste contra Postgres de verdade.

## Pendencias minhas

- Merge dos PRs 5, 6 e 13 na ordem, depois rodar `pytest api ml` na main.
- Criar as issues 1 a 6 do `docs/fluxo-dia13.md`.
- Decidir com o grupo a issue 3 (a doacao confere capacidade ou isso fica so no matching).
- Refazer a rodada do dia 13 com matching e tela quando entrarem.
- Lembrar o grupo do pause do Supabase antes da defesa (hoje ativo).

## Nao conferido

- `pip-audit` e `gitleaks` nao estao instalados aqui, entao nenhum rodou.
- O fluxo da demo rodou em memoria; no Supabase so conferi saude e listagem, nao gravei
  nada de novo.
- Nao consegui ver se Anthony e Gustavo tem trabalho em branch fora do GitHub.
