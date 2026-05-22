"""
Backfill DATOS_CAISO en dos fases:
  Fase 1 — Patch PML_IVY/OMS en 26 dias con nulls (2021-2025)
  Fase 2 — Backfill completo 2024-07-05 -> hoy
            (DA_ROA, DA_TJI, FMM_ROA, FMM_TJI, PML_IVY, PML_OMS, LOAD, SOLAR)

Ejecutar desde la carpeta raiz:
    python scripts/backfill_caiso.py
"""
import sys, os, pyodbc, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import date, datetime, timedelta
import pandas as pd
import urllib3
urllib3.disable_warnings()

from etl.caiso.caiso_api import (
    get_da_prices, get_fmm_prices, get_load, get_solar, get_pml_cenace,
    NODE_ROA, NODE_TJI, NODE_IVY, NODE_OMS,
)

# ── Config ─────────────────────────────────────────────────────────────────────
DB_OFFICE = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=100.70.216.12;DATABASE=XTS;"
    "UID=sa;PWD=XTS_operations.XiiX;Connection Timeout=10;"
)

# Fase 2: backfill completo desde el mismo inicio que ERCOT
FASE2_INI = date(2024, 7, 5)
FASE2_FIN = date.today()

# Dias con PML null (detectados por query)
DIAS_NULL_PML = [
    date(2021, 3, 14),
    date(2025, 3, 10), date(2025, 3, 11), date(2025, 3, 12),
    date(2025, 3, 14), date(2025, 3, 15), date(2025, 3, 16),
    date(2025, 3, 17), date(2025, 3, 18), date(2025, 3, 19),
    date(2025, 3, 20), date(2025, 3, 21), date(2025, 3, 22),
    date(2025, 3, 23), date(2025, 3, 24), date(2025, 3, 28),
    date(2025, 4,  2), date(2025, 4,  5), date(2025, 4,  6),
    date(2025, 4,  7),
    date(2025, 6, 29), date(2025, 6, 30),
    date(2025, 7,  5), date(2025, 7, 18), date(2025, 7, 29),
    date(2025, 9,  5),
]

# ── DB con reconexion ──────────────────────────────────────────────────────────
def db_execute(sql, vals, retries=3):
    for attempt in range(retries):
        try:
            conn = pyodbc.connect(DB_OFFICE)
            cur  = conn.cursor()
            cur.execute(sql, vals)
            conn.commit()
            rc = cur.rowcount
            conn.close()
            return rc
        except pyodbc.OperationalError as e:
            if attempt < retries - 1:
                print(f"  Reconectando DB ({e})...", flush=True)
                time.sleep(3)
            else:
                raise

def upsert_row(fecha_dt, col_vals: dict):
    """UPDATE si existe, INSERT si no. col_vals = {col: valor}."""
    col_vals = {k: v for k, v in col_vals.items() if v is not None and not (isinstance(v, float) and pd.isna(v))}
    if not col_vals:
        return

    sets = ", ".join(f"{c}=?" for c in col_vals)
    vals = list(col_vals.values())

    rc = db_execute(
        f"UPDATE dbo.DATOS_CAISO SET {sets} WHERE fecha=?",
        vals + [fecha_dt],
    )
    if rc == 0:
        cols = ["fecha"] + list(col_vals.keys())
        ph   = ", ".join(["?"] * len(cols))
        db_execute(
            f"INSERT INTO dbo.DATOS_CAISO ({', '.join(cols)}) VALUES ({ph})",
            [fecha_dt] + vals,
        )

# ── PML CENACE en chunks de 7 dias ────────────────────────────────────────────
def fetch_pml_range(fecha_ini: date, fecha_fin: date, nodo: str) -> dict:
    """Retorna dict {datetime: pml} para el rango, llamando en chunks de 7 dias."""
    result = {}
    cur = fecha_ini
    while cur <= fecha_fin:
        chunk_fin = min(cur + timedelta(days=6), fecha_fin)
        df = get_pml_cenace(cur.strftime("%Y-%m-%d"), chunk_fin.strftime("%Y-%m-%d"), nodo)
        if not df.empty:
            for _, row in df.iterrows():
                result[row["fecha"]] = row["pml"]
        cur = chunk_fin + timedelta(days=1)
        time.sleep(0.3)
    return result

