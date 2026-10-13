# Limite de pedidos e de tamanho de corpo (dia 18)

Codigo em `api/limites.py`, testes em `api/tests/test_limites.py`.

## Limite de pedidos por minuto

Janela deslizante de 60 s, por **rota e por quem chama**: o usuario do token, ou o IP quando o
token falta ou e invalido. O IP vem de `auditoria.ip_do_cliente`: o `client.host`, ou o
`CF-Connecting-IP` quando `CONFIAR_CF_CONNECTING_IP=1` (so no Render, `docs/deploy-render.md`). Estourou: `429` com `Retry-After` (segundos) e uma linha
`limite.estourado` no log de auditoria.

| Onde | Limite | Por que esse |
|---|---|---|
| Todas as rotas (geral) | 120 / min | Painel que atualiza sozinho gasta alguns pedidos por minuto; 120 sobra pra uso humano e barra script |
| `POST /lotes` | 30 / min | Roda o modelo de IA em cada pedido |
| `POST /doacoes` | 30 / min | Escrita que reserva lote |
| `POST /usuarios` | 10 / min | Cria conta |
| `POST /auth/login` | 5 erros / 15 min por e-mail | Ja existia (dia 15), e mais apertado que o geral |
| **`POST /matching/{lote_id}`** | **20 / min (pronto, nao ligado)** | A rota ainda nao existe |

`/health`, `/health/db` e `/auth/login` ficam fora do limite **geral**: o Render chama o health
o tempo todo, e o login ja tem o limite proprio.

**Matching:** o roadmap pede o limite no `/matching`, mas o endpoint nao chegou ao repo. Deixei
`limites.MATCHING = 20` e a dependencia pronta (`test_limita_pronto_pra_rota_do_matching` prova
que funciona). Quando a rota entrar, e uma linha:

```python
@router.post("/{lote_id}", dependencies=[Depends(limites.limita("matching", limites.MATCHING))])
```

## Tamanho do corpo

`413` com `{"detail": "Corpo do pedido grande demais", "limite_bytes": ...}` quando o corpo passa
de **64 KiB** (`MAX_BODY_BYTES`, em bytes). O maior pedido legitimo da API tem alguns KB: a
`descricao` do lote tem no maximo 500 caracteres. O middleware confere o `Content-Length` antes
de ler e tambem conta os bytes que chegam, pra pegar corpo em pedacos (chunked) sem o cabecalho.
Roda por dentro da auditoria, entao o 413 sai no log, e antes de olhar o token.

Mudou uma coisa visivel: texto enorme (acima de 64 KiB) agora volta **413** em vez de 422. Texto
grande que cabe no corpo (ex.: `descricao` de 5.000 caracteres) continua 422 pelo Pydantic.

## Um defeito que o teste achou

A primeira versao devolvia **400** (nao 413) para corpo em pedacos. O FastAPI embrulha qualquer
`Exception` levantada ao ler o corpo num 400 "error parsing the body". A excecao do limite agora
herda de `BaseException` pra atravessar isso. Conferido tambem com o `uvicorn` de verdade
(`Transfer-Encoding: chunked` com 70 KB: 413).

## Limites desse limite

- **Estado na memoria do processo.** Serve pro Render com um worker. Com varios workers cada um
  conta o seu; o certo seria Redis, fora do escopo.
- **Atras do proxy do Render o IP e o do proxy** (o `X-Forwarded-For` nao e confiavel, ver
  `api/auditoria.py`). Quem nao tem token valido divide um contador so. Por isso o login nao
  entra no limite geral e tem o proprio. Quem tem token e contado por usuario, que e o que
  importa.
- **Pedido barrado ainda custa um pouco**: o 429 sai depois de decodificar o token. O 413 sai antes.
- Os numeros sao chute informado, sem medicao de uso real. Ajustar pelas constantes de
  `api/limites.py`.
