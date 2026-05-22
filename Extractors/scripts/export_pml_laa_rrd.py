"""
Exporta PML MDA de nodos 06LAA-138 y 06RRD-138 a Excel.
Intenta BD primero (PML.MDA_D), luego CENACE API.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pandas as pd
import requests, json, time
import urllib3
from datetime import date, datetime, timedelta

urllib3.disable_warnings()

FECHA_INI = date(2026, 3, 14)
FECHA_FIN = date(2026, 3, 18)
OUT = os.path.join(os.path.dirname(__file__), "..", "PML_LAA_RRD_14_18mar2026.xlsx")

DB = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=100.70.216.12;DATABASE=XTS;"
    "UID=sa;PWD=XTS_operations.XiiX;Connection Timeout=10;"
)
DB_PML = DB.replace("DATABASE=XTS", "DATABASE=PML")

CENACE_BASE = "https://ws01.cenace.gob.mx:8082/SWPML/SIM"


# ── Intento 1: DATOS_ERCOT (columnas PML_LAA / PML_RRD) ─────────────────────
def from_datos_ercot():
    import pyodbc
    try:
        conn = pyodbc.connect(DB)
        df = pd.read_sql(
            """
            SELECT fecha, PML_LAA, PML_RRD
            FROM dbo.DATOS_ERCOT
            WHERE CAST(fecha AS DATE) BETWEEN ? AND ?
              AND (PML_LAA IS NOT NULL OR PML_RRD IS NOT NULL)
            ORDER BY fecha
            """,
            conn, params=[FECHA_INI, FECHA_FIN],
        )
        conn.close()
        if not df.empty:
            print(f"[BD] DATOS_ERCOT: {len(df)} filas")
            return df
    except Exception as e:
        print(f"[BD] DATOS_ERCOT error: {e}")
    return None


# ── Intento 2: PML.MDA_D ─────────────────────────────────────────────────────
def from_pml_mda():
    import pyodbc
    try:
        conn = pyodbc.connect(DB_PML)
        df = pd.read_sql(
            """
            SELECT fecha, hora,
                   MAX(CASE WHEN Zona_Carga = '06LAA-138' THEN PZ END) AS PML_LAA,
                   MAX(CASE WHEN Zona_Carga = '06LAA-138' THEN PZ_ENE END) AS PML_LAA_ENE,
                   MAX(CASE WHEN Zona_Carga = '06LAA-138' THEN PZ_PER END) AS PML_LAA_PER,
                   MAX(CASE WHEN Zona_Carga = '06LAA-138' THEN PZ_CNG END) AS PML_LAA_CNG,
                   MAX(CASE WHEN Zona_Carga = '06RRD-138' THEN PZ END) AS PML_RRD,
                   MAX(CASE WHEN Zona_Carga = '06RRD-138' THEN PZ_ENE END) AS PML_RRD_ENE,
                   MAX(CASE WHEN Zona_Carga = '06RRD-138' THEN PZ_PER END) AS PML_RRD_PER,
                   MAX(CASE WHEN Zona_Carga = '06RRD-138' THEN PZ_CNG END) AS PML_RRD_CNG
            FROM dbo.MDA_D
            WHERE fecha BETWEEN ? AND ?
              AND Zona_Carga IN ('06LAA-138', '06RRD-138')
            GROUP BY fecha, hora
            ORDER BY fecha, hora
            """,
            conn, params=[FECHA_INI, FECHA_FIN],
        )
        conn.close()
        if not df.empty:
            print(f"[BD] PML.MDA_D: {len(df)} filas")
            return df
    except Exception as e:
        print(f"[BD] PML.MDA_D error: {e}")
    return None


# ── Intento 3: CENACE API ─────────────────────────────────────────────────────
def from_cenace_api():
    print("[API] Consultando CENACE API...")
    ini = FECHA_INI.strftime("%Y/%m/%d")
    fin = FECHA_FIN.strftime("%Y/%m/%d")

    rows = []
    for nodo in ["06LAA-138", "06RRD-138"]:
        url = f"{CENACE_BASE}/SIN/MDA/{nodo}/{ini}/{fin}/JSON"
        try:
            resp = requests.get(url, timeout=60, verify=False)
            data = resp.json()
            resultado = data.get("Resultados", [{}])[0]
            valores   = resultado.get("Valores", [])
            for v in valores:
                rows.append({
                    "nodo":    nodo,
                    "fecha":   v.get("fecha"),
                    "hora":    int(v.get("hora", 0)),
                    "pml":     float(v.get("pml", 0) or 0),
                    "pml_ene": float(v.get("pml_ene", 0) or 0),
                    "pml_per": float(v.get("pml_per", 0) or 0),
                    "pml_cng": float(v.get("pml_cng", 0) or 0),
                })
            print(f"  {nodo}: {len(valores)} valores")
            time.sleep(0.5)
        except Exception as e:
            print(f"  {nodo} error: {e}")

    if not rows:
        return None

    df = pd.DataFrame(rows)
    # Pivot: una fila por (fecha, hora), columnas por nodo
    laa = df[df["nodo"] == "06LAA-138"].rename(columns={
        "pml": "PML_LAA", "pml_ene": "PML_LAA_ENE",
        "pml_per": "PML_LAA_PER", "pml_cng": "PML_LAA_CNG"
    }).drop(columns=["nodo"])
    rrd = df[df["nodo"] == "06RRD-138"].rename(columns={
        "pml": "PML_RRD", "pml_ene": "PML_RRD_ENE",
        "pml_per": "PML_RRD_PER", "pml_cng": "PML_RRD_CNG"
    }).drop(columns=["nodo"])

    merged = pd.merge(laa, rrd, on=["fecha", "hora"], how="outer")
    print(f"[API] Total: {len(merged)} filas")
    return merged


# ── Main ──────────────────────────────────────────────────────────────────────
print(f"Exportando PML LAA/RRD  {FECHA_INI} -> {FECHA_FIN}")

df = from_datos_ercot()
if df is None:
    df = from_pml_mda()
if df is None:
    df = from_cenace_api()

if df is None or df.empty:
    print("ERROR: No se obtuvieron datos de ninguna fuente.")
    sys.exit(1)

# Normalizar columnas si vienen de DATOS_ERCOT
if "fecha" in df.columns and "hora" not in df.columns:
    df["fecha"] = pd.to_datetime(df["fecha"])
    df.insert(0, "Fecha", df["fecha"].dt.strftime("%Y-%m-%d"))
    df.insert(1, "Hora",  df["fecha"].dt.strftime("%H:00"))
    df = df.drop(columns=["fecha"])
else:
    df.insert(0, "Fecha", df["fecha"])
    df.insert(1, "Hora",  df["hora"].apply(lambda h: f"{int(h)-1:02d}:00"))
    df = df.drop(columns=["fecha", "hora"])

# Renombrar columnas a nombres legibles
rename = {
    "PML_LAA":     "LAA PML (MXN/MWh)",
    "PML_LAA_ENE": "LAA Energia",
    "PML_LAA_PER": "LAA Perdidas",
    "PML_LAA_CNG": "LAA Congestion",
    "PML_RRD":     "RRD PML (MXN/MWh)",
    "PML_RRD_ENE": "RRD Energia",
    "PML_RRD_PER": "RRD Perdidas",
    "PML_RRD_CNG": "RRD Congestion",
}
df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})

# Exportar
with pd.ExcelWriter(OUT, engine="openpyxl") as writer:
    df.to_excel(writer, index=False, sheet_name="PML MDA")

    # Hoja resumen diario
    num_cols = [c for c in df.columns if "MXN" in c or "Energia" in c or "Perdidas" in c or "Congestion" in c]
    if "Fecha" in df.columns and num_cols:
        resumen = df.groupby("Fecha")[num_cols].agg(["mean", "max", "min"]).round(2)
        resumen.columns = [f"{c[0]} {c[1]}" for c in resumen.columns]
        resumen.reset_index().to_excel(writer, index=False, sheet_name="Resumen Diario")

print(f"\nExportado: {OUT}  ({len(df)} filas)")
print(f"Columnas:  {list(df.columns)}")
