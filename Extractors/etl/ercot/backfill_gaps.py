"""
Backfill de semanas con errores en ERCOT API.
Intenta ERCOT primero; si falla (500/conexion), usa Enverus Mosaic como fallback.

Uso:
    python -m etl.ercot.backfill_gaps
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pandas as pd
import requests
import urllib3
import time
from datetime import datetime, timedelta

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from etl.ercot.ercot_extractor import extract_ercot, upsert_ercot
from etl.common.db_connection import get_connection

# ── Semanas con errores identificadas en logs ──────────────────────────────────
GAPS = [
    ("2025-11-22", "2025-11-28"),
    ("2025-12-27", "2026-01-02"),
    ("2026-01-03", "2026-01-09"),
    ("2026-01-10", "2026-01-16"),
    ("2026-01-17", "2026-01-23"),
    ("2026-02-07", "2026-02-13"),
    ("2026-02-14", "2026-02-20"),
]

# ── Enverus config ─────────────────────────────────────────────────────────────
ENV_USER = os.environ.get("ENVERUS_USER", "mvidals@xiix.mx")
ENV_PASS = os.environ.get("ENVERUS_PASS", "")
ENV_ROOT = "https://api-mosaic-prod.enverus.com/mosaic-api"

# Datasets Enverus para ERCOT precios de nodo (pnode)
ENV_DA_DS  = "ercot-price-pnode-iso_actual_da_peakwd"   # DA weekday on-peak
ENV_RT_DS  = "ercot-price-pnode-iso_actual_rt"          # RT actual por pnode

# Posibles entity_ids para DC_L y DC_R en Enverus (probar en orden)
_DCL_IDS = ["dc_l", "DC_L", "dc_l_dc_r", "HB_BUSAVG"]
_DCR_IDS = ["dc_r", "DC_R", "dc_l_dc_r"]


# ── Helpers Enverus ────────────────────────────────────────────────────────────
def _env_get(dataset: str, start: str, end: str, entity_id: str) -> pd.DataFrame:
    """Hace GET a Enverus timeseries y retorna DataFrame crudo."""
    url = f"{ENV_ROOT}/timeseries/{dataset}"
    params = {
        "start_datetime": start,
        "end_datetime":   end,
        "response_type":  "csv_wide",
        "entity_ids":     entity_id,
    }
    r = requests.get(url, params=params, auth=(ENV_USER, ENV_PASS),
                     timeout=30, verify=False)
    if r.status_code == 200 and r.text.strip():
        from io import StringIO
        return pd.read_csv(StringIO(r.text))
    return pd.DataFrame()


def _find_entity(dataset: str, start: str, end: str, candidates: list) -> pd.DataFrame:
    """Prueba entity_ids candidatos hasta encontrar datos."""
    for eid in candidates:
        df = _env_get(dataset, start, end, eid)
        if not df.empty:
            print(f"    [Enverus] entity_id '{eid}' OK -> {len(df)} filas")
            return df
        else:
            print(f"    [Enverus] entity_id '{eid}' -> sin datos")
    return pd.DataFrame()


def _enverus_rt_hourly(start: str, end: str, node: str) -> pd.DataFrame:
    """
    Descarga RT hourly prices de Enverus para un nodo (DC_L o DC_R).
    Retorna df con columnas [fecha, precio_hora].
    """
    candidates = _DCL_IDS if "L" in node.upper() else _DCR_IDS
    df = _find_entity(ENV_RT_DS, start, end, candidates)
    if df.empty:
        return pd.DataFrame()

    # Normalizar: buscar columna de timestamp y precio
    ts_col  = next((c for c in df.columns if "interval_start" in c.lower() or "datetime" in c.lower()), None)
    lmp_col = next((c for c in df.columns if "lmp" in c.lower() or "price" in c.lower()), None)
    if ts_col is None or lmp_col is None:
        print(f"    [Enverus] Columnas inesperadas: {df.columns.tolist()}")
        return pd.DataFrame()

    df["fecha"] = pd.to_datetime(df[ts_col]).dt.tz_localize(None)
    # Enverus puede devolver intervalos de 15 min -> promediar a hora
    df["fecha_h"] = df["fecha"].dt.floor("h")
    agg = df.groupby("fecha_h")[lmp_col].mean().reset_index()
    agg.columns = ["fecha", "precio_hora"]
    return agg


def _enverus_da_hourly(start: str, end: str, node: str) -> pd.DataFrame:
    """
    DA weekday on-peak de Enverus. Nota: Enverus puede no tener DA horario completo.
    Retorna df con columnas [fecha, precio_hora].
    """
    candidates = _DCL_IDS if "L" in node.upper() else _DCR_IDS
    df = _find_entity(ENV_DA_DS, start, end, candidates)
    if df.empty:
        return pd.DataFrame()

    ts_col  = next((c for c in df.columns if "interval_start" in c.lower() or "datetime" in c.lower()), None)
    lmp_col = next((c for c in df.columns if "lmp" in c.lower() or "price" in c.lower()), None)
    if ts_col is None or lmp_col is None:
        print(f"    [Enverus] DA columnas inesperadas: {df.columns.tolist()}")
        return pd.DataFrame()

    df["fecha"] = pd.to_datetime(df[ts_col]).dt.tz_localize(None)
    df["fecha_h"] = df["fecha"].dt.floor("h")
    agg = df.groupby("fecha_h")[lmp_col].mean().reset_index()
    agg.columns = ["fecha", "precio_hora"]
    return agg


# ── Backfill con fallback ──────────────────────────────────────────────────────
def backfill_gap(fecha_ini: str, fecha_fin: str) -> bool:
    """
    Intenta llenar el gap fecha_ini -> fecha_fin.
    1) Intenta extract_ercot (API oficial ERCOT)
    2) Si falla, construye df columna por columna con Enverus fallback
    Retorna True si guardó algo.
    """
    print(f"\n{'='*60}")
    print(f"  GAP: {fecha_ini} -> {fecha_fin}")
    print(f"{'='*60}")

    # ── 1. Intento ERCOT API ──────────────────────────────────────────────────
    try:
        print("  [Paso 1] Intentando ERCOT API...")
        df = extract_ercot(fecha_ini, fecha_fin)
        if not df.empty and df[["DA_DCL","DA_DCR","RT_DCL","RT_DCR"]].notna().any().any():
            upsert_ercot(df)
            print(f"  OK ERCOT API OK — {len(df)} filas guardadas")
            return True
        else:
            print("  FAIL ERCOT API retornó datos vacíos")
    except Exception as e:
        print(f"  FAIL ERCOT API falló: {e}")

    # ── 2. Fallback Enverus ───────────────────────────────────────────────────
    print("  [Paso 2] Intentando Enverus Mosaic como fallback...")
    horas = pd.date_range(fecha_ini, fecha_fin + " 23:00", freq="h")
    df_env = pd.DataFrame({"fecha": horas})

    for nodo, col_rt, col_da in [("DC_L", "RT_DCL", "DA_DCL"),
                                  ("DC_R", "RT_DCR", "DA_DCR")]:
        print(f"  -> RT {nodo}:")
        rt = _enverus_rt_hourly(fecha_ini, fecha_fin, nodo)
        if not rt.empty:
            df_env = df_env.merge(rt.rename(columns={"precio_hora": col_rt}),
                                  on="fecha", how="left")
        else:
            print(f"    Sin datos RT {nodo} en Enverus")

        print(f"  -> DA {nodo}:")
        da = _enverus_da_hourly(fecha_ini, fecha_fin, nodo)
        if not da.empty:
            df_env = df_env.merge(da.rename(columns={"precio_hora": col_da}),
                                  on="fecha", how="left")
        else:
            print(f"    Sin datos DA {nodo} en Enverus")

    # Verificar si obtuvimos algo útil
    price_cols = [c for c in ["DA_DCL","DA_DCR","RT_DCL","RT_DCR"] if c in df_env.columns]
    if price_cols and df_env[price_cols].notna().any().any():
        upsert_ercot(df_env)
        filled = df_env[price_cols].notna().sum().to_dict()
        print(f"  OK Enverus fallback guardado — filas con datos: {filled}")
        return True
    else:
        print(f"  FAIL Enverus tampoco pudo llenar el gap {fecha_ini} -> {fecha_fin}")
        return False


# ── Main ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    resultados = {}
    for ini, fin in GAPS:
        ok = backfill_gap(ini, fin)
        resultados[f"{ini}->{fin}"] = "OK" if ok else "FALLO"
        time.sleep(2)  # pausa entre semanas

    print("\n\n" + "="*60)
    print("  RESUMEN BACKFILL")
    print("="*60)
    for rango, estado in resultados.items():
        icon = "OK" if estado == "OK" else "FAIL"
        print(f"  {icon}  {rango}  ->  {estado}")
