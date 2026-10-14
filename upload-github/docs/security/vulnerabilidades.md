# Vulnerabilidades: achados e decisoes

Dados vem dos relatorios reais do repo (`docs/checkpoint-semana2.md`,
`docs/security/trivy-imagem.md`) e da rodada local de 13/10 (`infra/security/run_sast.py`,
JSONs em `docs/security/`). **Trivy no CI: [preencher apos o 1o run verde, com data e link].**
Nada aqui foi inventado; o que nao rodou esta marcado.

## Bandit (rodado `run_sast.py`, 32 arquivos, sem testes)

0 critica, 0 alta, 0 media, **5 baixa**. Relatorio: `bandit-report.json`, resumo em `resumo.md`.

| Achado | Severidade | Onde | Decisao |
|---|---|---|---|
| B311 `random` | baixa | `data/gerar_dataset_v0.py:159` | aceito: dataset simulado, seed fixa |
| B101 x3 `assert` | baixa | `data/gerar_dataset_v0.py:162-164` | aceito: script manual, confere o dataset |
| B404 import de `subprocess` | baixa | `infra/security/run_sast.py:14` | aceito: ferramenta de desenvolvimento, chama so Bandit, pip-audit, Trivy e Docker com lista de argumentos fixa, sem shell; nao roda na API |

Historico: no dia 14 o Rafael achou um B310 media em `api/seed_dev.py` (`urlopen` aceitava
`file://`); corrigido, e o `# nosec B310` ali vale so pra esse teste.
Gate do CI: `--severity-level medium` (as 5 baixas nao quebram o pipeline).

## pip-audit (2.10.1)

| Arquivo | Antes | Correcao |
|---|---|---|
| `api/requirements.txt` | 7 CVEs no starlette 0.38.6 | `fastapi==0.142.2` |
| `infra/db/requirements.txt` | 4 no pymongo, 1 no python-dotenv | `pymongo==4.18.2`, `python-dotenv==1.2.3` |
| `ml/requirements.txt` | 0 | n/a |

Rodada de 13/10 (`run_sast.py`): `No known vulnerabilities found` nos tres arquivos
(`api`, `ml`, `infra/db`).

## Trivy 0.75.0 

Imagem: 0 CRITICAL, 44 HIGH em 8 CVEs de pacotes Debian, **nenhum com correcao**. Python: 0.
Dockerfile: 0 misconfig. Corrigidos: pip desatualizado, liblzma (apt upgrade), usuario root do
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
- Trivy no CI: ainda nao rodou la. Preencher a tabela acima com o resultado do primeiro run.