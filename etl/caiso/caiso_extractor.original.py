"""
ETL CAISO — extrae precios DA/FMM para nodos de interconexión México-CAISO
(CFEROA=ROA, CFETIJ=TJI, Imperial Valley=IVY) y los guarda en DATOS_CAISO.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pandas as pd
from datetime import timedelta

from etl.common.db_connection  import get_connection
from etl.caiso.caiso_api       import (
    get_da_prices, get_fmm_prices, get_load, get_solar,
    NODE_ROA, NODE_TJI, NODE_IVY, NODE_OMS,
)


# ── Extracción ────────────────────────────────────────────────────────────────
def extract_caiso(fecha_ini: str, fecha_fin: str) -> pd.DataFrame:
    """
    Extrae datos CAISO para [fecha_ini, fecha_fin].
    Retorna DataFrame con columnas de DATOS_CAISO.
    """
    print(f"[CAISO] Extrayendo {fecha_ini} -> {fecha_fin}")

    # DA prices para ROA y TJI
    print("[CAISO] DA prices ROA...")
    da_roa = get_da_prices(fecha_ini, fecha_fin, NODE_ROA).rename(
        columns={"precio_da": "DA_ROA"})

    print("[CAISO] DA prices TJI...")
    da_tji = get_da_prices(fecha_ini, fecha_fin, NODE_TJI).rename(
        columns={"precio_da": "DA_TJI"})

    # FMM (RT) prices para ROA y TJI
    print("[CAISO] FMM prices ROA...")
    fmm_roa = get_fmm_prices(fecha_ini, fecha_fin, NODE_ROA).rename(
        columns={"precio_fmm": "FMM_ROA"})

    print("[CAISO] FMM prices TJI...")
    fmm_tji = get_fmm_prices(fecha_ini, fecha_fin, NODE_TJI).rename(
        columns={"precio_fmm": "FMM_TJI"})

    # DA prices para IVY (PML en pesos — nota: OASIS da USD, se convierte con TC)
    print("[CAISO] DA prices IVY...")
    da_ivy = get_da_prices(fecha_ini, fecha_fin, NODE_IVY).rename(
        columns={"precio_da": "PML_IVY"})

    print("[CAISO] DA prices OMS...")
    da_oms = get_da_prices(fecha_ini, fecha_fin, NODE_OMS).rename(
        columns={"precio_da": "PML_OMS"})

    # Load y solar
    print("[CAISO] Load...")
    df_load = get_load(fecha_ini, fecha_fin).rename(columns={"load_mw": "LOAD_CAISO"})

    print("[CAISO] Solar...")
    df_solar = get_solar(fecha_ini, fecha_fin).rename(columns={"solar_mw": "SOLAR_CAISO"})

    # Esqueleto horario
    horas = pd.date_range(fecha_ini, fecha_fin + " 23:00", freq="h")
    df = pd.DataFrame({"fecha": horas})

    for parte in [da_roa, da_tji, fmm_roa, fmm_tji, da_ivy, da_oms, df_load, df_solar]:
        if parte is not None and not parte.empty:
            df = df.merge(parte, on="fecha", how="left")

    return df


# ── Upsert ────────────────────────────────────────────────────────────────────
def upsert_caiso(df: pd.DataFrame) -> None:
    """Inserta o actualiza filas en XTS.dbo.DATOS_CAISO."""
    if df.empty:
        print("[CAISO] Sin datos para guardar.")
        return

    conn   = get_connection("XTS")
    cursor = conn.cursor()

    caiso_cols = ["DA_ROA", "DA_TJI", "FMM_ROA", "FMM_TJI",
                  "PML_IVY", "PML_OMS", "LOAD_CAISO", "SOLAR_CAISO"]
    update_cols = [c for c in caiso_cols if c in df.columns]

    for _, row in df.iterrows():
        cursor.execute(
            "SELECT COUNT(*) FROM DATOS_CAISO WHERE fecha = ?", row["fecha"])
        existe = cursor.fetchone()[0]

        col_vals = {c: (float(row[c]) if pd.notna(row.get(c)) else None)
                    for c in update_cols}

        if existe:
            sets = ", ".join(f"{c} = ?" for c, v in col_vals.items() if v is not None)
            vals = [v for v in col_vals.values() if v is not None]
            if sets:
                cursor.execute(
                    f"UPDATE DATOS_CAISO SET {sets} WHERE fecha = ?",
                    *vals, row["fecha"]
                )
        else:
            filled = {c: v for c, v in col_vals.items() if v is not None}
            cols   = ["fecha"] + list(filled.keys())
            vals   = [row["fecha"]] + list(filled.values())
            ph     = ", ".join("?" * len(vals))
            cursor.execute(
                f"INSERT INTO DATOS_CAISO ({', '.join(cols)}) VALUES ({ph})",
                *vals
            )

    conn.commit()
    cursor.close()
    conn.close()
    print(f"[CAISO] {len(df)} filas guardadas en DATOS_CAISO.")
