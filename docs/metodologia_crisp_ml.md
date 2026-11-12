# Metodología CRISP-ML(Q)

## Fase 1. Comprensión del negocio y de los datos

**Usuario y decisión.** Agricultores, asistentes técnicos y organizaciones productivas que necesitan estimar cuánto reservar para insumos en el próximo semestre.

**Variable objetivo.** Índice nacional total de precios de insumos agrícolas de la UPRA (enero de 2021 = 100), con horizonte de uno a seis meses.

**Criterio de éxito.** Mejorar de manera consistente a la persistencia en evaluación temporal. No se fijó una precisión anticipada.

**Riesgos.**

| Riesgo | Tratamiento |
|---|---|
| Serie corta (93 meses) | Modelos parsimoniosos y regularización |
| Cambio de canasta en 2024 | Revisión del salto mensual antes de modelar |
| Choques internacionales | Intervalos calibrados con errores históricos, incluido 2021-2022 |
| Fuga de información | Evaluación por origen y pruebas automáticas |
| Confundir índice con precio | Advertencias en la plataforma y contraste con SIPSA-I |

## Fase 2. Preparación de datos

El reporte completo está en [`reports/calidad_datos.json`](../reports/calidad_datos.json).

- 93 observaciones de diciembre de 2018 a agosto de 2026, sin meses ausentes ni faltantes en el índice total.
- El anexo coincide con Datos Abiertos: la diferencia máxima es de 0,005 puntos, atribuible al redondeo.
- Los ceros del anexo representan ausencia de dato y se convirtieron en faltantes. Otros insumos inicia en enero de 2021, clorpirifos termina en diciembre de 2023 y fipronil en agosto de 2024.
- La ampliación de canasta de enero de 2024 coincide con una variación de -1,63 % (z robusto -1,02) y la exclusión de fipronil en septiembre de 2024 con +0,22 % (z robusto 0,06). Ninguna aparece como atípica, así que no se aplicó empalme. Esto solo evalúa el índice total y no descarta efectos menores de composición.
- Los meses atípicos (2021-2023 y abril-mayo de 2026) se conservan porque corresponden a movimientos reales del mercado.
- SIPSA-I se resumió con la mediana mensual. Para contrastar, se encadenó la mediana de las variaciones de series comparables (mismo artículo, casa comercial, presentación y departamento). Su variación a 12 meses tiene correlación de 0,87 a 0,98 con los subíndices UPRA.

## Fase 3. Modelado

Todos los modelos reciben únicamente datos hasta el mes de origen.

| Modelo | Tipo | Especificación |
|---|---|---|
| Persistencia | Referencia | Repite el último valor |
| Estacional ingenuo | Referencia | Repite el valor del mismo mes del año anterior |
| ETS | Estadístico | Sobre logaritmo; AICc elige entre sin tendencia, tendencia aditiva o amortiguada |
| SARIMA | Estadístico | Sobre logaritmo con d = 1, p y q de 0 a 2 y término estacional opcional, elegidos por AICc en cada origen |
| Ridge directo | Aprendizaje automático | Un modelo por horizonte para el cambio logarítmico; rezagos del índice, variaciones de TRM, urea y DAP, y estacionalidad; alfa elegido con validación temporal interna |

## Fase 4. Evaluación

**Diseño.** Validación progresiva con ventana creciente y al menos 36 meses de entrenamiento: 40 orígenes de validación (nov. 2021 a feb. 2025) y 12 de prueba (mar. 2025 a feb. 2026). La regla de selección se fijó antes de consultar la prueba: menor MASE en validación entre los tres candidatos, y persistencia si ninguno la supera.

El MASE escala el error con el error absoluto medio de la persistencia a un mes dentro del entrenamiento. Por eso puede ser mayor que 1 en horizontes largos aunque el modelo sea útil. La comparación relevante es contra la persistencia evaluada a igual horizonte.

| Modelo | MASE val. | MAE val. | RMSE val. | MASE prueba | MAE prueba | RMSE prueba |
|---|---:|---:|---:|---:|---:|---:|
| Persistencia | 4,321 | 12,781 | 18,841 | 1,715 | 5,063 | 9,498 |
| Estacional ingenuo | 15,677 | 48,827 | 58,057 | 3,531 | 10,706 | 12,426 |
| ETS | 3,545 | 10,948 | 20,744 | 1,837 | 5,458 | 9,195 |
| SARIMA | 3,324 | 10,297 | 18,907 | 1,837 | 5,456 | 9,195 |
| Ridge directo | 4,420 | 14,118 | 21,079 | 2,138 | 6,402 | 9,610 |

