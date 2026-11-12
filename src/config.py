from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
RAW = RAIZ / "data" / "raw"
PROCESSED = RAIZ / "data" / "processed"
REPORTES = RAIZ / "reports"
FIGURAS = REPORTES / "figures"
WEB_DATA = RAIZ / "web" / "data"

ANEXO_UPRA = RAW / "AnexoAgo26_20260921.xlsx"
SIPSA_XLSX = RAW / "sipsa_departamento.xlsx"
PINK_SHEET_XLSX = RAW / "CMO-Historical-Data-Monthly.xlsx"
TRM_CSV = RAW / "trm_mensual.csv"
MAYORISTAS = RAW / "mayoristas"

# Series historicas de precios mayoristas de alimentos (DANE, SIPSA). Los anos cerrados no cambian.
_DANE = "https://www.dane.gov.co/files"
URL_MAYORISTAS = {
    **{a: f"{_DANE}/investigaciones/agropecuario/sipsa/series-historicas/series-historicas-precios-mayoristas-{a}.xlsx"
       for a in range(2018, 2023)},
    2023: f"{_DANE}/operaciones/SIPSA/anex-SIPSA-SerieHistoricaMayorista-Dic2023.xlsx",
}
URL_MAYORISTAS_ANUAL = _DANE + "/operaciones/SIPSA/anex-SIPSA-SerieHistoricaMayorista-{anio}.xlsx"

URL_SIPSA = "https://www.dane.gov.co/files/operaciones/SIPSA/anex-SIPSAInsumos-SeriesHistoricasDep-2018-2026.xlsx"
URL_UPRA_API = "https://www.datos.gov.co/resource/gwbi-fnzs.csv?$limit=5000"
URL_TRM_API = (
    "https://www.datos.gov.co/resource/mcec-87by.csv?"
    "$select=date_trunc_ym(vigenciadesde) as mes,avg(valor) as trm"
    "&$group=mes&$order=mes&$limit=1000"
)
URL_PINK_SHEET = (
    "https://thedocs.worldbank.org/en/doc/74e8be41ceb20fa0da750cda2f6b9e4e-0050012026/"
    "related/CMO-Historical-Data-Monthly.xlsx"
)

HORIZONTE = 6
MIN_ENTRENAMIENTO = 36   # meses antes del primer origen de validacion
ORIGENES_PRUEBA = 12     # ultimos origenes, reservados para la prueba final

SERIES = {
    "total": "T_Índice",
    "fertilizantes": "T_Fertilizantes",
    "plaguicidas": "T_Plaguicidas",
}
CANDIDATOS = ["ets", "sarima", "ridge"]
REFERENCIAS = ["naive", "snaive"]
