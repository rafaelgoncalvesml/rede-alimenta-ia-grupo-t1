"""Roda Bandit, pip-audit e Trivy de verdade e grava os relatorios em docs/security/.

    python infra/security/run_sast.py              # Bandit + Trivy (repo e imagem)
    python infra/security/run_sast.py --so-resumo  # so refaz o resumo dos JSONs ja gravados

Precisa de `pip install bandit` (esta em api/requirements-dev.txt). Pro Trivy usa o binario
`trivy` se estiver no PATH; senao usa a imagem oficial `aquasec/trivy` pelo Docker, igual ao
Rafael (docs/security/trivy-imagem.md). Nada aqui inventa resultado: o resumo sai dos JSONs que
as ferramentas gravaram. Cole a saida real no grupo.
"""
import argparse
import json
import shutil
import subprocess
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
SAIDA = RAIZ / "docs" / "security"
ORDEM = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "UNKNOWN"]
IMAGEM_LOCAL = "rede-alimenta-api:local"
TRIVY_DOCKER = "aquasec/trivy:0.75.0"  # a versao que o Rafael usou; ajuste se a tag nao existir
REQUIREMENTS = ["api/requirements.txt", "ml/requirements.txt", "infra/db/requirements.txt"]


def rodar(cmd, **kw):
    print("$", " ".join(map(str, cmd)))
    return subprocess.run(cmd, cwd=RAIZ, check=False, **kw)  # nosec B603


def bandit():
    destino = SAIDA / "bandit-report.json"
    destino.unlink(missing_ok=True)
    r = rodar([sys.executable, "-m", "bandit", "-r", "api", "ml", "infra", "data",
               "-x", "api/tests,ml/tests", "-f", "json", "-o", str(destino)])
    # o bandit sai com 1 quando acha algo; se nao gravou o relatorio, a ferramenta falhou
    if not destino.exists():
        sys.exit(f"Bandit nao gerou relatorio (codigo {r.returncode}). Instalou? pip install bandit")


def pip_audit():
    # um requirements por vez, como o Rafael rodou; saida so no terminal
    for req in REQUIREMENTS:
        print(f"\n== pip-audit {req}")
        rodar([sys.executable, "-m", "pip_audit", "-r", req])


def trivy():
    local = shutil.which("trivy") is not None
    docker = shutil.which("docker") is not None
    if not local and not docker:
        print("AVISO: nem trivy nem docker encontrados, pulando o Trivy. Veja https://trivy.dev")
        return
    # com Docker o repo e montado em /repo; com trivy local os caminhos sao relativos a raiz
    pre = "" if local else "/repo/"
    cmd = ["trivy"] if local else ["docker", "run", "--rm", "-v", f"{RAIZ}:/repo",
                                   "-v", "trivy-cache:/root/.cache", TRIVY_DOCKER]
    # o .env real fica de fora do scan: tem a senha do banco
    rodar(cmd + ["fs", pre + ".", "--scanners", "vuln,secret,misconfig",
                 "--skip-files", pre + ".env", "--skip-dirs", pre + ".venv",
                 "--format", "json", "--output", pre + "docs/security/trivy-fs-report.json"])
    if not docker:
        print("AVISO: docker nao encontrado, pulando o Trivy da imagem.")
        return
    tar = SAIDA / "imagem.tar"
    build = rodar(["docker", "build", "-f", "api/Dockerfile", "-t", IMAGEM_LOCAL, "."])
    if build.returncode == 0 and rodar(["docker", "save", IMAGEM_LOCAL, "-o", str(tar)]).returncode == 0:
        rodar(cmd + ["image", "--input", pre + "docs/security/imagem.tar",
                     "--scanners", "vuln,secret,misconfig", "--format", "json",
                     "--output", pre + "docs/security/trivy-image-report.json"])
    tar.unlink(missing_ok=True)  # centenas de MB, nao vai pro Git


def le(nome):
    p = SAIDA / nome
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def tabela_contagem(contagem):
    linhas = ["| Severidade | Qtd |", "|---|---|"]
    linhas += [f"| {s} | {contagem.get(s, 0)} |" for s in ORDEM if contagem.get(s, 0) or s != "UNKNOWN"]
    return linhas


