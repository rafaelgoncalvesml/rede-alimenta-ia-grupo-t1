# Vulnerabilidades: achados e decisoes

Dados vem dos relatorios reais do repo (`docs/checkpoint-semana2.md`,
`docs/security/trivy-imagem.md`), de uma rodada local de Anthony em 13/10 e do CI do GitHub em 14/10.
O que nao rodou esta marcado.

## Bandit

No CI (`bandit -r api ml infra`, sem os testes): 0 achados em qualquer severidade. O CI falha com
qualquer achado, e o relatorio sobe como artefato de cada execucao.

Rodada local de Anthony em 13/10, que incluiu `data/`: 0 critica, 0 alta, 0 media, 5 baixa, todas
em `data/gerar_dataset_v0.py`. O CI nao escaneia `data/`, entao elas nao derrubam o pipeline.

| Achado | Severidade | Onde | Decisao |
|---|---|---|---|
| B311 `random` | baixa | `data/gerar_dataset_v0.py:159` | aceito: dataset simulado, seed fixa |
| B101 x3 `assert` | baixa | `data/gerar_dataset_v0.py:162-164` | aceito: script manual, confere o dataset |

Historico: no dia 14 o Rafael achou um B310 media em `api/seed_dev.py` (`urlopen` aceitava
`file://`); corrigido, e o `# nosec B310` ali vale so pra esse teste.

## pip-audit (2.10.1)

| Arquivo | Antes | Correcao |
|---|---|---|
| `api/requirements.txt` | 7 CVEs no starlette 0.38.6 | `fastapi==0.142.2` |
| `infra/db/requirements.txt` | 4 no pymongo, 1 no python-dotenv | `pymongo==4.18.2`, `python-dotenv==1.2.3` |
| `ml/requirements.txt` | 0 | n/a |

Rodada de 13/10 e de 14/10: `No known vulnerabilities found` nos tres arquivos (`api`, `ml`,
`infra/db`). O CI audita os tres a cada execucao.

## Trivy

Rodada de Rafael em 12/10 (Trivy 0.75.0, sem filtro): imagem com 0 CRITICAL e 44 HIGH em 8 CVEs de pacotes Debian, **nenhum com correcao**. Python: 0. Dockerfile: 0 misconfig.

No CI (14/10, run 38506939946 na `main`, action `aquasecurity/trivy-action@v0.36.0` com `--ignore-unfixed` e HIGH/CRITICAL): imagem Debian 13.7 com 0 vulnerabilidade e pacotes Python com 0, Dockerfile sem achado de configuracao. O job passou. Corrigidos: pip desatualizado, liblzma (apt upgrade), usuario root do
`infra/deploy-test`.

| CVE | Pacote | Decisao |
|---|---|---|
| CVE-2026-76642, 78408, 78409, 78410 | util-linux | aceito: API nao monta FS nem usa nsenter (leitura de codigo, nao exploracao) |
| CVE-2025-69720 | ncurses | aceito: sem terminal interativo |
| CVE-2026-16742 | systemd (libsystemd0, libudev1) | aceito: sem systemd-homed |
| CVE-2026-54369 | libacl1 | aceito: sem uso direto |
| CVE-2026-9538 | perl-base | aceito: sem Archive-Tar |

Revisar a cada build: quando a Debian corrigir, o `--ignore-unfixed` passa a barrar sozinho.

## Pendencias abertas

- Identificadores antigos do `.env.example` no historico do Git: decidir se vale reescrever o
  historico ou so rotacionar a credencial. [GRUPO/Rafael]
- Protecao de branch na `main`: indisponivel em repo privado de conta free (`docs/stride.md`, S5).
- Os HIGH sem correcao do Debian seguem fora do gate por causa do `--ignore-unfixed`: reavaliar quando a Debian publicar as correcoes.