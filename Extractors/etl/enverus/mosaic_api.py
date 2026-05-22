"""
Cliente para la API de Enverus Mosaic.

Autenticación: HTTP Basic Auth (usuario/contraseña directa).
Base URL: https://api-mosaic-prod.enverus.com/mosaic-api/

Endpoints usados:
  - /datasets          → catálogo de datasets disponibles
  - /timeseries/{dataset_name} → datos de timeseries

Datasets principales:
  Wind forecast (region):  ercot-generation_wind-geographical_region-iso_forecast_rpp
  Solar forecast (system): ercot-generation_solar-system_wide-iso_forecast_stpf
  Load forecast:           ercot-load-system_wide-iso_forecast_hourly
  Wind actual:             ercot-generation_wind-system_wide-iso_actual
  Solar actual:            ercot-generation_solar-system_wide-iso_actual
  Load actual:             ercot-load-system_wide-iso_actual
  Outages (dispatch):      ercot-grid_conditions-system_wide-iso_actual_dispatchable_outages
  Outages (renewable):     ercot-grid_conditions-system_wide-iso_actual_renewable_outages
  Tie flows:               ercot-grid_conditions-tie_flow-iso_actual_tie_flows
"""
import logging
import time

import pandas as pd
import requests
from io import StringIO

log = logging.getLogger(__name__)

MOSAIC_BASE = "https://api-mosaic-prod.enverus.com/mosaic-api"

# Dataset names
DS_WIND_FCST   = "ercot-generation_wind-geographical_region-iso_forecast_rpp"
DS_SOLAR_FCST  = "ercot-generation_solar-system_wide-iso_forecast_stpf"
DS_LOAD_FCST   = "ercot-load-system_wide-iso_forecast_hourly"
DS_WIND_ACT    = "ercot-generation_wind-system_wide-iso_actual"
DS_SOLAR_ACT   = "ercot-generation_solar-system_wide-iso_actual"
DS_LOAD_ACT    = "ercot-load-system_wide-iso_actual"
DS_OUT_DISP    = "ercot-grid_conditions-system_wide-iso_actual_dispatchable_outages"
DS_OUT_RENEW   = "ercot-grid_conditions-system_wide-iso_actual_renewable_outages"
DS_TIE_FLOWS   = "ercot-grid_conditions-tie_flow-iso_actual_tie_flows"
DS_GRID_COND   = "ercot-grid_conditions-system_wide-iso_actual_prc"
DS_WIND_SOLAR  = "ercot-grid_conditions-system_wide-iso_actual_combined_wind_and_solar"


def _auth():
    from etl.base.credentials import get_enverus_creds
    creds = get_enverus_creds()
    if not creds["username"] or not creds["password"]:
        raise ValueError("ENVERUS_USERNAME / ENVERUS_PASSWORD no configurados en .env")
    return (creds["username"], creds["password"])


def _fmt_dt(fecha: str, end: bool = False) -> str:
    """Convierte YYYY-MM-DD al formato ISO que requiere Mosaic API."""
    if "T" in fecha:
        return fecha
    return f"{fecha}T23:59:59" if end else f"{fecha}T00:00:00"


def _get_csv(dataset_name: str, params: dict, retries: int = 3) -> pd.DataFrame:
    """GET /timeseries/{dataset_name} — retorna DataFrame CSV."""
    url = f"{MOSAIC_BASE}/timeseries/{dataset_name}"
    # Normalizar fechas al formato que requiere la API
    if "start_datetime" in params:
        params = {**params,
                  "start_datetime": _fmt_dt(params["start_datetime"]),
                  "end_datetime":   _fmt_dt(params.get("end_datetime", params["start_datetime"]), end=True),
                  "response_type":  "csv_wide"}
    else:
        params = {**params, "response_type": "csv_wide"}
    last_err = None

    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(url, params=params, auth=_auth(), timeout=60)
            if resp.status_code == 429:
                wait = 30 * attempt
                log.warning(f"[Enverus] Rate limit, esperando {wait}s...")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return pd.read_csv(StringIO(resp.text))
        except Exception as e:
            last_err = e
            log.warning(f"[Enverus] {dataset_name} intento {attempt} falló: {e}")
            if attempt < retries:
                time.sleep(15)

    raise last_err or RuntimeError(f"[Enverus] {dataset_name} falló tras {retries} intentos")


# ── Wind forecasts ────────────────────────────────────────────────────────────

