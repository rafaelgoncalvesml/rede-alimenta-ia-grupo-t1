# Resumo SAST (gerado em 13/10/2026 23:33)

Gerado por `infra/security/run_sast.py` a partir dos JSONs desta pasta. Nao editar a mao:
a decisao sobre cada achado (mitigado, aceito, pendente) fica em `vulnerabilidades.md`.
A tabela de Trivy lista so HIGH e CRITICAL; o JSON tem tudo.

## Bandit

5 achado(s) em 32 arquivo(s) analisados.

| Severidade | Qtd |
|---|---|
| CRITICAL | 0 |
| HIGH | 0 |
| MEDIUM | 0 |
| LOW | 5 |

| Sev. | Teste | Onde | O que |
|---|---|---|---|
| LOW | B311 | `data\gerar_dataset_v0.py:159` | Standard pseudo-random generators are not suitable for security/cryptographic purposes. |
| LOW | B101 | `data\gerar_dataset_v0.py:162` | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| LOW | B101 | `data\gerar_dataset_v0.py:163` | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| LOW | B101 | `data\gerar_dataset_v0.py:164` | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| LOW | B404 | `infra\security\run_sast.py:14` | Consider possible security implications associated with the subprocess module. |

## trivy-fs-report.json

Relatorio ainda nao gerado.

## trivy-image-report.json

Relatorio ainda nao gerado.
