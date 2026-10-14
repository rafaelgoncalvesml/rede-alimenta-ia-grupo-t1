"""Reset da demo no banco em nuvem (dia 24). Roda da raiz do repo, com SUPABASE_DB_URL no .env.

    python -m infra.db.reset_demo backup             guarda data/seed_demo.json no banco
    python -m infra.db.reset_demo reset              so mostra o que apagaria (nao muda nada)
    python -m infra.db.reset_demo reset --aplicar    apaga e recarrega o seed
    python -m infra.db.reset_demo reset --aplicar --seed-do-banco   usa a copia do banco

O reset apaga doacoes, lotes, doadores, ONGs e todo usuario que nao seja admin, zera os ids
(o primeiro lote volta a ser o 1) e recarrega o seed pelas mesmas regras da API, com a
prioridade vinda do modelo. Os admins ficam. Tudo numa transacao: se algo falha, o banco fica
como estava. Antes de apagar, o que existia vai pra backups/ (fora do git).

Precisa da tabela demo_seed: python infra/db/aplicar_schema.py (seguro repetir).
"""
import argparse
import json
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit

import psycopg
from dotenv import load_dotenv
from psycopg import sql
from psycopg.errors import UndefinedTable
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from api.ia import classificar_lote
from api.models import DoadorCreate, LoteCreate, OngCreate
from api.storage import COLUNAS

RAIZ = Path(__file__).resolve().parents[2]
SEED = RAIZ / "data" / "seed_demo.json"
BACKUPS = RAIZ / "backups"

# filhas antes das tabelas-mae por causa das chaves estrangeiras
APAGAR = ("doacoes", "lotes", "doadores", "ongs")


def montar(seed):
    """Valida o seed pelos modelos da API e classifica os lotes. Nao toca o banco."""
    try:
        doadores = [DoadorCreate(**d).model_dump(mode="json") for d in seed["doadores"]]
        ongs = [OngCreate(**o).model_dump(mode="json") for o in seed["ongs"]]
        nomes = {d["nome"] for d in doadores}
        lotes = []
        for l in seed["lotes"]:
            if l["doador"] not in nomes:
                raise ValueError(f"lote de doador que nao esta no seed: {l['doador']}")
            corpo = {"doador_id": 1, "descricao": l["descricao"], "quantidade_kg": l["quantidade_kg"],
                     "armazenamento": l["armazenamento"],
                     "validade": date.today() + timedelta(days=l["validade_em_dias"])}
            lote = LoteCreate(**corpo).model_dump(mode="json")
            lote.update(classificar_lote(lote))
            lote["doador"] = l["doador"]
            lotes.append(lote)
    except (ValueError, KeyError) as erro:
        sys.exit(f"seed invalido: {erro}")
    return doadores, ongs, lotes


def inserir(conn, tabela, dados):
    cols = [c for c in COLUNAS[tabela] if c in dados]
    q = sql.SQL("insert into {} ({}) values ({}) returning id").format(
        sql.Identifier(tabela),
        sql.SQL(", ").join(map(sql.Identifier, cols)),
        sql.SQL(", ").join(sql.Placeholder() * len(cols)),
    )
    return conn.execute(q, [dados[c] for c in cols]).fetchone()[0]


def contar(conn):
    tabelas = APAGAR + ("usuarios",)
    return {t: conn.execute(sql.SQL("select count(*) from {}").format(sql.Identifier(t))).fetchone()[0]
            for t in tabelas}


def guardar_o_que_existe(conn):
    """Despeja as linhas atuais num JSON local, sem o hash das senhas."""
    consultas = {t: sql.SQL("select * from {} order by id").format(sql.Identifier(t)) for t in APAGAR}
    consultas["usuarios"] = sql.SQL("select id, email, papel, doador_id, ong_id from usuarios order by id")
    cur = conn.cursor(row_factory=dict_row)
    dump = {t: cur.execute(q).fetchall() for t, q in consultas.items()}
    BACKUPS.mkdir(exist_ok=True)
    arquivo = BACKUPS / f"antes-do-reset-{datetime.now():%Y%m%d-%H%M%S}.json"
    arquivo.write_text(json.dumps(dump, default=str, ensure_ascii=False, indent=1), encoding="utf-8")
    return arquivo


