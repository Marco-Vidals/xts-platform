"""
Cliente para Enverus Mosaic — fallback de precios RT/DA para nodos DC tie (DC_L, DC_R)
que no están disponibles en el API pública de ERCOT (np6-905-cd).
"""
import os
import requests
import urllib3
import pandas as pd

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

ENV_USER = os.environ.get("ENVERUS_USER", "mvidals@xiix.mx")
ENV_PASS = os.environ.get("ENVERUS_PASS", "")
ENV_ROOT = "https://api-mosaic-prod.enverus.com/mosaic-api"

ENV_DA_DS = "ercot-price-pnode-iso_actual_da_peakwd"
ENV_RT_DS = "ercot-price-pnode-iso_actual_rt"

_DCL_IDS = ["DC_L", "dc_l", "dc_l_dc_r", "HB_BUSAVG"]
_DCR_IDS = ["DC_R", "dc_r", "dc_l_dc_r"]


def _env_get(dataset: str, start: str, end: str, entity_id: str) -> pd.DataFrame:
    from io import StringIO
    url = f"{ENV_ROOT}/timeseries/{dataset}"
    params = {
        "start_datetime": start,
        "end_datetime":   end,
        "response_type":  "csv_wide",
        "entity_ids":     entity_id,
    }
    try:
        r = requests.get(url, params=params, auth=(ENV_USER, ENV_PASS),
                         timeout=30, verify=False)
        if r.status_code == 200 and r.text.strip():
            return pd.read_csv(StringIO(r.text))
    except Exception as e:
        print(f"[Enverus] {dataset} {entity_id}: {e}")
    return pd.DataFrame()


def _find_entity(dataset: str, start: str, end: str, candidates: list) -> pd.DataFrame:
    for eid in candidates:
        df = _env_get(dataset, start, end, eid)
        if not df.empty:
            print(f"  [Enverus] {dataset} entity '{eid}' → {len(df)} filas")
            return df
        print(f"  [Enverus] {dataset} entity '{eid}' → sin datos")
    return pd.DataFrame()


def _to_hourly(df: pd.DataFrame) -> pd.DataFrame:
    """Normaliza columnas timestamp/precio y promedia a hora si es 15-min."""
    ts_col  = next((c for c in df.columns if "interval_start" in c.lower()
                    or "datetime" in c.lower()), None)
    lmp_col = next((c for c in df.columns if "lmp" in c.lower()
                    or "price" in c.lower()), None)
    if ts_col is None or lmp_col is None:
        print(f"  [Enverus] columnas inesperadas: {df.columns.tolist()}")
        return pd.DataFrame()
    df["fecha"]   = pd.to_datetime(df[ts_col]).dt.tz_localize(None)
    df["fecha_h"] = df["fecha"].dt.floor("h")
    agg = df.groupby("fecha_h")[lmp_col].mean().reset_index()
    agg.columns = ["fecha", "precio_hora"]
    return agg


def get_rt_hourly(fecha_ini: str, fecha_fin: str, node: str) -> pd.DataFrame:
    """
    RT hourly prices de Enverus para DC_L o DC_R.
    Retorna df con columnas [fecha, precio_hora] o DataFrame vacío si falla.
    """
    candidates = _DCL_IDS if "L" in node.upper() else _DCR_IDS
    df = _find_entity(ENV_RT_DS, fecha_ini, fecha_fin, candidates)
    if df.empty:
        return pd.DataFrame(columns=["fecha", "precio_hora"])
    return _to_hourly(df)


def get_da_hourly(fecha_ini: str, fecha_fin: str, node: str) -> pd.DataFrame:
    """
    DA hourly prices de Enverus para DC_L o DC_R.
    Retorna df con columnas [fecha, precio_hora] o DataFrame vacío si falla.
    """
    candidates = _DCL_IDS if "L" in node.upper() else _DCR_IDS
    df = _find_entity(ENV_DA_DS, fecha_ini, fecha_fin, candidates)
    if df.empty:
        return pd.DataFrame(columns=["fecha", "precio_hora"])
    return _to_hourly(df)
