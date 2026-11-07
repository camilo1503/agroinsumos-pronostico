-- Esquema de la plataforma de pronostico de agroinsumos.
-- Las series y resultados los escribe solo el pipeline (service role).
-- Cada usuario autenticado lee los resultados y administra unicamente sus propios registros.

create table public.indice_mensual (
  fecha date primary key,
  indice_total numeric(10,4) not null check (indice_total > 0),
  fertilizantes numeric(10,4),
  plaguicidas numeric(10,4),
  otros numeric(10,4),
  simples numeric(10,4),
  compuestos numeric(10,4),
  herbicidas numeric(10,4),
  fungicidas numeric(10,4),
  insecticidas numeric(10,4)
);

create table public.corrida_modelo (
  id bigint generated always as identity primary key,
  fecha_corte date not null unique,
  ejecutado_en timestamptz not null,
  modelo_seleccionado text not null,
  nombre_modelo text not null,
  supera_persistencia_validacion boolean not null,
  supera_persistencia_prueba boolean not null,
  cobertura_prueba jsonb not null,
  detalle jsonb not null
);

create table public.metrica_modelo (
  corrida_id bigint not null references public.corrida_modelo(id) on delete cascade,
  modelo text not null,
  bloque text not null check (bloque in ('validacion', 'prueba')),
  horizonte smallint not null check (horizonte between 0 and 6),
  mae numeric(10,4) not null,
  rmse numeric(10,4) not null,
  mase numeric(10,4) not null,
  primary key (corrida_id, modelo, bloque, horizonte)
);

create table public.pronostico (
  corrida_id bigint not null references public.corrida_modelo(id) on delete cascade,
  serie text not null check (serie in ('total', 'fertilizantes', 'plaguicidas')),
  fecha date not null,
  horizonte smallint not null check (horizonte between 1 and 6),
  valor numeric(10,3) not null,
  li80 numeric(10,3) not null,
  ls80 numeric(10,3) not null,
  li95 numeric(10,3) not null,
  ls95 numeric(10,3) not null,
  primary key (corrida_id, serie, horizonte)
);

create table public.backtest_modelo (
  corrida_id bigint not null references public.corrida_modelo(id) on delete cascade,
  modelo text not null,
  bloque text not null check (bloque in ('validacion', 'prueba')),
  origen date not null,
  horizonte smallint not null check (horizonte between 1 and 6),
  fecha date not null,
  real numeric(10,4) not null,
  pred numeric(10,4) not null,
  primary key (corrida_id, modelo, origen, horizonte)
);

create table public.sipsa_precio (
  grupo text not null,
  producto text not null,
  presentacion text not null,
  departamento text not null,
  fecha date not null,
  precio numeric(14,2) not null check (precio > 0),
  n_registros integer not null check (n_registros > 0),
  primary key (grupo, producto, presentacion, departamento, fecha)
);

create table public.sipsa_contraste (
  grupo text not null,
  fecha date not null,
  valor numeric(12,3) not null,
  primary key (grupo, fecha)
);

create table public.presupuesto (
  id bigint generated always as identity primary key,
  user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
  nombre text not null check (char_length(nombre) between 1 and 80),
  fertilizantes numeric(16,2) not null default 0 check (fertilizantes >= 0),
  plaguicidas numeric(16,2) not null default 0 check (plaguicidas >= 0),
  otros numeric(16,2) not null default 0 check (otros >= 0),
  creado_en timestamptz not null default now()
);
create index presupuesto_user_id_idx on public.presupuesto (user_id);

create table public.regla_alerta (
  id bigint generated always as identity primary key,
  user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
  nombre text not null check (char_length(nombre) between 1 and 80),
  serie text not null default 'total' check (serie in ('total', 'fertilizantes', 'plaguicidas')),
  direccion text not null default 'sube' check (direccion in ('sube', 'baja')),
  umbral_pct numeric(6,2) not null check (umbral_pct > 0),
  horizonte smallint not null default 6 check (horizonte between 1 and 6),
  usar_limite_80 boolean not null default false,
  activa boolean not null default true,
  creado_en timestamptz not null default now()
);
create index regla_alerta_user_id_idx on public.regla_alerta (user_id);

create table public.alerta_evento (
  id bigint generated always as identity primary key,
  user_id uuid not null references auth.users(id) on delete cascade,
  regla_id bigint not null references public.regla_alerta(id) on delete cascade,
  corrida_id bigint not null references public.corrida_modelo(id) on delete cascade,
  variacion_pct numeric(8,2) not null,
  mensaje text not null,
  leida boolean not null default false,
  creado_en timestamptz not null default now(),
  unique (regla_id, corrida_id)
);
create index alerta_evento_user_id_idx on public.alerta_evento (user_id, creado_en desc);
create index alerta_evento_corrida_id_idx on public.alerta_evento (corrida_id);

create table public.reporte_generado (
  id bigint generated always as identity primary key,
  user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
  tipo text not null check (tipo in ('proyeccion', 'presupuesto', 'alertas')),
  corrida_id bigint references public.corrida_modelo(id) on delete set null,
  creado_en timestamptz not null default now()
);
create index reporte_generado_user_id_idx on public.reporte_generado (user_id, creado_en desc);
create index reporte_generado_corrida_id_idx on public.reporte_generado (corrida_id);

-- Catalogos para los filtros de precios (security_invoker: respetan el RLS de quien consulta).
create view public.sipsa_catalogo with (security_invoker = true) as
  select distinct grupo, producto, presentacion from public.sipsa_precio;

create view public.sipsa_departamentos with (security_invoker = true) as
  select distinct grupo, producto, presentacion, departamento from public.sipsa_precio;

