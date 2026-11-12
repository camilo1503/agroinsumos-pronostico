"""Fase 2 de CRISP-ML(Q): serie mensual limpia, exogenas alineadas y reporte de calidad."""
import json

import numpy as np
import pandas as pd

from . import config as c
from .ingest import comparar_con_api

MESES = {m: i + 1 for i, m in enumerate(
    ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
     "septiembre", "octubre", "noviembre", "diciembre"])}
HOJAS_SIPSA = {"1.3": "Fertilizantes", "1.4": "Fungicidas", "1.5": "Herbicidas", "1.6": "Insecticidas"}
COLUMNAS_INDICE = ["T_Índice", "T_Fertilizantes", "T_Plaguicidas", "T_Otros", "T_Simples",
                   "T_Compuestos", "T_Herbicidas", "T_Fungicidas", "T_Insecticidas"]


def cargar_indice(ruta=c.ANEXO_UPRA):
    d = pd.read_excel(ruta, sheet_name="Indice_DetalladoAgricola", header=2)
    d = d.rename(columns={d.columns[0]: "fecha"})
    d["fecha"] = pd.to_datetime(d["fecha"], errors="coerce")
    d = d.dropna(subset=["fecha"]).set_index("fecha").sort_index()
    d = d[~d.index.duplicated()].apply(pd.to_numeric, errors="coerce")
    # En el anexo un cero significa "sin dato": el subindice no existia o el producto salio de la canasta.
    return d.replace(0, np.nan).asfreq("MS")


def cargar_exogenas(indice):
    trm = pd.read_csv(c.TRM_CSV, parse_dates=["fecha"]).set_index("fecha")["trm"]
    crudo = pd.read_excel(c.PINK_SHEET_XLSX, sheet_name="Monthly Prices", header=None)
    nombres = crudo.iloc[4].astype(str).str.strip().str.lower()
    col_urea = nombres[nombres == "urea"].index[0]
    col_dap = nombres[nombres == "dap"].index[0]
    tabla = crudo.iloc[6:, [0, col_urea, col_dap]].copy()
    tabla.columns = ["periodo", "urea_usd", "dap_usd"]
    tabla["fecha"] = pd.to_datetime(tabla["periodo"].astype(str).str.replace("M", "-"),
                                    format="%Y-%m", errors="coerce")
    tabla = tabla.dropna(subset=["fecha"]).set_index("fecha")[["urea_usd", "dap_usd"]]
    tabla = tabla.apply(pd.to_numeric, errors="coerce")
    inicio = indice.index.min() - pd.DateOffset(months=13)
    return pd.concat([trm.rename("trm"), tabla], axis=1).sort_index().loc[inicio:]


def reporte_calidad(d):
    esperadas = pd.date_range(d.index.min(), d.index.max(), freq="MS")
    vm = np.log(d["T_Índice"]).diff()
    z = (vm - vm.median()) / (1.4826 * (vm - vm.median()).abs().median())
    saltos = {}
    for etiqueta, f in {"ene_2024_amplia_canasta": "2024-01-01", "sep_2024_excluye_fipronil": "2024-09-01"}.items():
        f = pd.Timestamp(f)
        saltos[etiqueta] = {"variacion_mes_pct": round(float(np.expm1(vm[f]) * 100), 2),
                            "z_robusto": round(float(z[f]), 2)}
    faltantes = d.isna().sum()
    return {
        "desde": d.index.min().strftime("%Y-%m"),
        "hasta": d.index.max().strftime("%Y-%m"),
        "observaciones": int(len(d)),
        "meses_ausentes": int(len(esperadas.difference(d.index))),
        "faltantes_indice_total": int(d["T_Índice"].isna().sum()),
        "columnas_con_faltantes": {k: int(v) for k, v in faltantes[faltantes > 0].items()},
        "primer_mes_otros_insumos": d["T_Otros"].first_valid_index().strftime("%Y-%m"),
        "ultimo_mes_clorpirifos": d["Clorpirifos"].last_valid_index().strftime("%Y-%m"),
        "ultimo_mes_fipronil": d["Fipronil"].last_valid_index().strftime("%Y-%m"),
        "cambios_de_canasta": saltos,
        "meses_atipicos_z_mayor_3": [f.strftime("%Y-%m") for f in z[z.abs() > 3].index],
    }


