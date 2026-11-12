"""Ejecuta las fases de preparacion, modelado y evaluacion y deja los resultados listos para publicar.

Uso: python -m src.pipeline [--actualizar-fuentes] [--sin-preparar]
"""
import argparse
import hashlib
import json
import platform
from datetime import datetime, timezone

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import sklearn
import statsmodels

from . import config as c
from . import evaluate as ev
from . import ingest, prepare, productos
from .models import MODELOS, NOMBRES


def _huella(ruta):
    return hashlib.sha256(ruta.read_bytes()).hexdigest()[:16]


def _cargar_series():
    ind = pd.read_csv(c.PROCESSED / "indice_mensual.csv", parse_dates=["fecha"], index_col="fecha").asfreq("MS")
    exo = pd.read_csv(c.PROCESSED / "exogenas_mensual.csv", parse_dates=["fecha"], index_col="fecha")
    return ind, exo


def _pronostico(y, exo, modelo, cuantiles):
    pred = MODELOS[modelo](y, c.HORIZONTE, exo=exo.loc[: y.index[-1]])
    fechas = pd.date_range(y.index[-1] + pd.DateOffset(months=1), periods=c.HORIZONTE, freq="MS")
    filas = []
    for i, (f, v) in enumerate(zip(fechas, pred), start=1):
        q80, q95 = cuantiles[i][0.8], cuantiles[i][0.95]
        filas.append({"fecha": f.strftime("%Y-%m-%d"), "horizonte": i, "valor": round(float(v), 3),
                      "li80": round(float(v * np.exp(-q80)), 3), "ls80": round(float(v * np.exp(q80)), 3),
                      "li95": round(float(v * np.exp(-q95)), 3), "ls95": round(float(v * np.exp(q95)), 3)})
    return filas


def _figuras(y, bt, metricas, elegido, pron):
    c.FIGURAS.mkdir(parents=True, exist_ok=True)
    verde, azul, gris = "#1f5c4a", "#2f5f8f", "#8a938e"

    fig, ax = plt.subplots(figsize=(9, 4))
    ax.plot(y.index, y, color=verde, lw=2, label="Índice observado")
    fechas = pd.to_datetime([p["fecha"] for p in pron])
    ax.plot(fechas, [p["valor"] for p in pron], color=azul, lw=2, label=f"Pronóstico: {NOMBRES[elegido]}")
    ax.fill_between(fechas, [p["li80"] for p in pron], [p["ls80"] for p in pron], color=azul, alpha=.2, label="Intervalo 80 %")
    ax.set_ylabel("Índice (ene. 2021 = 100)")
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(c.FIGURAS / "pronostico.png", dpi=150)
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(10, 3.8), sharey=True)
    colores = {"naive": gris, "snaive": "#c2a14d", "ets": azul, "sarima": "#b8435a", "ridge": verde}
    for ax, bloque in zip(axes, ["validacion", "prueba"]):
        sub = metricas[(metricas.bloque == bloque) & (metricas.horizonte > 0)]
        for m, g in sub.groupby("modelo"):
            ax.plot(g.horizonte, g.mase, marker="o", color=colores[m], label=NOMBRES[m])
        ax.set_title(f"MASE por horizonte: {bloque}")
        ax.set_xlabel("Meses adelante")
        ax.spines[["top", "right"]].set_visible(False)
    axes[0].legend(frameon=False, fontsize=7)
    fig.tight_layout()
    fig.savefig(c.FIGURAS / "mase_por_horizonte.png", dpi=150)
    plt.close(fig)


