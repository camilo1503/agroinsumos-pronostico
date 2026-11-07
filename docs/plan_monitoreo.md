# Plan de monitoreo y mantenimiento

## Actualización mensual

La UPRA publica el índice alrededor de tres semanas después de terminar el mes. Al salir un dato nuevo:

1. Descargar el anexo en `data/raw/` y actualizar `ANEXO_UPRA` en `src/config.py`.
2. Revisar la ficha técnica y las notas del conjunto de datos por cambios de canasta.
3. Ejecutar `python -m pytest`.
4. Ejecutar `python -m src.pipeline --actualizar-fuentes`.
5. Revisar `reports/calidad_datos.json`: meses ausentes, diferencia con Datos Abiertos y atípicos.
6. Ejecutar `python -m src.load_supabase`, que publica la corrida y evalúa las alertas.
7. Confirmar los cambios en el repositorio para versionar datos procesados y resultados.

## Control del desempeño

Cada corrida conserva sus pronósticos. La vista `monitoreo_pronostico` los compara con el valor oficial en cuanto se conoce.

| Señal | Regla | Acción |
|---|---|---|
| Degradación | MAE a seis meses de los últimos seis pronósticos mayor que el de validación | Reevaluar candidatos con la nueva información |
| Cobertura | Menos de 70 % de los valores dentro del intervalo de 80 % en 12 verificaciones | Recalibrar intervalos |
| Datos | Mes ausente o diferencia con Datos Abiertos mayor que 0,05 puntos | Detener la publicación y revisar la fuente |
| Metodología | La UPRA o el DANE anuncian cambios de canasta o cobertura | Evaluar el efecto antes de modelar |
| Referencia | Persistencia gana durante 12 meses verificados | Considerar publicarla como pronóstico principal |

## Versionamiento

Cada corrida registra fecha de corte, fecha de ejecución, modelo, parámetros de evaluación, versiones de librerías y huella SHA-256 de los datos en `corrida_modelo` y `reports/resultados.json`. Las dependencias están fijadas en `requirements.txt`.

## Continuidad

- Reevaluar Ridge y las variables externas cuando haya más orígenes de prueba.
- Agregar notificaciones por correo para las alertas.
- Automatizar la actualización mensual con un flujo programado.
