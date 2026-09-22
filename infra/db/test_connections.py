"""
Testa a conexao com Supabase (Postgres) e MongoDB Atlas usando as credenciais
do .env. Rodar com: python infra/db/test_connections.py

Nao cria nada em nenhum dos dois bancos, so conecta e roda uma query leve
pra confirmar que a string de conexao esta certa.
"""
import os
import sys
import time

from dotenv import load_dotenv

load_dotenv()


def test_supabase():
    db_url = os.getenv("SUPABASE_DB_URL")
    if not db_url or "[SUA-SENHA]" in db_url:
        print("[Supabase] SUPABASE_DB_URL nao configurada no .env, pulando.")
        return

    import psycopg

    print("[Supabase] Conectando...")
    start = time.time()
    conn = psycopg.connect(db_url, connect_timeout=10)
    elapsed = time.time() - start

    cur = conn.cursor()
    cur.execute("SELECT version();")
    version = cur.fetchone()[0]

    cur.execute(
        "SELECT pg_database_size(current_database());"
    )
    db_size_bytes = cur.fetchone()[0]

    cur.close()
    conn.close()

    print(f"[Supabase] OK em {elapsed:.2f}s")
    print(f"[Supabase] {version}")
    print(f"[Supabase] Tamanho atual do banco: {db_size_bytes / 1024 / 1024:.2f} MB (limite free tier: 500 MB)")


def test_mongo_atlas():
    uri = os.getenv("MONGODB_URI")
    if not uri or "[SENHA]" in uri:
        print("[MongoDB Atlas] MONGODB_URI nao configurada no .env, pulando.")
        return

    from pymongo import MongoClient
    from pymongo.server_api import ServerApi

    print("[MongoDB Atlas] Conectando...")
    start = time.time()
    client = MongoClient(uri, server_api=ServerApi("1"), serverSelectionTimeoutMS=10000)
    client.admin.command("ping")
    elapsed = time.time() - start

    db_names = client.list_database_names()
    stats = client.get_database(db_names[0] if db_names else "test").command("dbstats")

    print(f"[MongoDB Atlas] OK em {elapsed:.2f}s")
    print(f"[MongoDB Atlas] Bancos visiveis: {db_names}")
    print(f"[MongoDB Atlas] Tamanho de dados: {stats.get('dataSize', 0) / 1024 / 1024:.2f} MB (limite free tier: 512 MB)")

    client.close()


if __name__ == "__main__":
    ok = True
    for fn in (test_supabase, test_mongo_atlas):
        try:
            fn()
        except Exception as exc:
            ok = False
            print(f"[ERRO] {fn.__name__}: {exc}")
    sys.exit(0 if ok else 1)
