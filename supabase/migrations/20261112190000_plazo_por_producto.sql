-- Plazo de la recomendacion por producto: 3 meses para alimentos y 6 para insumos.
alter table public.producto_resumen rename column var_6m_pct to var_plazo_pct;
alter table public.producto_resumen add column plazo smallint not null default 6 check (plazo between 1 and 6);
