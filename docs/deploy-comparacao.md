# Render vs Hugging Face Spaces - teste de deploy

Testado em setembro/2026 com o FastAPI hello world de `infra/deploy-test/`
(nao e a API final, so pra comparar as duas plataformas antes da trava do
dia 4 em `docs/decisoes.md`).

## Render (free tier)

Deploy via Blueprint (`render.yaml` na raiz do repo), conectando o GitHub
direto pelo dashboard.

- Precisou instalar o GitHub App do Render (OAuth), autorizando so o
  repositorio do projeto - depois disso o Render leu o `render.yaml`
  sozinho e ja sugeriu criar o web service certo, sem configurar nada manual
- Build: 42,5s (pip install + start)
- Request morna: 0,3-0,8s
- Cold start medido de verdade: **21,65s** na primeira requisicao depois de
  ~32min sem trafego (o Render avisa no dashboard que pode chegar a 50s+,
  mas no teste ficou bem abaixo disso)
- Sem custo, sem cartao pedido em nenhum momento

## Hugging Face Spaces (free tier)

Nao deu pra completar o teste. Na tela de criar Space (`New Space`), os
SDKs **Gradio** e **Docker** aparecem marcados como "Paid" - so o SDK
**Static** e gratuito, e Static so serve arquivo estatico, nao roda um
processo Python/FastAPI.

Conferido em Settings > Billing da conta: nao tem verificacao de telefone
nem nenhum caminho gratuito pra liberar isso - as unicas opcoes sao
`Add Credits` (pede cartao) ou assinar o plano PRO. Ou seja, o free tier do
HF Spaces mudou e nao suporta mais rodar uma API custom (FastAPI, Flask,
etc via Docker) sem pagar - diferente do que era antes.

## Leitura rapida

Pro nosso caso, isso praticamente decide a questao: o Render aceita o
FastAPI de graca e sem fricao (só autorizar o repo), o HF Spaces free tier
bloqueia exatamente o cenario que a gente precisa (rodar a API). Cold start
existe no Render free (~22s apos idle, medido) mas e aceitavel pra MVP/demo -
o normal seria manter isso em mente na hora de apresentar o projeto (dar um
"ping" na API antes da demonstracao).

## Como testar de novo

1. `infra/deploy-test/` tem o FastAPI hello world, o `Dockerfile` (pro HF,
   se algum dia liberar) e o `README.md` com o front-matter que o HF espera
2. `render.yaml` na raiz do repo configura o Blueprint do Render
   (`rootDir: infra/deploy-test`)
3. Pra reproduzir o deploy no Render: dashboard.render.com > New > Blueprint
   > conectar o repo (GitHub App) > Deploy Blueprint
4. Pra medir cold start: esperar uns 15-20min sem bater na URL, depois
   `curl -w "%{time_total}s\n" -o /dev/null -s <url>/health`
