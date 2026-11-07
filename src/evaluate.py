"""Validacion temporal progresiva, seleccion del modelo e intervalos conformales por horizonte."""
import numpy as np
import pandas as pd
from joblib import Parallel, delayed
from scipy import stats

from . import config as c
from .models import MODELOS


def origenes(y):
    """Separa los origenes en validacion y prueba. El ultimo origen aun tiene seis meses observados."""
    n = len(y)
    ultimo = n - c.HORIZONTE - 1
    primero_prueba = ultimo - c.ORIGENES_PRUEBA + 1
    val = list(range(c.MIN_ENTRENAMIENTO - 1, primero_prueba))
    prueba = list(range(primero_prueba, ultimo + 1))
    return val, prueba


def _un_origen(nombre, y, exo, i, bloque):
    entrenamiento = y.iloc[: i + 1]
    exo_hasta = exo.loc[: entrenamiento.index[-1]]
    pred = MODELOS[nombre](entrenamiento, c.HORIZONTE, exo=exo_hasta)
    escala = entrenamiento.diff().abs().mean()
    filas = []
    for paso in range(1, c.HORIZONTE + 1):
        real = y.iloc[i + paso]
        filas.append({"modelo": nombre, "bloque": bloque, "origen": y.index[i], "fecha": y.index[i + paso],
                      "horizonte": paso, "real": real, "pred": pred[paso - 1], "escala": escala})
    return filas


def backtest(y, exo, modelos=None):
    modelos = modelos or list(MODELOS)
    val, prueba = origenes(y)
    tareas = [(m, i, "validacion") for m in modelos for i in val] + [(m, i, "prueba") for m in modelos for i in prueba]
    salida = Parallel(n_jobs=-1)(delayed(_un_origen)(m, y, exo, i, b) for m, i, b in tareas)
    return pd.DataFrame([f for grupo in salida for f in grupo])


def _metricas(g):
    e = g["real"] - g["pred"]
    return pd.Series({"mae": e.abs().mean(), "rmse": np.sqrt((e ** 2).mean()),
                      "mase": (e.abs() / g["escala"]).mean(), "n": len(g)})


def tabla_metricas(bt):
    glob = bt.groupby(["modelo", "bloque"])[["real", "pred", "escala"]].apply(_metricas).reset_index()
    glob["horizonte"] = 0
    por_h = bt.groupby(["modelo", "bloque", "horizonte"])[["real", "pred", "escala"]].apply(_metricas).reset_index()
    return pd.concat([glob, por_h], ignore_index=True)


def seleccionar(metricas):
    """Escoge por MASE de validacion. Si ningun candidato supera a persistencia, se queda persistencia."""
    v = metricas[(metricas["bloque"] == "validacion") & (metricas["horizonte"] == 0)].set_index("modelo")["mase"]
    mejor = v[c.CANDIDATOS].idxmin()
    if v[mejor] >= v["naive"]:
        return "naive", False
    return mejor, True


def diebold_mariano(bt, modelo, bloque="prueba", horizonte=6, referencia="naive"):
    """DM con correccion de Harvey, Leybourne y Newbold. Positivo: el modelo tiene menor error absoluto."""
    a = bt[(bt.modelo == modelo) & (bt.bloque == bloque) & (bt.horizonte == horizonte)].set_index("origen")
    b = bt[(bt.modelo == referencia) & (bt.bloque == bloque) & (bt.horizonte == horizonte)].set_index("origen")
    d = ((b["real"] - b["pred"]).abs() - (a["real"] - a["pred"]).abs()).to_numpy()
    n, media = len(d), d.mean()
    var = np.var(d)
    for k in range(1, horizonte):
        if k < n:
            var += 2 * np.mean((d[k:] - media) * (d[:-k] - media))
    if var <= 0:
        return {"estadistico": None, "p_valor": None, "n": n}
    dm = media / np.sqrt(var / n)
    dm *= np.sqrt((n + 1 - 2 * horizonte + horizonte * (horizonte - 1) / n) / n)
    return {"estadistico": round(float(dm), 3), "p_valor": round(float(2 * stats.t.sf(abs(dm), n - 1)), 3), "n": n}


def superacion(bt, modelo, referencia="naive"):
    """Porcentaje de pronosticos en los que el modelo erro menos que la referencia, por bloque."""
    a = bt[bt.modelo == modelo].set_index(["bloque", "origen", "horizonte"])
    b = bt[bt.modelo == referencia].set_index(["bloque", "origen", "horizonte"])
    gana = (a["real"] - a["pred"]).abs() < (b["real"] - b["pred"]).abs()
    return {k: round(float(v) * 100, 1) for k, v in gana.groupby("bloque").mean().items()}


def cuantiles_conformales(bt, modelo, bloques, niveles=(0.8, 0.95)):
    """Cuantil del error logaritmico absoluto por horizonte, con el ajuste de muestra finita."""
    g = bt[(bt.modelo == modelo) & bt.bloque.isin(bloques)]
    q = {}
    for paso, sub in g.groupby("horizonte"):
        e = np.sort(np.abs(np.log(sub["real"]) - np.log(sub["pred"])).to_numpy())
        n = len(e)
        q[int(paso)] = {nivel: float(e[min(int(np.ceil((n + 1) * nivel)) - 1, n - 1)]) for nivel in niveles}
    return q


def cobertura_prueba(bt, modelo):
    """Calibra solo con validacion y mide cuantos valores de prueba caen dentro del intervalo."""
    q = cuantiles_conformales(bt, modelo, ["validacion"])
    g = bt[(bt.modelo == modelo) & (bt.bloque == "prueba")]
    err = np.abs(np.log(g["real"]) - np.log(g["pred"]))
    salida = {}
    for nivel in (0.8, 0.95):
        limite = g["horizonte"].map(lambda h: q[int(h)][nivel])
        salida[str(int(nivel * 100))] = round(float((err <= limite).mean()) * 100, 1)
    return salida