def preparar_sipsa():
    """Resume SIPSA-I a mediana mensual por producto y departamento, y arma un indice de contraste."""
    partes = []
    for hoja, grupo in HOJAS_SIPSA.items():
        t = pd.read_excel(c.SIPSA_XLSX, sheet_name=hoja, header=8, usecols=range(11), dtype=object)
        t.columns = ["anio", "mes", "cod_dep", "departamento", "cpc", "producto", "articulo",
                     "casa", "ica", "presentacion", "precio"]
        t = t[pd.to_numeric(t["anio"], errors="coerce").notna()].copy()
        t["grupo"] = grupo
        partes.append(t)
    s = pd.concat(partes, ignore_index=True)
    s["mes_n"] = s["mes"].astype(str).str.strip().str.lower().map(MESES)
    s["precio"] = pd.to_numeric(s["precio"], errors="coerce")
    s = s.dropna(subset=["mes_n", "precio"])
    s = s[s["precio"] > 0].copy()
    s["fecha"] = pd.to_datetime(dict(year=s["anio"].astype(int), month=s["mes_n"].astype(int), day=1))
    for col in ["producto", "articulo", "presentacion", "departamento", "casa"]:
        s[col] = s[col].astype(str).str.strip()

    # Contraste: variacion mediana de series comparables (mismo articulo, casa, presentacion y departamento).
    llave = ["grupo", "articulo", "casa", "presentacion", "departamento"]
    panel = s.groupby(llave + ["fecha"], as_index=False)["precio"].mean().sort_values(llave + ["fecha"])
    panel["dlog"] = panel.groupby(llave)["precio"].transform(lambda x: np.log(x).diff())
    panel["brecha"] = panel.groupby(llave)["fecha"].diff().dt.days
    validos = panel[(panel["brecha"] <= 31) & panel["dlog"].abs().lt(0.5)]
    cadena = validos.groupby(["grupo", "fecha"])["dlog"].median().unstack(0).sort_index()
    contraste = np.exp(cadena.fillna(0).cumsum()) * 100

    # Para la plataforma: productos con mejor cobertura, en su presentacion mas frecuente.
    conteo = s.groupby(["grupo", "producto", "presentacion"]).size().rename("n").reset_index()
    top = conteo.sort_values("n", ascending=False).groupby("grupo").head(15)
    base = s.merge(top[["grupo", "producto", "presentacion"]], on=["grupo", "producto", "presentacion"])
    claves = ["fecha", "grupo", "producto", "presentacion"]
    por_dep = base.groupby(claves + ["departamento"], as_index=False).agg(
        precio=("precio", "median"), n_registros=("precio", "size"))
    nacional = base.groupby(claves, as_index=False).agg(precio=("precio", "median"), n_registros=("precio", "size"))
    nacional["departamento"] = "Nacional"
    precios = pd.concat([nacional, por_dep], ignore_index=True)
    precios["precio"] = precios["precio"].round(2)
    return precios, contraste


def preparar_mercado():
    """TRM y precios internacionales de fertilizantes (Pink Sheet) para la vista de mercado."""
    trm = pd.read_csv(c.TRM_CSV, parse_dates=["fecha"]).set_index("fecha")["trm"]
    crudo = pd.read_excel(c.PINK_SHEET_XLSX, sheet_name="Monthly Prices", header=None)
    nombres = crudo.iloc[4].astype(str).str.replace("*", "", regex=False).str.strip().str.lower()
    columnas = {"urea_usd": "urea", "dap_usd": "dap", "kcl_usd": "potassium chloride", "tsp_usd": "tsp"}
    posiciones = [nombres[nombres == v].index[0] for v in columnas.values()]
    tabla = crudo.iloc[6:, [0] + posiciones].copy()
    tabla.columns = ["periodo"] + list(columnas)
    tabla["fecha"] = pd.to_datetime(tabla["periodo"].astype(str).str.replace("M", "-"),
                                    format="%Y-%m", errors="coerce")
    tabla = tabla.dropna(subset=["fecha"]).set_index("fecha")[list(columnas)]
    tabla = tabla.apply(pd.to_numeric, errors="coerce")
    mercado = pd.concat([trm.rename("trm"), tabla], axis=1).sort_index().loc["2018-01-01":]
    return mercado.dropna(how="all").round(2)


def correr():
    c.PROCESSED.mkdir(parents=True, exist_ok=True)
    c.REPORTES.mkdir(parents=True, exist_ok=True)
    d = cargar_indice()
    exo = cargar_exogenas(d)
    calidad = reporte_calidad(d)
    calidad["comparacion_datos_abiertos"] = comparar_con_api(d)

    d[COLUMNAS_INDICE].round(4).to_csv(c.PROCESSED / "indice_mensual.csv")
    exo.round(4).to_csv(c.PROCESSED / "exogenas_mensual.csv")
    precios, contraste = preparar_sipsa()
    precios.to_csv(c.PROCESSED / "sipsa_precios.csv", index=False)
    contraste.round(3).to_csv(c.PROCESSED / "sipsa_contraste.csv")
    preparar_mercado().to_csv(c.PROCESSED / "mercado_mensual.csv", index_label="fecha")

    mapa = {"Fertilizantes": "T_Fertilizantes", "Herbicidas": "T_Herbicidas",
            "Fungicidas": "T_Fungicidas", "Insecticidas": "T_Insecticidas"}
    corr = {}
    for grupo, col in mapa.items():
        corr[grupo] = round(float(np.log(contraste[grupo]).diff(12).corr(np.log(d[col]).diff(12))), 3)
    calidad["correlacion_variacion_12m_sipsa_vs_upra"] = corr
    calidad["sipsa_ultima_fecha"] = precios["fecha"].max().strftime("%Y-%m")
    calidad["exogenas_ultima_fecha"] = {k: exo[k].last_valid_index().strftime("%Y-%m") for k in exo}
    (c.REPORTES / "calidad_datos.json").write_text(
        json.dumps(calidad, indent=2, ensure_ascii=False), encoding="utf-8")
    return calidad


if __name__ == "__main__":
    print(json.dumps(correr(), indent=2, ensure_ascii=False))
