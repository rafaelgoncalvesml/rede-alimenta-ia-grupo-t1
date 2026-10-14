# Roteiro do pitch (rascunho pro ensaio de 14/10)

Defesa em 15/10. Ainda nao ha tempo oficial da banca. Os blocos abaixo somam 10 min 30 s e servem de
proporcao: cronometrar no ensaio e cortar o que passar. Quem fala em cada bloco e proposta pelos papeis
do README (Gustavo interface, Charles IA, Anthony DevSecOps, Rafael backend, banco e deploy); o grupo
ajusta. Os numeros sao os do repo em 13/10.

## Antes de comecar (Rafael abre a demo)

- Abrir `/health` da URL publica 10 minutos antes: o primeiro pedido acorda o servico (~22 s). O modelo
  agora carrega na subida (`modelo.carregado` no log do Render), entao o `POST /lotes` de aquecimento so
  e preciso se o log nao mostrar essa linha. Medir depois do redeploy.
- Deixar o banco no estado da demo (5 lotes, 3 doadores, 4 ONGs reais) com
  `python -m infra.db.reset_demo reset --aplicar`, que apaga e recarrega `data/seed_demo.json`. Na
  apresentacao, dizer que capacidade e necessidades das ONGs sao simuladas.
- Login de admin ja feito no Swagger (`Authorize`) e aba aberta em `/docs`.

## 1. Problema (Gustavo, 1 min)

Ha comida sendo descartada enquanto ONGs ficam sem. O doador nao sabe quem precisa e a ONG nao sabe
o que vai vencer. Um slide so, sem numero de fonte que o grupo nao tenha conferido.

## 2. Solucao (Gustavo, 1 min 30 s)

O doador cadastra o lote, a IA diz o que e urgente, a doacao e confirmada para uma ONG e o impacto
aparece em KPIs. Mostrar o diagrama de arquitetura (secao Arquitetura do README).

O matching entrou na API em 14/10: `POST /matching/{lote_id}` devolve as ONGs que aceitam a categoria e
o peso do lote, da mais perto pra mais longe. A tela de Matchings usa essa rota e confirma a doacao por
ela; o servidor recalcula distancia e score, o cliente nao manda esses numeros.

## 3. IA (Charles, 2 min)

Um modelo classifica a categoria do alimento e a prioridade de descarte (alta, media, baixa) a partir
de categoria, validade, quantidade e armazenamento.

Numeros do modelo v2 (`models/metrics.json`): Random Forest com F1 macro 0,669 no teste, contra 0,610 da
regra so por dias. Recall da classe "alta" de 0,83, e 2,2% das altas mandadas pro fim da fila.

Limites, ditos antes de a banca perguntar: o dataset e simulado, entao as metricas mostram que o pipeline
funciona e nao a qualidade em dado real. O ganho sobre a regra simples e pequeno: a diferenca de F1 vai de
-0,001 a +0,117 no intervalo de 95% (README). A acuracia de 1,00 do classificador de categoria vem de
descricoes geradas de listas fixas. O aviso de dado simulado tambem sai em todo `/kpis/ia`. O historico
do dashboard (`data/historico_simulado.json`) e todo simulado, com 12 ONGs inventadas; as 4 ONGs da demo
sao reais (CNPJ ativo na Receita), mas capacidade e necessidades delas sao simuladas e elas nao foram
consultadas.

Matching: `ml/matching.py` filtra ONG por categoria e capacidade (a mesma regra que a doacao confere) e
ordena por distancia (haversine); `score` = distancia / 100 km, menor e melhor. Sem peso aprendido: e uma
regra, nao um modelo, e assim deve ser dito. Distancia em linha reta; sem coordenada, centro da cidade.

## 4. DevSecOps (Anthony, 2 min)

No ar hoje: login com JWT de 30 min, papeis admin, doador e ong, senha com argon2, bloqueio apos 5 erros de
login, limite de pedidos (120 por minuto por rota, 30 em `POST /lotes`), erro 500 generico sem stack
trace, log de auditoria sem CPF nem e-mail, imagem Docker sem root, Trivy na imagem (0 critica, 0 em
pacote Python) e Bandit (0 achados em 13/10 sobre `api`, `ml` e `infra`).

Pipeline em `.github/workflows/ci.yml`: ruff, pytest, Bandit, pip-audit, build e Trivy da imagem. Passou
verde no GitHub em 14/10; conferir a aba Actions de novo antes de apresentar. Existem tambem
`docs/stride.md` e `docs/lgpd.md`, os dois como rascunho pra revisao.

Existem 29 testes de ataque (`api/tests/test_seguranca.py`) e um `docker-compose.yml` da API. Falta: deploy automatico (hoje e manual pelo painel do Render), protecao de branch (o plano free nao tem) e revisao juridica da LGPD.

## 5. Banco e deploy (Rafael, 1 min)

Supabase porque as entidades se ligam por chave estrangeira. Render porque o Hugging Face pediu
pagamento pra rodar Docker. Custo zero nos dois. Cold start medido de 22 s no Render free, com banco e
API na mesma regiao (Ohio). Mostrar `/health/db` devolvendo `storage: postgres`.

## 6. Demo ao vivo (Rafael conduz, Gustavo narra, 2 min)

Se houver tela de dashboard, ela entra no lugar do Swagger. Sem tela, o caminho e este:

1. `POST /lotes` com um lote de alface (refrigerado, validade em 2 dias): a resposta traz `prioridade` e
   `tipo` vindos do modelo.
2. `POST /matching/{id}` do lote: o ranking das ONGs reais da demo, com distancia e score.
3. `POST /doacoes` com a primeira do ranking: o lote passa a `reservado`, com distancia e score gravados
   pelo servidor.
4. Repetir a doacao: volta 409, porque o lote ja nao esta disponivel.
5. `PUT /lotes/{id}` com `doado`.
6. `GET /kpis/impacto`: `kg_doados`, `refeicoes_geradas` (com `fator_kg_por_refeicao: 0.5` visivel) e
   `tempo_medio_match_s`. Dizer: "0,5 kg por refeicao e premissa nossa; a unica referencia que achamos e
   dos EUA, 0,544 kg, da Feeding America. Nao e fonte brasileira."

Se algo quebrar, seguir o roteiro e explicar falando, sem mexer em codigo.

## 7. Impacto e fechamento (Gustavo 30 s, Charles 30 s)

O que mudaria com a rede funcionando e o que falta pra chegar la: dados reais de lotes e de ONGs
(capacidade e necessidades informadas por elas), distancia de rota em vez de linha reta e o frontend
publicado. Terminar nos proximos passos, sem frase de efeito.

## Perguntas provaveis

As de arquitetura estao em `docs/arquitetura-perguntas.md`. As de IA e de seguranca ficam com quem fala o
bloco.
