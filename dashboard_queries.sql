-- DASHBOARD OPERACIONAL — CHOQUE MENTAL 3.1

-- 1. Próximos posts agendados
select id, pilar, tema_base, subtema, indice_uso, engajamento_score, created_at
from posts
where status = 'agendado'
order by indice_uso asc, engajamento_score desc, id asc
limit 50;

-- 2. Posts com erro
select id, pilar, subtema, erro, updated_at
from posts
where status = 'erro'
order by updated_at desc
limit 50;

-- 3. Top hooks por score
select id, pilar, hook_gerado, engajamento_score, data_publicacao, video_public_url
from posts
where status = 'postado'
order by engajamento_score desc
limit 50;

-- 4. Performance por pilar
select
  pilar,
  count(*) as posts,
  round(avg(engajamento_score), 2) as media_score,
  max(engajamento_score) as melhor_score
from posts
where status = 'postado'
group by pilar
order by media_score desc nulls last;

-- 5. Performance por pilar nos últimos 7 dias
select * from performance_por_pilar_7d;

-- 6. Fila RSS viva por pilar
select * from rss_fila_viva;

-- 7. Últimas notícias RSS capturadas
select pilar, source_name, titulo, link, published_at, usado
from rss_items
order by created_at desc
limit 100;

-- 8. Posts prontos para reciclagem
select id, pilar, hook_gerado, data_publicacao, indice_uso
from posts
where status = 'postado'
  and data_publicacao <= now() - interval '60 days'
order by data_publicacao asc;

-- 9. Métricas recentes
select
  p.id,
  p.pilar,
  p.hook_gerado,
  m.curtidas,
  m.comentarios,
  m.compartilhamentos,
  m.salvamentos,
  m.alcance,
  m.score,
  m.coletado_em
from metricas m
join posts p on p.id = m.post_id
order by m.coletado_em desc
limit 100;

-- 10. Logs operacionais
select etapa, status, detalhe, post_id, created_at
from execucoes
order by created_at desc
limit 200;
