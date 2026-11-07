import numpy as np
import pandas as pd
import pytest

from src import config as c
from src import evaluate as ev
from src import models as m
from src import prepare


@pytest.fixture(scope="module")
def indice():
    return prepare.cargar_indice()


@pytest.fixture
def serie():
    idx = pd.date_range("2018-12-01", periods=60, freq="MS")
    rng = np.random.default_rng(1)
    return pd.Series(100 * np.exp(np.cumsum(rng.normal(0.005, 0.02, 60))), index=idx)


@pytest.fixture
def exo(serie):
    idx = pd.date_range(serie.index[0] - pd.DateOffset(months=13), serie.index[-1], freq="MS")
    rng = np.random.default_rng(2)
    return pd.DataFrame({k: 100 * np.exp(np.cumsum(rng.normal(0, 0.02, len(idx))))
                         for k in ("trm", "urea_usd", "dap_usd")}, index=idx)


def test_indice_sin_huecos_ni_ceros(indice):
    assert indice.index.to_series().diff().dropna().dt.days.between(28, 31).all()
    assert indice["T_Índice"].notna().all()
    assert (indice.select_dtypes("number").fillna(1) > 0).all().all()


def test_base_enero_2021_es_100(indice):
    assert indice.loc["2021-01-01", "T_Índice"] == pytest.approx(100, abs=0.5)


def test_origenes_no_se_cruzan_y_dejan_horizonte_completo():
    y = pd.Series(range(93), index=pd.date_range("2018-12-01", periods=93, freq="MS"), dtype=float)
    val, prueba = ev.origenes(y)
    assert max(val) < min(prueba)
    assert len(prueba) == c.ORIGENES_PRUEBA
    assert max(prueba) + c.HORIZONTE == len(y) - 1


def test_features_no_cambian_con_datos_futuros(serie, exo):
    corte = serie.iloc[:40]
    a = m.construir_features(corte, exo.loc[:corte.index[-1]]).iloc[-1]
    b = m.construir_features(serie, exo).loc[corte.index[-1]]
    pd.testing.assert_series_equal(a, b, check_names=False)


def test_ridge_no_usa_futuro(serie, exo):
    corte = serie.iloc[:45]
    exo_corte = exo.loc[:corte.index[-1]]
    base = m.ridge(corte, 6, exo=exo_corte)
    alterada = exo.copy()
    alterada.loc[alterada.index > corte.index[-1]] *= 50
    otra = m.ridge(corte, 6, exo=alterada.loc[:corte.index[-1]])
    np.testing.assert_allclose(base, otra)


@pytest.mark.parametrize("nombre", list(m.MODELOS))
def test_modelos_devuelven_seis_niveles_positivos(nombre, serie, exo):
    pred = m.MODELOS[nombre](serie, 6, exo=exo)
    assert len(pred) == 6
    assert np.isfinite(pred).all() and (pred > 0).all()


def test_mase_de_persistencia_en_paseo_unitario():
    g = pd.DataFrame({"real": [11.0, 12.0], "pred": [10.0, 10.0], "escala": [1.0, 1.0]})
    assert ev._metricas(g)["mase"] == pytest.approx(1.5)


def test_seleccion_conserva_persistencia_si_nadie_la_supera():
    filas = [{"modelo": k, "bloque": "validacion", "horizonte": 0, "mase": v}
             for k, v in {"naive": 1.0, "snaive": 2.0, "ets": 1.2, "sarima": 1.1, "ridge": 1.3}.items()]
    assert ev.seleccionar(pd.DataFrame(filas)) == ("naive", False)
