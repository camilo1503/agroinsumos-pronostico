"""Referencias y modelos candidatos. Todos reciben solo datos hasta el origen y devuelven niveles del indice."""
import warnings

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from statsmodels.tsa.exponential_smoothing.ets import ETSModel
from statsmodels.tsa.statespace.sarimax import SARIMAX

ALFAS = [0.1, 1.0, 10.0, 100.0, 1000.0]
GRILLA_ARIMA = [(p, 1, q) for p in range(3) for q in range(3)]
GRILLA_ESTACIONAL = [(0, 0, 0, 0), (1, 0, 0, 12)]


def naive(y, h, **_):
    return np.repeat(y.iloc[-1], h)


def snaive(y, h, **_):
    return np.array([y.iloc[-12 + (i % 12)] for i in range(h)])


def ets(y, h, **_):
    """Suavizamiento exponencial sobre el logaritmo; AICc elige si la tendencia se amortigua."""
    log_y = np.log(y)
    opciones = [dict(trend=None), dict(trend="add", damped_trend=False), dict(trend="add", damped_trend=True)]
    mejor, mejor_aicc = None, np.inf
    for op in opciones:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            try:
                ajuste = ETSModel(log_y, error="add", **op).fit(disp=False, maxiter=500)
            except Exception:
                continue
        if np.isfinite(ajuste.aicc) and ajuste.aicc < mejor_aicc:
            mejor, mejor_aicc = ajuste, ajuste.aicc
    if mejor is None:
        return naive(y, h)
    return np.exp(np.asarray(mejor.forecast(h)))


def sarima(y, h, **_):
    """ARIMA con d=1 y termino estacional opcional; el orden se elige por AICc en cada origen."""
    log_y = np.log(y)
    mejor, mejor_aicc = None, np.inf
    for orden in GRILLA_ARIMA:
        for est in GRILLA_ESTACIONAL:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                try:
                    ajuste = SARIMAX(log_y, order=orden, seasonal_order=est, trend="n",
                                     enforce_stationarity=True, enforce_invertibility=True).fit(disp=False, maxiter=200)
                except Exception:
                    continue
            if np.isfinite(ajuste.aicc) and ajuste.aicc < mejor_aicc:
                mejor, mejor_aicc = ajuste, ajuste.aicc
    if mejor is None:
        return naive(y, h)
    return np.exp(np.asarray(mejor.forecast(h)))


def construir_features(y, exo):
    """Cada fila usa informacion disponible en el mes t. Nada posterior a t entra a la fila."""
    log_y = np.log(y)
    x = pd.DataFrame(index=y.index)
    for k in (1, 2, 3, 6, 12):
        x[f"y_var_{k}"] = log_y.diff(k)
    log_exo = np.log(exo.reindex(y.index.union(exo.index)).sort_index())
    for col in ("trm", "urea_usd", "dap_usd"):
        for k in (1, 3, 6):
            x[f"{col}_var_{k}"] = log_exo[col].diff(k).reindex(y.index)
    x["mes_sen"] = np.sin(2 * np.pi * y.index.month / 12)
    x["mes_cos"] = np.cos(2 * np.pi * y.index.month / 12)
    return x


def _alfa_por_validacion(X, objetivo):
    if len(X) < 30:
        return 100.0
    errores = {}
    for alfa in ALFAS:
        acumulado = []
        for tr, va in TimeSeriesSplit(n_splits=3, test_size=6).split(X):
            m = make_pipeline(StandardScaler(), Ridge(alpha=alfa)).fit(X[tr], objetivo[tr])
            acumulado.append(np.mean(np.abs(m.predict(X[va]) - objetivo[va])))
        errores[alfa] = np.mean(acumulado)
    return min(errores, key=errores.get)


def ridge(y, h, exo=None, **_):
    """Regresion directa: un modelo por horizonte para el cambio logaritmico entre t y t+h."""
    x = construir_features(y, exo)
    log_y = np.log(y).to_numpy()
    n = len(y)
    pred = []
    for paso in range(1, h + 1):
        # La ultima fila entrenable es n-1-paso: su objetivo t+paso ya esta observado en el origen.
        filas = np.arange(n - paso)
        objetivo = log_y[filas + paso] - log_y[filas]
        validas = x.iloc[filas].notna().all(axis=1).to_numpy()
        X = x.iloc[filas][validas].to_numpy()
        z = objetivo[validas]
        alfa = _alfa_por_validacion(X, z)
        modelo = make_pipeline(StandardScaler(), Ridge(alpha=alfa)).fit(X, z)
        ultimo = x.iloc[[-1]].to_numpy()
        pred.append(float(np.exp(log_y[-1] + modelo.predict(ultimo)[0])))
    return np.array(pred)


MODELOS = {"naive": naive, "snaive": snaive, "ets": ets, "sarima": sarima, "ridge": ridge}
NOMBRES = {
    "naive": "Persistencia (referencia)",
    "snaive": "Estacional ingenuo (referencia)",
    "ets": "Suavizamiento exponencial (ETS)",
    "sarima": "SARIMA",
    "ridge": "Ridge directo con variables externas",
}
