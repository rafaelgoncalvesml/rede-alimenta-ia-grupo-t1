"""Aplica infra/db/schema.sql no Supabase usando SUPABASE_DB_URL do .env.

    python infra/db/aplicar_schema.py

O schema usa "if not exists", entao rodar de novo e seguro.
"""
import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv

raiz = Path(__file__).resolve().parents[2]
load_dotenv(raiz / ".env")

url = os.environ["SUPABASE_DB_URL"]
schema = (Path(__file__).parent / "schema.sql").read_text(encoding="utf-8")

with psycopg.connect(url, connect_timeout=15) as conn:
    conn.execute(schema)
    tabelas = conn.execute(
        "select tablename, rowsecurity from pg_tables where schemaname = 'public' order by 1"
    ).fetchall()

for nome, rls in tabelas:
    print(f"{nome}: RLS {'ligado' if rls else 'DESLIGADO'}")