# ── Fase 1: Patch PML nulls ────────────────────────────────────────────────────
def fase1_patch_pml():
    print("\n=== FASE 1: Patch PML_IVY / PML_OMS en dias con nulls ===", flush=True)
    total = 0
    for d in DIAS_NULL_PML:
        ds = d.strftime("%Y-%m-%d")
        pml_ivy = fetch_pml_range(d, d, NODE_IVY)
        pml_oms = fetch_pml_range(d, d, NODE_OMS)
        upd = 0
        for h in range(24):
            fecha_dt = datetime(d.year, d.month, d.day, h, 0, 0)
            cv = {}
            if fecha_dt in pml_ivy:
                cv["PML_IVY"] = pml_ivy[fecha_dt]
            if fecha_dt in pml_oms:
                cv["PML_OMS"] = pml_oms[fecha_dt]
            if cv:
                upsert_row(fecha_dt, cv)
                upd += 1
        total += upd
        print(f"  {ds}  ivy={len(pml_ivy)}h  oms={len(pml_oms)}h  upd={upd}  total={total}", flush=True)
    print(f"FASE 1 COMPLETA -- {total} filas actualizadas", flush=True)

# ── Fase 2: Backfill completo 2025-11-15 → hoy ───────────────────────────────
def fase2_backfill():
    print(f"\n=== FASE 2: Backfill completo {FASE2_INI} -> {FASE2_FIN} ===", flush=True)

    ini_s = FASE2_INI.strftime("%Y-%m-%d")
    fin_s = FASE2_FIN.strftime("%Y-%m-%d")

    print("Descargando DA ROA...", flush=True)
    da_roa = get_da_prices(ini_s, fin_s, NODE_ROA)
    print(f"  {len(da_roa)} filas", flush=True)

    print("Descargando DA TJI...", flush=True)
    da_tji = get_da_prices(ini_s, fin_s, NODE_TJI)
    print(f"  {len(da_tji)} filas", flush=True)

    print("Descargando FMM ROA...", flush=True)
    fmm_roa = get_fmm_prices(ini_s, fin_s, NODE_ROA)
    print(f"  {len(fmm_roa)} filas", flush=True)

    print("Descargando FMM TJI...", flush=True)
    fmm_tji = get_fmm_prices(ini_s, fin_s, NODE_TJI)
    print(f"  {len(fmm_tji)} filas", flush=True)

    print("Descargando PML IVY (chunks 7d)...", flush=True)
    pml_ivy = fetch_pml_range(FASE2_INI, FASE2_FIN, NODE_IVY)
    print(f"  {len(pml_ivy)} horas", flush=True)

    print("Descargando PML OMS (chunks 7d)...", flush=True)
    pml_oms = fetch_pml_range(FASE2_INI, FASE2_FIN, NODE_OMS)
    print(f"  {len(pml_oms)} horas", flush=True)

    print("Descargando Load CAISO...", flush=True)
    df_load = get_load(ini_s, fin_s)
    print(f"  {len(df_load)} filas", flush=True)

    print("Descargando Solar CAISO...", flush=True)
    df_solar = get_solar(ini_s, fin_s)
    print(f"  {len(df_solar)} filas", flush=True)

    # Indexar DataFrames por fecha para lookup rapido
    def to_dict(df, col):
        if df is None or df.empty or col not in df.columns:
            return {}
        return dict(zip(df["fecha"], df[col]))

    d_da_roa  = to_dict(da_roa,  "precio_da")
    d_da_tji  = to_dict(da_tji,  "precio_da")
    d_fmm_roa = to_dict(fmm_roa, "precio_fmm")
    d_fmm_tji = to_dict(fmm_tji, "precio_fmm")
    d_load    = to_dict(df_load,  "load_mw")
    d_solar   = to_dict(df_solar, "solar_mw")

    print("\nEscribiendo en DB hora a hora...", flush=True)
    cur = FASE2_INI
    total = 0
    while cur <= FASE2_FIN:
        day_upd = 0
        for h in range(24):
            fecha_dt = datetime(cur.year, cur.month, cur.day, h, 0, 0)
            cv = {
                "DA_ROA":    d_da_roa.get(fecha_dt),
                "DA_TJI":    d_da_tji.get(fecha_dt),
                "FMM_ROA":   d_fmm_roa.get(fecha_dt),
                "FMM_TJI":   d_fmm_tji.get(fecha_dt),
                "PML_IVY":   pml_ivy.get(fecha_dt),
                "PML_OMS":   pml_oms.get(fecha_dt),
                "LOAD_CAISO": d_load.get(fecha_dt),
                "SOLAR_CAISO": d_solar.get(fecha_dt),
            }
            if any(v is not None for v in cv.values()):
                upsert_row(fecha_dt, cv)
                day_upd += 1
        total += day_upd
        print(f"  {cur.strftime('%Y-%m-%d')}  upd={day_upd}  total={total}", flush=True)
        cur += timedelta(days=1)

    print(f"FASE 2 COMPLETA -- {total} filas escritas", flush=True)


# ── Main ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    fase1_patch_pml()
    fase2_backfill()
    print("\nBACKFILL CAISO COMPLETO")
