"""Armazenamento dos dados: memoria (testes e dev rapido) ou Postgres/Supabase.

Quem escolhe e a variavel STORAGE ("memory" por padrao, "postgres" pra usar o
banco em nuvem). Os dois backends tem a mesma interface, os routers nao sabem
qual esta por baixo. Todas as linhas saem como dict.
"""
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

COLUNAS = {
    "doadores": ["nome", "tipo_pessoa", "documento", "telefone", "email", "cidade",
                 "estado", "latitude", "longitude"],
    "ongs": ["nome", "cnpj", "endereco", "cidade", "estado", "latitude", "longitude",
             "capacidade_kg", "necessidades"],
    "lotes": ["doador_id", "descricao", "tipo", "quantidade_kg", "validade",
              "armazenamento", "status", "prioridade"],
    "doacoes": ["lote_id", "ong_id", "distancia_km", "score", "status", "confirmado_em",
                "tempo_match_s"],
}
# o que o banco preenche sozinho quando a coluna nao vem no insert
PADROES = {"lotes": {"status": "disponivel", "prioridade": None, "tipo": None}}


class MemoryStorage:
    def __init__(self):
        self.reset()

    def reset(self):
        self._linhas = {t: {} for t in COLUNAS}
        self._proximo = {t: 1 for t in COLUNAS}

    def listar(self, tabela, **filtros):
        return [dict(l) for l in self._linhas[tabela].values()
                if all(l.get(k) == v for k, v in filtros.items())]

    def buscar(self, tabela, id_):
        linha = self._linhas[tabela].get(id_)
        return dict(linha) if linha else None

    def existe(self, tabela, **filtros):
        return bool(self.listar(tabela, **filtros))

    def criar(self, tabela, dados):
        linha = {**PADROES.get(tabela, {}), **dados}
        linha["id"] = self._proximo[tabela]
        linha["criado_em"] = datetime.now(timezone.utc)
        self._proximo[tabela] += 1
        self._linhas[tabela][linha["id"]] = linha
        return dict(linha)

    def atualizar(self, tabela, id_, mudancas):
        linha = self._linhas[tabela].get(id_)
        if linha is None:
            return None
        linha.update(mudancas)
        return dict(linha)

    def apagar(self, tabela, id_):
        return self._linhas[tabela].pop(id_, None) is not None

    def confirmar_doacao(self, lote_id, ong_id, distancia_km, score):
        """Reserva o lote e grava a doacao de uma vez. None se o lote nao esta disponivel."""
        lote = self._linhas["lotes"].get(lote_id)
        if lote is None or lote["status"] != "disponivel":
            return None
        lote["status"] = "reservado"
        doacao = self.criar("doacoes", {
            "lote_id": lote_id, "ong_id": ong_id, "distancia_km": distancia_km,
            "score": score, "status": "confirmada",
        })
        agora = doacao["criado_em"]
        return self.atualizar("doacoes", doacao["id"], {
            "confirmado_em": agora,
            "tempo_match_s": (agora - lote["criado_em"]).total_seconds(),
        })


class PostgresStorage:
    def __init__(self, url):
        from psycopg.rows import dict_row
        from psycopg_pool import ConnectionPool

        # o pooler do Supabase derruba conexao ociosa, entao testa antes de usar
        self._pool = ConnectionPool(
            url,
            min_size=1,
            max_size=5,
            kwargs={"row_factory": dict_row, "connect_timeout": 15},
            check=ConnectionPool.check_connection,
            open=False,
        )
        self._pool.open(wait=True, timeout=30)

    def _rodar(self, consulta, params=None):
        with self._pool.connection() as conn:
            return conn.execute(consulta, params).fetchall()

    def _where(self, filtros):
        from psycopg import sql

        if not filtros:
            return sql.SQL(""), []
        partes = [sql.SQL("{} = %s").format(sql.Identifier(k)) for k in filtros]
        return sql.SQL(" WHERE ") + sql.SQL(" AND ").join(partes), list(filtros.values())

    def ping(self):
        self._rodar("select 1")

    def listar(self, tabela, **filtros):
        from psycopg import sql

        where, params = self._where(filtros)
        q = sql.SQL("SELECT * FROM {}").format(sql.Identifier(tabela)) + where
        return self._rodar(q + sql.SQL(" ORDER BY id"), params)

    def buscar(self, tabela, id_):
        linhas = self.listar(tabela, id=id_)
        return linhas[0] if linhas else None

    def existe(self, tabela, **filtros):
        return bool(self.listar(tabela, **filtros))

    def criar(self, tabela, dados):
        from psycopg import sql

        cols = [c for c in dados if c in COLUNAS[tabela]]
        q = sql.SQL("INSERT INTO {} ({}) VALUES ({}) RETURNING *").format(
            sql.Identifier(tabela),
            sql.SQL(", ").join(map(sql.Identifier, cols)),
            sql.SQL(", ").join(sql.Placeholder() * len(cols)),
        )
        return self._rodar(q, [dados[c] for c in cols])[0]

    def atualizar(self, tabela, id_, mudancas):
        from psycopg import sql

        cols = [c for c in mudancas if c in COLUNAS[tabela]]
        sets = sql.SQL(", ").join(sql.SQL("{} = %s").format(sql.Identifier(c)) for c in cols)
        q = sql.SQL("UPDATE {} SET {} WHERE id = %s RETURNING *").format(
            sql.Identifier(tabela), sets
        )
        linhas = self._rodar(q, [mudancas[c] for c in cols] + [id_])
        return linhas[0] if linhas else None

    def apagar(self, tabela, id_):
        from psycopg import sql

        q = sql.SQL("DELETE FROM {} WHERE id = %s RETURNING id").format(sql.Identifier(tabela))
        return bool(self._rodar(q, [id_]))

    def confirmar_doacao(self, lote_id, ong_id, distancia_km, score):
        """Reserva o lote e grava a doacao num unico statement: o UPDATE so pega lote
        disponivel, entao dois pedidos simultaneos nunca confirmam o mesmo lote."""
        linhas = self._rodar(
            """
            WITH reservado AS (
                UPDATE lotes SET status = 'reservado'
                WHERE id = %s AND status = 'disponivel'
                RETURNING criado_em
            )
            INSERT INTO doacoes (lote_id, ong_id, distancia_km, score, status,
                                 confirmado_em, tempo_match_s)
            SELECT %s::bigint, %s::bigint, %s::double precision, %s::double precision,
                   'confirmada', now(),
                   extract(epoch FROM now() - reservado.criado_em)::double precision
            FROM reservado
            RETURNING *
            """,
            [lote_id, lote_id, ong_id, distancia_km, score],
        )
        return linhas[0] if linhas else None


_storage = None


def get_storage():
    global _storage
    if _storage is None:
        # .env so existe na maquina local; no Render as variaveis vem do painel
        load_dotenv(Path(__file__).resolve().parent.parent / ".env")
        if os.getenv("STORAGE", "memory") == "postgres":
            _storage = PostgresStorage(os.environ["SUPABASE_DB_URL"])
        else:
            _storage = MemoryStorage()
    return _storage