def get_wind_forecasts(fecha_ini: str, fecha_fin: str) -> pd.DataFrame:
    """
    Wind forecasts ERCOT por región (south, west, north, coastal, panhandle).
    Retorna df: fecha, iso, resource_type, region, gen_mw
    """
    rows = []
    for region in ["south", "west", "north", "coastal", "panhandle"]:
        try:
            df = _get_csv(DS_WIND_FCST, {
                "start_datetime": fecha_ini,
                "end_datetime":   fecha_fin,
                "as_of":          "prior_day_rolling",
                "entity_ids":     region,
            })
            if df.empty:
                continue
            gen_col = next((c for c in df.columns if "generation_mw" in c.lower()), None)
            ts_col  = next((c for c in df.columns if "interval_start" in c.lower()), None) or next((c for c in df.columns if "datetime" in c.lower() or "timestamp" in c.lower()), df.columns[0])
            if not gen_col:
                continue
            for _, r in df.iterrows():
                rows.append({
                    "fecha":         pd.to_datetime(r[ts_col]),
                    "iso":           "ERCOT",
                    "resource_type": "WIND",
                    "region":        region.upper(),
                    "model":         "RPP",
                    "gen_mw":        float(r[gen_col]) if pd.notna(r[gen_col]) else None,
                })
        except Exception as e:
            log.warning(f"[Enverus] wind {region}: {e}")

    return pd.DataFrame(rows) if rows else pd.DataFrame()


# ── Solar forecasts ───────────────────────────────────────────────────────────

def get_solar_forecasts(fecha_ini: str, fecha_fin: str) -> pd.DataFrame:
    """
    Solar forecasts ERCOT system-wide (STPF).
    Retorna df: fecha, iso, resource_type, region, gen_mw
    """
    try:
        df = _get_csv(DS_SOLAR_FCST, {
            "start_datetime": fecha_ini,
            "end_datetime":   fecha_fin,
            "as_of":          "prior_day_rolling",
            "entity_ids":     "total",
        })
        if df.empty:
            return pd.DataFrame()
        gen_col = next((c for c in df.columns if "generation_mw" in c.lower() or "stpf" in c.lower()), None)
        ts_col  = next((c for c in df.columns if "interval_start" in c.lower()), None) or next((c for c in df.columns if "datetime" in c.lower() or "timestamp" in c.lower()), df.columns[0])
        if not gen_col:
            return pd.DataFrame()
        rows = []
        for _, r in df.iterrows():
            rows.append({
                "fecha":         pd.to_datetime(r[ts_col]),
                "iso":           "ERCOT",
                "resource_type": "SOLAR",
                "region":        "SYSTEM",
                "model":         "STPF",
                "gen_mw":        float(r[gen_col]) if pd.notna(r[gen_col]) else None,
            })
        return pd.DataFrame(rows)
    except Exception as e:
        log.warning(f"[Enverus] solar forecast: {e}")
        return pd.DataFrame()


# ── Load forecasts ────────────────────────────────────────────────────────────

def get_load_forecasts(fecha_ini: str, fecha_fin: str) -> pd.DataFrame:
    """
    Load forecasts ERCOT system-wide.
    Retorna df: fecha, iso, resource_type, region, gen_mw
    """
    try:
        df = _get_csv(DS_LOAD_FCST, {
            "start_datetime": fecha_ini,
            "end_datetime":   fecha_fin,
            "as_of":          "prior_day_rolling",
            "entity_ids":     "total",
        })
        if df.empty:
            return pd.DataFrame()
        load_col = next((c for c in df.columns if "load_mw" in c.lower() or "mw" in c.lower()), None)
        ts_col   = next((c for c in df.columns if "datetime" in c.lower() or "timestamp" in c.lower()), df.columns[0])
        if not load_col:
            return pd.DataFrame()
        rows = []
        for _, r in df.iterrows():
            rows.append({
                "fecha":         pd.to_datetime(r[ts_col]),
                "iso":           "ERCOT",
                "resource_type": "LOAD",
                "region":        "SYSTEM",
                "gen_mw":        float(r[load_col]) if pd.notna(r[load_col]) else None,
            })
        return pd.DataFrame(rows)
    except Exception as e:
        log.warning(f"[Enverus] load forecast: {e}")
        return pd.DataFrame()


# ── Load forecasts ────────────────────────────────────────────────────────────

def get_load_forecasts(fecha_ini: str, fecha_fin: str) -> pd.DataFrame:
    """
    Load forecasts ERCOT system-wide (hourly).
    Retorna df: fecha, iso, resource_type, region, model, gen_mw
    """
    try:
        df = _get_csv(DS_LOAD_FCST, {
            "start_datetime": fecha_ini,
            "end_datetime":   fecha_fin,
            "as_of":          "prior_day_rolling",
            "entity_ids":     "total",
        })
        if df.empty:
            return pd.DataFrame()
        ts_col   = next((c for c in df.columns if "interval_start" in c.lower()), None) or \
                   next((c for c in df.columns if "datetime" in c.lower()), df.columns[0])
        load_col = next((c for c in df.columns if "load_mw" in c.lower()), None)
        if not load_col:
            return pd.DataFrame()
        rows = []
        for _, r in df.iterrows():
            rows.append({
                "fecha":         pd.to_datetime(r[ts_col]),
                "iso":           "ERCOT",
                "resource_type": "LOAD",
                "region":        "SYSTEM",
                "model":         "ISO_FCST",
                "gen_mw":        float(r[load_col]) if pd.notna(r[load_col]) else None,
            })
        return pd.DataFrame(rows)
    except Exception as e:
        log.warning(f"[Enverus] load forecast: {e}")
        return pd.DataFrame()


