-- La canasta admite alimentos de la canasta familiar, ademas de insumos.
alter table public.canasta_item drop constraint canasta_item_grupo_check;
alter table public.canasta_item add constraint canasta_item_grupo_check check (char_length(grupo) between 1 and 60);