-- Monitoreo: compara cada pronostico publicado con el valor oficial cuando este se conoce.
create view public.monitoreo_pronostico with (security_invoker = true) as
  select c.fecha_corte, p.serie, p.fecha, p.horizonte, p.valor as pronosticado,
         o.observado,
         round((p.valor - o.observado) / o.observado * 100, 2) as error_pct,
         o.observado between p.li80 and p.ls80 as dentro_80
  from public.pronostico p
  join public.corrida_modelo c on c.id = p.corrida_id
  join lateral (
    select case p.serie when 'total' then i.indice_total
                        when 'fertilizantes' then i.fertilizantes
                        else i.plaguicidas end as observado
    from public.indice_mensual i where i.fecha = p.fecha
  ) o on true;

-- Evalua reglas activas contra una corrida. No se expone a los usuarios por la API.
create function public.evaluar_reglas(p_corrida_id bigint, p_regla_id bigint default null)
returns integer
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_insertadas integer;
begin
  with base as (
    select r.id as regla_id, r.user_id, r.nombre, r.direccion, r.umbral_pct, r.horizonte,
           case when r.usar_limite_80 and r.direccion = 'sube' then p.ls80
                when r.usar_limite_80 then p.li80
                else p.valor end as referencia,
           case r.serie when 'total' then u.indice_total
                        when 'fertilizantes' then u.fertilizantes
                        else u.plaguicidas end as ultimo
    from public.regla_alerta r
    join public.corrida_modelo c on c.id = p_corrida_id
    join public.pronostico p on p.corrida_id = c.id and p.serie = r.serie and p.horizonte = r.horizonte
    join public.indice_mensual u on u.fecha = c.fecha_corte
    where r.activa and (p_regla_id is null or r.id = p_regla_id)
  ), calculo as (
    select *, round((referencia / ultimo - 1) * 100, 2) as variacion from base
  )
  insert into public.alerta_evento (user_id, regla_id, corrida_id, variacion_pct, mensaje)
  select user_id, regla_id, p_corrida_id, variacion,
         format('%s: variación estimada de %s %% a %s meses (umbral %s %%).',
                nombre, variacion, horizonte, umbral_pct)
  from calculo
  where (direccion = 'sube' and variacion >= umbral_pct)
     or (direccion = 'baja' and variacion <= -umbral_pct)
  on conflict (regla_id, corrida_id) do nothing;

  get diagnostics v_insertadas = row_count;
  return v_insertadas;
end;
$$;

create function public.evaluar_regla_nueva()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_corrida bigint;
begin
  select id into v_corrida from public.corrida_modelo order by fecha_corte desc limit 1;
  if v_corrida is not null then
    delete from public.alerta_evento where regla_id = new.id and corrida_id = v_corrida;
    perform public.evaluar_reglas(v_corrida, new.id);
  end if;
  return new;
end;
$$;

create trigger regla_alerta_evaluar
  after insert or update of serie, direccion, umbral_pct, horizonte, usar_limite_80, activa
  on public.regla_alerta
  for each row execute function public.evaluar_regla_nueva();

revoke all on function public.evaluar_reglas(bigint, bigint) from public, anon, authenticated;
revoke all on function public.evaluar_regla_nueva() from public, anon, authenticated;
grant execute on function public.evaluar_reglas(bigint, bigint) to service_role;

-- RLS en todas las tablas. Sin politica para anon: nada se lee sin iniciar sesion.
alter table public.indice_mensual enable row level security;
alter table public.corrida_modelo enable row level security;
alter table public.metrica_modelo enable row level security;
alter table public.pronostico enable row level security;
alter table public.backtest_modelo enable row level security;
alter table public.sipsa_precio enable row level security;
alter table public.sipsa_contraste enable row level security;
alter table public.presupuesto enable row level security;
alter table public.regla_alerta enable row level security;
alter table public.alerta_evento enable row level security;
alter table public.reporte_generado enable row level security;

create policy lectura_autenticada on public.indice_mensual for select to authenticated using (true);
create policy lectura_autenticada on public.corrida_modelo for select to authenticated using (true);
create policy lectura_autenticada on public.metrica_modelo for select to authenticated using (true);
create policy lectura_autenticada on public.pronostico for select to authenticated using (true);
create policy lectura_autenticada on public.backtest_modelo for select to authenticated using (true);
create policy lectura_autenticada on public.sipsa_precio for select to authenticated using (true);
create policy lectura_autenticada on public.sipsa_contraste for select to authenticated using (true);

create policy propios on public.presupuesto for all to authenticated
  using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy propios on public.regla_alerta for all to authenticated
  using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy leer_propios on public.alerta_evento for select to authenticated
  using ((select auth.uid()) = user_id);
create policy marcar_propios on public.alerta_evento for update to authenticated
  using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy leer_propios on public.reporte_generado for select to authenticated
  using ((select auth.uid()) = user_id);
create policy crear_propios on public.reporte_generado for insert to authenticated
  with check ((select auth.uid()) = user_id);

-- Permisos minimos a nivel de columna y tabla, ademas del RLS.
revoke all on all tables in schema public from anon, authenticated;
grant select on public.indice_mensual, public.corrida_modelo, public.metrica_modelo, public.pronostico,
  public.backtest_modelo, public.sipsa_precio, public.sipsa_contraste, public.sipsa_catalogo,
  public.sipsa_departamentos, public.monitoreo_pronostico to authenticated;
grant select, insert, update, delete on public.presupuesto, public.regla_alerta to authenticated;
grant select on public.alerta_evento to authenticated;
grant update (leida) on public.alerta_evento to authenticated;
grant select, insert on public.reporte_generado to authenticated;
