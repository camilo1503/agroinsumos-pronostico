"""Pronostico del precio nacional de cada producto (insumos y alimentos) y recomendacion de compra.

Se comparan persistencia y ETS en validacion temporal; ETS solo se usa si su error es menor.
El plazo de la recomendacion es 3 meses para alimentos y 6 para insumos.
"""
import re

import numpy as np
import pandas as pd
from joblib import Parallel, delayed

from . import config as c
from .models import ets, naive

ORIGENES = 18          # origenes de validacion por producto
MIN_MESES = 48         # historia minima para pronosticar
MAX_REZAGO = 2         # meses de atraso permitidos frente al ultimo mes de SIPSA-I
CLAVE = ["grupo", "producto", "presentacion"]
CANDIDATOS = {"naive": naive, "ets": ets}
INSUMOS = {"Fertilizantes", "Fungicidas", "Herbicidas", "Insecticidas"}


def plazo(grupo):
    # Los alimentos frescos cambian de precio mucho mas rapido; a 6 meses el rango sale demasiado ancho.
    return c.HORIZONTE if grupo in INSUMOS else 3


def series_nacionales(precios):
    """Serie mensual por producto. Rellena huecos de hasta tres meses y conserva el tramo final continuo."""
    nac = precios[precios["departamento"] == "Nacional"]
    ultimo_grupo = nac.groupby("grupo")["fecha"].max()   # insumos y alimentos se publican en fechas distintas
    salida = {}
    for clave, g in nac.groupby(CLAVE):
        y = g.set_index("fecha")["precio"].sort_index().asfreq("MS").interpolate(limit=3)
        if y.index[-1] < ultimo_grupo[clave[0]] - pd.DateOffset(months=MAX_REZAGO):
            continue
        faltantes = np.flatnonzero(y.isna().to_numpy())
        if len(faltantes):
            y = y.iloc[faltantes[-1] + 1:]
        if len(y) >= MIN_MESES:
            salida[clave] = y
    return salida


def evaluar(y, h=c.HORIZONTE, origenes=ORIGENES, meses=None):
    """Modelo elegido (por MAE hasta `meses`), MAE de cada candidato y cuantil 80 % del error por horizonte."""
    meses = meses or h
    n = len(y)
    errores = {m: [] for m in CANDIDATOS}
    for i in range(n - h - origenes, n - h):
        entrenamiento = y.iloc[: i + 1]
        real = y.iloc[i + 1: i + 1 + h].to_numpy()
        for m, f in CANDIDATOS.items():
            errores[m].append((real, np.asarray(f(entrenamiento, h))))
    mae = {m: float(np.mean([np.abs(r[:meses] - p[:meses]).mean() for r, p in v])) for m, v in errores.items()}
    elegido = "ets" if mae["ets"] < mae["naive"] else "naive"
    log_err = np.abs(np.array([np.log(r) - np.log(p) for r, p in errores[elegido]]))   # origenes x horizonte
    k = min(int(np.ceil((origenes + 1) * 0.8)) - 1, origenes - 1)
    cuantil = np.sort(log_err, axis=0)[k]
    return elegido, mae, cuantil


def nutrientes(producto, presentacion):
    """Kilos de nutrientes (N + P2O5 + K2O) por unidad, para fertilizantes solidos con grado declarado."""
    kg = re.fullmatch(r"(\d+(?:[.,]\d+)?) kilogramos?", presentacion.strip())
    if not kg:
        return None
    grado = re.search(r"(\d+)-(\d+)-(\d+)", producto)
    if grado:
        pct = sum(int(x) for x in grado.groups())
    elif producto.lower().startswith("urea"):
        pct = int(re.search(r"(\d+)\s*%", producto).group(1))
    else:
        return None
    return float(kg.group(1).replace(",", ".")) * pct / 100 if pct else None


def recomendar(posicion, var, li80, ls80, precio, meses=6):
    """Regla de compra: que tan caro esta hoy frente a dos anos y hacia donde va el rango estimado."""
    if ls80 < precio:
        return "esperar", f"Se espera que baje en los próximos {meses} meses."
    if posicion >= 0.67 and var <= -2:
        return "esperar", "Está cerca de su precio más alto en dos años y se espera que baje."
    if li80 > precio:
        return "comprar", f"Se espera que suba en los próximos {meses} meses."
    if posicion <= 0.33 and var >= -1:
        return "comprar", "Está cerca de su precio más bajo en dos años y no se estima una baja."
    return "normal", "Precio en la zona media de los últimos dos años, sin señal clara."


def _un_producto(clave, y):
    elegido, mae, cuantil = evaluar(y, meses=plazo(clave[0]))
    pred = np.asarray(CANDIDATOS[elegido](y, c.HORIZONTE))
    precio = float(y.iloc[-1])
    fechas = pd.date_range(y.index[-1] + pd.DateOffset(months=1), periods=c.HORIZONTE, freq="MS")
    base = dict(zip(CLAVE, clave))
    pron = [{**base, "horizonte": i + 1, "fecha": fechas[i].strftime("%Y-%m-%d"), "valor": round(float(pred[i]), 2),
             "li80": round(float(pred[i] * np.exp(-cuantil[i])), 2), "ls80": round(float(pred[i] * np.exp(cuantil[i])), 2)}
            for i in range(c.HORIZONTE)]
    ventana = y.tail(24)
    rango = float(ventana.max() - ventana.min())
    posicion = (precio - float(ventana.min())) / rango if rango > 0 else 0.5
    meses = plazo(clave[0])
    p = pron[meses - 1]
    var = (p["valor"] / precio - 1) * 100
    codigo, motivo = recomendar(posicion, var, p["li80"], p["ls80"], precio, meses)
    kg = nutrientes(clave[1], clave[2]) if clave[0] == "Fertilizantes" else None
    resumen = {
        **base, "fecha_precio": y.index[-1].strftime("%Y-%m-%d"), "precio": round(precio, 2),
        "minimo_24m": round(float(ventana.min()), 2), "maximo_24m": round(float(ventana.max()), 2),
        "posicion_24m": round(posicion, 3),
        "var_12m_pct": round((precio / float(y.iloc[-13]) - 1) * 100, 2) if len(y) > 12 else None,
        "plazo": meses, "var_plazo_pct": round(var, 2), "modelo": elegido,
        "mae_modelo": round(mae[elegido], 2), "mae_persistencia": round(mae["naive"], 2),
        "recomendacion": codigo, "motivo": motivo,
        "kg_nutriente": round(kg, 3) if kg else None,
        "precio_kg_nutriente": round(precio / kg, 2) if kg else None,
    }
    return pron, resumen


def correr():
    archivos = [c.PROCESSED / n for n in ("sipsa_precios.csv", "alimentos_precios.csv")]
    precios = pd.concat([pd.read_csv(a, parse_dates=["fecha"]) for a in archivos if a.exists()], ignore_index=True)
    series = series_nacionales(precios)
    salida = Parallel(n_jobs=-1)(delayed(_un_producto)(k, y) for k, y in series.items())
    pron = pd.DataFrame([f for p, _ in salida for f in p])
    resumen = pd.DataFrame([r for _, r in salida])
    pron.to_csv(c.PROCESSED / "producto_pronostico.csv", index=False)
    resumen.to_csv(c.PROCESSED / "producto_resumen.csv", index=False)
    return {
        "productos": int(len(resumen)),
        "con_ets": int((resumen["modelo"] == "ets").sum()),
        "recomendaciones": resumen["recomendacion"].value_counts().to_dict(),
    }


if __name__ == "__main__":
    print(correr())
