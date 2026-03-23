"""
ETL ERCOT — extrae precios DA/RT (DC_L, DC_R), carga y viento,
más pronósticos sintéticos de MarginalUnit, y los guarda en XTS.DATOS_ERCOT.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pandas as pd
from datetime import date, timedelta

from etl.common.db_connection import get_connection
from etl.ercot.ercot_api     import get_token, get_da_prices, get_rt_prices, get_load, get_wind
from etl.ercot.marginalunit_api import get_forecast_daily

# Nodos activos en ERCOT
NODOS = ["DC_L", "DC_R"]


# ── Extracción ────────────────────────────────────────────────────────────────
def extract_ercot(fecha_ini: str, fecha_fin: str) -> pd.DataFrame:
    """
    Extrae datos ERCOT del rango [fecha_ini, fecha_fin] (formato YYYY-MM-DD).
    Retorna un DataFrame diario con todas las columnas de DATOS_ERCOT
    que provienen de fuentes ERCOT/MarginalUnit.
    """
    print(f"[ERCOT] Obteniendo token...")
    token = get_token()

    # ── Precios DA ────────────────────────────────────────────────────────────
    print(f"[ERCOT] Precios DA {fecha_ini} → {fecha_fin}")
    da_dcl = get_da_prices(token, fecha_ini, fecha_fin, "DC_L").rename(
        columns={"precio_diario": "DA_DCL"})
    da_dcr = get_da_prices(token, fecha_ini, fecha_fin, "DC_R").rename(
        columns={"precio_diario": "DA_DCR"})

    # ── Precios RT ────────────────────────────────────────────────────────────
    print(f"[ERCOT] Precios RT {fecha_ini} → {fecha_fin}")
    rt_dcl = get_rt_prices(token, fecha_ini, fecha_fin, "DC_L").rename(
        columns={"precio_diario": "RT_DCL"})
    rt_dcr = get_rt_prices(token, fecha_ini, fecha_fin, "DC_R").rename(
        columns={"precio_diario": "RT_DCR"})

    # ── Carga ─────────────────────────────────────────────────────────────────
    print(f"[ERCOT] Carga del sistema {fecha_ini} → {fecha_fin}")
    df_load = get_load(token, fecha_ini, fecha_fin).rename(
        columns={"load_mw": "LOAD_ERCOT"})

    # ── Viento ────────────────────────────────────────────────────────────────
    print(f"[ERCOT] Generación eólica {fecha_ini} → {fecha_fin}")
    df_wind = get_wind(token, fecha_ini, fecha_fin).rename(
        columns={"wind_mw": "WIND_ERCOT"})

    # ── Pronósticos MarginalUnit ──────────────────────────────────────────────
    print(f"[MarginalUnit] Pronóstico DA {fecha_ini} → {fecha_fin}")
    try:
        df_da_fcst = get_forecast_daily("lmp_da", NODOS, fecha_ini, fecha_fin)
        if not df_da_fcst.empty:
            df_da_fcst = df_da_fcst.rename(columns={
                "DC_L_fcst": "DA_DCL_FCST",
                "DC_R_fcst": "DA_DCR_FCST",
            })
    except Exception as e:
        print(f"[MarginalUnit] DA forecast falló: {e}")
        df_da_fcst = pd.DataFrame()

    print(f"[MarginalUnit] Pronóstico RT {fecha_ini} → {fecha_fin}")
    try:
        df_rt_fcst = get_forecast_daily("lmp_rt", NODOS, fecha_ini, fecha_fin)
        if not df_rt_fcst.empty:
            df_rt_fcst = df_rt_fcst.rename(columns={
                "DC_L_fcst": "RT_DCL_FCST",
                "DC_R_fcst": "RT_DCR_FCST",
            })
    except Exception as e:
        print(f"[MarginalUnit] RT forecast falló: {e}")
        df_rt_fcst = pd.DataFrame()

    # ── Merge de todas las fuentes por fecha ─────────────────────────────────
    fechas = pd.date_range(fecha_ini, fecha_fin, freq="D").to_frame(
        index=False, name="fecha")

    df = fechas
    for parte in [da_dcl, da_dcr, rt_dcl, rt_dcr, df_load, df_wind]:
        if not parte.empty:
            df = df.merge(parte, on="fecha", how="left")

    if not df_da_fcst.empty:
        df = df.merge(df_da_fcst, on="fecha", how="left")
    if not df_rt_fcst.empty:
        df = df.merge(df_rt_fcst, on="fecha", how="left")

    return df


# ── Upsert en SQL Server ──────────────────────────────────────────────────────
def upsert_ercot(df: pd.DataFrame) -> None:
    """Inserta o actualiza filas en XTS.dbo.DATOS_ERCOT."""
    if df.empty:
        print("[ERCOT] Sin datos para guardar.")
        return

    conn = get_connection("XTS")
    cursor = conn.cursor()

    # Columnas que esta ETL puede actualizar (CENACE las llena por separado)
    ercot_cols = [
        "DA_DCL", "DA_DCR", "RT_DCL", "RT_DCR",
        "LOAD_ERCOT", "WIND_ERCOT",
        "DA_DCL_FCST", "DA_DCR_FCST",
        "RT_DCL_FCST", "RT_DCR_FCST",
    ]
    # Solo actualizar columnas que existen en el df
    update_cols = [c for c in ercot_cols if c in df.columns]

    for _, row in df.iterrows():
        fecha = row["fecha"].date() if hasattr(row["fecha"], "date") else row["fecha"]

        # Verificar si ya existe la fila
        cursor.execute(
            "SELECT COUNT(*) FROM DATOS_ERCOT WHERE FECHA = ?", fecha)
        existe = cursor.fetchone()[0]

        if existe:
            sets = ", ".join(
                f"{c} = ?" for c in update_cols
                if row.get(c) is not None and not _isnan(row.get(c))
            )
            vals = [
                row[c] for c in update_cols
                if row.get(c) is not None and not _isnan(row.get(c))
            ]
            if sets:
                cursor.execute(
                    f"UPDATE DATOS_ERCOT SET {sets} WHERE FECHA = ?",
                    *vals, fecha
                )
        else:
            all_cols = ["FECHA"] + [
                c for c in update_cols
                if row.get(c) is not None and not _isnan(row.get(c))
            ]
            all_vals = [fecha] + [
                row[c] for c in update_cols
                if row.get(c) is not None and not _isnan(row.get(c))
            ]
            placeholders = ", ".join("?" * len(all_vals))
            cursor.execute(
                f"INSERT INTO DATOS_ERCOT ({', '.join(all_cols)}) "
                f"VALUES ({placeholders})",
                *all_vals
            )

    conn.commit()
    cursor.close()
    conn.close()
    print(f"[ERCOT] {len(df)} registros guardados en DATOS_ERCOT.")


def _isnan(v) -> bool:
    try:
        import math
        return math.isnan(float(v))
    except (TypeError, ValueError):
        return False