def resumo_bandit(rel):
    achados = rel["results"]
    c = Counter(a["issue_severity"] for a in achados)
    out = ["## Bandit", "", f"{len(achados)} achado(s) em {len(rel['metrics']) - 1} arquivo(s) analisados.", ""]
    out += tabela_contagem(c)
    if achados:
        out += ["", "| Sev. | Teste | Onde | O que |", "|---|---|---|---|"]
        for a in sorted(achados, key=lambda x: ORDEM.index(x["issue_severity"])):
            out.append(f"| {a['issue_severity']} | {a['test_id']} | `{a['filename']}:{a['line_number']}` "
                       f"| {a['issue_text']} |")
    return out


def resumo_trivy(rel, titulo):
    vulns, segredos, configs = [], [], []
    for res in rel.get("Results") or []:
        alvo = res.get("Target", "?")
        vulns += [(alvo, v) for v in res.get("Vulnerabilities") or []]
        segredos += [(alvo, s) for s in res.get("Secrets") or []]
        configs += [(alvo, m) for m in res.get("Misconfigurations") or []]
    out = [f"## {titulo}", "", f"{len(vulns)} vulnerabilidade(s), {len(segredos)} segredo(s), "
           f"{len(configs)} problema(s) de configuracao.", ""]
    out += tabela_contagem(Counter(v["Severity"] for _, v in vulns))
    sem_correcao = sum(1 for _, v in vulns if not v.get("FixedVersion"))
    out += ["", f"Sem correcao publicada: {sem_correcao} de {len(vulns)}.", ""]
    altas = [(a, v) for a, v in vulns if v["Severity"] in ("CRITICAL", "HIGH")]
    if altas:
        out += ["| Sev. | Pacote | Instalada | Corrigida em | ID |", "|---|---|---|---|---|"]
        for _alvo, v in sorted(altas, key=lambda x: ORDEM.index(x[1]["Severity"])):
            out.append(f"| {v['Severity']} | {v['PkgName']} | {v.get('InstalledVersion', '')} "
                       f"| {v.get('FixedVersion') or 'sem correcao'} | {v['VulnerabilityID']} |")
    if segredos:
        out += ["", "**Segredos (rotacionar e tirar do historico):**", ""]
        out += [f"- `{alvo}`: {s.get('Title', s.get('RuleID'))} (linha {s.get('StartLine')})" for alvo, s in segredos]
    if configs:
        out += ["", "| Sev. | Onde | Problema |", "|---|---|---|"]
        out += [f"| {m['Severity']} | `{alvo}` | {m['ID']}: {m['Title']} |" for alvo, m in configs]
    return out


def resumo():
    partes = [f"# Resumo SAST (gerado em {datetime.now():%d/%m/%Y %H:%M})", "",
              "Gerado por `infra/security/run_sast.py` a partir dos JSONs desta pasta. Nao editar a mao:",
              "a decisao sobre cada achado (mitigado, aceito, pendente) fica em `vulnerabilidades.md`.",
              "A tabela de Trivy lista so HIGH e CRITICAL; o JSON tem tudo.", ""]
    for nome, fn in (("bandit-report.json", resumo_bandit),
                     ("trivy-fs-report.json", lambda r: resumo_trivy(r, "Trivy fs (repositorio)")),
                     ("trivy-image-report.json", lambda r: resumo_trivy(r, "Trivy image (imagem da API)"))):
        rel = le(nome)
        partes += (fn(rel) + [""]) if rel else [f"## {nome}", "", "Relatorio ainda nao gerado.", ""]
    (SAIDA / "resumo.md").write_text("\n".join(partes), encoding="utf-8")
    print("Resumo em docs/security/resumo.md")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--so-resumo", action="store_true")
    args = ap.parse_args()
    SAIDA.mkdir(parents=True, exist_ok=True)
    if not args.so_resumo:
        bandit()
        pip_audit()
        trivy()
    resumo()