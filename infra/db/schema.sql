-- Schema Postgres (Supabase) pra Rede Alimenta IA.
-- Rodar no SQL editor do Supabase quando a conexao real entrar (dia 10).
-- Por enquanto so a tabela de doadores (dia 4); ONG, lote e doacao entram
-- junto com os CRUDs delas.

create table if not exists doadores (
    id bigint generated always as identity primary key,
    nome text not null,
    tipo_pessoa text not null check (tipo_pessoa in ('fisica', 'juridica')),
    documento text not null unique, -- CPF ou CNPJ, sem mascara
    telefone text,
    email text,
    cidade text not null,
    estado text not null,
    latitude double precision,
    longitude double precision,
    criado_em timestamptz not null default now()
);
