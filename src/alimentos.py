"""Precios mayoristas de alimentos de la canasta familiar (SIPSA, DANE), resumidos por mes y departamento."""
import re
import unicodedata

import pandas as pd

from . import config as c

GRUPOS = {
    "verduras y hortalizas": "Verduras y hortalizas", "frutas": "Frutas",
    "tuberculos, raices y platanos": "Tubérculos y plátanos", "granos y cereales": "Granos y cereales",
    "carnes": "Carnes", "lacteos y huevos": "Lácteos y huevos", "pescados": "Pescados", "procesados": "Abarrotes",
}
# Productos de mayor consumo en los hogares, con el nombre que usa SIPSA.
CANASTA = [
    "Papa criolla limpia", "Papa capira", "Papa única", "Papa parda pastusa", "Plátano hartón verde",
    "Yuca criolla", "Yuca ICA", "Arracacha amarilla",
    "Tomate chonto", "Cebolla cabezona blanca", "Cebolla junca", "Zanahoria", "Pimentón", "Habichuela",
    "Arveja verde en vaina", "Lechuga Batavia", "Repollo blanco", "Ahuyama", "Cilantro", "Ajo", "Pepino cohombro",
    "Banano criollo", "Naranja Valencia", "Limón Tahití", "Limón común", "Mango Tommy", "Guayaba pera",
    "Mora de Castilla", "Tomate de árbol", "Lulo", "Papaya Maradol", "Piña gold", "Aguacate papelillo", "Maracuyá",
    "Arroz de primera", "Lenteja importada", "Fríjol cargamanto rojo", "Maíz blanco trillado",
    "Arveja verde seca importada", "Garbanzo importado",
    "Pechuga de pollo", "Pierna pernil con rabadilla", "Carne de res, sobrebarriga", "Carne de res, bola de pierna",
    "Carne de res, costilla", "Carne de cerdo, lomo sin hueso", "Carne de cerdo, costilla",
    "Huevo rojo AA", "Huevo rojo A", "Queso campesino", "Queso costeño", "Leche en polvo",
    "Tilapia roja entera fresca", "Bocachico importado congelado",
    "Aceite vegetal mezcla", "Azúcar sulfitada", "Panela cuadrada morena", "Sal yodada", "Harina de trigo",
    "Harina precocida de maíz", "Pastas alimenticias", "Café molido", "Chocolate dulce", "Lomitos de atún en lata",
]
DEPARTAMENTOS = {
    "bogota, d.c.": "Bogotá, D.C.", "valle del cauca": "Valle del Cauca", "norte de santander": "Norte de Santander",
    "la guajira": "La Guajira", "narino": "Nariño", "quindio": "Quindío", "boyaca": "Boyacá", "caqueta": "Caquetá",
    "cordoba": "Córdoba", "bolivar": "Bolívar", "atlantico": "Atlántico", "choco": "Chocó",
    "archipielago de san andres, providencia y santa catalina": "San Andrés",
}


def _norm(texto):
    sin = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", sin).strip().lower()


def _departamento(nombre):
    n = _norm(nombre)
    return DEPARTAMENTOS.get(n, n.title())


def presentacion(producto):
    n = _norm(producto)
    if n.startswith("huevo"):
        return "1 unidad"
    if n.startswith("aceite"):
        return "1 litro"
    return "1 kilogramo"


def leer_archivo(ruta):
    """Devuelve las filas de precios y, si el archivo la trae, la tabla de mercado a departamento."""
    libro = pd.ExcelFile(ruta)
    partes, fuentes = [], {}
    for hoja in libro.sheet_names:
        d = libro.parse(hoja, header=None, dtype=object)
        if hoja == "Fuentes":
            fuentes = {str(m).strip(): _departamento(dep) for m, dep in zip(d[0][1:], d[1][1:])}
            continue
        fila = d.index[d[0].astype(str).str.strip() == "Fecha"]
        if not len(fila):
            continue
        cab = [str(v).strip() for v in d.loc[fila[0]]]
        t = d.loc[fila[0] + 1:].copy()
        t.columns = cab
        mercado = "Mercado" if "Mercado" in cab else "Fuente"
        precio = next(col for col in cab if col.startswith("Precio"))
        t = t[["Fecha", "Grupo", "Producto", mercado, precio]]
        t.columns = ["fecha", "grupo", "producto", "mercado", "precio"]
        partes.append(t)
    return (pd.concat(partes, ignore_index=True) if partes else pd.DataFrame()), fuentes


def resumir(crudo, fuentes):
    """Mediana mensual por producto y departamento, y mediana nacional entre mercados."""
    s = crudo.copy()
    s["fecha"] = pd.to_datetime(s["fecha"], errors="coerce")
    s["precio"] = pd.to_numeric(s["precio"], errors="coerce")
    s = s.dropna(subset=["fecha", "precio"])
    s = s[s["precio"] > 0].copy()
    s["fecha"] = s["fecha"].dt.to_period("M").dt.to_timestamp()
    for col in ("producto", "mercado"):
        s[col] = s[col].astype(str).str.strip()
    s["grupo"] = s["grupo"].map(lambda g: GRUPOS.get(_norm(g)))
    elegidos = {_norm(p): p for p in CANASTA}
    s["producto"] = s["producto"].map(lambda p: elegidos.get(_norm(p)))
    s = s.dropna(subset=["grupo", "producto"])
    s["presentacion"] = s["producto"].map(presentacion)
    en_parentesis = s["mercado"].str.extract(r"\(([^)]+)\)")[0]
    s["departamento"] = s["mercado"].map(fuentes).fillna(en_parentesis.map(_departamento, na_action="ignore"))

    claves = ["fecha", "grupo", "producto", "presentacion"]
    nacional = s.groupby(claves, as_index=False).agg(precio=("precio", "median"), n_registros=("precio", "size"))
    nacional["departamento"] = "Nacional"
    por_dep = s.dropna(subset=["departamento"]).groupby(claves + ["departamento"], as_index=False).agg(
        precio=("precio", "median"), n_registros=("precio", "size"))
    salida = pd.concat([nacional, por_dep], ignore_index=True)
    salida["precio"] = salida["precio"].round(2)
    return salida.sort_values(claves + ["departamento"]).reset_index(drop=True)


def preparar():
    partes, fuentes = [], {}
    for ruta in sorted(c.MAYORISTAS.glob("*.xlsx")):
        filas, f = leer_archivo(ruta)
        partes.append(filas)
        fuentes.update(f)
    return resumir(pd.concat(partes, ignore_index=True), fuentes)
