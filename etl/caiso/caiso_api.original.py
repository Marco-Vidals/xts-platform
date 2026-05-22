"""
Cliente para la API pública de CAISO OASIS.
Extrae precios DA/FMM (5-min RT), load y solar para nodos de interconexión
con México: CFEROA (Rosarito), CFETIJ (Tijuana), y nodos de WECC.

API doc: https://www.caiso.com/documents/oasisapispecification.pdf
"""
import io
import zipfile
import requests
import pandas as pd
from datetime import datetime, timedelta, date

OASIS_BASE = "https://oasis.caiso.com/oasisapi/SingleZip"
_TIMEOUT   = 60

# Nodos de interconexión México-CAISO
NODE_ROA   = "CFEROA_1_N001"   # Rosarito (La Rosita)
NODE_TJI   = "CFETIJ_1_N001"   # Tijuana International
NODE_IVY   = "IMPRL_VLLY_NR_B_APND"  # Imperial Valley (IID)
NODE_OMS   = "OTAY_MESA_1_N001"       # Otay Mesa (posible OMS)

# Aliases usados en DATOS_CAISO
NODO_MAP = {
    "ROA": NODE_ROA,
    "TJI": NODE_TJI,
    "IVY": NODE_IVY,
    "OMS": NODE_OMS,
}


# ── Helpers ───────────────────────────────────────────────────────────────────
def _fmt_dt(d: str, hour: int = 0) -> str:
    """Convierte fecha YYYY-MM-DD + hora a formato OASIS: YYYYMMDDTHH:00-0000"""
    return f"{d.replace('-', '')}T{hour:02d}:00-0000"


def _fetch_oasis(queryname: str, start_dt: str, end_dt: str, **kwargs) -> pd.DataFrame:
    """
    Hace GET a OASIS SingleZip y retorna el CSV dentro del ZIP como DataFrame.
    """
    params = {
        "queryname":     queryname,
        "startdatetime": start_dt,
        "enddatetime":   end_dt,
        "version":       "1",
        "resultformat":  "6",   # CSV
    }
    params.update(kwargs)

    resp = requests.get(OASIS_BASE, params=params, timeout=_TIMEOUT)
    resp.raise_for_status()

    # La respuesta es siempre un ZIP aunque se pida CSV
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        # Buscar el archivo CSV dentro del ZIP
        csv_files = [n for n in zf.namelist() if n.endswith(".csv") or n.endswith(".xml")]
        if not csv_files:
            return pd.DataFrame()
        fname = csv_files[0]
        with zf.open(fname) as f:
            # CAISO CSV tiene cabeceras en las primeras filas, datos en el medio
            raw = f.read().decode("utf-8", errors="replace")

    # Parsear CSV — CAISO incluye líneas de metadata al inicio y final
    lines = raw.strip().splitlines()
    # Encontrar la línea de cabecera real (la que tiene "INTERVALSTARTTIME" o "OPR_DT")
    header_idx = 0
    for i, line in enumerate(lines):
        if "INTERVALSTARTTIME" in line or "OPR_DT" in line or "STARTTIME" in line:
            header_idx = i
            break

    csv_clean = "\n".join(lines[header_idx:])
    try:
        df = pd.read_csv(io.StringIO(csv_clean))
    except Exception:
        return pd.DataFrame()

    return df


