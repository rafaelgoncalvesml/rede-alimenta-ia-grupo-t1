# API em container, contra o banco em nuvem (dia 19)

Testado em 06/10 na maquina do Rafael (Windows, Docker Desktop 29.7). A imagem e o
`.dockerignore` sao meus porque o Dockerfile do Anthony (dia 15) nao chegou ao repo; se o dele
vier, vale juntar os dois em vez de manter dois.

## Como rodar

Da raiz do repo:

```
docker build -t rede-alimenta-api -f api/Dockerfile .
docker run -d --name rede-api -p 8000:8000 \
  -e STORAGE=postgres -e SUPABASE_DB_URL -e JWT_SECRET -e ADMIN_EMAIL -e ADMIN_PASSWORD \
  rede-alimenta-api
```

`-e VAR` sem valor copia a variavel do shell, entao a senha do banco nao aparece no comando nem
no historico. **Sem `STORAGE=postgres` a API sobe em memoria** e perde tudo ao reiniciar, sem
reclamar. Segredos entram so na hora do `run`; nada deles esta na imagem.

## O que a imagem e

| | |
|---|---|
| Base | `python:3.12-slim` (o roadmap diz 3.10, mas o scikit-learn 1.8 e o pandas 3 pedem 3.11 ou mais) |
| Tamanho | 714 MB (pandas, scikit-learn e scipy pesam quase tudo) |
| Usuario | `app`, uid 10001, sem shell. Nao roda como root |
| Conteudo | `api/`, `ml/` e `models/`. Sem `.env`, testes, dados de treino nem docs (conferido com `ls` dentro da imagem) |
| Healthcheck | `GET /health` a cada 30 s |

## O que rodou contra o Supabase de verdade

`API_URL=http://localhost:8780 python -m infra.db.testar_login`: o mesmo teste dos dias 15 e 16,
agora por HTTP contra o container. **28 verificacoes passaram** (login, 401, 403, 429, chaves
estrangeiras, `check` do schema, regras de dono, doacao, e prioridade preenchida pelo modelo).
O script apaga o que cria e confere a contagem de linhas: o banco ficou igual ao de antes.

Medido na mesma rodada:

| | Resultado |
|---|---|
| Container pronto (`/health` 200) | ~5 s, ja criando o admin no Supabase |
| Healthcheck | `healthy` |
| Memoria | 135,6 MiB depois de carregar o modelo e rodar o teste (uma amostra, nao um pico) |
| Latencia de uma consulta ao Supabase | ~0,63 s (5 chamadas: 0,63 a 0,79 s). O servidor e `us-east-2` |
| `/health` sem banco | ~5 ms |
| Reinicio (`docker restart`) | volta em ~5 s e reconecta sozinho |
| Corpo de 70 KB | 413 dentro do container, como fora |
| Logs (108 linhas) | sem traceback, sem JWT, sem `postgresql://`, sem senha |

**O modelo treinado no Python 3.14 carrega e responde no 3.12 do container.** Era um risco
real (o `joblib` guarda pickle), e o teste confirma: o lote cadastrado volta com `prioridade`.

## O que nao foi testado

- **`docker compose up` na maquina de alguem.** O `docker-compose.yml` entrou em 14/10 (so a API) e
  o job `compose` do CI o sobe e confere `/health`. Nesta maquina rodei so a imagem sozinha.
- **Trivy.** Em 06/10 nao tinha rodado. Rodou em 12/10 e o Dockerfile mudou por causa dele (pip
  fora da imagem final, `apt-get upgrade`); relatorio em `docs/security/trivy-imagem.md`.
  Esta pagina descreve a imagem do dia 19, antes dessas duas mudancas; tamanho e medidas
  continuam os mesmos (714 MB, ~140 MiB).
- **Outra maquina.** So testei no Windows. O ponto do "na minha maquina funciona" fica aberto
  ate alguem do grupo repetir.
- **Memoria no pico e no Render.** A medida de 135 MiB e depois do teste, nao sob carga. O free
  tier do Render tem 512 MB, entao deve caber, mas isso e inferencia minha, nao medida (e item
  do Charles, dia 22).

## Detalhes que pegam

- O admin e criado a cada subida em que `ADMIN_EMAIL` e `ADMIN_PASSWORD` existem e o e-mail ainda
  nao esta no banco. Reiniciar o container recria o admin de teste se ele tiver sido apagado.
- A imagem nao tem teste nem `pytest`. Teste de unidade roda fora, no CI.
