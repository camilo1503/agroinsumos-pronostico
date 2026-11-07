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


def descargar_todo(forzar=False):
    c.RAW.mkdir(parents=True, exist_ok=True)
    _bajar(c.URL_SIPSA, c.SIPSA_XLSX, forzar)
    _bajar(c.URL_PINK_SHEET, c.PINK_SHEET_XLSX, forzar)
    if forzar or not c.TRM_CSV.exists():
        r = requests.get(c.URL_TRM_API, headers=UA, timeout=120)
        r.raise_for_status()
        trm = pd.read_csv(io.StringIO(r.text), parse_dates=["mes"])
        trm.rename(columns={"mes": "fecha"}).to_csv(c.TRM_CSV, index=False)


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