# ── Precios DA (Day-Ahead Market) ─────────────────────────────────────────────
def get_da_prices(fecha_ini: str, fecha_fin: str, node: str) -> pd.DataFrame:
    """
    Precios LMP DA horarios para un nodo.
    Retorna df con columnas: fecha (datetime UTC-6 CAISO), precio_da
    """
    # OASIS usa dia anterior como startdate para cubrir las 24h del día operativo
    ini_dt = datetime.strptime(fecha_ini, "%Y-%m-%d")
    fin_dt = datetime.strptime(fecha_fin, "%Y-%m-%d")

    frames = []
    cur = ini_dt
    while cur <= fin_dt:
        # CAISO: start 8:00 UTC = 00:00 PPT (previo día), end 8:00 UTC del día siguiente
        start = _fmt_dt(cur.strftime("%Y-%m-%d"), hour=8)
        end   = _fmt_dt((cur + timedelta(days=1)).strftime("%Y-%m-%d"), hour=8)

        try:
            df = _fetch_oasis("PRC_LMP", start, end,
                              market_run_id="DAM", node=node)
            if not df.empty:
                frames.append(df)
        except Exception as e:
            print(f"[CAISO DA] {cur.date()} {node} error: {e}")
        cur += timedelta(days=1)

    if not frames:
        return pd.DataFrame()

    df_all = pd.concat(frames, ignore_index=True)
    return _normalize_lmp(df_all, "precio_da")


# ── Precios FMM/RT (Fifteen-Minute Market) ────────────────────────────────────
def get_fmm_prices(fecha_ini: str, fecha_fin: str, node: str) -> pd.DataFrame:
    """
    Precios LMP FMM (15-min) para un nodo, promediados a horario.
    Retorna df con columnas: fecha, precio_fmm
    """
    ini_dt = datetime.strptime(fecha_ini, "%Y-%m-%d")
    fin_dt = datetime.strptime(fecha_fin, "%Y-%m-%d")

    frames = []
    cur = ini_dt
    while cur <= fin_dt:
        start = _fmt_dt(cur.strftime("%Y-%m-%d"), hour=8)
        end   = _fmt_dt((cur + timedelta(days=1)).strftime("%Y-%m-%d"), hour=8)
        try:
            df = _fetch_oasis("PRC_LMP", start, end,
                              market_run_id="HASP", node=node)
            if not df.empty:
                frames.append(df)
        except Exception as e:
            print(f"[CAISO FMM] {cur.date()} {node} error: {e}")
        cur += timedelta(days=1)

    if not frames:
        return pd.DataFrame()

    df_all = pd.concat(frames, ignore_index=True)
    df_norm = _normalize_lmp(df_all, "precio_fmm")

    if df_norm.empty:
        return df_norm

    # Promediar a horario (FMM es cada 15 min)
    df_norm["hora"] = df_norm["fecha"].dt.floor("h")
    return df_norm.groupby("hora")["precio_fmm"].mean().reset_index().rename(
        columns={"hora": "fecha"})


# ── Load Forecast ─────────────────────────────────────────────────────────────
def get_load(fecha_ini: str, fecha_fin: str) -> pd.DataFrame:
    """Carga del sistema CAISO (horaria). Retorna df: fecha, load_mw"""
    ini_dt = datetime.strptime(fecha_ini, "%Y-%m-%d")
    fin_dt = datetime.strptime(fecha_fin, "%Y-%m-%d")

    frames = []
    cur = ini_dt
    while cur <= fin_dt:
        start = _fmt_dt(cur.strftime("%Y-%m-%d"), hour=8)
        end   = _fmt_dt((cur + timedelta(days=1)).strftime("%Y-%m-%d"), hour=8)
        try:
            df = _fetch_oasis("SLD_FCST", start, end, market_run_id="DAM")
            if not df.empty:
                frames.append(df)
        except Exception as e:
            print(f"[CAISO Load] {cur.date()} error: {e}")
        cur += timedelta(days=1)

    if not frames:
        return pd.DataFrame()

    df_all = pd.concat(frames, ignore_index=True)
    return _normalize_load(df_all)


