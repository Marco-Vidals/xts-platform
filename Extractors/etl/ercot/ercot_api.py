"""
Cliente para la ERCOT Public API.
Extrae precios DA/RT (DC_L, DC_R) y datos de carga y viento en granularidad HORARIA.

DA  (NP4-190-CD): ya viene horario (hourEnding 1-24) → 1 fila por hora.
RT  (NP6-905-CD): viene en intervalos de 15 min (deliveryInterval 1-4) →
                  si la API no ofrece versión horaria, se promedian los 4
                  intervalos de cada hora → 1 fila por hora.
Load (NP3-565-CD): hourly por weather zone → 1 fila por hora.
Wind (NP4-732-CD): hourly → 1 fila por hora.
"""
import os
import time
import requests
import pandas as pd
from datetime import timedelta

# ── Credenciales ──────────────────────────────────────────────────────────────
ERCOT_USERNAME  = os.environ.get("ERCOT_USERNAME",  "mvidals@xiix.mx")
ERCOT_PASSWORD  = os.environ.get("ERCOT_PASSWORD",  "")
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


def _get_all_pages(token: str, endpoint: str, params: dict, timeout: int = 90) -> pd.DataFrame:
    """
    Descarga todas las páginas de un endpoint ERCOT.
    La API devuelve data como lista de listas; usa 'fields' para los nombres de columna.
    Retorna DataFrame con columnas nombradas.
    """
    hdrs = _headers(token)
    all_rows = []
    col_names = None
    page = 1
    while True:
        params["page"] = page
        for attempt in range(4):
            resp = requests.get(
                f"{ERCOT_BASE}/{endpoint}",
                headers=hdrs,
                params=params,
                timeout=timeout,
            )
            if resp.status_code == 429:
                wait = 15 * (attempt + 1)
                print(f"[ERCOT] Rate limit, esperando {wait}s...")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            break
        js = resp.json()

        # Extraer nombres de columnas de 'fields' (solo primera página)
        if col_names is None:
            fields = js.get("fields", [])
            if fields and isinstance(fields[0], dict):
                col_names = [f["name"] for f in fields]

        all_rows.extend(js.get("data", []))
        if page >= js.get("_meta", {}).get("totalPages", 1):
            break
        page += 1

    if not all_rows:
        return pd.DataFrame()

    # Construir DataFrame con nombres de columna correctos
    if col_names and isinstance(all_rows[0], list):
        return pd.DataFrame(all_rows, columns=col_names)
    # Fallback: la API devolvió dicts (comportamiento antiguo)
    return pd.DataFrame(all_rows)


def _hour_ending_to_ts(df: pd.DataFrame,
                        date_col: str = "deliveryDate",
                        hour_col: str = "hourEnding") -> pd.Series:
    """
    Convierte deliveryDate + hourEnding a timestamp horario.
    Acepta dos formatos:
      - Entero/string numérico: '1' o 1 → 00:00, '24' o 24 → 23:00
      - 'HH:MM' (ej: '01:00') → hora = HH - 1
    """
    base = pd.to_datetime(df[date_col])
    raw  = df[hour_col].astype(str)

    # Detectar formato 'HH:MM'
    if raw.str.contains(":").any():
        horas = raw.str.split(":").str[0].astype(int) - 1
    else:
        horas = pd.to_numeric(raw, errors="coerce").fillna(1).astype(int) - 1

    return base + pd.to_timedelta(horas, unit="h")


# ── Precios DA ────────────────────────────────────────────────────────────────
def get_da_prices(token: str, fecha_ini: str, fecha_fin: str,
                  settlement_point: str) -> pd.DataFrame:
    """
    Precios DA (NP4-190-CD) — ya vienen horarios (hourEnding 1-24).
    Retorna df con columnas: fecha (datetime horario), precio_hora.
    """
    df = _get_all_pages(token, "np4-190-cd/dam_stlmnt_pnt_prices", {
        "deliveryDateFrom": fecha_ini,
        "deliveryDateTo":   fecha_fin,
        "settlementPoint":  settlement_point,
        "size":             1000,
    })
    if df.empty:
        return pd.DataFrame(columns=["fecha", "precio_hora"])

    df["fecha"] = _hour_ending_to_ts(df, "deliveryDate", "hourEnding")
    df["precio_hora"] = pd.to_numeric(df["settlementPointPrice"], errors="coerce")
    return (
        df.groupby("fecha")["precio_hora"]
        .mean()                        # por si hubiera duplicados
        .reset_index()
    )


# ── Precios RT ────────────────────────────────────────────────────────────────
def get_rt_prices(token: str, fecha_ini: str, fecha_fin: str,
                  settlement_point: str) -> pd.DataFrame:
    """
    Precios RT (NP6-905-CD) — intervalos de 15 min (deliveryInterval 1-4).
    Se promedian los intervalos de cada hora → 1 fila por hora.
    Retorna df con columnas: fecha (datetime horario), precio_hora.
    """
    df = _get_all_pages(token, "np6-905-cd/spp_node_zone_hub", {
        "deliveryDateFrom": fecha_ini,
        "deliveryDateTo":   fecha_fin,
        "settlementPoint":  settlement_point,
        "size":             1000,
    })
    if df.empty:
        return pd.DataFrame(columns=["fecha", "precio_hora"])
    # deliveryHour (1-24) → timestamp horario
    df["fecha"] = _hour_ending_to_ts(df, "deliveryDate", "deliveryHour")
    df["settlementPointPrice"] = pd.to_numeric(df["settlementPointPrice"], errors="coerce")
    # Promedio de los intervalos de 15 min dentro de cada hora
    return (
        df.groupby("fecha")["settlementPointPrice"]
        .mean()
        .reset_index()
        .rename(columns={"settlementPointPrice": "precio_hora"})
    )