**Selección.** SARIMA.

**Lectura.**

- SARIMA redujo el MASE frente a persistencia en validación, y sus pronósticos fueron mejores en 80,8 % de los casos de ese bloque. En prueba solo lo fue en 31,9 %.
- En prueba, persistencia obtuvo mejor MAE y MASE. SARIMA y ETS tuvieron un RMSE apenas menor.
- Diebold-Mariano a seis meses con corrección de muestra pequeña: p = 0,76 en validación y p = 0,95 en prueba. No hay evidencia de una diferencia.
- Ridge con variables externas no mejoró a persistencia en ningún bloque. La TRM y los precios internacionales no aportaron mejora fuera de muestra con esta especificación.
- El bloque de prueba tiene 12 orígenes y un periodo de relativa calma seguido por el alza de abril y mayo de 2026. Un periodo así favorece a la persistencia, y la muestra es demasiado corta para generalizar.

**Conclusión.** El criterio de éxito no se cumple: ningún modelo mejora de manera consistente a persistencia. El prototipo sí aporta una forma reproducible de medirlo y una comunicación explícita de la incertidumbre. Los modelos no se reajustaron después de ver la prueba para no invalidarla.

**Incertidumbre.** Los intervalos son conformales por horizonte: usan el cuantil del error logarítmico absoluto. Calibrados solo con validación, cubrieron en prueba 91,7 % (nominal 80 %) y 100 % (nominal 95 %). Son conservadores porque validación incluye el choque de 2021-2022. Los de la plataforma se calibran con validación y prueba.

Las figuras están en [`reports/figures`](../reports/figures).

### Pronóstico por producto

Además del índice, se pronostica hasta seis meses adelante el precio mediano nacional de cada producto con al menos 48 meses continuos y dato reciente (`src/productos.py`): los insumos de SIPSA-I y 64 alimentos de la canasta familiar tomados de los precios mayoristas de SIPSA (`src/alimentos.py`), elegidos por ser de consumo frecuente en los hogares. Los precios de alimentos son mayoristas, de plazas y centrales de abastos; el precio al consumidor es mayor. Para cada producto se comparan persistencia y suavizamiento exponencial (ETS) en 18 orígenes de validación temporal; se publica ETS solo si su MAE es menor, y en caso contrario la estimación central es el último precio. El intervalo de 80 % sale del cuantil del error logarítmico por horizonte en esos mismos orígenes, por lo que no hay un bloque de prueba independiente por producto.

El plazo de la recomendación es de 3 meses para alimentos y 6 para insumos. Los alimentos frescos cambian de precio muy rápido: a 6 meses el rango de 80 % tiene un ancho mediano de 50 % del precio, y a 3 meses de 36 %, lo que permite dar señales más útiles. En insumos el rango a 6 meses es de 8 %. En cada producto el modelo se elige por su error dentro de su plazo.

La recomendación es una regla: "comprar" si todo el rango al plazo queda por encima del precio de hoy, o si el precio está en el tercio más bajo de los últimos 24 meses y no se espera que baje; "esperar" si todo el rango queda por debajo, o si está en el tercio más alto y la estimación central baja al menos 2 %; "precio normal" en los demás casos. En fertilizantes sólidos con grado declarado se calcula además el precio por kilo de nutriente (N + P2O5 + K2O).

## Fase 5. Despliegue

Plataforma web estática conectada a Supabase. La autenticación usa Supabase Auth, y el acceso a los datos se controla con Row Level Security: los resultados se leen solo con sesión iniciada y cada persona accede únicamente a sus presupuestos, reglas, alertas y reportes. Ver la [guía de usuario](guia_usuario.md).

## Fase 6. Monitorización y mantenimiento

Ver el [plan de monitoreo](plan_monitoreo.md).

## Referencias

- Hewamalage, H., Ackermann, K., & Bergmeir, C. (2023). Forecast evaluation for data scientists: Common pitfalls and best practices. *Data Mining and Knowledge Discovery, 37*, 788-832. https://doi.org/10.1007/s10618-022-00894-5
- Studer, S., Bui, T. B., Drescher, C., Hanuschkin, A., Winkler, L., Peters, S., & Müller, K.-R. (2021). Towards CRISP-ML(Q): A machine learning process model with quality assurance methodology. *Machine Learning and Knowledge Extraction, 3*(2), 392-413. https://doi.org/10.3390/make3020020
