-- Schema Postgres (Supabase) pra Rede Alimenta IA.
-- Aplicar com: python infra/db/aplicar_schema.py (ou colar no SQL editor do Supabase).
-- Pode rodar de novo sem estragar nada.

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

-- Uma linha por match confirmado. tempo_match_s = confirmado_em menos lotes.criado_em,
-- gravado na confirmacao pra o KPI de tempo medio de match ser um avg(). Doacao nao se
-- edita nem se apaga: o lote volta a ficar disponivel e a doacao vira 'cancelada'.
create table if not exists doacoes (
    id bigint generated always as identity primary key,
    lote_id bigint not null references lotes (id),
    ong_id bigint not null references ongs (id),
    distancia_km double precision check (distancia_km >= 0),
    score double precision check (score >= 0),
    status text not null default 'confirmada' check (status in ('confirmada', 'cancelada')),
    criado_em timestamptz not null default now(),
    confirmado_em timestamptz not null,
    tempo_match_s double precision not null check (tempo_match_s >= 0)
);

-- no maximo uma doacao confirmada por lote, mesmo com dois pedidos ao mesmo tempo
create unique index if not exists doacoes_uma_confirmada_por_lote
    on doacoes (lote_id) where status = 'confirmada';

-- Quem entra na API. Senha so como hash (argon2). doador e ong apontam pra entidade que o
-- usuario representa; o check garante que cada papel tem a ligacao certa.
create table if not exists usuarios (
    id bigint generated always as identity primary key,
    email text not null unique check (email = lower(email)),
    senha_hash text not null,
    papel text not null check (papel in ('admin', 'doador', 'ong')),
    doador_id bigint references doadores (id),
    ong_id bigint references ongs (id),
    criado_em timestamptz not null default now(),
    check (
        (papel = 'admin' and doador_id is null and ong_id is null)
        or (papel = 'doador' and doador_id is not null and ong_id is null)
        or (papel = 'ong' and ong_id is not null and doador_id is null)
    )
);

-- Copia do seed da demo (data/seed_demo.json), guardada pelo infra/db/reset_demo.py. Serve pra
-- recarregar a demo de uma maquina que nao tem o arquivo. Uma linha por versao do seed.
create table if not exists demo_seed (
    versao text primary key,
    conteudo jsonb not null,
    salvo_em timestamptz not null default now()
);

-- O Supabase expoe tabelas do schema public numa API REST propria (PostgREST).
-- Com RLS ligado e sem policy, essa API nao le nem escreve nada. A nossa API
-- conecta como o dono das tabelas (postgres), que ignora o RLS.
alter table doadores enable row level security;
alter table ongs enable row level security;
alter table lotes enable row level security;
alter table doacoes enable row level security;
alter table usuarios enable row level security;
alter table demo_seed enable row level security;
