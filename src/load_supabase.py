"""Carga series y resultados en Supabase y evalua las alertas de los usuarios.

Requiere SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY en el archivo .env.
Uso: python -m src.load_supabase [--sin-sipsa]
"""
import argparse
import json
import os

import numpy as np
import pandas as pd
import requests
from dotenv import load_dotenv

from . import config as c

COLUMNAS_INDICE = {
    "T_Índice": "indice_total", "T_Fertilizantes": "fertilizantes", "T_Plaguicidas": "plaguicidas",
    "T_Otros": "otros", "T_Simples": "simples", "T_Compuestos": "compuestos",
    "T_Herbicidas": "herbicidas", "T_Fungicidas": "fungicidas", "T_Insecticidas": "insecticidas",
}


class Cliente:
    def __init__(self):
        load_dotenv(c.RAIZ / ".env")
        self.base = os.environ["SUPABASE_URL"].rstrip("/") + "/rest/v1"
        llave = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
        self.s = requests.Session()
        self.s.headers.update({"apikey": llave, "Authorization": f"Bearer {llave}", "Content-Type": "application/json"})

    def upsert(self, tabla, filas, conflicto, lote=1000, devolver=False):
        prefer = "resolution=merge-duplicates," + ("return=representation" if devolver else "return=minimal")
        salida = []
        for i in range(0, len(filas), lote):
            r = self.s.post(f"{self.base}/{tabla}", params={"on_conflict": conflicto},
                            headers={"Prefer": prefer}, data=json.dumps(filas[i:i + lote], allow_nan=False))
            r.raise_for_status()
            if devolver:
                salida += r.json()
        return salida

    def rpc(self, funcion, cuerpo):
        r = self.s.post(f"{self.base}/rpc/{funcion}", data=json.dumps(cuerpo))
        r.raise_for_status()
        return r.json()


def _registros(df):
    df = df.astype(object).where(df.notna(), None)
    return df.to_dict(orient="records")


def cargar(incluir_sipsa=True):
    cli = Cliente()

    ind = pd.read_csv(c.PROCESSED / "indice_mensual.csv", parse_dates=["fecha"]).rename(columns=COLUMNAS_INDICE)
    ind["fecha"] = ind["fecha"].dt.strftime("%Y-%m-%d")
    cli.upsert("indice_mensual", _registros(ind), "fecha")

    res = json.loads((c.REPORTES / "resultados.json").read_text(encoding="utf-8"))
    detalle = {k: res[k] for k in ("origenes", "pct_pronosticos_mejor_que_persistencia", "diebold_mariano_h6",
                                   "resumen", "versiones", "huella_datos")}
    corrida = cli.upsert("corrida_modelo", [{
        "fecha_corte": res["fecha_corte"], "ejecutado_en": res["ejecutado_en"],
        "modelo_seleccionado": res["modelo_seleccionado"], "nombre_modelo": res["nombre_modelo"],
        "supera_persistencia_validacion": res["supera_persistencia_validacion"],
        "supera_persistencia_prueba": res["supera_persistencia_prueba"],
        "cobertura_prueba": res["cobertura_prueba_pct"], "detalle": detalle,
    }], "fecha_corte", devolver=True)[0]
    cid = corrida["id"]

    m = pd.read_csv(c.REPORTES / "metricas.csv").drop(columns=["n"])
    m.insert(0, "corrida_id", cid)
    cli.upsert("metrica_modelo", _registros(m), "corrida_id,modelo,bloque,horizonte")

    filas = [{"corrida_id": cid, "serie": s, **p} for s, ps in res["pronostico"].items() for p in ps]
    cli.upsert("pronostico", filas, "corrida_id,serie,horizonte")

    bt = pd.read_csv(c.REPORTES / "backtest.csv").drop(columns=["escala"])
    bt.insert(0, "corrida_id", cid)
    cli.upsert("backtest_modelo", _registros(bt), "corrida_id,modelo,origen,horizonte")

    mer = pd.read_csv(c.PROCESSED / "mercado_mensual.csv")
    cli.upsert("mercado_mensual", _registros(mer), "fecha")

    if incluir_sipsa:
        pr = pd.read_csv(c.PROCESSED / "sipsa_precios.csv")
        cli.upsert("sipsa_precio", _registros(pr), "grupo,producto,presentacion,departamento,fecha")
        co = pd.read_csv(c.PROCESSED / "sipsa_contraste.csv").melt("fecha", var_name="grupo", value_name="valor").dropna()
        cli.upsert("sipsa_contraste", _registros(co), "grupo,fecha")

    nuevas = cli.rpc("evaluar_reglas", {"p_corrida_id": cid})
    print(f"Corrida {cid} cargada ({res['fecha_corte']}). Alertas nuevas: {nuevas}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--sin-sipsa", action="store_true")
    cargar(not p.parse_args().sin_sipsa)
