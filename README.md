# Pronóstico de variaciones de precios de agroinsumos colombianos mediante CRISP-ML(Q)

Proyecto de la materia Machine Learning. Pronostica a seis meses el índice nacional de precios de insumos agrícolas de la UPRA, lo compara con modelos de referencia y publica el resultado en una plataforma con inicio de sesión, señal de compra, canasta de insumos en pesos, comparador regional, mercado internacional, proyección, presupuesto, alertas, reportes y monitoreo.

## Problema

Los precios de fertilizantes y plaguicidas cambian de forma difícil de anticipar y eso complica presupuestar una producción agrícola. La pregunta del proyecto es qué desempeño alcanzan modelos estadísticos y de aprendizaje automático al pronosticar el índice nacional a seis meses, frente a referencias sencillas.

El proyecto no predice el precio que pagará cada agricultor ni demuestra relaciones causales.

## Resultado principal

Validación temporal con 40 orígenes (nov. 2021 a feb. 2025) y prueba final con 12 orígenes (mar. 2025 a feb. 2026), con corte de datos en agosto de 2026.

| Modelo | MASE validación | MASE prueba | MAE prueba | RMSE prueba |
|---|---:|---:|---:|---:|
| Persistencia (referencia) | 4,32 | **1,72** | 5,06 | 9,50 |
| Estacional ingenuo (referencia) | 15,68 | 3,53 | 10,71 | 12,43 |
| ETS | 3,55 | 1,84 | 5,46 | 9,20 |
| **SARIMA (seleccionado)** | **3,32** | 1,84 | 5,46 | 9,20 |
| Ridge directo con variables externas | 4,42 | 2,14 | 6,40 | 9,61 |

SARIMA ganó la selección en validación, pero **no superó a persistencia en la prueba final**, y la prueba de Diebold-Mariano a seis meses no muestra diferencia (p = 0,95). El criterio de mejora consistente no se cumple. Por eso la plataforma presenta el pronóstico como señal de apoyo, junto con sus intervalos: los de 80 %, calibrados en validación, cubrieron 91,7 % de los valores de prueba.

## Estructura

```
data/raw/            Anexo UPRA y TRM (SIPSA y Pink Sheet se descargan con el pipeline)
data/processed/      Series limpias y resumen de SIPSA-I
src/                 Ingesta, preparación, modelos, evaluación, pipeline y carga a Supabase
tests/               Pruebas de datos, métricas y fuga de información
reports/             Calidad de datos, métricas, backtest, resultados y figuras
supabase/            Migraciones y configuración de autenticación
web/                 Documentación pública, inicio de sesión y plataforma
docs/                Metodología, diccionario, guía de usuario y plan de monitoreo
```

## Ejecutar

Se necesita Python 3.13.

```bash
pip install -r requirements.txt
python -m pytest
python -m src.pipeline --actualizar-fuentes
```

Para publicar resultados en la base de datos, copie `.env.example` como `.env`, complete las llaves y ejecute:

```bash
python -m src.load_supabase
```

Para ver el sitio localmente:

```bash
python -m http.server 8000 --directory web
```

## Publicar el sitio con ngrok

Con ngrok instalado y autenticado, ejecute `iniciar_sitio.bat`. El sitio queda en <https://debrief-smartly-taco.ngrok-free.dev> mientras la ventana esté abierta. La base de datos y el inicio de sesión están en Supabase y funcionan siempre.

## Documentación

- [Metodología CRISP-ML(Q)](docs/metodologia_crisp_ml.md)
- [Diccionario de datos](docs/diccionario_datos.md)
- [Guía de usuario](docs/guia_usuario.md)
- [Plan de monitoreo y mantenimiento](docs/plan_monitoreo.md)

## Fuentes

- UPRA y Datos Abiertos Colombia: [índice de precios de insumos agrícolas](https://www.datos.gov.co/Agricultura-y-Desarrollo-Rural/-ndice-de-precios-de-insumos-agr-colas/gwbi-fnzs/about_data)
- DANE: [SIPSA-I, series históricas](https://www.dane.gov.co/index.php/estadisticas-por-tema/agropecuario/sistema-de-informacion-de-precios-sipsa/componente-insumos-1/componente-insumos-historicos)
- Superintendencia Financiera: [TRM histórica](https://www.datos.gov.co/Econom-a-y-Finanzas/Tasa-de-Cambio-Representativa-del-Mercado-Historic/mcec-87by)
- Banco Mundial: [Commodity Markets, Pink Sheet](https://www.worldbank.org/en/research/commodity-markets)

Los resultados son estimaciones sujetas a incertidumbre. No son asesoría financiera ni garantía de precios.
