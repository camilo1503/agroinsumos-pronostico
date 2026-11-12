"""Descarga de fuentes oficiales y comparacion del anexo UPRA contra Datos Abiertos."""
import io

import pandas as pd
import requests

from . import config as c

UA = {"User-Agent": "Mozilla/5.0 (proyecto academico)"}


def _bajar(url, destino, forzar=False):
    if destino.exists() and not forzar:
        return destino
    r = requests.get(url, headers=UA, timeout=300)
    r.raise_for_status()
    destino.write_bytes(r.content)
    return destino


def descargar_mayoristas(forzar=False):
    """Baja un archivo por ano. Los anos cerrados se conservan; el actual y el anterior se refrescan."""
    c.MAYORISTAS.mkdir(parents=True, exist_ok=True)
    actual = pd.Timestamp.now().year
    urls = {**c.URL_MAYORISTAS, **{a: c.URL_MAYORISTAS_ANUAL.format(anio=a) for a in range(2024, actual + 1)}}
    for anio, url in urls.items():
        try:
            _bajar(url, c.MAYORISTAS / f"{anio}.xlsx", forzar and anio >= actual - 1)
        except requests.RequestException:
            if anio < actual:   # el archivo del ano en curso puede no existir en enero
                raise


def descargar_todo(forzar=False):
    c.RAW.mkdir(parents=True, exist_ok=True)
    descargar_mayoristas(forzar)
    _bajar(c.URL_SIPSA, c.SIPSA_XLSX, forzar)
    _bajar(c.URL_PINK_SHEET, c.PINK_SHEET_XLSX, forzar)
    if forzar or not c.TRM_CSV.exists():
        r = requests.get(c.URL_TRM_API, headers=UA, timeout=120)
        r.raise_for_status()
        trm = pd.read_csv(io.StringIO(r.text), parse_dates=["mes"])
        trm.rename(columns={"mes": "fecha"}).to_csv(c.TRM_CSV, index=False)


API_A_ANEXO = {
    "indice_total": "T_Índice", "total_fertilizantes": "T_Fertilizantes", "total_plaguicidas": "T_Plaguicidas",
    "total_otros": "T_Otros", "total_simples": "T_Simples", "total_compuestos": "T_Compuestos",
    "total_herbicidas": "T_Herbicidas", "total_fungicidas": "T_Fungicidas", "total_insecticidas": "T_Insecticidas",
}


def extender_con_api(indice):
    """Agrega los meses que Datos Abiertos ya publico y el anexo local aun no tiene."""
    try:
        r = requests.get(c.URL_UPRA_API, headers=UA, timeout=120)
        r.raise_for_status()
        api = pd.read_csv(io.StringIO(r.text), parse_dates=["fecha"]).set_index("fecha").sort_index()
    except (requests.RequestException, ValueError, KeyError):
        return indice
    nuevos = api.loc[api.index > indice.index.max(), list(API_A_ANEXO)].rename(columns=API_A_ANEXO)
    nuevos = nuevos.apply(pd.to_numeric, errors="coerce").replace(0, float("nan")).dropna(subset=["T_Índice"])
    if nuevos.empty:
        return indice
    return pd.concat([indice, nuevos]).asfreq("MS")


def comparar_con_api(indice):
    """Devuelve la mayor diferencia absoluta entre el anexo y la API oficial."""
    r = requests.get(c.URL_UPRA_API, headers=UA, timeout=120)
    r.raise_for_status()
    api = pd.read_csv(io.StringIO(r.text), parse_dates=["fecha"]).set_index("fecha").sort_index()
    comun = indice.index.intersection(api.index)
    dif = (indice.loc[comun, "T_Índice"] - api.loc[comun, "indice_total"]).abs()
    return {
        "meses_comparados": int(len(comun)),
        "diferencia_maxima": round(float(dif.max()), 4),
        "ultima_fecha_api": api.index.max().strftime("%Y-%m"),
    }
