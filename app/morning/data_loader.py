"""
Carga de datos para Morning Dashboard ERCOT.
Intenta conectarse a la BD; si falla, retorna datos demo sintéticos.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# ── Cargar .env de Extractors/ para que db_connection use el servidor correcto ─
def _load_env():
    _env = os.path.join(os.path.dirname(__file__), "..", "..", "Extractors", ".env")
    if not os.path.exists(_env):
        return
    with open(_env, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            k = k.strip(); v = v.strip().strip('"').strip("'")
            if k and k not in os.environ:
                os.environ[k] = v

_load_env()

# ── Intento de conexión BD ─────────────────────────────────────────────────────
def _get_conn(database="XTS"):
    try:
        from etl.common.db_connection import get_connection
        return get_connection(database)
    except Exception:
        return None


# ── ERCOT: precios + carga + viento ───────────────────────────────────────────
def load_ercot(days: int = 7) -> tuple[pd.DataFrame, bool]:
    """
    Retorna (df, is_live).
    Carga las ultimas `days`*24 horas disponibles en BD (no necesariamente desde hoy).
    df columnas: fecha, DA_DCL, DA_DCR, RT_DCL, RT_DCR,
                 DA_DCL_FCST, DA_DCR_FCST, RT_DCL_FCST, RT_DCR_FCST,
                 LOAD_ERCOT, WIND_ERCOT
    """
    import warnings
    conn = _get_conn("XTS")
    if conn:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                df = pd.read_sql(
                    f"""
                    SELECT TOP {days * 24} fecha,
                           DA_DCL, DA_DCR, RT_DCL, RT_DCR,
                           DA_DCL_FCST, DA_DCR_FCST,
                           RT_DCL_FCST, RT_DCR_FCST,
                           LOAD_ERCOT, WIND_ERCOT
                    FROM dbo.DATOS_ERCOT
                    ORDER BY fecha DESC
                    """,
                    conn,
                )
            conn.close()
            df["fecha"] = pd.to_datetime(df["fecha"])
            df = df.sort_values("fecha").reset_index(drop=True)
            if not df.empty:
                return df, True
        except Exception as e:
            print(f"[data_loader] BD error: {e}")

    return _demo_ercot(days), False


def _demo_ercot(days: int) -> pd.DataFrame:
    np.random.seed(42)
    horas = pd.date_range(end=datetime.today().replace(minute=0, second=0, microsecond=0),
                          periods=days * 24, freq="h")
    n = len(horas)
    hora_idx = horas.hour  # 0-23

    # Perfil horario base (precios suben en picos de demanda)
    perfil = np.array([18, 17, 16, 15, 14, 14, 16, 20, 28, 32, 35, 38,
                       40, 42, 43, 45, 50, 55, 58, 55, 48, 40, 30, 22], dtype=float)

    da_dcl = perfil[hora_idx] + np.random.normal(0, 3, n)
    da_dcr = da_dcl + np.random.normal(-2, 2, n)
    rt_dcl = da_dcl + np.random.normal(0, 8, n)
    rt_dcr = da_dcr + np.random.normal(0, 8, n)

    load_base = np.array([35, 34, 33, 32, 32, 33, 36, 40, 44, 46, 47, 47,
                          47, 48, 48, 49, 51, 53, 54, 52, 49, 45, 41, 37], dtype=float)
    load = load_base[hora_idx] * 1000 + np.random.normal(0, 500, n)

    wind = np.clip(np.random.normal(12000, 3000, n), 2000, 25000)

    return pd.DataFrame({
        "fecha":       horas,
        "DA_DCL":      da_dcl,
        "DA_DCR":      da_dcr,
        "RT_DCL":      rt_dcl,
        "RT_DCR":      rt_dcr,
        "DA_DCL_FCST": da_dcl + np.random.normal(0, 2, n),
        "DA_DCR_FCST": da_dcr + np.random.normal(0, 2, n),
        "RT_DCL_FCST": rt_dcl + np.random.normal(0, 4, n),
        "RT_DCR_FCST": rt_dcr + np.random.normal(0, 4, n),
        "LOAD_ERCOT":  load,
        "WIND_ERCOT":  wind,
    })


# ── Temperaturas ──────────────────────────────────────────────────────────────
def load_temperaturas(days: int = 3) -> tuple[pd.DataFrame, bool]:
    """
    Columnas: fecha, NLR, LRD, RYN, MCA, TIJ, SND
    """
    import warnings
    conn = _get_conn("XTS")
    if conn:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                df = pd.read_sql(
                    f"""
                    SELECT TOP {days * 24} fecha, NLR, LRD, RYN, MCA, TIJ, SND
                    FROM dbo.TEMPERATURAS
                    ORDER BY fecha DESC
                    """,
                    conn,
                )
            conn.close()
            df["fecha"] = pd.to_datetime(df["fecha"])
            df = df.sort_values("fecha").reset_index(drop=True)
            if not df.empty:
                return df, True
        except Exception as e:
            print(f"[data_loader] Temperaturas error: {e}")

    return _demo_temperaturas(days), False


def _demo_temperaturas(days: int) -> pd.DataFrame:
    np.random.seed(7)
    horas = pd.date_range(end=datetime.today().replace(minute=0, second=0, microsecond=0),
                          periods=days * 24, freq="h")
    n = len(horas)
    hora_idx = horas.hour

    perfil = np.array([22, 21, 20, 20, 19, 19, 20, 22, 25, 28, 31, 33,
                       35, 36, 37, 37, 36, 34, 32, 30, 28, 27, 25, 23], dtype=float)

    return pd.DataFrame({
        "fecha": horas,
        "NLR":   perfil[hora_idx] + 2 + np.random.normal(0, 1, n),
        "LRD":   perfil[hora_idx] + 1 + np.random.normal(0, 1, n),
        "RYN":   perfil[hora_idx] + np.random.normal(0, 1, n),
        "MCA":   perfil[hora_idx] - 1 + np.random.normal(0, 1, n),
        "TIJ":   perfil[hora_idx] - 5 + np.random.normal(0, 1, n),
        "SND":   perfil[hora_idx] - 6 + np.random.normal(0, 1, n),
    })


# ── Tipo de cambio ────────────────────────────────────────────────────────────
def load_tipo_cambio() -> tuple[float, bool]:
    """
    Retorna (TC, is_live).
    Intenta obtener el tipo de cambio FIX (para solventar obligaciones) de Banxico.
    Fallback: base de datos local.
    """
    # 1) Banxico SIE — scraping tipCamMIAction (serie SF43718 = FIX solventar obligaciones)
    try:
        import requests
        from bs4 import BeautifulSoup
        r = requests.get(
            "https://www.banxico.org.mx/tipcamb/tipCamMIAction.do",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10,
        )
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            # La tabla tiene columnas: Fecha | Para pagos | Para solventar obligaciones
            # Buscamos la celda con el valor FIX (3ra columna de la primera fila de datos)
            for row in soup.find_all("tr"):
                cells = row.find_all("td")
                if len(cells) >= 3:
                    try:
                        val = float(cells[2].get_text(strip=True).replace(",", "."))
                        if 10 < val < 30:  # rango razonable MXN/USD
                            return val, True
                    except (ValueError, AttributeError):
                        pass
    except Exception as e:
        print(f"[data_loader] Banxico scrape error: {e}")

    # 2) Fallback: base de datos local
    import warnings
    conn = _get_conn("XTS")
    if conn:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                df = pd.read_sql(
                    "SELECT TOP 1 TC FROM dbo.Tipo_Cambio ORDER BY fecha DESC", conn
                )
            conn.close()
            if not df.empty:
                return float(df.iloc[0]["TC"]), True
        except Exception as e:
            print(f"[data_loader] TC BD error: {e}")

    return 17.50, False


# ── CAISO: precios DA/FMM + PML CENACE + Load + Solar ────────────────────────
def load_caiso(days: int = 7) -> tuple[pd.DataFrame, bool]:
    """
    Retorna (df, is_live).
    Carga las ultimas `days`*24 horas disponibles en BD.
    df columnas: fecha, DA_ROA, DA_TJI, FMM_ROA, FMM_TJI,
                 PML_IVY, PML_OMS, LOAD_CAISO, SOLAR_CAISO
    """
    import warnings
    conn = _get_conn("XTS")
    if conn:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                _base_cols = "fecha, DA_ROA, DA_TJI, FMM_ROA, FMM_TJI, PML_IVY, PML_OMS, LOAD_CAISO, SOLAR_CAISO"
                _wind_exists = pd.read_sql(
                    "SELECT COUNT(*) AS n FROM INFORMATION_SCHEMA.COLUMNS "
                    "WHERE TABLE_NAME='DATOS_CAISO' AND COLUMN_NAME='WIND_CAISO'",
                    conn,
                ).iloc[0, 0]
                _sel = _base_cols + (", WIND_CAISO" if _wind_exists else "")
                df = pd.read_sql(
                    f"SELECT {_sel} FROM dbo.DATOS_CAISO "
                    f"WHERE fecha >= DATEADD(day, -{days}, CAST(GETDATE() AS DATE)) "
                    f"ORDER BY fecha ASC",
                    conn,
                )
                if "WIND_CAISO" not in df.columns:
                    df["WIND_CAISO"] = None
            conn.close()
            df["fecha"] = pd.to_datetime(df["fecha"])
            df = df.sort_values("fecha").reset_index(drop=True)
            if not df.empty:
                return df, True
        except Exception as e:
            print(f"[data_loader] CAISO BD error: {e}")

    return _demo_caiso(days), False


def _demo_caiso(days: int) -> pd.DataFrame:
    np.random.seed(99)
    horas = pd.date_range(end=datetime.today().replace(minute=0, second=0, microsecond=0),
                          periods=days * 24, freq="h")
    n = len(horas)
    hora_idx = horas.hour

    perfil = np.array([30, 28, 27, 26, 26, 27, 32, 42, 55, 62, 65, 68,
                       66, 64, 62, 60, 64, 72, 78, 74, 65, 55, 44, 36], dtype=float)

    da_roa = perfil[hora_idx] + np.random.normal(0, 4, n)
    da_tji = da_roa + np.random.normal(-1, 2, n)
    fmm_roa = da_roa + np.random.normal(0, 10, n)
    fmm_tji = da_tji + np.random.normal(0, 10, n)
    tc = 17.5
    pml_ivy = da_roa * tc + np.random.normal(0, 30, n)
    pml_oms = da_roa * tc + np.random.normal(5, 30, n)

    load_base = np.array([22, 21, 20, 20, 20, 21, 24, 28, 33, 37, 40, 42,
                          43, 43, 42, 42, 44, 47, 48, 46, 42, 37, 31, 26], dtype=float)
    load = load_base[hora_idx] * 1000 + np.random.normal(0, 500, n)
    solar = np.clip(np.where((hora_idx >= 7) & (hora_idx <= 18),
                             (np.sin((hora_idx - 7) * np.pi / 11) * 8000)[hora_idx],
                             0) + np.random.normal(0, 300, n), 0, None)

    wind = np.clip(np.random.normal(2000, 500, n), 500, 4000)
    return pd.DataFrame({
        "fecha": horas, "DA_ROA": da_roa, "DA_TJI": da_tji,
        "FMM_ROA": fmm_roa, "FMM_TJI": fmm_tji,
        "PML_IVY": pml_ivy, "PML_OMS": pml_oms,
        "LOAD_CAISO": load, "SOLAR_CAISO": solar, "WIND_CAISO": wind,
    })


# ── Morning snapshot (última entrada) ────────────────────────────────────────
def load_spread_data(nodo_cenace: str, nodo_ercot: str, dias: int = 30) -> tuple[pd.DataFrame, bool, str]:
    """
    Retorna (df, is_live, error_msg).
    df columnas: fecha_dia, pml_mxn, rt_usd, tipo_cambio, pml_usd, spread
    """
    import warnings
    from datetime import date, timedelta
    fecha_ini = (date.today() - timedelta(days=dias)).strftime("%Y-%m-%d")
    conn = _get_conn("XTS")
    if conn is None:
        return pd.DataFrame(), False, "No se pudo obtener conexión a BD (check .env / Tailscale)"
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            df_cenace = pd.read_sql(
                "SELECT CAST(fecha AS DATE) AS fecha_dia, AVG(pml) AS pml_mxn "
                "FROM cenace.pml_nodos_p WHERE nodo=? AND mercado='MDA' AND fecha>=? "
                "GROUP BY CAST(fecha AS DATE)",
                conn, params=[nodo_cenace, fecha_ini],
            )
            rt_col = "RT_DCL" if nodo_ercot.upper() == "DC_L" else "RT_DCR"
            df_ercot = pd.read_sql(
                f"SELECT CAST(fecha AS DATE) AS fecha_dia, AVG({rt_col}) AS rt_usd "
                "FROM dbo.DATOS_ERCOT WHERE fecha>=? "
                "GROUP BY CAST(fecha AS DATE)",
                conn, params=[fecha_ini],
            )
            df_tc = pd.read_sql(
                "SELECT CAST(fecha AS DATE) AS fecha_dia, TC AS tipo_cambio "
                "FROM TIPO_CAMBIO WHERE fecha>=?",
                conn, params=[fecha_ini],
            )
        conn.close()
        df = df_cenace.merge(df_ercot, on="fecha_dia", how="inner")
        df = df.merge(df_tc, on="fecha_dia", how="left")
        df = df.sort_values("fecha_dia")
        df["tipo_cambio"] = df["tipo_cambio"].ffill()
        df["pml_usd"] = df["pml_mxn"] / df["tipo_cambio"]
        df["spread"] = df["rt_usd"] - df["pml_usd"]
        df["fecha_dia"] = pd.to_datetime(df["fecha_dia"])
        if not df.empty:
            return df, True, ""
        return pd.DataFrame(), False, f"Consulta OK pero sin datos (cenace:{len(df_cenace)} ercot:{len(df_ercot)} tc:{len(df_tc)})"
    except Exception as e:
        return pd.DataFrame(), False, str(e)


def load_trades(days: int = 180) -> tuple[pd.DataFrame, bool]:
    """
    Retorna (df, is_live).
    df columnas: id, fecha_operacion, mercado, direccion, nodo, hora, mw,
                 precio_da, precio_rt, contraparte, notas, pnl
    """
    import warnings
    from datetime import date, timedelta
    fecha_ini = (date.today() - timedelta(days=days)).strftime("%Y-%m-%d")
    conn = _get_conn("XTS")
    if conn:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                df = pd.read_sql(
                    "SELECT id, fecha_operacion, mercado, direccion, nodo, hora, mw, "
                    "precio_da, precio_rt, contraparte, notas, created_at "
                    "FROM trading.trades WHERE fecha_operacion >= ? ORDER BY fecha_operacion DESC",
                    conn, params=[fecha_ini],
                )
            conn.close()
            if not df.empty:
                df["fecha_operacion"] = pd.to_datetime(df["fecha_operacion"])
                # P&L: COMPRA = long (gana cuando RT > DA), VENTA = short (gana cuando DA > RT)
                sign = df["direccion"].str.upper().map({"COMPRA": 1, "VENTA": -1}).fillna(1)
                df["pnl"] = sign * (df["precio_rt"] - df["precio_da"]) * df["mw"].abs()
                return df, True
        except Exception as e:
            print(f"[data_loader] trades error: {e}")
    return pd.DataFrame(), False


def load_morning_snapshot() -> tuple[pd.DataFrame, bool]:
    """Última fila de trading.morning_ercot_hist (si existe)."""
    conn = _get_conn("XTS")
    if conn:
        try:
            df = pd.read_sql(
                """
                SELECT TOP 24 *
                FROM trading.morning_ercot_hist
                ORDER BY fecha_operacion DESC, fecha DESC
                """,
                conn,
            )
            conn.close()
            return df, True
        except Exception:
            pass

    return pd.DataFrame(), False


# ══════════════════════════════════════════════════════════════════════════════
# MÓDULO MORNING OFFERS — contrapartes, fees, rutas, ofertas
# ══════════════════════════════════════════════════════════════════════════════

_CP_DEFAULTS = [
    {"id": 1, "code": "MFT",   "name": "MFT",   "price_delta_usd": 0.0, "sort_order": 1, "active": True},
    {"id": 2, "code": "SHELL", "name": "Shell",  "price_delta_usd": 3.0, "sort_order": 2, "active": True},
    {"id": 3, "code": "BETM",  "name": "BETM",   "price_delta_usd": 3.0, "sort_order": 3, "active": True},
]

_FEES_DEFAULTS = {"IMPORT": 20.0, "EXPORT": 15.0, "CARBON": 1.0, "SLEEVE": 3.0}

_PATHS_DEFAULTS = [
    {"id": 1, "code": "ROA_IVY",  "name": "ROA — IVY",              "market": "CAISO", "us_node": "ROA",  "mx_node": "IVY"},
    {"id": 2, "code": "TJI_OMS",  "name": "TJI — OMS",              "market": "CAISO", "us_node": "TJI",  "mx_node": "OMS"},
    {"id": 3, "code": "DC_L_LAA", "name": "DC_L — LAA (Laredo)",    "market": "ERCOT", "us_node": "DC_L", "mx_node": "LAA"},
    {"id": 4, "code": "DC_R_RRD", "name": "DC_R — RRD (Río Grande)", "market": "ERCOT", "us_node": "DC_R", "mx_node": "RRD"},
]


def load_counterparties() -> list[dict]:
    """Retorna lista de contrapartes activas ordenadas por sort_order."""
    import warnings
    conn = _get_conn("XTS")
    if conn:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                df = pd.read_sql(
                    "SELECT id, code, name, price_delta_usd, sort_order, active "
                    "FROM trading.counterparties WHERE active=1 ORDER BY sort_order",
                    conn,
                )
            conn.close()
            if not df.empty:
                return df.to_dict("records")
        except Exception as e:
            print(f"[data_loader] load_counterparties error: {e}")
    return _CP_DEFAULTS


def load_fees() -> dict:
    """Retorna dict {fee_type: fee_usd} de fees activos."""
    import warnings
    conn = _get_conn("XTS")
    if conn:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                df = pd.read_sql(
                    "SELECT fee_type, fee_usd FROM trading.fees WHERE active=1",
                    conn,
                )
            conn.close()
            if not df.empty:
                return dict(zip(df["fee_type"], df["fee_usd"].astype(float)))
        except Exception as e:
            print(f"[data_loader] load_fees error: {e}")
    return _FEES_DEFAULTS


def load_paths() -> list[dict]:
    """Retorna lista de rutas activas."""
    import warnings
    conn = _get_conn("XTS")
    if conn:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                df = pd.read_sql(
                    "SELECT id, code, name, market, us_node, mx_node "
                    "FROM trading.paths WHERE active=1 ORDER BY id",
                    conn,
                )
            conn.close()
            if not df.empty:
                return df.to_dict("records")
        except Exception as e:
            print(f"[data_loader] load_paths error: {e}")
    return _PATHS_DEFAULTS


def save_counterparty(cp_id: int | None, code: str, name: str, delta: float, sort_order: int) -> tuple[bool, str]:
    """Inserta o actualiza una contraparte. cp_id=None para insertar."""
    conn = _get_conn("XTS")
    if not conn:
        return False, "Sin conexión a BD"
    try:
        cur = conn.cursor()
        if cp_id is None:
            cur.execute(
                "INSERT INTO trading.counterparties (code, name, price_delta_usd, sort_order) "
                "VALUES (?, ?, ?, ?)",
                (code.upper(), name, delta, sort_order),
            )
        else:
            cur.execute(
                "UPDATE trading.counterparties "
                "SET code=?, name=?, price_delta_usd=?, sort_order=? WHERE id=?",
                (code.upper(), name, delta, sort_order, cp_id),
            )
        conn.commit()
        conn.close()
        return True, "Guardado"
    except Exception as e:
        return False, str(e)


def save_fee(fee_type: str, fee_usd: float) -> tuple[bool, str]:
    """Actualiza un fee existente."""
    conn = _get_conn("XTS")
    if not conn:
        return False, "Sin conexión a BD"
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE trading.fees SET fee_usd=? WHERE fee_type=?",
            (fee_usd, fee_type.upper()),
        )
        conn.commit()
        conn.close()
        return True, "Guardado"
    except Exception as e:
        return False, str(e)


def load_morning_offers_for_edit(trade_date: str, path_id: int, direction: str) -> "pd.DataFrame":
    """
    Carga oferta existente en formato de grilla (24 filas × columnas de tiers).
    Retorna DataFrame vacío si no hay datos.
    """
    import warnings
    conn = _get_conn("XTS")
    if not conn:
        return pd.DataFrame()
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            cps_df = pd.read_sql(
                "SELECT id, sort_order FROM trading.counterparties WHERE active=1 ORDER BY sort_order",
                conn,
            )
        if cps_df.empty:
            conn.close()
            return pd.DataFrame()
        cp_ids = cps_df.set_index("sort_order")["id"].to_dict()

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            df = pd.read_sql(
                "SELECT mo.hour_ending, mo.tier, mo.be_usd_c1, "
                "ISNULL(l1.volume_mw,0) AS mw_c1, "
                "ISNULL(l2.volume_mw,0) AS mw_c2, "
                "ISNULL(l3.volume_mw,0) AS mw_c3 "
                "FROM trading.morning_offers mo "
                "LEFT JOIN trading.morning_offer_lines l1 ON l1.offer_id=mo.id AND l1.cp_id=? "
                "LEFT JOIN trading.morning_offer_lines l2 ON l2.offer_id=mo.id AND l2.cp_id=? "
                "LEFT JOIN trading.morning_offer_lines l3 ON l3.offer_id=mo.id AND l3.cp_id=? "
                "WHERE mo.trade_date=? AND mo.path_id=? AND mo.direction=? "
                "ORDER BY mo.hour_ending, mo.tier",
                conn,
                params=[cp_ids.get(1, 0), cp_ids.get(2, 0), cp_ids.get(3, 0),
                        trade_date, path_id, direction],
            )
        conn.close()
        if df.empty:
            return pd.DataFrame()

        grid: dict = {}
        for _, row in df.iterrows():
            he, t = int(row["hour_ending"]), int(row["tier"])
            if he not in grid:
                grid[he] = {"HE": he,
                            "T1 BE $": 0.0, "T1 MW C1": 0.0, "T1 MW C2": 0.0, "T1 MW C3": 0.0,
                            "T2 BE $": 0.0, "T2 MW C1": 0.0, "T2 MW C2": 0.0, "T2 MW C3": 0.0,
                            "T3 BE $": 0.0, "T3 MW C1": 0.0, "T3 MW C2": 0.0, "T3 MW C3": 0.0}
            grid[he][f"T{t} BE $"]   = float(row["be_usd_c1"])
            grid[he][f"T{t} MW C1"]  = float(row["mw_c1"])
            grid[he][f"T{t} MW C2"]  = float(row["mw_c2"])
            grid[he][f"T{t} MW C3"]  = float(row["mw_c3"])

        for he in range(1, 25):
            if he not in grid:
                grid[he] = {"HE": he,
                            "T1 BE $": 0.0, "T1 MW C1": 0.0, "T1 MW C2": 0.0, "T1 MW C3": 0.0,
                            "T2 BE $": 0.0, "T2 MW C1": 0.0, "T2 MW C2": 0.0, "T2 MW C3": 0.0,
                            "T3 BE $": 0.0, "T3 MW C1": 0.0, "T3 MW C2": 0.0, "T3 MW C3": 0.0}

        return pd.DataFrame(list(grid.values())).sort_values("HE").reset_index(drop=True)
    except Exception as e:
        print(f"[data_loader] load_morning_offers_for_edit error: {e}")
        return pd.DataFrame()


def save_morning_offers(trade_date: str, path_id: int, direction: str, tdc: float,
                        fees: dict, grid_df: "pd.DataFrame",
                        counterparties: list, cpt_off: int = 0) -> tuple[bool, str]:
    """
    Guarda ofertas de mañana (DELETE + INSERT).
    grid_df: 24 filas, columnas HE, T1 BE $, T1 MW C1/C2/C3, T2..., T3...
    """
    conn = _get_conn("XTS")
    if not conn:
        return False, "Sin conexión a BD"

    fee_carbon = fees.get("CARBON", 1.0)
    fee_sleeve = fees.get("SLEEVE", 3.0)
    if direction == "IMPO":
        fee_dir, sign = fees.get("IMPORT", 20.0), 1
    else:
        fee_dir, sign = fees.get("EXPORT", 15.0), -1
    fee_total = fee_dir + fee_carbon + fee_sleeve

    try:
        cur = conn.cursor()

        # Migración: agregar be_ofertado_usd si no existe
        cur.execute(
            "IF NOT EXISTS (SELECT 1 FROM sys.columns "
            "WHERE object_id=OBJECT_ID('trading.morning_offers') AND name='be_ofertado_usd') "
            "ALTER TABLE trading.morning_offers ADD be_ofertado_usd FLOAT NULL"
        )
        conn.commit()

        cur.execute(
            "DELETE mol FROM trading.morning_offer_lines mol "
            "JOIN trading.morning_offers mo ON mo.id=mol.offer_id "
            "WHERE mo.trade_date=? AND mo.path_id=? AND mo.direction=?",
            (trade_date, path_id, direction),
        )
        cur.execute(
            "DELETE FROM trading.morning_offers WHERE trade_date=? AND path_id=? AND direction=?",
            (trade_date, path_id, direction),
        )

        n_cps = len(counterparties)
        n_saved = 0
        for _, row in grid_df.iterrows():
            he = int(row["HE"])

            # BE ofertado: min (IMPO) o max (EXPO) de tiers con MW total > 0
            active_bes = []
            for t in [1, 2, 3]:
                total_mw = sum(
                    float(row.get(f"T{t} MW C{ci+1}", 0.0)) for ci in range(n_cps)
                )
                if total_mw > 0:
                    active_bes.append(float(row[f"T{t} BE $"]))
            be_ofertado = (
                (min(active_bes) if direction == "IMPO" else max(active_bes))
                if active_bes else None
            )

            for tier in [1, 2, 3]:
                be_c1 = float(row[f"T{tier} BE $"])
                mws = [float(row.get(f"T{tier} MW C{ci+1}", 0.0)) for ci in range(n_cps)]
                if be_c1 == 0 and all(m == 0 for m in mws):
                    continue

                cur.execute(
                    "INSERT INTO trading.morning_offers "
                    "(trade_date,path_id,direction,hour_ending,hour_ending_cpt,"
                    "tier,tdc,be_usd_c1,be_ofertado_usd) "
                    "OUTPUT INSERTED.id VALUES (?,?,?,?,?,?,?,?,?)",
                    (trade_date, path_id, direction, he, he + cpt_off,
                     tier, tdc, be_c1, be_ofertado),
                )
                offer_id = cur.fetchone()[0]

                for i, cp in enumerate(counterparties):
                    delta = float(cp["price_delta_usd"])
                    be_cp = be_c1 + sign * delta
                    price_mxn = (be_cp + sign * fee_total) * tdc
                    cur.execute(
                        "INSERT INTO trading.morning_offer_lines "
                        "(offer_id,cp_id,volume_mw,be_usd,price_mxn) VALUES (?,?,?,?,?)",
                        (offer_id, int(cp["id"]), mws[i] if i < len(mws) else 0.0,
                         round(be_cp, 4), round(price_mxn, 4)),
                    )
                n_saved += 1

        conn.commit()
        conn.close()
        return True, f"{n_saved} registros guardados"
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        return False, str(e)


def load_be_ofertado(trade_date: str) -> pd.DataFrame:
    """
    Retorna tabla pivoteada con be_ofertado_usd por hora para una fecha dada.
    Columnas: hour_ending, <path_name> IMPO, <path_name> EXPO, ...
    """
    conn = _get_conn("XTS")
    if not conn:
        return pd.DataFrame()
    try:
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            df = pd.read_sql(
                "SELECT mo.hour_ending, p.name AS path_name, p.mx_node, mo.direction, "
                "MAX(mo.be_ofertado_usd) AS be_ofertado_usd "
                "FROM trading.morning_offers mo "
                "JOIN trading.paths p ON p.id = mo.path_id "
                "WHERE mo.trade_date = ? "
                "GROUP BY mo.hour_ending, p.name, p.mx_node, mo.direction "
                "ORDER BY mo.hour_ending, p.name, mo.direction",
                conn, params=[trade_date],
            )
        conn.close()
        if df.empty:
            return pd.DataFrame()
        pivot = df.pivot_table(
            index="hour_ending",
            columns=["mx_node", "direction"],
            values="be_ofertado_usd",
            aggfunc="max",
        )
        pivot.columns = [f"{mx} {d}" for mx, d in pivot.columns]
        pivot = pivot.reset_index().rename(columns={"hour_ending": "HE"})
        for c in pivot.columns:
            if c != "HE":
                pivot[c] = pivot[c].apply(lambda x: f"${x:.2f}" if pd.notna(x) else "—")
        return pivot
    except Exception:
        return pd.DataFrame()


def calc_offer_prices(be_usd_c1: float, tdc: float, fees: dict, counterparties: list[dict], direction: str) -> list[dict]:
    """
    Calcula precio MXN por contraparte dado un break-even C1.

    Fórmula:
      IMPO: precio_mxn = (be + delta + fee_IMPORT + fee_CARBON + fee_SLEEVE) * TDC
      EXPO: precio_mxn = (be - delta - fee_EXPORT - fee_CARBON - fee_SLEEVE) * TDC

    Retorna lista [{code, name, delta, be_usd, price_mxn}]
    """
    fee_carbon = fees.get("CARBON", 1.0)
    fee_sleeve = fees.get("SLEEVE", 3.0)
    if direction == "IMPO":
        fee_dir = fees.get("IMPORT", 20.0)
        sign = 1
    else:
        fee_dir = fees.get("EXPORT", 15.0)
        sign = -1

    fee_total = fee_dir + fee_carbon + fee_sleeve
    result = []
    for cp in counterparties:
        delta = float(cp["price_delta_usd"])
        be_cp = be_usd_c1 + sign * delta
        price_mxn = (be_cp + sign * fee_total) * tdc
        result.append({
            "code":      cp["code"],
            "name":      cp["name"],
            "delta":     delta,
            "be_usd":    round(be_cp, 4),
            "price_mxn": round(price_mxn, 4),
        })
    return result
