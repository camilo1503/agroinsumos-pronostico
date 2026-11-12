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


def test_mercado_tiene_series_positivas_y_fechas_unicas():
    if not c.PINK_SHEET_XLSX.exists():
        pytest.skip("Pink Sheet no descargado")
    m = prepare.preparar_mercado()
    assert list(m.columns) == ["trm", "urea_usd", "dap_usd", "kcl_usd", "tsp_usd"]
    assert m.index.is_unique and m.index.is_monotonic_increasing
    assert (m.dropna() > 0).all().all()
    assert m["urea_usd"].notna().sum() > 60


def test_pronostico_por_producto_no_usa_el_futuro_y_elige_el_menor_error():
    from src import productos as p
    idx = pd.date_range("2019-01-01", periods=84, freq="MS")
    rng = np.random.default_rng(3)
    y = pd.Series(50000 * np.exp(np.cumsum(rng.normal(0.004, 0.03, 84))), index=idx)
    elegido, mae, cuantil = p.evaluar(y)
    assert mae[elegido] == min(mae.values())
    assert len(cuantil) == c.HORIZONTE and (cuantil >= 0).all()
    alterada = y.copy()
    alterada.iloc[-1] *= 3   # el ultimo mes solo puede afectar al ultimo origen
    _, mae2, _ = p.evaluar(alterada.iloc[:-1])
    _, mae3, _ = p.evaluar(y.iloc[:-1])
    assert mae2 == mae3


def test_recomendacion_y_nutrientes():
    from src import productos as p
    assert p.recomendar(0.5, -10, 80, 95, 100)[0] == "esperar"
    assert p.recomendar(0.5, 10, 105, 120, 100)[0] == "comprar"
    assert p.recomendar(0.1, 0, 90, 110, 100)[0] == "comprar"
    assert p.recomendar(0.9, -5, 85, 105, 100)[0] == "esperar"
    assert p.recomendar(0.5, 0, 90, 110, 100)[0] == "normal"
    assert "3 meses" in p.recomendar(0.5, 10, 105, 120, 100, 3)[1]
    assert p.plazo("Frutas") == 3 and p.plazo("Fertilizantes") == 6
    assert p.nutrientes("Urea 46%", "50 kilogramos") == pytest.approx(23)
    assert p.nutrientes("Fosfato Diamónico (DAP) 18-46-0", "50 kilogramos") == pytest.approx(32)
    assert p.nutrientes("Cal Dolomita", "50 kilogramos") is None
    assert p.nutrientes("Nutrimins", "1 litro") is None


def test_alimentos_resume_por_departamento_y_filtra_la_canasta():
    from src import alimentos as a
    crudo = pd.DataFrame({
        "fecha": ["2026-01-01"] * 5,
        "grupo": ["TUBERCULOS, RAICES Y PLATANOS"] * 3 + ["LÁCTEOS Y HUEVOS", "FRUTAS"],
        "producto": ["Papa única", "Papa única", "Papa única", "Huevo rojo AA", "Kiwi"],
        "mercado": ["Bogotá, D.C., Corabastos", "Tunja, Complejo de Servicios del Sur", "Sogamoso (Boyacá)", "Cali, Cavasa", "Cali, Cavasa"],
        "precio": [1000, 2000, 3000, 500, 9000],
    })
    fuentes = {"Bogotá, D.C., Corabastos": "Bogotá, D.C.", "Tunja, Complejo de Servicios del Sur": "Boyacá", "Cali, Cavasa": "Valle del Cauca"}
    r = a.resumir(crudo, fuentes)
    assert "Kiwi" not in set(r["producto"])
    papa = r[r["producto"] == "Papa única"].set_index("departamento")
    assert papa.loc["Nacional", "precio"] == 2000 and papa.loc["Nacional", "n_registros"] == 3
    assert papa.loc["Boyacá", "precio"] == 2500     # Tunja por la tabla de fuentes y Sogamoso por el paréntesis
    assert set(papa["grupo"]) == {"Tubérculos y plátanos"}
    assert r[r["producto"] == "Huevo rojo AA"]["presentacion"].iloc[0] == "1 unidad"

