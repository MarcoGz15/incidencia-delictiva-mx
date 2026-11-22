"""
limpieza_y_filtro.py

Incidencia delictiva en México: comparativo 2025 vs 2024 por estado y tipo de delito.

Fuente: SESNSP, incidencia delictiva del fuero común a nivel estatal
        (datos.gob.mx, archivo INM_estatal_dic25.csv).
Unidad: carpetas de investigación (denuncias formales), no víctimas.

Qué hace:
    1. Carga el CSV crudo y lo recorta a 2024-2025.
    2. Limpia y estandariza columnas.
    3. Compara 2025 contra 2024 y clasifica cada caso como positivo (bajó) o negativo (subió).
    4. Guarda las tablas listas para Power BI en data/processed/.

Uso (desde la carpeta raíz del proyecto):
    python scripts/limpieza_y_filtro.py
"""

import pandas as pd
import numpy as np

# ----------------------------------------------------------------------
# Carga del CSV crudo
# ----------------------------------------------------------------------
RUTA_RAW = "data/raw/INM_estatal_dic25.csv"

# clave_ent se lee como texto para conservar el cero inicial ("01", "02", ...)
df = pd.read_csv(RUTA_RAW, dtype={"clave_ent": str})

# ----------------------------------------------------------------------
# Limpieza
# ----------------------------------------------------------------------

# Ventana de análisis: los dos años más recientes
df = df[df["anio"].isin([2024, 2025])].copy()

# Mes en número, para que Power BI ordene de enero a diciembre y no alfabéticamente
MESES = {"Enero": 1, "Febrero": 2, "Marzo": 3, "Abril": 4, "Mayo": 5, "Junio": 6,
         "Julio": 7, "Agosto": 8, "Septiembre": 9, "Octubre": 10, "Noviembre": 11, "Diciembre": 12}
df["mes_num"] = df["mes"].map(MESES)
assert df["mes_num"].isna().sum() == 0, "Hay meses con un nombre no reconocido"

df["fecha"] = pd.to_datetime(df["fecha"])

# Nombres de columnas cortos y claros.
# "estado" es el nombre corto (Coahuila); "estado_nombre_oficial" el completo (Coahuila de Zaragoza).
df = df.rename(columns={
    "clave_ent": "clave_entidad",
    "entidad_federativa": "estado",
    "entidad": "estado_nombre_oficial",
    "bien_juridico_afectado": "bien_juridico",
    "incidencia_delictiva": "incidencia",
})

# ----------------------------------------------------------------------
# Tabla de hechos y catálogos (modelo estrella para Power BI)
# ----------------------------------------------------------------------
df.to_csv("data/processed/fact_incidencia_mensual.csv", index=False, encoding="utf-8-sig")

dim_estado = df[["clave_entidad", "estado", "estado_nombre_oficial"]].drop_duplicates()
dim_estado.to_csv("data/processed/dim_estado.csv", index=False, encoding="utf-8-sig")

dim_delito = df[["bien_juridico", "tipo_delito"]].drop_duplicates()
dim_delito.to_csv("data/processed/dim_delito.csv", index=False, encoding="utf-8-sig")


# ----------------------------------------------------------------------
# Comparativo 2025 vs 2024
# ----------------------------------------------------------------------
def comparar(df, por):
    """Suma la incidencia por año y calcula la variación de 2025 contra 2024.

    Clasificación (variación = total 2025 - total 2024):
        < 0  -> "Positivo (bajó)"
        > 0  -> "Negativo (subió)"
        = 0  -> "Sin cambio"
    """
    comp = df.pivot_table(index=por, columns="anio", values="incidencia",
                          aggfunc="sum", fill_value=0).reset_index()
    comp.columns.name = None
    comp = comp.rename(columns={2024: "total_2024", 2025: "total_2025"})

    comp["variacion_abs"] = comp["total_2025"] - comp["total_2024"]
    comp["variacion_pct"] = comp["variacion_abs"] / comp["total_2024"]
    # Si en 2024 hubo 0 casos el porcentaje no está definido: se deja vacío en lugar de infinito
    comp["variacion_pct"] = comp["variacion_pct"].replace([np.inf, -np.inf], np.nan)

    comp["clasificacion"] = np.select(
        [comp["variacion_abs"] < 0, comp["variacion_abs"] > 0],
        ["Positivo (bajó)", "Negativo (subió)"],
        default="Sin cambio")

    return comp.sort_values("variacion_abs")


por_estado = comparar(df, ["clave_entidad", "estado"])
por_estado.to_csv("data/processed/comparativo_por_estado.csv", index=False, encoding="utf-8-sig")

por_delito = comparar(df, ["bien_juridico", "tipo_delito"])
por_delito.to_csv("data/processed/comparativo_por_delito.csv", index=False, encoding="utf-8-sig")

detalle = comparar(df, ["clave_entidad", "estado", "bien_juridico", "tipo_delito"])

# Con bases muy pequeñas el porcentaje engaña (pasar de 2 a 6 casos es +200 %).
# Esta bandera permite excluir esos casos al interpretar los porcentajes.
detalle["base_suficiente"] = detalle["total_2024"] >= 30
detalle.to_csv("data/processed/comparativo_estado_delito.csv", index=False, encoding="utf-8-sig")

# ----------------------------------------------------------------------
# Separación en positivos (bajó) y negativos (subió)
# ----------------------------------------------------------------------
positivos = detalle[detalle["clasificacion"] == "Positivo (bajó)"]
negativos = detalle[detalle["clasificacion"] == "Negativo (subió)"]

positivos.to_csv("data/processed/positivos_bajaron.csv", index=False, encoding="utf-8-sig")
negativos.to_csv("data/processed/negativos_subieron.csv", index=False, encoding="utf-8-sig")

# ----------------------------------------------------------------------
# Resumen en consola
# ----------------------------------------------------------------------
total_2024 = int(df.loc[df["anio"] == 2024, "incidencia"].sum())
total_2025 = int(df.loc[df["anio"] == 2025, "incidencia"].sum())

print(f"Total 2024: {total_2024:,} | Total 2025: {total_2025:,} | "
      f"Variación: {total_2025 - total_2024:+,} ({(total_2025 - total_2024) / total_2024:+.2%})")
print("Estados por clasificación:")
print(por_estado["clasificacion"].value_counts().to_string())
print(f"Tabla de hechos: {len(df):,} filas | Estados: {len(dim_estado)} | Delitos: {len(dim_delito)}")
print(f"Estado x delito: {len(detalle):,} filas | Positivos: {len(positivos)} | Negativos: {len(negativos)}")
print("Tablas guardadas en data/processed/")
