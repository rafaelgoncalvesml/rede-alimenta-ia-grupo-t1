# Testes de seguranca

Arquivo: `api/tests/test_seguranca.py` (roda no `pytest api ml`, em memoria).
Escrito por Anthony; rodado de novo em 14/10 sobre a `main` (Python 3.14, em memoria): 29 passed, 0 failed, 1 warning (aviso do `fastapi.testclient` sobre `httpx`, fora do nosso codigo). Com os demais testes, `pytest api ml` fecha em 487 passados. `ruff check .` limpo. O CI roda o mesmo no Python 3.12.

## O que ataca

| Ataque | Esperado |
|---|---|
| JWT `alg=none`, segredo errado, expirado, sem `exp`, sem `papel`, papel inexistente | 401 |
| Lixo no lugar do token, esquema `Basic` | 401 |
| Payload com `papel` trocado sem reassinar | 401 |
| Strings de SQL injection e XSS em `descricao` | 201, guardadas como texto |
| Injection em filtros (`status`, `doador_id`) | 422 |
| Id nao numerico no caminho (`abc`, `1;DROP`, `' OR 1=1`, `1.5`) | 422 |
| Id `-1` / id enorme | 404 / 404 ou 422 |
| Injection no login | 401 com mensagem generica |
| Senha 129 chars, e-mail 201+ chars | 422 |
| Token, documento e senha no log de auditoria | ausentes |

## O que os testes do Rafael ja cobrem (nao repeti)

RBAC (120 casos, falha se rota nova nao tem linha), limite de login (429), limites de taxa,
corpo > 64 KiB (413).

## Limites

- Injection foi testada em memoria. **Nao rodou contra Postgres real**; a protecao la e o uso de
  parametros no psycopg (revisao de codigo, nao teste).
- Atras do proxy do Render o IP pode ser compartilhado: medir o limite de taxa no ambiente real.
- Token nao e revogavel antes de expirar (30 min). Aceito.
- O `docker-compose.yml` e testado so no job `compose` do CI (sobe a API com `read_only` e confere `/health`); ninguem rodou na propria maquina.