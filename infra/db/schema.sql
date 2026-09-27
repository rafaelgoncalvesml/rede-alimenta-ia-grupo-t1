-- Schema Postgres (Supabase) pra Rede Alimenta IA.
-- Rodar no SQL editor do Supabase quando a conexao real entrar (dia 10).
-- Doador (dia 4), ONG e lote (dia 5). Doacao entra junto com o matching.

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

create table if not exists ongs (
    id bigint generated always as identity primary key,
    nome text not null,
    cnpj text not null unique, -- sem mascara
    endereco text not null,
    cidade text not null,
    estado text not null,
    latitude double precision,
    longitude double precision,
    capacidade_kg double precision not null check (capacidade_kg >= 0),
    necessidades text[] not null default '{}',
    criado_em timestamptz not null default now()
);

create table if not exists lotes (
    id bigint generated always as identity primary key,
    doador_id bigint not null references doadores (id),
    descricao text not null,
    tipo text, -- preenchido pela IA
    quantidade_kg double precision not null check (quantidade_kg > 0),
    validade date not null,
    armazenamento text not null check (armazenamento in ('ambiente', 'refrigerado', 'congelado')),
    status text not null default 'disponivel'
        check (status in ('disponivel', 'reservado', 'doado', 'descartado')),
    prioridade text, -- preenchido pela IA
    criado_em timestamptz not null default now()
);
