"""Gera app/dados/seguranca.json, que o bloco de seguranca do dashboard le.

    python infra/gerar_seguranca.py

Roda de verdade o Bandit, o pip-audit nas quatro listas de dependencias, o ruff e o pytest, e
pergunta ao GitHub (via `gh`, se estiver instalado) como terminou a ultima execucao do CI na main.
O que o Trivy achou nao roda aqui: vem do CI e de docs/security/vulnerabilidades.md.
"""
import json
import re
import subprocess  # nosec B404 - so roda ferramentas fixas desta lista, nada vem de entrada externa
import sys
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SAIDA = RAIZ / "app" / "dados" / "seguranca.json"
LISTAS = ["api/requirements.txt", "ml/requirements.txt", "app/requirements.txt", "infra/db/requirements.txt"]

# Corrigido ao longo do projeto, com a fonte de cada numero (docs/security/vulnerabilidades.md e
# docs/security/trivy-imagem.md). "achados" e a contagem de CVEs ou de itens do relatorio.
MITIGADAS = [
    {"item": "starlette 0.38.6 (via fastapi): atualizado pra fastapi 0.142.2", "achados": 7, "origem": "pip-audit"},
    {"item": "pymongo: atualizado pra 4.18.2", "achados": 4, "origem": "pip-audit"},
    {"item": "python-dotenv: atualizado pra 1.2.3", "achados": 1, "origem": "pip-audit"},
    {"item": "pip 25.0.1 da imagem base: atualizado no build", "achados": 6, "origem": "Trivy"},
    {"item": "urllib3, msgpack e setuptools embutidos no pip: pip removido da imagem final", "achados": 5, "origem": "Trivy"},
    {"item": "liblzma5 da imagem: apt upgrade no build", "achados": 2, "origem": "Trivy"},
    {"item": "urlopen aceitava file:// em api/seed_dev.py", "achados": 1, "origem": "Bandit B310"},
    {"item": "infra/deploy-test rodava como root: usuario sem privilegio", "achados": 1, "origem": "Trivy (DS-0002)"},
]

# HIGH da base Debian que ainda nao tem correcao; ficam fora do gate por causa do --ignore-unfixed
ACEITOS = [
    {"cve": "CVE-2026-76642, 78408, 78409, 78410", "pacote": "util-linux", "motivo": "a API nao monta sistema de arquivos nem usa nsenter"},
    {"cve": "CVE-2025-69720", "pacote": "ncurses", "motivo": "nao ha terminal interativo"},
    {"cve": "CVE-2026-16742", "pacote": "systemd (libsystemd0, libudev1)", "motivo": "nao usa systemd-homed"},
    {"cve": "CVE-2026-54369", "pacote": "libacl1", "motivo": "sem uso direto"},
    {"cve": "CVE-2026-9538", "pacote": "perl-base", "motivo": "sem Archive-Tar"},
]


def roda(*comando, **kw):
    return subprocess.run(comando, cwd=RAIZ, capture_output=True, text=True, **kw)  # nosec B603


def bandit():
    saida = roda(sys.executable, "-m", "bandit", "-r", "api", "ml", "infra", "app", "-x", "api/tests,ml/tests,app/tests", "-f", "json", "-q")
    total = json.loads(saida.stdout)["metrics"]["_totals"]
    return {
        "escopo": "api, ml, infra e app, sem os testes (o mesmo comando do CI)",
        "alta": int(total["SEVERITY.HIGH"]),
        "media": int(total["SEVERITY.MEDIUM"]),
        "baixa": int(total["SEVERITY.LOW"]),
    }


def pip_audit():
    resultado = []
    for lista in LISTAS:
        saida = roda(sys.executable, "-m", "pip_audit", "-r", lista, "-f", "json")
        dados = json.loads(saida.stdout)
        achados = sum(len(dep.get("vulns", [])) for dep in dados["dependencies"])
        resultado.append({"arquivo": lista, "vulnerabilidades": achados})
    return resultado


def ruff():
    return "passou" if roda(sys.executable, "-m", "ruff", "check", ".").returncode == 0 else "falhou"


def pytest():
    saida = roda(sys.executable, "-m", "pytest", "api", "ml", "app", "-q", "-p", "no:cacheprovider")
    texto = saida.stdout.strip().splitlines()[-1] if saida.stdout.strip() else ""
    def conta(palavra):
        achou = re.search(rf"(\d+) {palavra}", texto)
        return int(achou.group(1)) if achou else 0

    return {"passaram": conta("passed"), "falharam": conta("failed")}


def ci_da_main():
    """Jobs da ultima execucao do CI na main, ou None se o gh nao estiver disponivel."""
    try:
        lista = roda("gh", "run", "list", "--workflow", "CI", "--branch", "main", "--limit", "1",
                     "--json", "databaseId,conclusion,headSha,url,createdAt")
        execucao = json.loads(lista.stdout)[0]
        jobs = json.loads(roda("gh", "run", "view", str(execucao["databaseId"]), "--json", "jobs").stdout)["jobs"]
    except (OSError, ValueError, IndexError):
        return None
    return {
        "url": execucao["url"],
        "commit": execucao["headSha"][:7],
        "em": execucao["createdAt"],
        "gates": [
            {"nome": job["name"], "status": "passou" if job["conclusion"] == "success" else "falhou"}
            for job in jobs
        ],
    }


def main():
    medido = {"bandit": bandit(), "pip_audit": pip_audit(), "ruff": ruff(), "testes": pytest()}
    ci = ci_da_main()
    dados = {
        "gerado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "gerado_por": "infra/gerar_seguranca.py",
        "medido_agora": medido,
        "ci": ci,
        "gates": ci["gates"] if ci else [],
        "mitigadas": MITIGADAS,
        "aceitos": ACEITOS,
        "avisos": [
            "Bandit, pip-audit, ruff e pytest foram executados na hora de gerar este arquivo.",
            "O Trivy so roda no CI: o resultado vem da ultima execucao na main, nao daqui.",
            "Os HIGH da Debian sem correcao ficam fora do gate (--ignore-unfixed); a decisao esta em docs/security/.",
        ],
    }
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    SAIDA.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"gravado em {SAIDA.relative_to(RAIZ)}")
    print(json.dumps(medido, ensure_ascii=False))


if __name__ == "__main__":
    main()