def carregar_seed(url, do_banco):
    if not do_banco:
        return json.loads(SEED.read_text(encoding="utf-8"))
    with psycopg.connect(url, connect_timeout=15) as conn:
        linha = conn.execute("select conteudo from demo_seed order by salvo_em desc limit 1").fetchone()
    if linha is None:
        sys.exit("nao ha seed guardado no banco; rode o comando backup antes")
    return linha[0]


def backup(url):
    seed = json.loads(SEED.read_text(encoding="utf-8"))
    montar(seed)  # nao guarda no banco um seed que a API recusaria
    with psycopg.connect(url, connect_timeout=15) as conn:
        conn.execute(
            "insert into demo_seed (versao, conteudo) values (%s, %s) "
            "on conflict (versao) do update set conteudo = excluded.conteudo, salvo_em = now()",
            [seed["versao"], Jsonb(seed)],
        )
    print(f"seed {seed['versao']} guardado no banco ({len(seed['doadores'])} doadores, "
          f"{len(seed['ongs'])} ONGs, {len(seed['lotes'])} lotes)")


def resetar(url, aplicar, do_banco):
    doadores, ongs, lotes = montar(carregar_seed(url, do_banco))
    print(f"banco: {urlsplit(url).hostname}")
    with psycopg.connect(url, connect_timeout=15) as conn:
        antes = contar(conn)
        admins = conn.execute("select count(*) from usuarios where papel = 'admin'").fetchone()[0]
        print("hoje no banco:", antes, f"(dos {antes['usuarios']} usuarios, {admins} sao admin e ficam)")
        print(f"o seed poe de volta: {len(doadores)} doadores, {len(ongs)} ONGs, {len(lotes)} lotes")
        if not aplicar:
            print("\nsimulacao: nada foi apagado. Pra valer, rode de novo com --aplicar.")
            return

        print("\nlinhas anteriores guardadas em", guardar_o_que_existe(conn))
        conn.execute("delete from usuarios where papel <> 'admin'")
        for t in APAGAR:
            conn.execute(sql.SQL("delete from {}").format(sql.Identifier(t)))
            conn.execute(sql.SQL("alter table {} alter column id restart with 1").format(sql.Identifier(t)))

        id_doador = {d["nome"]: inserir(conn, "doadores", d) for d in doadores}
        for o in ongs:
            inserir(conn, "ongs", o)
        for l in lotes:
            inserir(conn, "lotes", {**l, "doador_id": id_doador[l["doador"]]})
        depois = contar(conn)
        sem_prioridade = conn.execute("select count(*) from lotes where prioridade is null").fetchone()[0]

    print("depois:", depois)
    if sem_prioridade:
        print(f"ATENCAO: {sem_prioridade} lote(s) sem prioridade (o modelo falhou; veja o log acima)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("comando", choices=["backup", "reset"])
    ap.add_argument("--aplicar", action="store_true", help="reset: apaga de verdade (sem isto so simula)")
    ap.add_argument("--seed-do-banco", action="store_true", help="reset: usa a copia do banco, nao o arquivo")
    args = ap.parse_args()

    load_dotenv(RAIZ / ".env")
    url = os.getenv("SUPABASE_DB_URL")
    if not url:
        sys.exit("defina SUPABASE_DB_URL (no .env ou no ambiente)")
    try:
        if args.comando == "backup":
            backup(url)
        else:
            resetar(url, args.aplicar, args.seed_do_banco)
    except UndefinedTable:
        sys.exit("falta a tabela demo_seed: rode python infra/db/aplicar_schema.py")
