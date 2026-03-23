"""
Cliente para la ERCOT Public API.
Extrae precios DA/RT (DC_L, DC_R) y datos de carga y viento.
"""
import os
import requests
import pandas as pd
from datetime import datetime, date

# ── Credenciales ──────────────────────────────────────────────────────────────
ERCOT_USERNAME  = os.environ.get("ERCOT_USERNAME",  "mvidals@xiix.mx")
ERCOT_PASSWORD  = os.environ.get("ERCOT_PASSWORD",  "Cocochou1305#")
ERCOT_KEY       = os.environ.get("ERCOT_KEY",       "8908c0fc88284dfdbaed3d01955dc934")
ERCOT_CLIENT_ID = os.environ.get("ERCOT_CLIENT_ID", "fec253ea-0d06-4272-a5e6-b478baeecd70")
ERCOT_TOKEN_URL = (
    "https://ercotb2c.b2clogin.com/ercotb2c.onmicrosoft.com"
    "/B2C_1_PUBAPI-ROPC-FLOW/oauth2/v2.0/token"
)
ERCOT_BASE = "https://api.ercot.com/api/public-reports"
_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# ── Auth ──────────────────────────────────────────────────────────────────────
def get_token() -> str:
    resp = requests.post(
        ERCOT_TOKEN_URL,
        data={
            "username":      ERCOT_USERNAME,
            "password":      ERCOT_PASSWORD,
            "grant_type":    "password",
            "scope":         f"openid {ERCOT_CLIENT_ID} offline_access",
            "client_id":     ERCOT_CLIENT_ID,
            "response_type": "id_token",
        },
        headers={"User-Agent": _UA},
        timeout=20,
    )
    resp.raise_for_status()
    js = resp.json()
    return js.get("id_token") or js.get("access_token")


def _headers(token: str) -> dict:
    return {
        "Authorization":             f"Bearer {token}",
        "Ocp-Apim-Subscription-Key": ERCOT_KEY,
        "Accept":                    "application/json",
    }


def _get_all_pages(token: str, endpoint: str, params: dict) -> list:
    """Descarga todas las páginas de un endpoint ERCOT."""
    hdrs = _headers(token)
    all_data = []
    page = 1
    while True:
        params["page"] = page
        resp = requests.get(
            f"{ERCOT_BASE}/{endpoint}",
            headers=hdrs,
            params=params,
            timeout=30,
        )
        resp.raise_for_status()
        js = resp.json()
        all_data.extend(js.get("data", []))
        if page >= js.get("_meta", {}).get("totalPages", 1):
            break
        page += 1
    return all_data


# ── Precios DA ────────────────────────────────────────────────────────────────
def get_da_prices(token: str, fecha_ini: str, fecha_fin: str,
                  settlement_point: str) -> pd.DataFrame:
    """
    Precios DA (NP4-190-CD) para un settlement point.
    Retorna df con columnas: fecha, precio_diario (promedio de 24 horas).
    """
    rows = _get_all_pages(token, "np4-190-cd/dam_stlmnt_pnt_prices", {
        "deliveryDateFrom": fecha_ini,
        "deliveryDateTo":   fecha_fin,
        "settlementPoint":  settlement_point,
        "size":             1000,
    })
    if not rows:
        return pd.DataFrame(columns=["fecha", "precio_diario"])

    df = pd.DataFrame(rows)
    df["fecha"] = pd.to_datetime(df["deliveryDate"])
    df["settlementPointPrice"] = pd.to_numeric(df["settlementPointPrice"], errors="coerce")
    return (
        df.groupby("fecha")["settlementPointPrice"]
        .mean()
        .reset_index()
        .rename(columns={"settlementPointPrice": "precio_diario"})
    )