# ── Carga del sistema ─────────────────────────────────────────────────────────
def get_load(token: str, fecha_ini: str, fecha_fin: str) -> pd.DataFrame:
    """
    Carga horaria ERCOT (NP6-345-CD) — actual system load by weather zone.
    Retorna df con columnas: fecha (datetime horario), load_mw.
    """
    df = _get_all_pages(token, "np6-345-cd/act_sys_load_by_wzn", {
        "operatingDayFrom": fecha_ini,
        "operatingDayTo":   fecha_fin,
        "size":             1000,
    })
    if df.empty:
        return pd.DataFrame(columns=["fecha", "load_mw"])

    df["fecha"]   = _hour_ending_to_ts(df, "operatingDay", "hourEnding")
    df["load_mw"] = pd.to_numeric(df["total"], errors="coerce")
    df = df.drop_duplicates(subset=["fecha"], keep="first")
    return df[["fecha", "load_mw"]].reset_index(drop=True)


# ── Generación eólica ─────────────────────────────────────────────────────────
_WIND_COLS = [
    "STWPFSystem",
    "STWPFLoadZoneSouthHouston",
    "STWPFLoadZoneWest",
    "STWPFLoadZoneNorth",
    "STWPFLoadZoneCoastal",
    "STWPFLoadZoneFarWest",
]

def get_wind(token: str, fecha_ini: str, fecha_fin: str) -> pd.DataFrame:
    """
    Generacion eolica ERCOT (NP4-732-CD) — actual system-wide generation.
    Consulta dia por dia para evitar timeouts por volumen de revisiones.
    Retorna df con columnas: fecha (datetime horario), wind_mw.
    """
    from datetime import date as _date, timedelta as _td
    ini = pd.to_datetime(fecha_ini).date()
    fin = pd.to_datetime(fecha_fin).date()
    frames = []
    cur = ini
    while cur <= fin:
        fecha_str = cur.strftime("%Y-%m-%d")
        try:
            df_day = _get_all_pages(token, "np4-732-cd/wpp_hrly_avrg_actl_fcast", {
                "deliveryDateFrom": fecha_str,
                "deliveryDateTo":   fecha_str,
                "size":             1000,
            })
            if not df_day.empty:
                frames.append(df_day)
        except Exception as e:
            print(f"[ERCOT Wind] {fecha_str} fallo: {e}")
        cur += _td(days=1)

    if not frames:
        return pd.DataFrame(columns=["fecha", "wind_mw"])

    df = pd.concat(frames, ignore_index=True)
    df["fecha"] = _hour_ending_to_ts(df, "deliveryDate", "hourEnding")

    # genSystemWide = generacion actual total del sistema
    # postedDatetime DESC -> mas reciente primero -> drop_duplicates conserva la mas reciente
    df["postedDatetime"] = pd.to_datetime(df["postedDatetime"], errors="coerce")
    df = df.sort_values("postedDatetime", ascending=False)
    df["wind_mw"] = pd.to_numeric(df["genSystemWide"], errors="coerce")
    df = df.drop_duplicates(subset=["fecha"], keep="first")
    return df[["fecha", "wind_mw"]].sort_values("fecha").reset_index(drop=True)


# ── Generación solar ──────────────────────────────────────────────────────────
def get_solar(token: str, fecha_ini: str, fecha_fin: str) -> pd.DataFrame:
    """
    Generacion solar ERCOT (NP4-745-CD) — actual system-wide PV generation.
    Consulta dia por dia para evitar timeouts.
    Retorna df con columnas: fecha (datetime horario), solar_mw.
    """
    from datetime import date as _date, timedelta as _td
    ini = pd.to_datetime(fecha_ini).date()
    fin = pd.to_datetime(fecha_fin).date()
    frames = []
    cur = ini
    while cur <= fin:
        fecha_str = cur.strftime("%Y-%m-%d")
        try:
            df_day = _get_all_pages(token, "np4-745-cd/spp_hrly_actual_fcast_geo", {
                "deliveryDateFrom": fecha_str,
                "deliveryDateTo":   fecha_str,
                "size":             1000,
            })
            if not df_day.empty:
                frames.append(df_day)
        except Exception as e:
            print(f"[ERCOT Solar] {fecha_str} fallo: {e}")
        cur += _td(days=1)

    if not frames:
        return pd.DataFrame(columns=["fecha", "solar_mw"])

    df = pd.concat(frames, ignore_index=True)
    df["fecha"] = _hour_ending_to_ts(df, "deliveryDate", "hourEnding")

    # genSystemWide = generacion actual total del sistema solar
    df["postedDatetime"] = pd.to_datetime(df.get("postedDatetime", pd.NaT), errors="coerce")
    df = df.sort_values("postedDatetime", ascending=False)
    df["solar_mw"] = pd.to_numeric(df["genSystemWide"], errors="coerce")
    df = df.drop_duplicates(subset=["fecha"], keep="first")
    return df[["fecha", "solar_mw"]].sort_values("fecha").reset_index(drop=True)