def correr(actualizar=False, preparar=True):
    if actualizar:
        ingest.descargar_todo(forzar=True)
    calidad = prepare.correr() if preparar else json.loads((c.REPORTES / "calidad_datos.json").read_text(encoding="utf-8"))
    if preparar:
        calidad["productos"] = productos.correr()
        (c.REPORTES / "calidad_datos.json").write_text(json.dumps(calidad, indent=2, ensure_ascii=False), encoding="utf-8")
    ind, exo = _cargar_series()
    y = ind[c.SERIES["total"]]

    bt = ev.backtest(y, exo)
    metricas = ev.tabla_metricas(bt)
    elegido, supera = ev.seleccionar(metricas)
    bt.round(4).to_csv(c.REPORTES / "backtest.csv", index=False)
    metricas.round(4).to_csv(c.REPORTES / "metricas.csv", index=False)

    pronosticos = {}
    for serie, col in c.SERIES.items():
        ys = ind[col]
        bt_s = bt if serie == "total" else ev.backtest(ys, exo, [elegido])
        q = ev.cuantiles_conformales(bt_s, elegido, ["validacion", "prueba"])
        pronosticos[serie] = _pronostico(ys, exo, elegido, q)

    _figuras(y, bt, metricas, elegido, pronosticos["total"])

    prueba = metricas[(metricas.bloque == "prueba") & (metricas.horizonte == 0)].set_index("modelo")
    validacion = metricas[(metricas.bloque == "validacion") & (metricas.horizonte == 0)].set_index("modelo")
    mejor_prueba_vs_naive = bool(prueba.loc[elegido, "mase"] < prueba.loc["naive", "mase"]) if elegido != "naive" else False
    val_o, pru_o = ev.origenes(y)
    resultado = {
        "ejecutado_en": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "fecha_corte": y.index[-1].strftime("%Y-%m-%d"),
        "modelo_seleccionado": elegido,
        "nombre_modelo": NOMBRES[elegido],
        "supera_persistencia_validacion": bool(supera),
        "supera_persistencia_prueba": mejor_prueba_vs_naive,
        "origenes": {"validacion": len(val_o), "prueba": len(pru_o),
                     "validacion_desde": y.index[val_o[0]].strftime("%Y-%m"), "validacion_hasta": y.index[val_o[-1]].strftime("%Y-%m"),
                     "prueba_desde": y.index[pru_o[0]].strftime("%Y-%m"), "prueba_hasta": y.index[pru_o[-1]].strftime("%Y-%m")},
        "pct_pronosticos_mejor_que_persistencia": {m: ev.superacion(bt, m) for m in c.CANDIDATOS},
        "diebold_mariano_h6": {m: {"validacion": ev.diebold_mariano(bt, m, "validacion"), "prueba": ev.diebold_mariano(bt, m, "prueba")} for m in c.CANDIDATOS},
        "cobertura_prueba_pct": ev.cobertura_prueba(bt, elegido),
        "resumen": {m: {"nombre": NOMBRES[m], "validacion": validacion.loc[m, ["mae", "rmse", "mase"]].round(3).to_dict(),
                        "prueba": prueba.loc[m, ["mae", "rmse", "mase"]].round(3).to_dict()} for m in MODELOS},
        "pronostico": pronosticos,
        "versiones": {"python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__,
                      "scikit-learn": sklearn.__version__, "statsmodels": statsmodels.__version__},
        "huella_datos": {"anexo_upra": _huella(c.ANEXO_UPRA), "indice_mensual": _huella(c.PROCESSED / "indice_mensual.csv")},
    }
    (c.REPORTES / "resultados.json").write_text(json.dumps(resultado, indent=2, ensure_ascii=False), encoding="utf-8")

    # Copia publica para la documentacion del proyecto: sin datos de usuarios.
    c.WEB_DATA.mkdir(parents=True, exist_ok=True)
    por_h = metricas[metricas.horizonte > 0][["modelo", "bloque", "horizonte", "mae", "rmse", "mase"]].round(3)
    publico = dict(resultado)
    publico["metricas_horizonte"] = por_h.to_dict(orient="records")
    publico["calidad"] = calidad
    publico["historico"] = [{"fecha": f.strftime("%Y-%m-%d"), "valor": round(float(v), 2)} for f, v in y.items()]
    (c.WEB_DATA / "resultados.json").write_text(json.dumps(publico, ensure_ascii=False), encoding="utf-8")
    return resultado


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--actualizar-fuentes", action="store_true")
    p.add_argument("--sin-preparar", action="store_true")
    a = p.parse_args()
    r = correr(a.actualizar_fuentes, not a.sin_preparar)
    print(json.dumps({k: r[k] for k in ("modelo_seleccionado", "supera_persistencia_validacion", "supera_persistencia_prueba",
                                        "origenes", "pct_pronosticos_mejor_que_persistencia", "diebold_mariano_h6",
                                        "cobertura_prueba_pct", "resumen")}, indent=1, ensure_ascii=False))
    print(json.dumps(r["pronostico"]["total"], ensure_ascii=False))