# ── Precios RT ────────────────────────────────────────────────────────────────
def get_rt_prices(token: str, fecha_ini: str, fecha_fin: str,
                  settlement_point: str) -> pd.DataFrame:
    """
    Precios RT (NP6-905-CD) para un settlement point (intervalos de 15 min).
    Retorna df con columnas: fecha, precio_diario (promedio del día).
    """
    rows = _get_all_pages(token, "np6-905-cd/spp_node_zone_hub", {
        "deliveryDateFrom": fecha_ini,
        "deliveryDateTo":   fecha_fin,
        "settlementPoint":  settlement_point,
        "size":             1000,
    })
    if not rows:
        return pd.DataFrame(columns=["fecha", "precio_diario"])

    df = pd.DataFrame(rows)
    df["fecha"] = pd.to_datetime(df["deliveryDate"])
    df["settlementPointPrice"] = pd.to_numeric(df["settlementPointPrice"], errors="coerce")
    return (
        df.groupby("fecha")["settlementPointPrice"]
        .mean()
        .reset_index()
        .rename(columns={"settlementPointPrice": "precio_diario"})
    )


# ── Carga del sistema ─────────────────────────────────────────────────────────
def get_load(token: str, fecha_ini: str, fecha_fin: str) -> pd.DataFrame:
    """
    Carga horaria ERCOT (NP3-565-CD).
    Retorna df con columnas: fecha, load_mw (promedio diario).
    """
    rows = _get_all_pages(token, "np3-565-cd/lf_by_model_weather_zone", {
        "deliveryDateFrom": fecha_ini,
        "deliveryDateTo":   fecha_fin,
        "size":             1000,
    })
    if not rows:
        return pd.DataFrame(columns=["fecha", "load_mw"])

    df = pd.DataFrame(rows)

    # Filtrar modelo STLF si está disponible
    if "model" in df.columns:
        for pref in ["STLF", "MTLF"]:
            if pref in df["model"].values:
                df = df[df["model"] == pref]
                break

    # Columna de total del sistema
    load_col = None
    for cand in ["systemTotal", "total", "systemtotal", "System Total"]:
        if cand in df.columns:
            load_col = cand
            break
    if load_col is None:
        return pd.DataFrame(columns=["fecha", "load_mw"])

    df["fecha"] = pd.to_datetime(df["deliveryDate"])
    df["load_mw"] = pd.to_numeric(df[load_col], errors="coerce")
    return (
        df.groupby("fecha")["load_mw"]
        .mean()
        .reset_index()
    )


# ── Generación eólica ─────────────────────────────────────────────────────────
_WIND_COLS = [
    "STWPFLoadZoneSouthHouston",
    "STWPFLoadZoneWest",
    "STWPFLoadZoneNorth",
    "STWPFLoadZoneCoastal",
    "STWPFLoadZoneFarWest",
    "STWPFSystem",
]

def get_wind(token: str, fecha_ini: str, fecha_fin: str) -> pd.DataFrame:
    """
    Generación eólica ERCOT (NP4-732-CD).
    Retorna df con columnas: fecha, wind_mw (promedio diario sistema).
    """
    rows = _get_all_pages(token, "np4-732-cd/wpp_hrly_avrg_actl_fcast", {
        "deliveryDateFrom": fecha_ini,
        "deliveryDateTo":   fecha_fin,
        "size":             1000,
    })
    if not rows:
        return pd.DataFrame(columns=["fecha", "wind_mw"])

    df = pd.DataFrame(rows)
    df["fecha"] = pd.to_datetime(df["deliveryDate"])

    # Buscar columna de total o sumar zonas disponibles
    total_col = next((c for c in _WIND_COLS if c in df.columns), None)
    if total_col:
        df["wind_mw"] = pd.to_numeric(df[total_col], errors="coerce")
    else:
        zone_cols = [c for c in df.columns if "STWPF" in c or "wind" in c.lower()]
        if not zone_cols:
            return pd.DataFrame(columns=["fecha", "wind_mw"])
        df["wind_mw"] = df[zone_cols].apply(pd.to_numeric, errors="coerce").sum(axis=1)

    return (
        df.groupby("fecha")["wind_mw"]
        .mean()
        .reset_index()
    )
