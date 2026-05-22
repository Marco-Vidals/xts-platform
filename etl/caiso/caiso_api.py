"""
Cliente para CAISO OASIS (ROA/TJI) y CENACE BCA (IVY/OMS).

CAISO OASIS:
  DA  (PRC_LMP, DAM):   ROA-230_2_N101, TJI-230_2_N101
  FMM (PRC_RTPD_LMP, RTPD): mismos nodos, intervalos 15-min -> promedio horario

CENACE BCA (API XML):
  PML_IVY: sistema=BCA, mercado=MDA, nodo=07IVY-230
  PML_OMS: sistema=BCA, mercado=MDA, nodo=07OMS-230
"""
import io
import time
import zipfile
import requests
import pandas as pd
from datetime import datetime, timedelta

# ── CAISO OASIS ───────────────────────────────────────────────────────────────
OASIS_BASE = "https://oasis.caiso.com/oasisapi/SingleZip"
_TIMEOUT_OASIS = 60

NODE_ROA = "ROA-230_2_N101"   # Rosarito / La Rosita
NODE_TJI = "TJI-230_2_N101"   # Tijuana International

# ── CENACE BCA ────────────────────────────────────────────────────────────────
CENACE_PML_URL = "https://ws01.cenace.gob.mx:8082/SWPML/SIM/{sistema}/{mercado}/{nodo}/{ai}/{mi}/{di}/{af}/{mf}/{df}/XML"
_TIMEOUT_CENACE = 30

NODE_IVY = "07IVY-230"   # Imperial Valley (BCA)
NODE_OMS = "07OMS-230"   # Otay Mesa (BCA)


# ── CAISO helpers ─────────────────────────────────────────────────────────────
def _caiso_dt(d: str, hour: int = 7) -> str:
    """
    Convierte fecha YYYY-MM-DD + hora UTC a formato OASIS YYYYMMDDTHH:MM-0000.
    CAISO usa T07:00-0000 como inicio del dia operativo (00:00 PPT ~ 07:00 UTC).
    """
    return f"{d.replace('-', '')}T{hour:02d}:00-0000"


def _fetch_oasis_xml(queryname: str, start_dt: str, end_dt: str,
                     version: str = "1", **kwargs) -> pd.DataFrame:
    """
    Hace GET a OASIS SingleZip y parsea el XML dentro del ZIP.
    Retorna DataFrame con campos: DATA_ITEM, RESOURCE_NAME, OPR_DATE,
    INTERVAL_NUM, INTERVAL_START_GMT, INTERVAL_END_GMT, VALUE.
    """
    params = {
        "queryname":     queryname,
        "startdatetime": start_dt,
        "enddatetime":   end_dt,
        "version":       version,
    }
    params.update(kwargs)

    for attempt in range(4):
        resp = requests.get(OASIS_BASE, params=params, timeout=_TIMEOUT_OASIS, verify=False)
        if resp.status_code == 429:
            wait = 10 * (attempt + 1)
            print(f"[CAISO] Rate limit, esperando {wait}s...")
            time.sleep(wait)
            continue
        resp.raise_for_status()
        break

    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        fname = zf.namelist()[0]
        with zf.open(fname) as f:
            xml_bytes = f.read()

    return _parse_oasis_xml(xml_bytes)


