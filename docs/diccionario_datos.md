# Diccionario de datos

## Archivos procesados

### `data/processed/indice_mensual.csv`

| Campo | Descripción | Unidad |
|---|---|---|
| `fecha` | Primer día del mes | Fecha |
| `T_Índice` | Índice nacional total (variable objetivo) | Enero 2021 = 100 |
| `T_Fertilizantes`, `T_Simples`, `T_Compuestos` | Subíndices de fertilizantes | Enero 2021 = 100 |
| `T_Plaguicidas`, `T_Herbicidas`, `T_Fungicidas`, `T_Insecticidas` | Subíndices de plaguicidas | Enero 2021 = 100 |
| `T_Otros` | Otros insumos; disponible desde enero de 2021 | Enero 2021 = 100 |

### `data/processed/exogenas_mensual.csv`

| Campo | Descripción | Unidad |
|---|---|---|
| `trm` | Promedio mensual de la TRM | COP por USD |
| `urea_usd` | Precio internacional de la urea, Pink Sheet | USD por tonelada métrica |
| `dap_usd` | Precio internacional del DAP, Pink Sheet | USD por tonelada métrica |

### `data/processed/mercado_mensual.csv`

| Campo | Descripción | Unidad |
|---|---|---|
| `trm` | Promedio mensual de la TRM | COP por USD |
| `urea_usd`, `dap_usd`, `kcl_usd`, `tsp_usd` | Precio internacional de urea, DAP, cloruro de potasio y TSP, Pink Sheet | USD por tonelada métrica |

### `data/processed/sipsa_precios.csv`

| Campo | Descripción |
|---|---|
| `fecha` | Primer día del mes |
| `grupo` | Fertilizantes, Fungicidas, Herbicidas o Insecticidas |
| `producto`, `presentacion` | Producto y presentación según SIPSA-I; 15 productos por grupo |
| `departamento` | Departamento, o `Nacional` para el resumen de todos |
| `precio` | Mediana de los precios promedio publicados, en COP |
| `n_registros` | Registros de SIPSA-I usados en la mediana |

### `data/processed/producto_pronostico.csv` y `producto_resumen.csv`

| Campo | Descripción |
|---|---|
| `horizonte`, `fecha`, `valor`, `li80`, `ls80` | Precio estimado y su intervalo de 80 % para cada uno de los seis meses, en COP |
| `precio`, `fecha_precio` | Último precio mediano nacional |
| `minimo_24m`, `maximo_24m`, `posicion_24m` | Rango de 24 meses y posición del precio actual (0 = mínimo, 1 = máximo) |
| `plazo`, `var_12m_pct`, `var_plazo_pct` | Meses de la recomendación (3 en alimentos, 6 en insumos), variación observada en doce meses y variación estimada al plazo |
| `modelo`, `mae_modelo`, `mae_persistencia` | Modelo publicado (`naive` o `ets`) y errores en validación |
| `recomendacion`, `motivo` | `comprar`, `esperar` o `normal`, y la razón |
| `kg_nutriente`, `precio_kg_nutriente` | Kilos de N + P2O5 + K2O por unidad y precio por kilo de nutriente |

### `data/processed/alimentos_precios.csv`

Mismos campos que `sipsa_precios.csv`, para 64 alimentos de la canasta familiar. `precio` es la mediana mensual de los precios mayoristas entre mercados (COP por kilogramo; huevos por unidad y aceite por litro) y `n_registros` el número de mercados. En la base de datos se guarda en la misma tabla `sipsa_precio`.

### `data/processed/sipsa_contraste.csv`

Índice encadenado por grupo, construido con la mediana de las variaciones mensuales de series comparables. Sirve para contrastar tendencias y no es un índice oficial.

## Base de datos

| Tabla o vista | Contenido | Acceso |
|---|---|---|
| `indice_mensual` | Serie oficial preparada | Lectura con sesión |
| `corrida_modelo` | Versión de cada ejecución: corte, modelo, cobertura, librerías y huella de datos | Lectura con sesión |
| `metrica_modelo` | MAE, RMSE y MASE por modelo, bloque y horizonte (0 = global) | Lectura con sesión |
| `pronostico` | Estimación e intervalos de 80 % y 95 % por serie | Lectura con sesión |
| `backtest_modelo` | Predicciones históricas por origen y horizonte | Lectura con sesión |
| `sipsa_precio`, `sipsa_contraste` | Precios resumidos y contraste | Lectura con sesión |
| `producto_pronostico`, `producto_resumen` | Pronóstico por producto y recomendación de compra | Lectura con sesión |
| `mercado_mensual` | TRM y precios internacionales de fertilizantes | Lectura con sesión |
| `sipsa_precio_reciente` | Último precio por producto y departamento en los tres meses más recientes | Lectura con sesión |
| `departamento_lista` | Departamentos con precios | Lectura con sesión |
| `perfil` | Nombre, tipo de usuario, departamento, cultivo y área de cada persona | Solo su registro |
| `canasta_item` | Productos y cantidades de la lista de compra | Solo sus registros |
| `presupuesto` | Gastos que registra cada persona | Solo sus registros |
| `regla_alerta` | Reglas de alerta personales | Solo sus registros |
| `alerta_evento` | Alertas activadas | Lectura y marcado de sus registros |
| `reporte_generado` | Historial de reportes | Solo sus registros |
| `monitoreo_pronostico` | Pronósticos publicados frente a valores observados | Lectura con sesión |
