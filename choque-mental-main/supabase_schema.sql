-- CHOQUE MENTAL 3.0 — Schema Supabase
-- Cole no SQL Editor do Supabase.
-- Recomendado: usar SERVICE_ROLE_KEY apenas no GitHub Secrets, nunca no front-end.

create extension if not exists pgcrypto;

-- =========================
-- ENUMS
-- =========================
do $$ begin
  create type post_status as enum ('agendado', 'processando', 'postado', 'erro', 'pausado');
exception when duplicate_object then null;
end $$;

-- =========================
-- POSTS — CÉREBRO EDITORIAL
-- =========================
create table if not exists public.posts (
  id bigserial primary key,
  tema_base text not null,
  pilar text not null check (pilar in (
    'Psicologia Sombria',
    'Sono e Energia',
    'Relacionamentos',
    'Dinheiro e Consumo',
    'Cérebro e Percepção',
    'Fatos Absurdos',
    'Produtividade'
  )),
  subtema text not null,
  status post_status not null default 'agendado',
  indice_uso integer not null default 0,
  engajamento_score numeric(12,4) not null default 0,
  data_publicacao timestamptz,
  link_artigo text,
  titulo_artigo text,
  resumo_artigo text,
  hook_gerado text,
  midia_texto text,
  legenda text,
  image_prompt text,
  cta_bio text,
  instagram_media_id text,
  video_storage_path text,
  video_public_url text,
  erro text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_posts_status_uso_id
on public.posts (status, indice_uso asc, id asc);

create index if not exists idx_posts_score
on public.posts (engajamento_score desc);

create index if not exists idx_posts_pilar
on public.posts (pilar);

-- =========================
-- MÉTRICAS — APRENDIZADO
-- =========================
create table if not exists public.metricas (
  id bigserial primary key,
  post_id bigint not null references public.posts(id) on delete cascade,
  instagram_media_id text,
  curtidas integer not null default 0,
  comentarios integer not null default 0,
  compartilhamentos integer not null default 0,
  salvamentos integer not null default 0,
  alcance integer not null default 0,
  impressoes integer not null default 0,
  score numeric(12,4) not null default 0,
  coletado_em timestamptz not null default now()
);

create index if not exists idx_metricas_post_id on public.metricas(post_id);
create index if not exists idx_metricas_score on public.metricas(score desc);

-- =========================
-- EXECUÇÕES — LOG OPERACIONAL
-- =========================
create table if not exists public.execucoes (
  id uuid primary key default gen_random_uuid(),
  post_id bigint references public.posts(id) on delete set null,
  etapa text not null,
  status text not null,
  detalhe text,
  created_at timestamptz not null default now()
);

-- =========================
-- CIÊNCIA CACHE — EVITA BUSCAS REPETIDAS
-- =========================
create table if not exists public.ciencia_cache (
  id bigserial primary key,
  query text not null unique,
  openalex_id text,
  titulo text,
  resumo text,
  link text,
  raw jsonb,
  created_at timestamptz not null default now()
);

-- =========================
-- UPDATED_AT AUTOMÁTICO
-- =========================
create or replace function public.set_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

drop trigger if exists trg_posts_updated_at on public.posts;
create trigger trg_posts_updated_at
before update on public.posts
for each row execute function public.set_updated_at();

-- =========================
-- SELEÇÃO INTELIGENTE
-- =========================
create or replace view public.proximo_post as
select *
from public.posts
where status = 'agendado'
order by indice_uso asc, engajamento_score desc, id asc
limit 1;

-- =========================
-- FUNÇÃO DE RECICLAGEM 60 DIAS
-- =========================
create or replace function public.reciclar_posts_antigos()
returns integer as $$
declare
  total integer;
begin
  update public.posts
  set status = 'agendado',
      indice_uso = indice_uso + 1,
      hook_gerado = null,
      midia_texto = null,
      legenda = null,
      image_prompt = null,
      cta_bio = null,
      instagram_media_id = null,
      video_storage_path = null,
      video_public_url = null,
      erro = null
  where status = 'postado'
    and data_publicacao <= now() - interval '60 days';

  get diagnostics total = row_count;
  return total;
end;
$$ language plpgsql;

-- =========================
-- SEMENTE INICIAL — 7 PILARES
-- Edite, apague ou expanda livremente.
-- =========================
insert into public.posts (tema_base, pilar, subtema, status) values
('Manipulação social', 'Psicologia Sombria', 'viés de autoridade', 'agendado'),
('Manipulação social', 'Psicologia Sombria', 'obediência e pressão de grupo', 'agendado'),
('Sono moderno', 'Sono e Energia', 'privação de sono e tomada de decisão', 'agendado'),
('Sono moderno', 'Sono e Energia', 'luz azul e ritmo circadiano', 'agendado'),
('Desejo e vínculo', 'Relacionamentos', 'apego ansioso e rejeição', 'agendado'),
('Desejo e vínculo', 'Relacionamentos', 'sinais de status e atração', 'agendado'),
('Consumo invisível', 'Dinheiro e Consumo', 'preço psicológico', 'agendado'),
('Consumo invisível', 'Dinheiro e Consumo', 'escassez artificial', 'agendado'),
('Realidade cerebral', 'Cérebro e Percepção', 'memória falsa', 'agendado'),
('Realidade cerebral', 'Cérebro e Percepção', 'atenção seletiva', 'agendado'),
('Ciência perturbadora', 'Fatos Absurdos', 'experimentos históricos estranhos', 'agendado'),
('Ciência perturbadora', 'Fatos Absurdos', 'comportamentos coletivos extremos', 'agendado'),
('Controle pessoal', 'Produtividade', 'fricção ambiental e hábito', 'agendado'),
('Controle pessoal', 'Produtividade', 'fadiga decisória', 'agendado')
on conflict do nothing;

-- =========================
-- STORAGE
-- No painel Supabase: Storage > Create bucket > choque-videos > Public.
-- Ou rode via dashboard/API. SQL direto para bucket pode variar por permissão.
-- =========================

-- ============================================================
-- EXTENSÃO 3.1 — BANCO CIENTÍFICO INFINITO VIA RSS AO VIVO
-- ============================================================

create table if not exists public.rss_sources (
  id bigserial primary key,
  nome text not null,
  url text not null unique,
  pilar_padrao text check (pilar_padrao is null or pilar_padrao in (
    'Psicologia Sombria',
    'Sono e Energia',
    'Relacionamentos',
    'Dinheiro e Consumo',
    'Cérebro e Percepção',
    'Fatos Absurdos',
    'Produtividade'
  )),
  descricao text,
  prioridade integer not null default 100,
  ativo boolean not null default true,
  created_at timestamptz not null default now()
);

create index if not exists idx_rss_sources_ativo_prioridade
on public.rss_sources (ativo, prioridade asc);

create table if not exists public.rss_items (
  id bigserial primary key,
  source_id bigint references public.rss_sources(id) on delete set null,
  source_name text,
  pilar text not null check (pilar in (
    'Psicologia Sombria',
    'Sono e Energia',
    'Relacionamentos',
    'Dinheiro e Consumo',
    'Cérebro e Percepção',
    'Fatos Absurdos',
    'Produtividade'
  )),
  titulo text not null,
  resumo text,
  link text not null unique,
  published_at timestamptz,
  usado boolean not null default false,
  post_id bigint references public.posts(id) on delete set null,
  raw jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_rss_items_pilar_usado_data
on public.rss_items (pilar, usado, published_at desc nulls last, created_at desc);

create index if not exists idx_rss_items_usado
on public.rss_items (usado);

-- Fontes RSS. Algumas fontes podem mudar URLs com o tempo; se alguma falhar, o bot ignora e segue.
insert into public.rss_sources (nome, url, pilar_padrao, descricao, prioridade) values
('ScienceDaily — Neuroscience', 'https://www.sciencedaily.com/rss/mind_brain/neuroscience.xml', 'Cérebro e Percepção', 'Neurociência prática, cognição, cérebro e percepção.', 10),
('ScienceDaily — Psychology', 'https://www.sciencedaily.com/rss/mind_brain/psychology.xml', 'Psicologia Sombria', 'Psicologia comportamental, vieses, tomada de decisão.', 11),
('ScienceDaily — Sleep Disorders', 'https://www.sciencedaily.com/rss/health_medicine/sleep_disorders.xml', 'Sono e Energia', 'Sono, insônia, descanso e energia biológica.', 12),
('EurekAlert — News Releases', 'https://www.eurekalert.org/rss.xml', null, 'Novas descobertas globais; pilar classificado por palavras-chave.', 20),
('PsyPost — Psychology News', 'https://www.psypost.org/feed/', null, 'Comportamento humano, psicologia social, vieses e manipulação.', 21),
('Psychology Today — Latest', 'https://www.psychologytoday.com/us/rss', null, 'Comportamento humano e psicologia aplicada.', 22)
on conflict (url) do update set
  nome = excluded.nome,
  pilar_padrao = excluded.pilar_padrao,
  descricao = excluded.descricao,
  prioridade = excluded.prioridade,
  ativo = true;

-- ============================================================
-- EXTENSÃO 3.2 — GOOGLE SHEETS COMO BANCO AUXILIAR FREE
-- ============================================================

create table if not exists public.sheets_import_log (
  id bigserial primary key,
  chave text not null unique,
  post_id bigint references public.posts(id) on delete set null,
  raw jsonb,
  imported_at timestamptz not null default now()
);

create index if not exists idx_sheets_import_chave on public.sheets_import_log(chave);

-- ============================================================
-- CONSULTAS OPERACIONAIS RÁPIDAS
-- ============================================================

create or replace view public.rss_fila_viva as
select
  pilar,
  count(*) filter (where usado = false) as disponiveis,
  max(published_at) as noticia_mais_recente
from public.rss_items
group by pilar
order by disponiveis desc;

create or replace view public.performance_por_pilar_7d as
select
  p.pilar,
  count(*) as posts,
  round(avg(p.engajamento_score), 2) as media_score,
  max(p.engajamento_score) as melhor_score
from public.posts p
where p.status = 'postado'
  and p.data_publicacao >= now() - interval '7 days'
group by p.pilar
order by media_score desc nulls last;
