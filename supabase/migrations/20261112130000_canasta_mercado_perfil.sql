-- Funciones para el productor: perfil, canasta de insumos en pesos, comparador regional y mercado internacional.

-- Variables de mercado que explican el costo de importacion (las escribe solo el pipeline).
create table public.mercado_mensual (
  fecha date primary key,
  trm numeric(10,2) check (trm > 0),
  urea_usd numeric(10,2) check (urea_usd > 0),
  dap_usd numeric(10,2) check (dap_usd > 0),
  kcl_usd numeric(10,2) check (kcl_usd > 0),
  tsp_usd numeric(10,2) check (tsp_usd > 0)
);

-- Un perfil por persona: define el departamento con el que se valoran sus compras.
create table public.perfil (
  user_id uuid primary key default auth.uid() references auth.users(id) on delete cascade,
  nombre text check (char_length(nombre) <= 80),
  tipo text not null default 'productor'
    check (tipo in ('productor', 'asociacion', 'almacen', 'asistente', 'otro')),
  departamento text not null default 'Nacional' check (char_length(departamento) between 1 and 60),
  cultivo text check (char_length(cultivo) <= 60),
  area_ha numeric(10,2) check (area_ha >= 0),
  actualizado_en timestamptz not null default now()
);

-- Lista de compra de cada persona, con productos del catalogo SIPSA-I.
create table public.canasta_item (
  id bigint generated always as identity primary key,
  user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
  grupo text not null check (grupo in ('Fertilizantes', 'Fungicidas', 'Herbicidas', 'Insecticidas')),
  producto text not null check (char_length(producto) between 1 and 120),
  presentacion text not null check (char_length(presentacion) between 1 and 60),
  cantidad numeric(10,2) not null check (cantidad > 0),
  creado_en timestamptz not null default now(),
  unique (user_id, grupo, producto, presentacion)
);

-- El reporte de canasta se suma a los existentes.
alter table public.reporte_generado drop constraint reporte_generado_tipo_check;
alter table public.reporte_generado add constraint reporte_generado_tipo_check
  check (tipo in ('proyeccion', 'presupuesto', 'alertas', 'canasta'));

-- Ultimo precio disponible por producto y departamento, dentro de los tres meses mas recientes.
create view public.sipsa_precio_reciente with (security_invoker = true) as
  select distinct on (grupo, producto, presentacion, departamento)
         grupo, producto, presentacion, departamento, fecha, precio, n_registros
  from public.sipsa_precio
  where fecha >= (select max(fecha) from public.sipsa_precio) - interval '3 months'
  order by grupo, producto, presentacion, departamento, fecha desc;

create view public.departamento_lista with (security_invoker = true) as
  select distinct departamento from public.sipsa_precio where departamento <> 'Nacional';

create index sipsa_precio_fecha_idx on public.sipsa_precio (fecha);

alter table public.mercado_mensual enable row level security;
alter table public.perfil enable row level security;
alter table public.canasta_item enable row level security;

create policy lectura_autenticada on public.mercado_mensual for select to authenticated using (true);
create policy propios on public.perfil for all to authenticated
  using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy propios on public.canasta_item for all to authenticated
  using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);

revoke all on public.mercado_mensual, public.perfil, public.canasta_item,
  public.sipsa_precio_reciente, public.departamento_lista from anon, authenticated;
grant select on public.mercado_mensual, public.sipsa_precio_reciente, public.departamento_lista to authenticated;
grant select, insert, update on public.perfil to authenticated;
grant select, insert, update, delete on public.canasta_item to authenticated;
