# Perguntas de arquitetura pra defesa

Respostas curtas, cada uma com o numero ou o arquivo que a sustenta. Quem responde na banca e
quem escreveu a parte, mas todos precisam saber o resumo.

## Por que FastAPI?

O enunciado pede FastAPI e Swagger. Alem de cumprir isso, a validacao do corpo vem dos modelos
Pydantic (`api/models.py`) e o Swagger sai pronto em `/docs`, sem escrever documentacao a parte.
Os 392 testes da API (na `main` de 13/10) rodam sem subir servidor (`TestClient`, sempre em memoria).
No plano free roda um processo so, sem fila nem worker.

## Por que Supabase (Postgres) e nao MongoDB Atlas?

Os dois free tiers sobram pro volume (500 MB contra 512 MB). O que decidiu foi o modelo de dados:
doador, ONG, lote e doacao se ligam por chave estrangeira, e o banco recusa lote de doador que
nao existe ou doacao de lote apagado. Em Mongo isso virava codigo nosso. Esta em
`docs/db-comparacao.md` e `docs/decisoes.md`.
O Supabase free pausa o projeto depois de 1 semana sem uso e nao tem backup automatico. O
`reset_demo.py` guarda o estado antes de apagar.

## Por que o RLS esta ligado e sem policy?

A API conecta como dono das tabelas, entao o RLS nao a atrapalha. Sem policy, a API REST publica
do Supabase nao le nada, e so a nossa API acessa os dados. Assim a chave publica do Supabase nao
da acesso aos dados. Esta nos comentarios de `infra/db/schema.sql`.

## Por que Render e nao Hugging Face Spaces?

Testamos os dois com um hello world (`docs/deploy-comparacao.md`). No Hugging Face, os SDKs Gradio e
Docker aparecem como pagos; so o Static e gratis, e ele nao roda FastAPI. O Render aceitou o
Blueprint (`render.yaml`) sem cartao. Custo: cold start de ~22 s depois de 15 min parado e o
primeiro `POST /lotes` de ~10 s, porque carregava o modelo (medido em 12/10). Desde 13/10 a `main`
carrega o modelo na subida, mas isso nao foi medido em producao. Antes de apresentar, abrir
`/health` e fazer um lote de aquecimento.

## Por que o deploy e manual?

`autoDeployTrigger: "off"` no `render.yaml`: publicar e uma acao manual no painel. Na primeira
subida o Render nao pediu `SUPABASE_DB_URL`, `ADMIN_EMAIL` e `ADMIN_PASSWORD` e o servico ficou
no ar sem elas (o `/health` deu 200 e o login deu 500), por isso conferimos `/health/db` e o
login depois de cada deploy. O CI roda os testes e a seguranca, mas nao publica.

## Por que o modelo vai dentro da imagem?

O `models/prioridade_v2.joblib` e versionado e copiado pro container. Simplifica: sem servidor de
modelos nem download no boot. Custo: trocar o modelo exige novo build e deploy. Em 06/10 testamos
que o modelo (ainda o v1) treinado no Python 3.14 carrega no 3.12 do container
(`docs/container.md`), porque o `joblib` e pickle e isso podia quebrar. O v2 ainda nao foi
testado dentro da imagem: rodar `docker build` e um `POST /lotes` antes de redeployar.

## O que acontece se o modelo falhar?

O lote e cadastrado mesmo assim, com `prioridade` e `tipo` nulos, e o erro vai pro log. O doador
nao perde o cadastro. Entrada que o modelo recusa (categoria invalida) devolve 422 e nao cadastra.

## Como a API se protege?

Login com JWT de 30 min, tres papeis, senha com argon2, 5 erros de login em 15 min bloqueiam com
429, limite de pedidos por rota e por usuario ou IP, corpo maximo de 64 KB, erro 500 sem stack
trace e log de auditoria sem dado pessoal (`docs/auth.md`, `docs/limites.md`). O container roda
sem root e sem shell. Nao existe cadastro aberto: so o admin cria usuario.

## O que o Trivy e o Bandit acharam?

Bandit: 0 achados em `api`, `ml` e `infra` (rodado em 13/10 na `main`, sem os testes). Trivy
na imagem: 0 critica, 0 em pacote Python, 164 em pacotes do Debian, nenhum com correcao
publicada (`docs/security/trivy-imagem.md`). O que mudou por causa do Trivy: `pip`
atualizado e removido da imagem final, `apt-get upgrade`, `USER app` no Dockerfile de teste.
A leitura de que os 44 HIGH nao sao alcancaveis pela API e nossa, nao teste de exploracao.

## Onde esta o pipeline de CI/CD?

`.github/workflows/ci.yml`, em push na `main` e em pull request: ruff e pytest, Bandit, pip-audit,
build da imagem, Trivy (`--severity HIGH,CRITICAL --ignore-unfixed`, derruba o job) e uma subida
do container conferindo `/health`. Passou nos tres jobs no GitHub em 14/10, depois de dois ajustes
nossos (o `pytest` precisou de `python -m` e a action do Trivy de uma tag valida). O deploy
continua manual: o CI testa e escaneia, mas nao publica.

## E o docker-compose?

Existe, so pra API (`docker-compose.yml`). O servico do Streamlit esta comentado ate o frontend
existir. O compose sobe a API com `read_only`, sem capabilities e sem privilegios novos; o job
`compose` do CI confere que ela responde em `/health` desse jeito, mas ninguem rodou na propria
maquina. Nao ha servico local de banco porque o banco e o Supabase.

## Como o sistema trata dado pessoal (LGPD)?

Guarda CPF/CNPJ, e-mail e telefone de doadores. O log de auditoria nao grava corpo nem
querystring, a API devolve erro sem eco do valor recebido, e o backup do reset sai sem o hash de
senha. O mapeamento esta em `docs/lgpd.md` (dados, terceiros, base legal proposta, direitos do titular,
lacunas). E rascunho sem revisao juridica: falar em "mapeamento", nao em "conformidade". A lacuna
mais clara e que doador com doacao registrada nao pode ser apagado pela API.

## O matching e automatico?

Na API publica, nao. `POST /doacoes` recebe `lote_id` e `ong_id`, e quem chama escolhe a ONG. A API
confere capacidade, categoria que a ONG aceita e se o lote esta disponivel, e registra
`tempo_match_s`. A funcao `matching()` em `ml/matching.py` ja existe e esta testada (filtra por
categoria e capacidade, ordena por distancia haversine, `docs/matching.md`), mas a rota
`POST /matching/{lote_id}` nao esta ligada. Ajustar esta resposta conforme a decisao do grupo.

## O que significa "refeicoes geradas"?

`kg_doados / 0,5`. O 0,5 kg por refeicao e premissa do grupo, sem fonte, e aparece em toda
resposta de `/kpis/impacto` como `fator_kg_por_refeicao`. So conta lote entregue (`doado`), nao
reservado.

## O que os dados reais teriam de diferente?

Os dados sao simulados. As metricas provam que o pipeline de treino e predicao funciona, nao que o
modelo acerta em doacao real. O proximo passo seria coletar lotes de doadores reais e retreinar.