def _parse_oasis_xml(xml_bytes: bytes) -> pd.DataFrame:
    """
    Parsea el XML de OASIS y extrae filas de REPORT_DATA.
    Soporta versiones v1 y v2 del esquema CAISO.
    """
    import xml.etree.ElementTree as ET

    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return pd.DataFrame()

    # Intentar ambas versiones del namespace
    for ns_uri in [
        "http://www.caiso.com/soa/OASISReport_v2.xsd",
        "http://www.caiso.com/soa/OASISReport_v1.xsd",
        "",  # sin namespace
    ]:
        ns = {"ns": ns_uri} if ns_uri else {}
        prefix = "ns:" if ns_uri else ""

        rows = root.findall(f".//{prefix}REPORT_DATA", ns)
        if rows:
            break

    if not rows:
        return pd.DataFrame()

    data = []
    for rd in rows:
        def _get(tag):
            el = rd.find(f"{prefix}{tag}", ns)
            return el.text if el is not None else None

        data.append({
            "DATA_ITEM":           _get("DATA_ITEM"),
            "RESOURCE_NAME":       _get("RESOURCE_NAME"),
            "OPR_DATE":            _get("OPR_DATE"),
            "INTERVAL_NUM":        _get("INTERVAL_NUM"),
            "INTERVAL_START_GMT":  _get("INTERVAL_START_GMT"),
            "INTERVAL_END_GMT":    _get("INTERVAL_END_GMT"),
            "VALUE":               _get("VALUE"),
        })

    return pd.DataFrame(data)


def _lmp_to_hourly(df: pd.DataFrame, price_col: str,
                   intervals_per_hour: int = 1) -> pd.DataFrame:
    """
    Convierte DataFrame de OASIS PRC_LMP/PRC_RTPD_LMP a una serie horaria.
    Filtra DATA_ITEM == 'LMP_PRC', agrupa por hora (promedio si hay multiples).
    Retorna df con columnas: fecha (datetime sin TZ), price_col.
    """
    if df.empty:
        return pd.DataFrame()

    # Filtrar solo LMP
    if "DATA_ITEM" in df.columns:
        df = df[df["DATA_ITEM"] == "LMP_PRC"]

    if df.empty or "INTERVAL_START_GMT" not in df.columns:
        return pd.DataFrame()

    df = df.copy()
    df["fecha"] = pd.to_datetime(df["INTERVAL_START_GMT"], errors="coerce", utc=True)
    df[price_col] = pd.to_numeric(df["VALUE"], errors="coerce")
    df = df.dropna(subset=["fecha", price_col])

    # Convertir a Pacific Local Time (CAISO usa "America/Los_Angeles")
    df["fecha"] = df["fecha"].dt.tz_convert("America/Los_Angeles").dt.tz_localize(None)
    df["fecha"] = df["fecha"].dt.floor("h")

    return df.groupby("fecha")[price_col].mean().reset_index()


# ── Precios DA CAISO (nodos ROA/TJI) ─────────────────────────────────────────
def get_da_prices(fecha_ini: str, fecha_fin: str, node: str) -> pd.DataFrame:
    """
    Precios LMP DA horarios (DAM) para nodo ROA o TJI.
    Retorna df: fecha (datetime hora local CAISO), precio_da.
    """
    ini_dt = datetime.strptime(fecha_ini, "%Y-%m-%d")
    fin_dt = datetime.strptime(fecha_fin, "%Y-%m-%d")

    frames = []
    cur = ini_dt
    while cur <= fin_dt:
        d   = cur.strftime("%Y-%m-%d")
        d1  = (cur + timedelta(days=1)).strftime("%Y-%m-%d")
        try:
            df = _fetch_oasis_xml(
                "PRC_LMP",
                _caiso_dt(d,  hour=7),
                _caiso_dt(d1, hour=7),
                version="1",
                market_run_id="DAM",
                node=node,
            )
            if not df.empty:
                frames.append(df)
        except Exception as e:
            print(f"[CAISO DA] {d} {node} error: {e}")
        cur += timedelta(days=1)

    if not frames:
        return pd.DataFrame(columns=["fecha", "precio_da"])

    df_all = pd.concat(frames, ignore_index=True)
    result = _lmp_to_hourly(df_all, "precio_da")
    return result if not result.empty else pd.DataFrame(columns=["fecha", "precio_da"])


