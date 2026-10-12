# Trivy na imagem da API e no repo (12/10)

Rodado pelo Rafael com o Trivy 0.75.0, pela imagem oficial `aquasec/trivy` (nada instalado na
maquina), sobre a imagem `rede-alimenta-api` e sobre o repo. Base `python:3.12-slim` (Debian
13.7). Resultado real, sem edicao. Falta o mesmo no pipeline (dia 18, Anthony).

```
docker save rede-alimenta-api -o imagem.tar
docker run --rm -v <pasta>:/work -v trivy-cache:/root/.cache aquasec/trivy:latest \
  image --input /work/imagem.tar --scanners vuln,secret,misconfig
docker run --rm -v <repo>:/repo -v trivy-cache:/root/.cache aquasec/trivy:latest \
  fs /repo --skip-dirs /repo/.venv --skip-dirs /repo/.git --skip-files /repo/.env \
  --scanners vuln,secret,misconfig --severity HIGH,CRITICAL
```

O `.env` real ficou fora do `fs` de proposito (tem a senha do banco).

## Imagem, depois das correcoes

| Alvo | Achados | Secrets | Misconfig |
|---|---|---|---|
| Pacotes do sistema (Debian 13.7) | 164 (1 UNKNOWN, 61 baixa, 58 media, 44 alta, **0 critica**) | 0 | 0 |
| Pacotes Python | **0** | 0 | 0 |
| `api/Dockerfile` | n/a | 0 | **0** |

**Nenhum dos 164 tem correcao publicada.** Os 44 HIGH sao 8 CVEs repetidos em varios pacotes
do mesmo codigo-fonte, todos `affected` (a Debian ainda nao corrigiu):

| CVE | Pacotes | Assunto |
|---|---|---|
| CVE-2026-76642, 78408, 78409, 78410 | util-linux (bsdutils, libblkid1, liblastlog2-2, libmount1, libsmartcols1, libuuid1, login, mount, util-linux) | `mount` e `nsenter` |
| CVE-2025-69720 | ncurses (4 pacotes) | buffer overflow |
| CVE-2026-16742 | libsystemd0, libudev1 | systemd-homed |
| CVE-2026-54369 | libacl1 | symlink em funcoes da libacl |
| CVE-2026-9538 | perl-base | Archive-Tar, DoS (correcao adiada pela Debian) |

Pelo que a API faz, quase nada disso e alcancavel: ela nao monta sistema de arquivos, nao
usa `nsenter`, systemd-homed, Archive-Tar nem tem shell de login (usuario `app`, uid 10001,
`nologin`). **Isso e leitura minha do codigo, nao teste de exploracao.** O que da pra fazer
hoje e esperar a Debian publicar e reconstruir; a imagem puxa a base de novo a cada build.

## O que mudou por causa do Trivy

| Achado | Correcao |
|---|---|
| `pip 25.0.1` da imagem base: 6 CVEs (5 medias, 1 baixa) | `pip` atualizado pra 26.2 no build |
| `pip` 26.2 traz `urllib3`, `msgpack` e `setuptools` embutidos: 3 HIGH, 2 MEDIUM | `pip uninstall` no fim do mesmo `RUN`. A API nao instala nada em producao, e some tambem o instalador de pacotes da imagem |
| `liblzma5 5.8.1-1+deb13u1` (2 UNKNOWN, com correcao na Debian) | `apt-get upgrade` no build (`deb13u2`) |
| `infra/deploy-test/Dockerfile` (hello world do dia 2): DS-0002, roda como root, HIGH | `USER app` sem root. Testado: sobe com uid 10001 |

Primeira rodada (antes de qualquer mudanca): 166 achados no sistema e 6 no Python, 0 critica.
Dos 44 HIGH daquele dia nenhum tinha correcao.

## Gate sugerido pro pipeline

`trivy image --severity HIGH,CRITICAL --ignore-unfixed --exit-code 1`: **passa hoje (exit 0)**.
Sem `--ignore-unfixed` o pipeline ficaria vermelho por causa dos 44 HIGH sem correcao, e a
unica saida seria trocar de base, o que nao resolve (Debian 13 inteira esta nesse estado). A
decisao de usar `--ignore-unfixed` e do Anthony e do grupo; aqui so registro o que o numero
significa.

## Nao coberto

- Rodei so na minha maquina e so na imagem local; o Trivy nao rodou em CI.
- O Trivy usa a base de vulnerabilidades do dia (12/10); o numero muda com o tempo.
- Nao e teste de intrusao. Ele diz o que tem de conhecido nos pacotes, nao se a API e explorada.
