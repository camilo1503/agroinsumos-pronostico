-- Pronostico del precio de cada producto y recomendacion de compra (los escribe solo el pipeline).

create table public.producto_pronostico (
  corrida_id bigint not null references public.corrida_modelo(id) on delete cascade,
  grupo text not null,
  producto text not null,
  presentacion text not null,
  horizonte smallint not null check (horizonte between 1 and 6),
  fecha date not null,
  valor numeric(14,2) not null check (valor > 0),
  li80 numeric(14,2) not null,
  ls80 numeric(14,2) not null,
  primary key (corrida_id, grupo, producto, presentacion, horizonte)
);

create table public.producto_resumen (
  corrida_id bigint not null references public.corrida_modelo(id) on delete cascade,
  grupo text not null,
  producto text not null,
  presentacion text not null,
  fecha_precio date not null,
  precio numeric(14,2) not null check (precio > 0),
  minimo_24m numeric(14,2) not null,
  maximo_24m numeric(14,2) not null,
  posicion_24m numeric(5,3) not null check (posicion_24m between 0 and 1),
  var_12m_pct numeric(8,2),
  var_6m_pct numeric(8,2) not null,
  modelo text not null check (modelo in ('naive', 'ets')),
  mae_modelo numeric(14,2) not null,
  mae_persistencia numeric(14,2) not null,
  recomendacion text not null check (recomendacion in ('comprar', 'esperar', 'normal')),
  motivo text not null,
  kg_nutriente numeric(10,3),
  precio_kg_nutriente numeric(14,2),
  primary key (corrida_id, grupo, producto, presentacion)
);

alter table public.producto_pronostico enable row level security;
alter table public.producto_resumen enable row level security;
create policy lectura_autenticada on public.producto_pronostico for select to authenticated using (true);
create policy lectura_autenticada on public.producto_resumen for select to authenticated using (true);
revoke all on public.producto_pronostico, public.producto_resumen from anon, authenticated;
grant select on public.producto_pronostico, public.producto_resumen to authenticated;