# ── Precios FMM/RT CAISO (nodos ROA/TJI) ─────────────────────────────────────
def get_fmm_prices(fecha_ini: str, fecha_fin: str, node: str) -> pd.DataFrame:
    """
    Precios LMP RTPD (15-min) para nodo ROA o TJI, promediados a horario.
    Retorna df: fecha, precio_fmm.
    """
    ini_dt = datetime.strptime(fecha_ini, "%Y-%m-%d")
    fin_dt = datetime.strptime(fecha_fin, "%Y-%m-%d")

    frames = []
    cur = ini_dt
    while cur <= fin_dt:
        d  = cur.strftime("%Y-%m-%d")
        d1 = (cur + timedelta(days=1)).strftime("%Y-%m-%d")
        try:
            df = _fetch_oasis_xml(
                "PRC_RTPD_LMP",
                _caiso_dt(d,  hour=7),
                _caiso_dt(d1, hour=7),
                version="3",
                market_run_id="RTPD",
                node=node,
            )
            if not df.empty:
                frames.append(df)
        except Exception as e:
            print(f"[CAISO FMM] {d} {node} error: {e}")
        cur += timedelta(days=1)

    if not frames:
        return pd.DataFrame(columns=["fecha", "precio_fmm"])

    df_all = pd.concat(frames, ignore_index=True)
    result = _lmp_to_hourly(df_all, "precio_fmm")
    return result if not result.empty else pd.DataFrame(columns=["fecha", "precio_fmm"])


# ── PML CENACE BCA (nodos IVY/OMS) ───────────────────────────────────────────
def get_pml_cenace(fecha_ini: str, fecha_fin: str, nodo: str,
                   sistema: str = "BCA", mercado: str = "MDA") -> pd.DataFrame:
    """
    PML horario CENACE para un nodo BCA (07IVY-230 o 07OMS-230).
    Retorna df: fecha (datetime horario), pml.
    URL: https://ws01.cenace.gob.mx:8082/SWPML/SIM/{sistema}/{mercado}/{nodo}/{ai}/{mi}/{di}/{af}/{mf}/{df}/XML
    """
    ini = datetime.strptime(fecha_ini, "%Y-%m-%d")
    fin = datetime.strptime(fecha_fin, "%Y-%m-%d")

    url = CENACE_PML_URL.format(
        sistema=sistema,
        mercado=mercado,
        nodo=nodo,
        ai=ini.year, mi=f"{ini.month:02d}", di=f"{ini.day:02d}",
        af=fin.year, mf=f"{fin.month:02d}", df=f"{fin.day:02d}",
    )

    try:
        resp = requests.get(url, timeout=_TIMEOUT_CENACE, verify=False)
        resp.raise_for_status()
    except Exception as e:
        print(f"[CENACE PML] {nodo} {fecha_ini}-{fecha_fin} error: {e}")
        return pd.DataFrame(columns=["fecha", "pml"])

    return _parse_cenace_pml(resp.content, nodo)


def _parse_cenace_pml(xml_bytes: bytes, nodo: str) -> pd.DataFrame:
    """Parsea respuesta XML del API CENACE PML."""
    import xml.etree.ElementTree as ET

    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return pd.DataFrame()

    rows = []
    # CENACE XML structure: Resultados/Nodo/Valores/Valor
    for nodo_el in root.findall(".//Nodo"):
        for valor in nodo_el.findall(".//Valor"):
            fecha_str = valor.get("fecha") or valor.findtext("fecha")
            hora_str  = valor.get("hora")  or valor.findtext("hora")
            pml_str   = valor.get("pml")   or valor.findtext("pml")

            if not fecha_str or not hora_str or not pml_str:
                continue
            try:
                hora = int(hora_str) - 1  # CENACE usa hora-ending 1-24
                fecha = pd.to_datetime(fecha_str) + pd.to_timedelta(hora, unit="h")
                rows.append({"fecha": fecha, "pml": float(pml_str)})
            except (ValueError, TypeError):
                continue

    if not rows:
        return pd.DataFrame(columns=["fecha", "pml"])

    df = pd.DataFrame(rows)
    return df.groupby("fecha")["pml"].mean().reset_index()


