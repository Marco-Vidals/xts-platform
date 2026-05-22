"""
ETL ERCOT — extrae precios DA/RT (DC_L, DC_R), carga, viento y solar en
granularidad HORARIA y los guarda en XTS.dbo.DATOS_ERCOT (24 filas por día).
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import math
import pandas as pd
from datetime import timedelta

from etl.base.db               import get_connection
from etl.ercot.ercot_api       import get_token, get_da_prices, get_rt_prices, get_load, get_wind, get_solar
from etl.ercot.marginalunit_api import get_forecast_hourly
from etl.ercot.config          import NODOS_DATOS_ERCOT

NODOS = NODOS_DATOS_ERCOT  # ["DC_L", "DC_R"]


# ── Extracción ────────────────────────────────────────────────────────────────
def extract_ercot(fecha_ini: str, fecha_fin: str) -> pd.DataFrame:
    """
    Extrae datos ERCOT hora por hora para [fecha_ini, fecha_fin].
    Retorna DataFrame con columnas de DATOS_ERCOT provenientes de ERCOT/MarginalUnit.
    Incluye SOLAR_ERCOT desde NP4-745-CD.
    """
    print("[ERCOT] Obteniendo token...")
    token = get_token()

    # ── Precios DA (ya vienen horarios) ──────────────────────────────────────
    print(f"[ERCOT] DA prices {fecha_ini} -> {fecha_fin}")
    da_dcl = get_da_prices(token, fecha_ini, fecha_fin, "DC_L").rename(
        columns={"precio_hora": "DA_DCL"})
    da_dcr = get_da_prices(token, fecha_ini, fecha_fin, "DC_R").rename(
        columns={"precio_hora": "DA_DCR"})
    try:
        da_dce = get_da_prices(token, fecha_ini, fecha_fin, "DC_E").rename(
            columns={"precio_hora": "DA_DCE"})
    except Exception:
        da_dce = pd.DataFrame()  # DC_E cerrado — sin datos

    # ── Precios RT (15 min -> promedio horario) ────────────────────────────────
    print(f"[ERCOT] RT prices {fecha_ini} -> {fecha_fin}")
    rt_dcl = get_rt_prices(token, fecha_ini, fecha_fin, "DC_L").rename(
        columns={"precio_hora": "RT_DCL"})
    rt_dcr = get_rt_prices(token, fecha_ini, fecha_fin, "DC_R").rename(
        columns={"precio_hora": "RT_DCR"})
    try:
        rt_dce = get_rt_prices(token, fecha_ini, fecha_fin, "DC_E").rename(
            columns={"precio_hora": "RT_DCE"})
    except Exception:
        rt_dce = pd.DataFrame()  # DC_E cerrado — sin datos

    # ── Carga ─────────────────────────────────────────────────────────────────
    print(f"[ERCOT] Load {fecha_ini} -> {fecha_fin}")
    df_load = get_load(token, fecha_ini, fecha_fin).rename(
        columns={"load_mw": "LOAD_ERCOT"})

    # ── Viento ────────────────────────────────────────────────────────────────
    print(f"[ERCOT] Wind {fecha_ini} -> {fecha_fin}")
    df_wind = get_wind(token, fecha_ini, fecha_fin).rename(
        columns={"wind_mw": "WIND_ERCOT"})

    # ── Solar ─────────────────────────────────────────────────────────────────
    print(f"[ERCOT] Solar {fecha_ini} -> {fecha_fin}")
    try:
        df_solar = get_solar(token, fecha_ini, fecha_fin).rename(
            columns={"solar_mw": "SOLAR_ERCOT"})
    except Exception as e:
        print(f"[ERCOT] Solar falló (no crítico): {e}")
        df_solar = pd.DataFrame()

    # ── Pronósticos MarginalUnit (horarios) ───────────────────────────────────
    print(f"[MarginalUnit] Forecast DA {fecha_ini} -> {fecha_fin}")
    try:
        df_da_fcst = get_forecast_hourly("lmp_da", NODOS, fecha_ini, fecha_fin)
        if not df_da_fcst.empty:
            df_da_fcst = df_da_fcst.rename(columns={
                "DC_L_fcst": "DA_DCL_FCST",
                "DC_R_fcst": "DA_DCR_FCST",
            })
    except Exception as e:
        print(f"[MarginalUnit] DA forecast falló: {e}")
        df_da_fcst = pd.DataFrame()

    print(f"[MarginalUnit] Forecast RT {fecha_ini} -> {fecha_fin}")
    try:
        df_rt_fcst = get_forecast_hourly("lmp_rt", NODOS, fecha_ini, fecha_fin)
        if not df_rt_fcst.empty:
            df_rt_fcst = df_rt_fcst.rename(columns={
                "DC_L_fcst": "RT_DCL_FCST",
                "DC_R_fcst": "RT_DCR_FCST",
            })
    except Exception as e:
        print(f"[MarginalUnit] RT forecast falló: {e}")
        df_rt_fcst = pd.DataFrame()

    # ── Merge por timestamp horario ───────────────────────────────────────────
    horas = pd.date_range(fecha_ini, fecha_fin + " 23:00", freq="h")
    df = pd.DataFrame({"fecha": horas})

    for parte in [da_dcl, da_dcr, da_dce, rt_dcl, rt_dcr, rt_dce, df_load, df_wind]:
        if not parte.empty:
            df = df.merge(parte, on="fecha", how="left")

    if not df_solar.empty:
        df = df.merge(df_solar, on="fecha", how="left")
    if not df_da_fcst.empty:
        df = df.merge(df_da_fcst, on="fecha", how="left")
    if not df_rt_fcst.empty:
        df = df.merge(df_rt_fcst, on="fecha", how="left")

    return df


def _safe_float(val):
    """Convierte NaN/inf a None para SQL Server."""
    if val is None:
        return None
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    except (TypeError, ValueError):
        return None


# ── Upsert en SQL Server ──────────────────────────────────────────────────────
def upsert_ercot(df: pd.DataFrame) -> None:
    """Inserta o actualiza filas en XTS.dbo.DATOS_ERCOT."""
    if df.empty:
        print("[ERCOT] Sin datos para guardar.")
        return

    conn   = get_connection("XTS")
    cursor = conn.cursor()

    ercot_cols = [
        "DA_DCL", "DA_DCR", "DA_DCE", "RT_DCL", "RT_DCR", "RT_DCE",
        "LOAD_ERCOT", "WIND_ERCOT", "SOLAR_ERCOT",
        "DA_DCL_FCST", "DA_DCR_FCST",
        "RT_DCL_FCST", "RT_DCR_FCST",
    ]
    update_cols = [c for c in ercot_cols if c in df.columns]

    for _, row in df.iterrows():
        cursor.execute(
            "SELECT COUNT(*) FROM DATOS_ERCOT WHERE fecha = ?", row["fecha"])
        existe = cursor.fetchone()[0]

        col_vals = {c: _safe_float(row.get(c)) for c in update_cols}

        if existe:
            sets = ", ".join(f"{c} = ?" for c, v in col_vals.items() if v is not None)
            vals = [v for v in col_vals.values() if v is not None]
            if sets:
                cursor.execute(
                    f"UPDATE DATOS_ERCOT SET {sets} WHERE fecha = ?",
                    *vals, row["fecha"]
                )
        else:
            filled = {c: v for c, v in col_vals.items() if v is not None}
            cols   = ["fecha"] + list(filled.keys())
            vals   = [row["fecha"]] + list(filled.values())
            ph     = ", ".join("?" * len(vals))
            cursor.execute(
                f"INSERT INTO DATOS_ERCOT ({', '.join(cols)}) VALUES ({ph})",
                *vals
            )

    conn.commit()
    cursor.close()
    conn.close()
    print(f"[ERCOT] {len(df)} filas guardadas en DATOS_ERCOT.")