# ── Outages ───────────────────────────────────────────────────────────────────

def get_outages(fecha_ini: str, fecha_fin: str) -> pd.DataFrame:
    """
    Outages dispatchable + renewable.
    Retorna df: fecha, iso, outage_type, capacity_mw
    """
    rows = []
    for ds, otype in [(DS_OUT_DISP, "DISPATCHABLE"), (DS_OUT_RENEW, "RENEWABLE")]:
        try:
            df = _get_csv(ds, {
                "start_datetime": fecha_ini,
                "end_datetime":   fecha_fin,
                "entity_ids":     "total",
            })
            if df.empty:
                continue
            mw_col = next((c for c in df.columns if "mw" in c.lower() or "capacity" in c.lower()), None)
            ts_col = next((c for c in df.columns if "datetime" in c.lower() or "timestamp" in c.lower()), df.columns[0])
            if not mw_col:
                continue
            for _, r in df.iterrows():
                rows.append({
                    "fecha":       pd.to_datetime(r[ts_col]),
                    "iso":         "ERCOT",
                    "outage_type": otype,
                    "capacity_mw": float(r[mw_col]) if pd.notna(r[mw_col]) else None,
                })
        except Exception as e:
            log.warning(f"[Enverus] outages {otype}: {e}")

    return pd.DataFrame(rows) if rows else pd.DataFrame()


# ── Tie flows ─────────────────────────────────────────────────────────────────

def get_tie_flows(fecha_ini: str, fecha_fin: str) -> pd.DataFrame:
    """
    Flujos inter-área ERCOT (DC_L, DC_R, DC_E, DC_N).
    Retorna df: fecha, iso, interface_id, flow_mw
    """
    try:
        df = _get_csv(DS_TIE_FLOWS, {
            "start_datetime": fecha_ini,
            "end_datetime":   fecha_fin,
        })
        if df.empty:
            return pd.DataFrame()
        ts_col = next((c for c in df.columns if "datetime" in c.lower() or "timestamp" in c.lower()), df.columns[0])
        rows = []
        for _, r in df.iterrows():
            fecha = pd.to_datetime(r[ts_col])
            for col in df.columns:
                if col == ts_col:
                    continue
                val = r[col]
                if pd.notna(val):
                    rows.append({
                        "fecha":        fecha,
                        "iso":          "ERCOT",
                        "interface_id": col.upper(),
                        "flow_mw":      float(val),
                    })
        return pd.DataFrame(rows) if rows else pd.DataFrame()
    except Exception as e:
        log.warning(f"[Enverus] tie flows: {e}")
        return pd.DataFrame()


# ── Grid conditions ───────────────────────────────────────────────────────────

def get_grid_conditions(fecha_ini: str, fecha_fin: str) -> pd.DataFrame:
    """
    PRC (Physical Responsive Capability) y condiciones del grid ERCOT.
    Retorna df: fecha, iso, frequency_hz, prc_mw, operating_reserves, dam_lambda, sced_lambda
    """
    try:
        df = _get_csv(DS_GRID_COND, {
            "start_datetime": fecha_ini,
            "end_datetime":   fecha_fin,
            "entity_ids":     "total",
        })
        if df.empty:
            return pd.DataFrame()
        ts_col = next((c for c in df.columns if "interval_start" in c.lower()), None) or \
                 next((c for c in df.columns if "datetime" in c.lower()), df.columns[0])
        rows = []
        for _, r in df.iterrows():
            row = {"fecha": pd.to_datetime(r[ts_col]), "iso": "ERCOT"}
            for c in df.columns:
                if c == ts_col:
                    continue
                row[c] = float(r[c]) if pd.notna(r.get(c)) else None
            rows.append(row)
        return pd.DataFrame(rows)
    except Exception as e:
        log.warning(f"[Enverus] grid conditions: {e}")
        return pd.DataFrame()


# ── Price forecasts (stub — Mosaic no tiene endpoint de price forecast) ───────

def get_price_forecasts(fecha_ini: str, fecha_fin: str, node: str = "DC_L") -> pd.DataFrame:
    """Price forecasts — no disponible en Mosaic API. Retorna vacío."""
    log.debug("[Enverus] price_forecasts no disponible en Mosaic API")
    return pd.DataFrame()
