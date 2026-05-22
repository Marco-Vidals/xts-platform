"""
Exporta POE (AMM) + LBR (CENACE 09LBR-230) de Guatemala a Excel.
Intenta BD primero (dbo.GTM), luego AMM Excel + CENACE API.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pandas as pd
import requests, json, io, time
import urllib.request
import urllib3
from datetime import date, timedelta

urllib3.disable_warnings()

FECHA_INI = date(2026, 3, 14)
FECHA_FIN = date(2026, 3, 18)
OUT = os.path.join(os.path.dirname(__file__), "..", "GTM_POE_LBR_14_18mar2026.xlsx")

DB = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=100.70.216.12;DATABASE=XTS;"
    "UID=sa;PWD=XTS_operations.XiiX;Connection Timeout=10;"
)
CENACE_BASE = "https://ws01.cenace.gob.mx:8082/SWPML/SIM"
NODO_LBR    = "09LBR-230"

_MESES = {
    "01": "ENERO",   "02": "FEBRERO",  "03": "MARZO",
    "04": "ABRIL",   "05": "MAYO",     "06": "JUNIO",
    "07": "JULIO",   "08": "AGOSTO",   "09": "SEPTIEMBRE",
    "10": "OCTUBRE", "11": "NOVIEMBRE","12": "DICIEMBRE",
}


# ── Intento 1: BD dbo.GTM ─────────────────────────────────────────────────────
def from_db():
    import pyodbc
    try:
        conn = pyodbc.connect(DB)
        df = pd.read_sql(
            """
            SELECT fecha, PPOE, LBR
            FROM dbo.GTM
            WHERE CAST(fecha AS DATE) BETWEEN ? AND ?
              AND (PPOE IS NOT NULL OR LBR IS NOT NULL)
            ORDER BY fecha
            """,
            conn, params=[FECHA_INI, FECHA_FIN],
        )
        conn.close()
        if not df.empty:
            print(f"[BD] dbo.GTM: {len(df)} filas")
            return df
    except Exception as e:
        print(f"[BD] GTM error: {e}")
    return None


# ── AMM Excel — POE ───────────────────────────────────────────────────────────
def _amm_url(d: date) -> str:
    mm  = d.strftime("%m")
    return (
        f"https://www.amm.org.gt/pdfs2/programas_despacho/"
        f"01_PROGRAMAS_DE_DESPACHO_DIARIO/{d.year}/"
        f"01_PROGRAMAS_DE_DESPACHO_DIARIO/{mm}_{_MESES[mm]}/"
        f"WEB{d.strftime('%d%m%Y')}.xlsx"
    )

def get_poe(d: date):
    url = _amm_url(d)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
        df = pd.read_excel(io.BytesIO(data), sheet_name="POE", skiprows=8, header=None)
        poe = pd.to_numeric(df.iloc[0:24, 4], errors="coerce").tolist()
        print(f"  POE {d}: {sum(1 for v in poe if v is not None)} valores")
        return poe
    except Exception as e:
        print(f"  POE {d} error: {e}")
        return [None] * 24


# ── CENACE API — LBR ─────────────────────────────────────────────────────────
def get_lbr_range(ini: date, fin: date):
    url = (f"{CENACE_BASE}/SIN/MDA/{NODO_LBR}/"
           f"{ini.year}/{ini.month:02d}/{ini.day:02d}/"
           f"{fin.year}/{fin.month:02d}/{fin.day:02d}/JSON")
    try:
        resp = requests.get(url, timeout=60, verify=False)
        valores = resp.json()["Resultados"][0]["Valores"]
        result = {}
        for v in valores:
            f_str = v.get("fecha")
            h     = int(v.get("hora", 1)) - 1   # hora 1-24 -> indice 0-23
            try:
                d = date.fromisoformat(f_str)
                result[(d, h)] = float(v.get("pml", 0) or 0)
            except Exception:
                pass
        print(f"  LBR {ini}->{fin}: {len(result)} valores")
        return result
    except Exception as e:
        print(f"  LBR error: {e}")
        return {}


# ── Intento 2: AMM + CENACE API ──────────────────────────────────────────────
def from_api():
    print("[API] Descargando POE (AMM) y LBR (CENACE)...")

    # LBR en un solo request (5 dias, dentro del limite de 7)
    lbr_dict = get_lbr_range(FECHA_INI, FECHA_FIN)

    rows = []
    d = FECHA_INI
    while d <= FECHA_FIN:
        poe = get_poe(d)
        time.sleep(0.3)
        for h in range(24):
            lbr = lbr_dict.get((d, h))
            rows.append({
                "fecha": d,
                "hora":  h,
                "PPOE":  poe[h],
                "LBR":   lbr,
            })
        d += timedelta(days=1)

    return pd.DataFrame(rows) if rows else None


# ── Main ──────────────────────────────────────────────────────────────────────
print(f"Exportando GTM POE/LBR  {FECHA_INI} -> {FECHA_FIN}")

df = from_db()
source = "BD"

if df is None or df.empty:
    df = from_api()
    source = "API"

if df is None or df.empty:
    print("ERROR: sin datos.")
    sys.exit(1)

# Normalizar columnas
if "fecha" in df.columns and "hora" not in df.columns:
    df["fecha"] = pd.to_datetime(df["fecha"])
    df["Fecha"] = df["fecha"].dt.strftime("%Y-%m-%d")
    df["Hora"]  = df["fecha"].dt.strftime("%H:00")
    df = df.drop(columns=["fecha"])
else:
    df["Fecha"] = df["fecha"].apply(lambda x: x.strftime("%Y-%m-%d") if hasattr(x, 'strftime') else str(x))
    df["Hora"]  = df["hora"].apply(lambda h: f"{int(h):02d}:00")
    df = df.drop(columns=["fecha", "hora"])

# Columnas finales
cols_order = ["Fecha", "Hora", "PPOE", "LBR"]
df = df[[c for c in cols_order if c in df.columns]]
df = df.rename(columns={
    "PPOE": "POE AMM (USD/MWh)",
    "LBR":  "LBR CENACE 09LBR-230 (MXN/MWh)",
})

# Exportar
with pd.ExcelWriter(OUT, engine="openpyxl") as writer:
    df.to_excel(writer, index=False, sheet_name="Guatemala")

    # Resumen diario
    num_cols = ["POE AMM (USD/MWh)", "LBR CENACE 09LBR-230 (MXN/MWh)"]
    num_cols = [c for c in num_cols if c in df.columns]
    if num_cols and "Fecha" in df.columns:
        res = df.groupby("Fecha")[num_cols].agg(["mean", "max", "min"]).round(3)
        res.columns = [f"{c[0].split('(')[0].strip()} {c[1]}" for c in res.columns]
        res.reset_index().to_excel(writer, index=False, sheet_name="Resumen Diario")

print(f"\nExportado ({source}): {OUT}  ({len(df)} filas)")
print(f"Columnas: {list(df.columns)}")