# ── Load CAISO — SLD_FCST DAM via CSV (resultformat=6) ───────────────────────
def get_load(fecha_ini: str, fecha_fin: str) -> pd.DataFrame:
    """
    Carga horaria DAM CAISO (SLD_FCST, resultformat=6 CSV).
    OPR_DATE + OPR_HR ya estan en PPT (Pacific Prevailing Time).
    Retorna df: fecha, load_mw.
    """
    ini_dt = datetime.strptime(fecha_ini, "%Y-%m-%d")
    fin_dt = datetime.strptime(fecha_fin, "%Y-%m-%d")

    frames = []
    cur = ini_dt
    while cur <= fin_dt:
        d  = cur.strftime("%Y-%m-%d")
        d1 = (cur + timedelta(days=1)).strftime("%Y-%m-%d")
        try:
            params = {
                "queryname":     "SLD_FCST",
                "startdatetime": _caiso_dt(d,  hour=7),
                "enddatetime":   _caiso_dt(d1, hour=7),
                "version":       "1",
                "market_run_id": "DAM",
                "resultformat":  6,
            }
            for attempt in range(4):
                resp = requests.get(OASIS_BASE, params=params, timeout=_TIMEOUT_OASIS, verify=False)
                if resp.status_code == 429:
                    time.sleep(10 * (attempt + 1))
                    continue
                resp.raise_for_status()
                break
            with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
                csv_name = next((n for n in zf.namelist() if n.endswith(".csv")), None)
                if csv_name:
                    df_day = pd.read_csv(zf.open(csv_name))
                    df_day.columns = [c.strip().upper() for c in df_day.columns]
                    frames.append(df_day)
        except Exception as e:
            print(f"[CAISO Load] {d} error: {e}")
        cur += timedelta(days=1)

    if not frames:
        return pd.DataFrame(columns=["fecha", "load_mw"])

    df_all = pd.concat(frames, ignore_index=True)

    date_col = next((c for c in ["OPR_DATE", "OPR_DT"] if c in df_all.columns), None)
    hr_col   = next((c for c in ["OPR_HR", "HE", "HOUR_ID"] if c in df_all.columns), None)
    mw_col   = next((c for c in ["MW", "LOAD_MW", "TOTAL"] if c in df_all.columns), None)

    if date_col is None or hr_col is None or mw_col is None:
        print(f"[CAISO Load] columnas no encontradas: {list(df_all.columns)}")
        return pd.DataFrame(columns=["fecha", "load_mw"])

    df_all = df_all.copy()
    # Filtrar a CA ISO-TAC (total sistema) y LABEL SYS_FCST para evitar sub-areas/desvíos
    tac_col   = next((c for c in ["TAC_AREA_NAME", "TAC_AREA"] if c in df_all.columns), None)
    label_col = next((c for c in ["LABEL", "XML_DATA_ITEM"] if c in df_all.columns), None)
    if tac_col:
        mask_tac = df_all[tac_col].str.upper().str.contains("CA ISO", na=False)
        if mask_tac.any():
            df_all = df_all[mask_tac]
    if label_col:
        mask_lbl = df_all[label_col].str.upper().str.contains("SYS_FCST", na=False)
        if mask_lbl.any():
            df_all = df_all[mask_lbl]

    df_all["fecha"]   = pd.to_datetime(df_all[date_col], errors="coerce")
    df_all["_hr"]     = pd.to_numeric(df_all[hr_col], errors="coerce") - 1
    df_all["fecha"]   = df_all["fecha"] + pd.to_timedelta(df_all["_hr"].clip(lower=0), unit="h")
    df_all["load_mw"] = pd.to_numeric(df_all[mw_col], errors="coerce")
    df_all = df_all.dropna(subset=["fecha", "load_mw"])
    return df_all.groupby("fecha")["load_mw"].mean().reset_index()


