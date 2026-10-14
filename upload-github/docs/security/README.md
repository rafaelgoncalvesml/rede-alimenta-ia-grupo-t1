# Seguranca no pipeline

Workflow: `.github/workflows/ci.yml`. Roda em todo push e PR. Python 3.12 (o mesmo da imagem).

| Job | O que faz | Quando falha |
|---|---|---|
| `lint-test` | `ruff check .` e `pytest api ml` | erro de lint ou teste |
| `sast-bandit` | Bandit em `api ml infra data` sem testes | achado **medium ou high** (os `low` do `data/gerar_dataset_v0.py` estao aceitos) |
| `pip-audit` | um `requirements.txt` por vez (api, ml, infra/db) | CVE conhecido em dependencia |
| `trivy` | `fs` (vuln, secret, misconfig) e imagem da API, via `aquasec/trivy:0.75.0` | HIGH/CRITICAL **com correcao publicada** |
| `compose` | `docker compose config` valida o arquivo | compose invalido |

`--ignore-unfixed` no Trivy e uma decisao: os 44 HIGH da Debian 13 ainda nao tem correcao
(`trivy-imagem.md`). Sem a flag o pipeline nunca ficaria verde. Reavaliar quando a Debian
publicar as correcoes. Decisao final: Anthony e o grupo.

Relatorios JSON do Bandit e do Trivy ficam como artefato de cada execucao do CI.

Deploy: `.github/workflows/deploy.yml` so roda depois que o CI passa na `main` e chama o deploy
hook do Render (secrets `RENDER_DEPLOY_HOOK_API`, opcional `RENDER_DEPLOY_HOOK_APP`). O
`autoDeployTrigger` do Render fica `off`, entao nada sobe sem o CI.

## Rodar local

```
python infra/security/run_sast.py          # Bandit + pip-audit + Trivy, gera docs/security/resumo.md
python infra/security/run_sast.py --so-resumo
```

Precisa de `pip install bandit pip-audit` e Docker (o Trivy roda pela imagem oficial).

## Outros arquivos

- `vulnerabilidades.md`: achados e decisoes
- `testes.md`: o que os testes de ataque cobrem e o que nao
- `trivy-imagem.md`: rodada do Rafael em 12/10
- `../stride.md`, `../lgpd.md`