# ── Solar ─────────────────────────────────────────────────────────────────────
def get_solar(fecha_ini: str, fecha_fin: str) -> pd.DataFrame:
    """Generación solar CAISO (horaria). Retorna df: fecha, solar_mw"""
    ini_dt = datetime.strptime(fecha_ini, "%Y-%m-%d")
    fin_dt = datetime.strptime(fecha_fin, "%Y-%m-%d")

    frames = []
    cur = ini_dt
    while cur <= fin_dt:
        start = _fmt_dt(cur.strftime("%Y-%m-%d"), hour=8)
        end   = _fmt_dt((cur + timedelta(days=1)).strftime("%Y-%m-%d"), hour=8)
        try:
            df = _fetch_oasis("SLD_REN_FCST", start, end, market_run_id="DAM")
            if not df.empty:
                frames.append(df)
        except Exception as e:
            print(f"[CAISO Solar] {cur.date()} error: {e}")
        cur += timedelta(days=1)

    if not frames:
        return pd.DataFrame()

    df_all = pd.concat(frames, ignore_index=True)
    return _normalize_solar(df_all)


# ── Normalización ─────────────────────────────────────────────────────────────
def _normalize_lmp(df: pd.DataFrame, price_col: str) -> pd.DataFrame:
    """Extrae timestamp y LMP de un reporte OASIS PRC_LMP."""
    if df.empty:
        return pd.DataFrame()

    # Columnas posibles para timestamp
    time_cols = ["INTERVALSTARTTIME_GMT", "STARTTIME", "OPR_DT"]
    lmp_cols  = ["MW", "LMP", "LMP_TYPE"]

    ts_col = next((c for c in time_cols if c in df.columns), None)

    # Para PRC_LMP, buscar la columna LMP (puede tener distintos nombres)
    # La columna "MW" contiene el valor del precio en reportes LMP
    price_raw = next((c for c in ["MW", "LMP_VALUE", "VALUE"] if c in df.columns), None)

    if ts_col is None or price_raw is None:
        # intentar columna genérica
        if df.shape[1] >= 2:
            ts_col    = df.columns[0]
            price_raw = df.columns[-1]
        else:
            return pd.DataFrame()

    result = pd.DataFrame({
        "fecha":    pd.to_datetime(df[ts_col], errors="coerce", utc=True),
        price_col:  pd.to_numeric(df[price_raw], errors="coerce"),
    }).dropna()

    # Convertir a hora CAISO (UTC-8, sin DST en PPT)
    result["fecha"] = result["fecha"].dt.tz_convert("America/Los_Angeles").dt.tz_localize(None)

    # Redondear a hora
    result["fecha"] = result["fecha"].dt.floor("h")
    return result.groupby("fecha")[price_col].mean().reset_index()


def _normalize_load(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()

    ts_col   = next((c for c in ["INTERVALSTARTTIME_GMT", "STARTTIME"] if c in df.columns), None)
    load_col = next((c for c in ["MW", "LOAD", "DEMAND"] if c in df.columns), None)

    if ts_col is None or load_col is None:
        return pd.DataFrame()

    result = pd.DataFrame({
        "fecha":    pd.to_datetime(df[ts_col], errors="coerce", utc=True),
        "load_mw":  pd.to_numeric(df[load_col], errors="coerce"),
    }).dropna()

    result["fecha"] = result["fecha"].dt.tz_convert("America/Los_Angeles").dt.tz_localize(None)
    result["fecha"] = result["fecha"].dt.floor("h")
    return result.groupby("fecha")["load_mw"].mean().reset_index()


def _normalize_solar(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()

    ts_col    = next((c for c in ["INTERVALSTARTTIME_GMT", "STARTTIME"] if c in df.columns), None)
    solar_col = next((c for c in ["MW", "SOLAR", "GENERATION"] if c in df.columns), None)

    if ts_col is None or solar_col is None:
        return pd.DataFrame()

    result = pd.DataFrame({
        "fecha":    pd.to_datetime(df[ts_col], errors="coerce", utc=True),
        "solar_mw": pd.to_numeric(df[solar_col], errors="coerce"),
    }).dropna()

    result["fecha"] = result["fecha"].dt.tz_convert("America/Los_Angeles").dt.tz_localize(None)
    result["fecha"] = result["fecha"].dt.floor("h")
    return result.groupby("fecha")["solar_mw"].mean().reset_index()