# ── Solar y Wind CAISO — via SLD_REN_FCST CSV (permite filtrar por tipo) ──────
def _fetch_ren_fcst_csv(fecha_ini: str, fecha_fin: str) -> pd.DataFrame:
    """
    Descarga SLD_REN_FCST DAM en CSV (resultformat=6) para el rango dado.
    Retorna DataFrame con columnas normalizadas en MAYUSCULAS.
    """
    ini_dt = datetime.strptime(fecha_ini, "%Y-%m-%d")
    fin_dt = datetime.strptime(fecha_fin, "%Y-%m-%d")
    frames = []
    cur = ini_dt
    while cur <= fin_dt:
        d  = cur.strftime("%Y-%m-%d")
        d1 = (cur + timedelta(days=1)).strftime("%Y-%m-%d")
        try:
            params = {
                "queryname":     "SLD_REN_FCST",
                "startdatetime": _caiso_dt(d,  hour=7),
                "enddatetime":   _caiso_dt(d1, hour=7),
                "version":       "1",
                "market_run_id": "DAM",
                "resultformat":  6,
            }
            for attempt in range(4):
                resp = requests.get(OASIS_BASE, params=params, timeout=_TIMEOUT_OASIS, verify=False)
                if resp.status_code == 429:
                    time.sleep(10 * (attempt + 1))
                    continue
                resp.raise_for_status()
                break
            with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
                csv_name = next((n for n in zf.namelist() if n.endswith(".csv")), None)
                if csv_name:
                    df_day = pd.read_csv(zf.open(csv_name))
                    df_day.columns = [c.strip().upper() for c in df_day.columns]
                    frames.append(df_day)
        except Exception as e:
            print(f"[CAISO REN CSV] {d} error: {e}")
        cur += timedelta(days=1)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _ren_csv_to_hourly(df: pd.DataFrame, ren_type: str, col: str) -> pd.DataFrame:
    """
    Filtra CSV de SLD_REN_FCST por tipo renovable (SOLAR, WIND) y retorna
    serie horaria en PPT (Pacific Prevailing Time = America/Los_Angeles).
    OPR_DATE + OPR_HR ya estan en PPT — no se necesita conversion de TZ.
    """
    if df.empty:
        return pd.DataFrame(columns=["fecha", col])

    type_col = next((c for c in ["RENEWABLE_TYPE", "FUEL_TYPE"] if c in df.columns), None)
    if type_col:
        df = df[df[type_col].str.upper().str.contains(ren_type.upper(), na=False)].copy()
    if df.empty:
        return pd.DataFrame(columns=["fecha", col])

    date_col = "OPR_DATE" if "OPR_DATE" in df.columns else None
    hr_col   = next((c for c in ["OPR_HR", "HE", "HOUR_ID"] if c in df.columns), None)
    mw_col   = next((c for c in ["LOAD_MW", "RENEWABLE_FORECAST_MW", "MW", "VALUE"] if c in df.columns), None)

    if date_col is None or hr_col is None or mw_col is None:
        return pd.DataFrame(columns=["fecha", col])

    df = df.copy()
    df["fecha"] = pd.to_datetime(df[date_col], errors="coerce")
    df["_hr"]   = pd.to_numeric(df[hr_col], errors="coerce") - 1
    df["fecha"] = df["fecha"] + pd.to_timedelta(df["_hr"].clip(lower=0), unit="h")
    df[col]     = pd.to_numeric(df[mw_col], errors="coerce")
    df = df.dropna(subset=["fecha", col])
    return df.groupby("fecha")[col].sum().reset_index()


def get_solar(fecha_ini: str, fecha_fin: str) -> pd.DataFrame:
    """Solar DAM CAISO (SLD_REN_FCST, tipo SOLAR). Retorna df: fecha, solar_mw."""
    df_all = _fetch_ren_fcst_csv(fecha_ini, fecha_fin)
    result = _ren_csv_to_hourly(df_all, "SOLAR", "solar_mw")
    return result if not result.empty else pd.DataFrame(columns=["fecha", "solar_mw"])


def get_wind(fecha_ini: str, fecha_fin: str) -> pd.DataFrame:
    """Wind DAM CAISO (SLD_REN_FCST, tipo WIND). Retorna df: fecha, wind_mw."""
    df_all = _fetch_ren_fcst_csv(fecha_ini, fecha_fin)
    result = _ren_csv_to_hourly(df_all, "WIND", "wind_mw")
    return result if not result.empty else pd.DataFrame(columns=["fecha", "wind_mw"])
