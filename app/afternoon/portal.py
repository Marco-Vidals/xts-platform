"""
XTS Afternoon Trading Platform
Captura resultados post-clearing, registro de trades y calculo de P&L.
Correr con: streamlit run app/afternoon/portal.py --server.port 8502
"""
import sys, os
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "Extractors", ".env"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, date, timedelta
import requests, warnings
import urllib3, base64 as _b64c

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ── Logo ───────────────────────────────────────────────────────────────────────
def _xts_logo_uri(height_px: int = 44) -> str:
    w = int(height_px * 2.45)
    svg = (
        f'<svg width="{w}" height="{height_px}" viewBox="0 0 {w} {height_px}" '
        'xmlns="http://www.w3.org/2000/svg">'
        '<defs><linearGradient id="g" x1="0%" y1="0%" x2="100%" y2="0%">'
        '<stop offset="0%" stop-color="#00eed8"/>'
        '<stop offset="40%" stop-color="#008888"/>'
        '<stop offset="100%" stop-color="#1c2b58"/>'
        '</linearGradient></defs>'
        f'<text x="1" y="{int(height_px * 0.9)}" '
        'font-family="Arial Black,Franklin Gothic Heavy,Segoe UI Black,sans-serif" '
        f'font-weight="900" font-size="{height_px}" letter-spacing="-2" fill="url(#g)">XTS</text>'
        '</svg>'
    )
    enc = _b64c.b64encode(svg.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{enc}"

_XTS_IMG    = f'<img src="{_xts_logo_uri(44)}" alt="XTS" style="height:44px;display:block;"/>'
_XTS_IMG_SM = f'<img src="{_xts_logo_uri(33)}" alt="XTS" style="height:33px;display:block;"/>'

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="XTS Afternoon Platform",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Session state ──────────────────────────────────────────────────────────────
if "logged_in"   not in st.session_state: st.session_state.logged_in   = False
if "auth"        not in st.session_state: st.session_state.auth        = None

# ══════════════════════════════════════════════════════════════════════════════
# LOGIN
# ══════════════════════════════════════════════════════════════════════════════
ENVERUS_USER = os.environ.get("ENVERUS_USER", "mvidals@xiix.mx")
ENVERUS_PASS = os.environ.get("ENVERUS_PASS", "")

def _enverus_login(user, password):
    try:
        resp = requests.get(
            "https://api-mosaic-prod.enverus.com/mosaic-api/datasets",
            auth=(user, password),
            params={"response_type": "csv_wide", "response_info": "base"},
            timeout=15, verify=False,
        )
        if resp.status_code == 200:
            return (user, password)
    except Exception:
        pass
    return None

if not st.session_state.logged_in:
    st.markdown("""
    <style>
        .stApp { background-color: #2d3242 !important; }
        [data-testid="stSidebar"], [data-testid="collapsedControl"] { display: none !important; }
        #MainMenu, footer, header { visibility: hidden !important; }
        .block-container { padding-top: 0 !important; max-width: 100% !important; }
        .stTextInput > div > div > input {
            background-color: #e9ebf0 !important; color: #1e2130 !important;
            border: none !important; border-radius: 3px !important; height: 42px !important; }
        .stButton > button {
            background-color: #1e2130 !important; color: #c0c4cc !important;
            border: 2px solid #f59e0b !important; border-radius: 4px !important;
            font-size: 0.9rem !important; font-weight: 700 !important;
            letter-spacing: 1.5px !important; text-transform: uppercase !important;
            width: 100% !important; height: 44px !important; margin-top: 4px !important; }
        .stButton > button:hover { background-color: #f59e0b !important; color: #1e2130 !important; }
    </style>""", unsafe_allow_html=True)

    st.markdown(
        "<div style='position:fixed;top:16px;left:28px;z-index:999;display:flex;align-items:center;gap:10px;'>"
        + _XTS_IMG
        + "<div style='color:#f59e0b;font-size:0.65rem;letter-spacing:2px;text-transform:uppercase;"
        "font-family:Segoe UI,sans-serif;align-self:flex-end;padding-bottom:6px;'>Afternoon Platform</div></div>",
        unsafe_allow_html=True,
    )
    st.markdown("<div style='height:28vh'></div>", unsafe_allow_html=True)

    _, col, _ = st.columns([1, 0.9, 1])
    with col:
        st.markdown(
            """<div style="background:#1e2130; border:1px solid #f59e0b40; border-radius:8px;
                padding:32px 36px 28px 36px;">
                <div style="color:#f59e0b; font-size:0.72rem; letter-spacing:3px;
                            text-transform:uppercase; margin-bottom:20px; text-align:center;">
                    Afternoon Platform
                </div>""",
            unsafe_allow_html=True,
        )
        user_in = st.text_input("Usuario", value=ENVERUS_USER, key="apm_user")
        pass_in = st.text_input("Contraseña", type="password", key="apm_pass")
        if st.button("ENTRAR", key="apm_btn"):
            if user_in and pass_in:
                with st.spinner("Autenticando..."):
                    auth = _enverus_login(user_in, pass_in)
                if auth:
                    st.session_state.logged_in = True
                    st.session_state.auth = auth
                    st.rerun()
                else:
                    st.error("Credenciales invalidas.")
        st.markdown("</div>", unsafe_allow_html=True)
    st.stop()


# ══════════════════════════════════════════════════════════════════════════════
# CSS GLOBAL
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("""<style>
    .stApp { background-color: #1a1e2e !important; }
    #MainMenu, footer, header { visibility: hidden !important; }
    .block-container { padding-top: 1rem !important; padding-bottom: 1rem !important; max-width: 100% !important; }
    html, body, [class*="css"] { color: #c0c4cc !important; font-family: 'Segoe UI', 'Consolas', monospace; }
    h1 { color: #f59e0b !important; font-size: 1.4rem !important; font-weight: 700 !important;
         letter-spacing: 1.5px !important; text-transform: uppercase !important;
         border-bottom: 1px solid #2d3350 !important; padding-bottom: 0.5rem !important; margin-bottom: 1rem !important; }
    h2, h3, h4 { color: #c0c4cc !important; font-size: 0.95rem !important; }
    [data-testid="stSidebar"] { background-color: #12151f !important; border-right: 1px solid #2d3350 !important; }
    [data-testid="stSidebar"] * { color: #c0c4cc !important; }
    [data-testid="stSidebar"] [data-testid="stSelectbox"] > div > div {
        background-color: #2d3350 !important; border: 1px solid #3d4468 !important; border-radius: 4px !important; }
    [data-testid="stSidebar"] [data-testid="stSelectbox"] > div > div > div,
    [data-testid="stSidebar"] [data-testid="stSelectbox"] span { color: #f59e0b !important; font-weight: 600 !important; }
    [data-testid="stSidebar"] [data-testid="stSelectbox"] svg { fill: #f59e0b !important; }
    [data-testid="stDataFrame"] { background-color: #1e2130 !important; border: 1px solid #2d3350 !important; }
    [data-testid="stDataFrame"] * { color: #c0c4cc !important; font-size: 0.82rem !important; font-family: Consolas, monospace !important; }
    [data-testid="stDataFrame"] th { background-color: #12151f !important; color: #5a6280 !important; }
    .stForm { border: 1px solid #2d3350 !important; border-radius: 8px !important; padding: 12px !important; }
    ::-webkit-scrollbar { width: 5px; height: 5px; }
    ::-webkit-scrollbar-track { background: #1a1e2e; }
    ::-webkit-scrollbar-thumb { background: #2d3350; border-radius: 3px; }
    .kpi-card { background: #1e2130; border-radius: 6px; padding: 12px 16px;
                border: 1px solid #2d3350; border-left: 3px solid #f59e0b; }
    .kpi-label { color: #5a6280; font-size: 0.68rem; text-transform: uppercase; letter-spacing: 1.2px; font-weight: 600; }
    .kpi-value { color: #f59e0b; font-size: 1.5rem; font-weight: 700; font-family: Consolas, monospace; margin: 3px 0; }
    .kpi-green  { color: #34d399 !important; }
    .kpi-red    { color: #f87171 !important; }
    .kpi-sub    { color: #5a6280; font-size: 0.74rem; }
    .pnl-pos { color: #34d399; font-weight: 700; }
    .pnl-neg { color: #f87171; font-weight: 700; }
    .trade-badge-import { background:#0d1a2e; color:#60a5fa; border:1px solid #60a5fa;
                          padding:2px 8px; border-radius:3px; font-size:0.72rem; font-weight:600; }
    .trade-badge-export { background:#1a0d2e; color:#c084fc; border:1px solid #c084fc;
                          padding:2px 8px; border-radius:3px; font-size:0.72rem; font-weight:600; }
</style>""", unsafe_allow_html=True)

# ── Colores ────────────────────────────────────────────────────────────────────
PLOT_BG  = "#1e2130"
PAPER_BG = "#1e2130"
GRID_COL = "#2d3350"
FONT_COL = "#c0c4cc"

COL_DA   = "#60a5fa"   # blue   — DA price
COL_RT   = "#f87171"   # red    — RT price
COL_DART = "#f59e0b"   # amber  — DART spread
COL_POS  = "#34d399"   # green  — positive P&L
COL_NEG  = "#f87171"   # red    — negative P&L
COL_PML  = "#a78bfa"   # purple — CENACE PML
CENACE_BASE = "https://ws01.cenace.gob.mx:8082/SWPML/SIM"


# ══════════════════════════════════════════════════════════════════════════════
# DB CONNECTION
# ══════════════════════════════════════════════════════════════════════════════
def _get_conn(database="XTS"):
    try:
        from etl.common.db_connection import get_connection
        return get_connection(database)
    except Exception:
        return None


# ══════════════════════════════════════════════════════════════════════════════
# DATA LOADERS
# ══════════════════════════════════════════════════════════════════════════════
@st.cache_data(ttl=300, show_spinner=False)
def load_ercot_today(d: date) -> tuple[pd.DataFrame, bool]:
    """DA + RT prices for today from DATOS_ERCOT."""
    conn = _get_conn()
    if conn:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                df = pd.read_sql(
                    """
                    SELECT fecha, DA_DCL, DA_DCR, RT_DCL, RT_DCR,
                           LOAD_ERCOT, WIND_ERCOT
                    FROM dbo.DATOS_ERCOT
                    WHERE CAST(fecha AS DATE) IN (?, ?)
                    ORDER BY fecha
                    """,
                    conn, params=[d - timedelta(days=1), d],
                )
            conn.close()
            df["fecha"] = pd.to_datetime(df["fecha"])
            if not df.empty:
                return df, True
        except Exception as e:
            print(f"[afternoon] ERCOT error: {e}")
    return pd.DataFrame(), False


@st.cache_data(ttl=300, show_spinner=False)
def load_cenace_today(d: date) -> tuple[pd.DataFrame, bool]:
    """CENACE PML data from DATOS_CAISO (PML_IVY, PML_OMS) + live API."""
    conn = _get_conn()
    if conn:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                df = pd.read_sql(
                    """
                    SELECT fecha, DA_ROA, DA_TJI, FMM_ROA, FMM_TJI,
                           PML_IVY, PML_OMS
                    FROM dbo.DATOS_CAISO
                    WHERE CAST(fecha AS DATE) IN (?, ?)
                    ORDER BY fecha
                    """,
                    conn, params=[d - timedelta(days=1), d],
                )
            conn.close()
            df["fecha"] = pd.to_datetime(df["fecha"])
            if not df.empty:
                return df, True
        except Exception as e:
            print(f"[afternoon] CAISO error: {e}")
    return pd.DataFrame(), False


@st.cache_data(ttl=600, show_spinner=False)
def load_capacidades() -> pd.DataFrame:
    conn = _get_conn()
    if conn:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                df = pd.read_sql("SELECT TOP 200 * FROM dbo.CAPACIDADES ORDER BY 1 DESC", conn)
            conn.close()
            return df
        except Exception:
            pass
    return pd.DataFrame()


@st.cache_data(ttl=600, show_spinner=False)
def load_def_exc() -> pd.DataFrame:
    conn = _get_conn()
    if conn:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                df = pd.read_sql("SELECT TOP 200 * FROM dbo.DEF_EXC ORDER BY 1 DESC", conn)
            conn.close()
            return df
        except Exception:
            pass
    return pd.DataFrame()


@st.cache_data(ttl=600, show_spinner=False)
def load_ofertas() -> pd.DataFrame:
    conn = _get_conn()
    if conn:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                df = pd.read_sql(
                    """
                    SELECT TOP 200 'T1' AS tier, * FROM dbo.OFERTAS_T1
                    UNION ALL
                    SELECT TOP 200 'T2', * FROM dbo.OFERTAS_T2
                    UNION ALL
                    SELECT TOP 200 'T3', * FROM dbo.OFERTAS_T3
                    ORDER BY 1
                    """,
                    conn,
                )
            conn.close()
            return df
        except Exception:
            pass
    return pd.DataFrame()


def load_trades(d: date) -> pd.DataFrame:
    """Carga trades de la fecha dada. No cache (puede cambiar frecuentemente)."""
    conn = _get_conn()
    if conn:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                df = pd.read_sql(
                    "SELECT * FROM trading.trades WHERE fecha_operacion = ? ORDER BY hora, mercado",
                    conn, params=[d],
                )
            conn.close()
            return df
        except Exception as e:
            print(f"[afternoon] trades error: {e}")
    return pd.DataFrame()


def insert_trade(row: dict) -> bool:
    """Inserta un trade en trading.trades. Retorna True si OK."""
    import pyodbc
    conn = _get_conn()
    if not conn:
        return False
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO trading.trades
                (fecha_operacion, mercado, direccion, nodo, hora, mw,
                 precio_da, precio_rt, contraparte, notas)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            row["fecha_operacion"], row["mercado"], row["direccion"],
            row["nodo"], row["hora"], row["mw"],
            row.get("precio_da"), row.get("precio_rt"),
            row.get("contraparte"), row.get("notas"),
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        st.error(f"Error guardando trade: {e}")
        return False


def delete_trade(trade_id: int) -> bool:
    conn = _get_conn()
    if not conn:
        return False
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM trading.trades WHERE id = ?", trade_id)
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        st.error(f"Error borrando trade: {e}")
        return False


@st.cache_data(ttl=900, show_spinner=False)
def live_pml_nodo(sistema: str, proceso: str, nodo: str, d: date) -> list:
    """24 valores PML MDA de CENACE para un nodo. None si no disponible."""
    url = (f"{CENACE_BASE}/{sistema}/{proceso}/{nodo}/"
           f"{d.year}/{d.month:02d}/{d.day:02d}/"
           f"{d.year}/{d.month:02d}/{d.day:02d}/JSON")
    try:
        resp = requests.get(url, timeout=30, verify=False)
        valores = resp.json()["Resultados"][0]["Valores"]
        vals = [float(v["pml"]) for v in valores]
        while len(vals) < 24:
            vals.append(None)
        return vals[:24]
    except Exception:
        return [None] * 24


# ══════════════════════════════════════════════════════════════════════════════
# PLOTLY BASE
# ══════════════════════════════════════════════════════════════════════════════
def _plotly_base(title: str = "", height: int = 320) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(
        title=dict(text=title, font=dict(size=13, color=FONT_COL), x=0.01),
        paper_bgcolor=PAPER_BG, plot_bgcolor=PLOT_BG,
        font=dict(color=FONT_COL, size=11),
        margin=dict(l=52, r=16, t=38, b=36),
        height=height,
        xaxis=dict(gridcolor=GRID_COL, showgrid=True, zeroline=False, color=FONT_COL),
        yaxis=dict(gridcolor=GRID_COL, showgrid=True, zeroline=False, color=FONT_COL),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                    font=dict(size=10, color="#ffffff")),
    )
    return fig

HOURS = [f"{h:02d}:00" for h in range(24)]

def kpi(label, value, sub="", color="#f59e0b"):
    return (
        f'<div class="kpi-card" style="border-left-color:{color};">'
        f'<div class="kpi-label">{label}</div>'
        f'<div class="kpi-value" style="color:{color};">{value}</div>'
        f'<div class="kpi-sub">{sub}</div>'
        f'</div>'
    )

def _fmt(v, fmt=".2f", prefix="", suffix="", na="—"):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return na
    return f"{prefix}{v:{fmt}}{suffix}"

def _safe_avg(vals):
    v = [x for x in vals if x is not None]
    return sum(v) / len(v) if v else None


# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown(
        "<div style='text-align:center;padding:14px 0 4px 0;'>"
        + _XTS_IMG
        + "<div style='color:#f59e0b;font-size:0.6rem;letter-spacing:2.5px;text-transform:uppercase;"
        "font-family:Segoe UI,sans-serif;margin-top:6px;'>AFTERNOON PLATFORM</div></div>",
        unsafe_allow_html=True,
    )
    st.divider()

    page = st.selectbox(
        "Página",
        ["Resumen", "DART — ERCOT", "CENACE MDA", "Trades & P&L", "Cross-Border",
         "Ofertas", "Energía Asignada"],
        key="apm_page",
    )
    st.divider()

    hoy_sel = st.date_input("Fecha de operación", value=date.today(), key="apm_fecha")
    st.divider()

    if st.button("Cerrar Sesión", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.auth = None
        st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# CARGA DE DATOS
# ══════════════════════════════════════════════════════════════════════════════
hoy = hoy_sel

with st.spinner("Cargando datos..."):
    df_ercot, live_ercot = load_ercot_today(hoy)
    df_caiso, live_caiso = load_cenace_today(hoy)
    df_trades = load_trades(hoy)

# Separar hoy vs ayer en ERCOT
df_ercot_hoy  = df_ercot[df_ercot["fecha"].dt.date == hoy]        if not df_ercot.empty else pd.DataFrame()
df_ercot_ayer = df_ercot[df_ercot["fecha"].dt.date == hoy - timedelta(days=1)] if not df_ercot.empty else pd.DataFrame()

# ── Header ─────────────────────────────────────────────────────────────────────
_now_str = datetime.now().strftime("%A %d %B %Y  %H:%M")
st.markdown(
    "<div style='display:flex;align-items:center;justify-content:space-between;"
    "padding:0 4px 12px 4px;border-bottom:1px solid #2d3350;margin-bottom:20px;'>"
    + _XTS_IMG_SM
    + f"<div style='flex:1;margin-left:14px;'>"
    "<div style='color:#c0c4cc;font-size:1rem;font-weight:700;letter-spacing:1px;'>AFTERNOON TRADING PLATFORM</div>"
    f"<div style='color:#4a5070;font-size:0.68rem;'>{_now_str} CT · {hoy.strftime('%d %b %Y')}</div>"
    "</div>"
    f"<div style='color:#f59e0b;font-size:0.8rem;font-weight:600;'>"
    f"{'🟢 BD LIVE' if (live_ercot or live_caiso) else '🟡 BD offline'}</div></div>",
    unsafe_allow_html=True,
)


# ══════════════════════════════════════════════════════════════════════════════
# PÁGINA: RESUMEN
# ══════════════════════════════════════════════════════════════════════════════
if page == "Resumen":

    # ── KPIs de precios ────────────────────────────────────────────────────────
    def _col_avg(df, col):
        if df.empty or col not in df.columns:
            return None
        return pd.to_numeric(df[col], errors="coerce").mean()

    da_dcl  = _col_avg(df_ercot_hoy, "DA_DCL")
    da_dcr  = _col_avg(df_ercot_hoy, "DA_DCR")
    rt_dcl  = _col_avg(df_ercot_hoy, "RT_DCL")
    rt_dcr  = _col_avg(df_ercot_hoy, "RT_DCR")
    dart_l  = (da_dcl - rt_dcl) if (da_dcl and rt_dcl) else None
    dart_r  = (da_dcr - rt_dcr) if (da_dcr and rt_dcr) else None

    # Trades P&L
    pnl_total = 0.0
    n_trades  = len(df_trades) if not df_trades.empty else 0
    if not df_trades.empty and "precio_da" in df_trades.columns and "precio_rt" in df_trades.columns:
        for _, row in df_trades.iterrows():
            pda = row.get("precio_da")
            prt = row.get("precio_rt")
            mw  = row.get("mw", 0)
            sig = 1 if str(row.get("direccion", "")).upper() in ("EXPORT", "VIRTUAL SUPPLY") else -1
            if pda and prt and mw:
                pnl_total += (prt - pda) * mw * sig

    k1, k2, k3, k4, k5 = st.columns(5)
    with k1: st.markdown(kpi("DA DCL Prom", _fmt(da_dcl, prefix="$", suffix=" $/MWh"), "Houston/North corridor", COL_DA), unsafe_allow_html=True)
    with k2: st.markdown(kpi("DA DCR Prom", _fmt(da_dcr, prefix="$", suffix=" $/MWh"), "South/West corridor", COL_DA), unsafe_allow_html=True)
    with k3: st.markdown(kpi("DART DCL",    _fmt(dart_l, "+.2f", suffix=" $/MWh"), "DA – RT promedio hoy", COL_DART if dart_l and dart_l >= 0 else COL_NEG), unsafe_allow_html=True)
    with k4: st.markdown(kpi("DART DCR",    _fmt(dart_r, "+.2f", suffix=" $/MWh"), "DA – RT promedio hoy", COL_DART if dart_r and dart_r >= 0 else COL_NEG), unsafe_allow_html=True)
    with k5:
        pnl_col = COL_POS if pnl_total >= 0 else COL_NEG
        st.markdown(kpi("P&L Estimado", _fmt(pnl_total, "+,.0f", prefix="$", suffix=" USD"), f"{n_trades} trades registrados", pnl_col), unsafe_allow_html=True)

    st.markdown("<div style='height:10px;'></div>", unsafe_allow_html=True)

    # ── Gráfica DART hoy ──────────────────────────────────────────────────────
    if not df_ercot_hoy.empty:
        fig = _plotly_base("DART Spread — DA vs RT (hoy)", height=320)
        h_hoy = [f"{int(r['fecha'].hour):02d}:00" for _, r in df_ercot_hoy.iterrows()]

        da_l_vals = df_ercot_hoy["DA_DCL"].tolist() if "DA_DCL" in df_ercot_hoy else []
        rt_l_vals = df_ercot_hoy["RT_DCL"].tolist() if "RT_DCL" in df_ercot_hoy else []
        dart_l_vals = [a - b if a and b and not (np.isnan(a) or np.isnan(b)) else None
                       for a, b in zip(da_l_vals, rt_l_vals)]

        fig.add_trace(go.Bar(x=h_hoy, y=dart_l_vals, name="DART DCL",
                             marker_color=[COL_POS if (v or 0) >= 0 else COL_NEG for v in dart_l_vals]))

        da_r_vals   = df_ercot_hoy["DA_DCR"].tolist() if "DA_DCR" in df_ercot_hoy else []
        rt_r_vals   = df_ercot_hoy["RT_DCR"].tolist() if "RT_DCR" in df_ercot_hoy else []
        dart_r_vals = [a - b if a and b and not (np.isnan(a) or np.isnan(b)) else None
                       for a, b in zip(da_r_vals, rt_r_vals)]
        fig.add_trace(go.Scatter(x=h_hoy, y=dart_r_vals, name="DART DCR",
                                 line=dict(color=COL_DART, width=2), mode="lines+markers"))

        fig.add_hline(y=0, line_dash="dot", line_color=GRID_COL)
        fig.update_layout(yaxis_title="$/MWh")
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    else:
        st.info("Sin datos ERCOT para hoy. Verificar BD o seleccionar fecha con datos.")

    # ── Últimos trades ─────────────────────────────────────────────────────────
    st.markdown("#### Trades del Día")
    if not df_trades.empty:
        disp = df_trades[["mercado", "direccion", "nodo", "hora", "mw",
                           "precio_da", "precio_rt", "contraparte"]].copy()
        disp.columns = ["Mercado", "Dirección", "Nodo", "Hora", "MW",
                        "Precio DA", "Precio RT", "Contraparte"]
        st.dataframe(disp, use_container_width=True, hide_index=True, height=220)
    else:
        st.info("No hay trades registrados para esta fecha. Ve a Trades & P&L para agregar.")

    # ── CENACE MDA en vivo ─────────────────────────────────────────────────────
    st.markdown("#### CENACE MDA — Nodos clave (hoy)")
    nodos_cenace = {
        "06LAA-138 (DC_L/SIN)": ("SIN", "MDA", "06LAA-138"),
        "06RRD-138 (DC_R/SIN)": ("SIN", "MDA", "06RRD-138"),
        "07IVY-230 (IVY/BCA)":  ("BCA", "MDA", "07IVY-230"),
        "07OMS-230 (OMS/BCA)":  ("BCA", "MDA", "07OMS-230"),
    }
    pml_rows = []
    for label, (sis, proc, nod) in nodos_cenace.items():
        vals = live_pml_nodo(sis, proc, nod, hoy)
        avg  = _safe_avg(vals)
        last = next((v for v in reversed(vals) if v is not None), None)
        pml_rows.append({"Nodo": label,
                         "Prom (MXN/MWh)": f"${avg:.1f}" if avg else "—",
                         "Último (MXN/MWh)": f"${last:.1f}" if last else "—"})
    st.dataframe(pd.DataFrame(pml_rows), use_container_width=True, hide_index=True, height=180)


# ══════════════════════════════════════════════════════════════════════════════
# PÁGINA: DART ERCOT
# ══════════════════════════════════════════════════════════════════════════════
elif page == "DART — ERCOT":
    st.markdown("# DART — Day-Ahead vs Real-Time · ERCOT")

    if df_ercot.empty:
        st.warning("Sin datos ERCOT en BD. Verifica conexión o selecciona otra fecha.")
    else:
        # DA hoy + RT hoy
        h_hoy  = [f"{int(r.fecha.hour):02d}:00" for _, r in df_ercot_hoy.iterrows()] if not df_ercot_hoy.empty else []
        h_ayer = [f"{int(r.fecha.hour):02d}:00" for _, r in df_ercot_ayer.iterrows()] if not df_ercot_ayer.empty else []

        def _vals(df, col):
            if df.empty or col not in df.columns:
                return []
            return pd.to_numeric(df[col], errors="coerce").tolist()

        da_l  = _vals(df_ercot_hoy,  "DA_DCL")
        da_r  = _vals(df_ercot_hoy,  "DA_DCR")
        rt_l  = _vals(df_ercot_hoy,  "RT_DCL")
        rt_r  = _vals(df_ercot_hoy,  "RT_DCR")
        da_l_ayer = _vals(df_ercot_ayer, "DA_DCL")
        rt_l_ayer = _vals(df_ercot_ayer, "RT_DCL")

        # KPIs
        dart_l_vals = [a - b if not (np.isnan(a) or np.isnan(b)) else None for a, b in zip(da_l, rt_l)]
        dart_r_vals = [a - b if not (np.isnan(a) or np.isnan(b)) else None for a, b in zip(da_r, rt_r)]
        k1, k2, k3, k4 = st.columns(4)
        with k1: st.markdown(kpi("DA DCL Prom", _fmt(_safe_avg(da_l),  prefix="$", suffix=" $/MWh"), "Hoy · Day-Ahead", COL_DA), unsafe_allow_html=True)
        with k2: st.markdown(kpi("RT DCL Prom", _fmt(_safe_avg(rt_l),  prefix="$", suffix=" $/MWh"), "Hoy · Real-Time", COL_RT), unsafe_allow_html=True)
        with k3: st.markdown(kpi("DART DCL",    _fmt(_safe_avg(dart_l_vals), "+.2f", suffix=" $/MWh"), "Prom hoy · + favorable DA", COL_DART), unsafe_allow_html=True)
        with k4: st.markdown(kpi("DART DCR",    _fmt(_safe_avg(dart_r_vals), "+.2f", suffix=" $/MWh"), "Prom hoy", COL_DART), unsafe_allow_html=True)

        st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)

        # Gráfica DA vs RT — DCL
        fig1 = _plotly_base("DA vs RT — DC_L", height=300)
        if h_ayer and da_l_ayer:
            fig1.add_trace(go.Scatter(x=h_ayer, y=da_l_ayer, name="DA ayer",
                                      line=dict(color="#374151", width=1.5, dash="dot"), opacity=0.6))
        if h_ayer and rt_l_ayer:
            fig1.add_trace(go.Scatter(x=h_ayer, y=rt_l_ayer, name="RT ayer",
                                      line=dict(color="#4b5563", width=1.5, dash="dot"), opacity=0.6))
        if h_hoy and da_l:
            fig1.add_trace(go.Scatter(x=h_hoy, y=da_l, name="DA hoy",
                                      line=dict(color=COL_DA, width=2.5)))
        if h_hoy and rt_l:
            fig1.add_trace(go.Scatter(x=h_hoy, y=rt_l, name="RT hoy",
                                      line=dict(color=COL_RT, width=2)))
        fig1.update_layout(yaxis_title="$/MWh")

        # Gráfica DART spread
        fig2 = _plotly_base("DART Spread (DA − RT)", height=260)
        if h_hoy and dart_l_vals:
            cols_bar = [COL_POS if (v or 0) >= 0 else COL_NEG for v in dart_l_vals]
            fig2.add_trace(go.Bar(x=h_hoy, y=dart_l_vals, name="DART DCL", marker_color=cols_bar))
        if h_hoy and dart_r_vals:
            fig2.add_trace(go.Scatter(x=h_hoy, y=dart_r_vals, name="DART DCR",
                                      line=dict(color=COL_DART, width=2)))
        fig2.add_hline(y=0, line_dash="dot", line_color=GRID_COL)
        fig2.update_layout(yaxis_title="$/MWh")

        st.plotly_chart(fig1, use_container_width=True, config={"displayModeBar": False})
        st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False})

        # Tabla resumen por hora
        if h_hoy:
            rows = []
            for i, h in enumerate(h_hoy):
                d_l = dart_l_vals[i] if i < len(dart_l_vals) else None
                d_r = dart_r_vals[i] if i < len(dart_r_vals) else None
                rows.append({
                    "Hora":     h,
                    "DA DCL":   _fmt(da_l[i] if i < len(da_l) else None, prefix="$"),
                    "RT DCL":   _fmt(rt_l[i] if i < len(rt_l) else None, prefix="$"),
                    "DART DCL": _fmt(d_l, "+.2f", prefix="$") if d_l is not None else "—",
                    "DA DCR":   _fmt(da_r[i] if i < len(da_r) else None, prefix="$"),
                    "RT DCR":   _fmt(rt_r[i] if i < len(rt_r) else None, prefix="$"),
                    "DART DCR": _fmt(d_r, "+.2f", prefix="$") if d_r is not None else "—",
                })
            st.markdown("#### Detalle Hora por Hora")
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True, height=400)


# ══════════════════════════════════════════════════════════════════════════════
# PÁGINA: CENACE MDA
# ══════════════════════════════════════════════════════════════════════════════
elif page == "CENACE MDA":
    st.markdown("# CENACE MDA — Resultados de Clearing")

    nodos = {
        "06LAA-138 · DC_L (SIN)": ("SIN", "MDA", "06LAA-138"),
        "06RRD-138 · DC_R (SIN)": ("SIN", "MDA", "06RRD-138"),
        "07IVY-230 · IVY (BCA)":  ("BCA", "MDA", "07IVY-230"),
        "07OMS-230 · OMS (BCA)":  ("BCA", "MDA", "07OMS-230"),
        "09LBR-230 · LBR (SIN)":  ("SIN", "MDA", "09LBR-230"),
    }

    with st.spinner("Consultando CENACE API..."):
        pml_data = {}
        for label, (sis, proc, nod) in nodos.items():
            pml_data[label] = live_pml_nodo(sis, proc, nod, hoy)

    # KPIs
    cols_kpi = st.columns(len(nodos))
    for i, (label, vals) in enumerate(pml_data.items()):
        avg = _safe_avg(vals)
        nodo_short = label.split("·")[0].strip()
        with cols_kpi[i]:
            st.markdown(kpi(nodo_short, _fmt(avg, prefix="$", suffix=" MXN"), "Prom MDA hoy", COL_PML),
                        unsafe_allow_html=True)

    st.markdown("<div style='height:10px;'></div>", unsafe_allow_html=True)

    # Gráfica todos los nodos
    fig = _plotly_base("PML MDA — Nodos clave (MXN/MWh)", height=350)
    colors = [COL_PML, "#60a5fa", "#34d399", "#f59e0b", "#f87171"]
    for i, (label, vals) in enumerate(pml_data.items()):
        lbl_short = label.split("·")[1].strip().split(" ")[0] if "·" in label else label
        fig.add_trace(go.Scatter(
            x=HOURS, y=vals, name=lbl_short,
            line=dict(color=colors[i % len(colors)], width=2),
            connectgaps=False,
        ))
    fig.update_layout(yaxis_title="MXN/MWh")
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    # Tabla comparativa hora x hora
    st.markdown("#### Precios MDA por Hora")
    tabla_rows = []
    for h in range(24):
        row = {"Hora": f"{h:02d}:00"}
        for label, vals in pml_data.items():
            nodo_short = label.split("·")[1].strip().split(" ")[0]
            row[nodo_short] = f"${vals[h]:.1f}" if vals[h] is not None else "—"
        tabla_rows.append(row)
    st.dataframe(pd.DataFrame(tabla_rows), use_container_width=True, hide_index=True, height=400)

    # Capacidades y DEF/EXC
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("#### Capacidades")
        df_cap = load_capacidades()
        if not df_cap.empty:
            st.dataframe(df_cap.head(50), use_container_width=True, hide_index=True, height=300)
        else:
            st.info("Tabla CAPACIDADES vacía o BD offline.")

    with col_b:
        st.markdown("#### Déficit / Excedente")
        df_de = load_def_exc()
        if not df_de.empty:
            st.dataframe(df_de.head(50), use_container_width=True, hide_index=True, height=300)
        else:
            st.info("Tabla DEF_EXC vacía o BD offline.")


# ══════════════════════════════════════════════════════════════════════════════
# PÁGINA: TRADES & P&L
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Trades & P&L":
    st.markdown("# Trades & P&L")

    tab1, tab2 = st.tabs(["📋 Trades del Día", "➕ Nuevo Trade"])

    # ── Tab 1: Ver trades ─────────────────────────────────────────────────────
    with tab1:
        # Recargar para obtener datos frescos
        df_t = load_trades(hoy)

        if df_t.empty:
            st.info(f"No hay trades registrados para {hoy.strftime('%d %b %Y')}.")
        else:
            # Calcular P&L por trade
            rows_pnl = []
            total_pnl = 0.0
            for _, row in df_t.iterrows():
                pda  = row.get("precio_da")
                prt  = row.get("precio_rt")
                mw   = float(row.get("mw", 0) or 0)
                direc = str(row.get("direccion", ""))
                sig  = 1 if direc.upper() in ("EXPORT", "VIRTUAL SUPPLY") else -1

                if pda and prt and mw:
                    pnl = (float(prt) - float(pda)) * mw * sig
                    total_pnl += pnl
                    pnl_str = f"${pnl:+,.0f}"
                elif pda and mw:
                    pnl_str = "RT pendiente"
                    pnl = None
                else:
                    pnl_str = "—"
                    pnl = None

                rows_pnl.append({
                    "ID":           int(row.get("id", 0)),
                    "Mercado":      row.get("mercado", ""),
                    "Dirección":    direc,
                    "Nodo":         row.get("nodo", ""),
                    "Hora":         int(row.get("hora", 0)),
                    "MW":           mw,
                    "Precio DA":    f"${float(pda):.2f}" if pda else "—",
                    "Precio RT":    f"${float(prt):.2f}" if prt else "—",
                    "P&L (USD)":    pnl_str,
                    "Contraparte":  row.get("contraparte", ""),
                })

            # KPI P&L total
            pnl_col = COL_POS if total_pnl >= 0 else COL_NEG
            k1, k2, k3 = st.columns(3)
            with k1: st.markdown(kpi("P&L Total", f"${total_pnl:+,.0f} USD", "Trades con DA+RT disponibles", pnl_col), unsafe_allow_html=True)
            with k2: st.markdown(kpi("Trades", str(len(df_t)), f"{hoy.strftime('%d %b %Y')}", "#f59e0b"), unsafe_allow_html=True)
            with k3:
                mw_total = float(df_t["mw"].sum()) if "mw" in df_t.columns else 0
                st.markdown(kpi("MW Totales", f"{mw_total:,.1f} MW", "Suma de posiciones", "#60a5fa"), unsafe_allow_html=True)

            st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
            st.dataframe(pd.DataFrame(rows_pnl), use_container_width=True, hide_index=True, height=340)

            # Eliminar trade
            with st.expander("Eliminar trade"):
                tid = st.number_input("ID del trade a eliminar", min_value=1, step=1, key="del_id")
                if st.button("Eliminar", key="btn_del", type="primary"):
                    if delete_trade(int(tid)):
                        st.success(f"Trade #{int(tid)} eliminado.")
                        st.rerun()

    # ── Tab 2: Nuevo trade ────────────────────────────────────────────────────
    with tab2:
        NODOS_SUGERIDOS = {
            "ERCOT":  ["DC_L", "DC_R", "HB_HOUSTON", "HB_NORTH", "HB_SOUTH", "HB_WEST"],
            "CAISO":  ["07IVY-230", "07OMS-230", "ROA-230_2_N101", "TJI-230_2_N101"],
            "CENACE": ["06LAA-138", "06RRD-138", "07IVY-230", "07OMS-230", "09LBR-230"],
            "GTM":    ["09LBR-230", "XULBAL", "AGUACAPA"],
        }

        with st.form("nuevo_trade_form"):
            st.markdown("### Registrar Trade")
            col1, col2 = st.columns(2)
            with col1:
                mercado  = st.selectbox("Mercado",  ["ERCOT", "CAISO", "CENACE", "GTM"])
                direccion = st.selectbox("Dirección", ["IMPORT", "EXPORT", "VIRTUAL SUPPLY", "VIRTUAL DEMAND"])
                hora     = st.number_input("Hora (1-24)", min_value=1, max_value=24, value=datetime.now().hour or 1)
                mw       = st.number_input("MW", min_value=0.1, value=50.0, step=5.0)
            with col2:
                nodos_opts = NODOS_SUGERIDOS.get(mercado, [])
                nodo     = st.selectbox("Nodo", nodos_opts + ["Otro..."])
                if nodo == "Otro...":
                    nodo = st.text_input("Nodo (manual)")
                precio_da = st.number_input("Precio DA ($/MWh)", min_value=0.0, value=0.0, step=0.5)
                precio_rt = st.number_input("Precio RT ($/MWh) — dejar en 0 si no disponible",
                                            min_value=0.0, value=0.0, step=0.5)
                contraparte = st.text_input("Contraparte")

            notas = st.text_area("Notas", height=60)

            submitted = st.form_submit_button("Guardar Trade", type="primary", use_container_width=True)

        if submitted:
            if not nodo or mw <= 0:
                st.error("Nodo y MW son requeridos.")
            else:
                ok = insert_trade({
                    "fecha_operacion": hoy,
                    "mercado":    mercado,
                    "direccion":  direccion,
                    "nodo":       nodo,
                    "hora":       int(hora),
                    "mw":         float(mw),
                    "precio_da":  float(precio_da) if precio_da else None,
                    "precio_rt":  float(precio_rt) if precio_rt else None,
                    "contraparte": contraparte or None,
                    "notas":      notas or None,
                })
                if ok:
                    st.success(f"Trade registrado: {direccion} {mw} MW {nodo} @ hora {int(hora)}")
                    st.cache_data.clear()
                    st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# PÁGINA: CROSS-BORDER
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Cross-Border":
    st.markdown("# Cross-Border Spreads")

    # Tipo de cambio
    try:
        from app.morning.data_loader import load_tipo_cambio
        tc, tc_live = load_tipo_cambio()
    except Exception:
        tc, tc_live = 20.0, False

    # PML vivo CENACE para nodos frontera
    with st.spinner("Consultando CENACE..."):
        pml_laa = live_pml_nodo("SIN", "MDA", "06LAA-138", hoy)
        pml_rrd = live_pml_nodo("SIN", "MDA", "06RRD-138", hoy)
        pml_ivy = live_pml_nodo("BCA", "MDA", "07IVY-230", hoy)
        pml_oms = live_pml_nodo("BCA", "MDA", "07OMS-230", hoy)

    def _usd(pml_vals, tc):
        return [v / tc if v else None for v in pml_vals]

    pml_laa_usd = _usd(pml_laa, tc)
    pml_rrd_usd = _usd(pml_rrd, tc)
    pml_ivy_usd = _usd(pml_ivy, tc)
    pml_oms_usd = _usd(pml_oms, tc)

    # DA ERCOT hoy
    da_l_hoy = df_ercot_hoy["DA_DCL"].tolist() if not df_ercot_hoy.empty and "DA_DCL" in df_ercot_hoy.columns else [None] * 24
    da_r_hoy = df_ercot_hoy["DA_DCR"].tolist() if not df_ercot_hoy.empty and "DA_DCR" in df_ercot_hoy.columns else [None] * 24
    h_hoy = [f"{h:02d}:00" for h in range(24)]
    if not df_ercot_hoy.empty:
        h_hoy_real = [f"{int(r.fecha.hour):02d}:00" for _, r in df_ercot_hoy.iterrows()]
    else:
        h_hoy_real = h_hoy

    # Spreads: ERCOT DA – PML CENACE (en USD)
    spread_l = [a - b if (a and b and not np.isnan(a)) else None
                for a, b in zip(da_l_hoy, pml_laa_usd[:len(da_l_hoy)])]
    spread_r = [a - b if (a and b and not np.isnan(a)) else None
                for a, b in zip(da_r_hoy, pml_rrd_usd[:len(da_r_hoy)])]
    spread_ivy = [a - b if (a and b and not np.isnan(a)) else None
                  for a, b in zip(
                      df_caiso.loc[df_caiso["fecha"].dt.date == hoy, "DA_ROA"].tolist()
                      if not df_caiso.empty and "DA_ROA" in df_caiso.columns else [None] * 24,
                      pml_ivy_usd,
                  )]

    # TC banner
    st.markdown(
        f"<div style='background:#1e2130;border:1px solid #2d3350;border-radius:6px;padding:8px 16px;"
        f"display:flex;align-items:center;gap:24px;margin-bottom:16px;'>"
        f"<span style='color:#5a6280;font-size:0.72rem;'>TIPO CAMBIO FIX</span>"
        f"<span style='color:#B7D433;font-size:1.3rem;font-weight:700;font-family:Consolas;'>{tc:.4f} MXN/USD</span>"
        f"<span style='color:#5a6280;font-size:0.72rem;'>{'🟢 Banxico live' if tc_live else '🟡 Fallback'}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )

    # KPIs spread
    k1, k2, k3, k4 = st.columns(4)
    with k1: st.markdown(kpi("Spread ERCOT–LAA", _fmt(_safe_avg(spread_l), "+.2f", suffix=" $/MWh"), "DA_DCL – PML LAA/TC", COL_DART), unsafe_allow_html=True)
    with k2: st.markdown(kpi("Spread ERCOT–RRD", _fmt(_safe_avg(spread_r), "+.2f", suffix=" $/MWh"), "DA_DCR – PML RRD/TC", COL_DART), unsafe_allow_html=True)
    with k3: st.markdown(kpi("TC hoy",           f"{tc:.4f} MXN", "FIX Banxico", "#B7D433"), unsafe_allow_html=True)
    with k4:
        avg_laa_mxn = _safe_avg(pml_laa)
        avg_laa_usd = avg_laa_mxn / tc if avg_laa_mxn else None
        st.markdown(kpi("PML LAA (USD)", _fmt(avg_laa_usd, prefix="$", suffix=" $/MWh"), f"= ${avg_laa_mxn:.1f} MXN" if avg_laa_mxn else "", "#a78bfa"), unsafe_allow_html=True)

    st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)

    # Gráfica ERCOT DA vs PML CENACE (en USD)
    fig = _plotly_base("ERCOT DA vs PML CENACE (USD/MWh) — Oportunidad de Arbitraje", height=340)
    if da_l_hoy and any(v is not None for v in da_l_hoy):
        fig.add_trace(go.Scatter(x=h_hoy_real, y=da_l_hoy[:len(h_hoy_real)], name="DA DCL (ERCOT)",
                                 line=dict(color=COL_DA, width=2.5)))
    if pml_laa_usd and any(v is not None for v in pml_laa_usd):
        fig.add_trace(go.Scatter(x=HOURS, y=pml_laa_usd, name="PML LAA/TC (MX→USD)",
                                 line=dict(color=COL_PML, width=2.5)))
    if pml_ivy_usd and any(v is not None for v in pml_ivy_usd):
        fig.add_trace(go.Scatter(x=HOURS, y=pml_ivy_usd, name="PML IVY/TC (MX→USD)",
                                 line=dict(color="#34d399", width=2, dash="dot")))
    fig.update_layout(yaxis_title="USD/MWh")
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    # Gráfica spread (arbitraje)
    fig2 = _plotly_base("Spread = ERCOT DA − PML CENACE/TC · (+) → Exportar México a ERCOT", height=260)
    if spread_l and any(v is not None for v in spread_l):
        cols = [COL_POS if (v or 0) >= 0 else COL_NEG for v in spread_l]
        fig2.add_trace(go.Bar(x=h_hoy_real, y=spread_l[:len(h_hoy_real)], name="Spread LAA", marker_color=cols))
    if spread_r and any(v is not None for v in spread_r):
        fig2.add_trace(go.Scatter(x=h_hoy_real, y=spread_r[:len(h_hoy_real)], name="Spread RRD",
                                  line=dict(color=COL_DART, width=2)))
    fig2.add_hline(y=0, line_dash="dot", line_color=GRID_COL)
    fig2.update_layout(yaxis_title="USD/MWh")
    st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False})

    # Ofertas activas
    st.markdown("#### Ofertas Activas (OFERTAS_T1/T2/T3)")
    df_of = load_ofertas()
    if not df_of.empty:
        st.dataframe(df_of.head(100), use_container_width=True, hide_index=True, height=280)
    else:
        st.info("Tabla OFERTAS vacía o BD offline.")


# ══════════════════════════════════════════════════════════════════════════════
# PÁGINA: OFERTAS
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Ofertas":
    st.title("Ofertas")
    st.info("Página en construcción.")


# ══════════════════════════════════════════════════════════════════════════════
# PÁGINA: ENERGÍA ASIGNADA
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Energía Asignada":
    import re as _re

    st.title("Energía Asignada — Confirmación de Flujo")

    uploaded = st.file_uploader(
        "Cargar Excel de Energía Asignada (CENACE)",
        type=["xlsx"],
        key="asig_upload",
        help="Archivo 'Energía asignada DD-MM-YYYY M024-XiiX.xlsx'",
    )

    if uploaded is None:
        st.info("Sube el Excel de energía asignada para comenzar.")
        st.stop()

    # ── Parseo del Excel ───────────────────────────────────────────────────────
    try:
        df_hdr = pd.read_excel(uploaded, header=None, nrows=1, engine="openpyxl")
        title_txt = next(
            (str(df_hdr.iloc[0, c]) for c in df_hdr.columns
             if "asignada" in str(df_hdr.iloc[0, c]).lower()),
            uploaded.name,
        )
        uploaded.seek(0)
        df_raw  = pd.read_excel(uploaded, header=3, engine="openpyxl")
        df_raw.columns = [str(c).strip() for c in df_raw.columns]
        df_data = df_raw[df_raw["Clave"].notna()].copy().reset_index(drop=True)
        hour_cols = [c for c in df_data.columns if _re.match(r"^\d+\-\d+$", c)]

        def _he(col):
            hi = int(col.split("-")[1])
            return 24 if hi == 0 else hi

        he_nums = [_he(c) for c in hour_cols]
    except Exception as exc:
        st.error(f"Error leyendo el Excel: {exc}")
        st.stop()

    # ── KPIs de cabecera ──────────────────────────────────────────────────────
    sistema_val  = str(df_data["Sistema"].iloc[0]) if not df_data.empty else "?"
    total_mwh_all = sum(
        float(r.get("Total de flujo Asignado (MWh)", 0) or 0)
        for _, r in df_data.iterrows()
    )
    nodos_con_asig = sum(
        1 for _, r in df_data.iterrows()
        if float(r.get("Total de flujo Asignado (MWh)", 0) or 0) > 0
    )

    h1, h2, h3, h4 = st.columns(4)
    h1.markdown(kpi("Archivo",         uploaded.name[:28],          "",                       "#60a5fa"), unsafe_allow_html=True)
    h2.markdown(kpi("Sistema",         sistema_val,                  "",                       COL_DART),  unsafe_allow_html=True)
    h3.markdown(kpi("Total Asignado",  f"{total_mwh_all:.0f} MWh",  f"{len(df_data)} nodos",  COL_POS),   unsafe_allow_html=True)
    h4.markdown(kpi("Con Asignación",  str(nodos_con_asig),          "nodos con MW > 0",       COL_RT),    unsafe_allow_html=True)

    st.markdown("<div style='height:14px;'></div>", unsafe_allow_html=True)

    fn = uploaded.name   # parte de las claves de sesión

    # ── Tablas por nodo ────────────────────────────────────────────────────────
    summary_rows = []

    for _, row in df_data.iterrows():
        clave    = str(row.get("Clave", "")).strip()
        tipo     = str(row.get("Tipo",  "")).strip()
        tot_asig = float(row.get("Total de flujo Asignado (MWh)", 0) or 0)
        icon     = "📥" if tipo == "IMP" else "📤"

        asig_vals = [float(row.get(hc, 0) or 0) for hc in hour_cols]

        # ── Estado de sesión para los MW a Fluir ──────────────────────────────
        skey = f"fluir_{fn}_{clave}"
        if skey not in st.session_state:
            st.session_state[skey] = asig_vals.copy()

        fluir_ss = st.session_state[skey]
        # Si cambió el largo (nuevo archivo distinto), reinicializar
        if len(fluir_ss) != len(asig_vals):
            fluir_ss = asig_vals.copy()
            st.session_state[skey] = fluir_ss

        diff_ss = [a - f for a, f in zip(asig_vals, fluir_ss)]

        df_edit = pd.DataFrame({
            "HE":              he_nums,
            "Asignado (MW)":   asig_vals,
            "Fluir (MW)":      fluir_ss,
            "Diferencia (MW)": diff_ss,
        })

        with st.expander(
            f"{icon}  {clave}   ·   {tipo}   ·   Asignado: {tot_asig:.0f} MWh",
            expanded=(tot_asig > 0),
        ):
            edited = st.data_editor(
                df_edit,
                column_config={
                    "HE":              st.column_config.NumberColumn("HE",              disabled=True, width="small",  format="%d"),
                    "Asignado (MW)":   st.column_config.NumberColumn("Asignado (MW)",   disabled=True, width="medium", format="%.1f"),
                    "Fluir (MW)":      st.column_config.NumberColumn("Fluir (MW)",      min_value=0.0, width="medium", step=1.0, format="%.1f"),
                    "Diferencia (MW)": st.column_config.NumberColumn("Diferencia (MW)", disabled=True, width="medium", format="%+.1f"),
                },
                hide_index=True,
                use_container_width=True,
                key=f"de_{fn}_{clave}",
                height=min(len(he_nums) * 35 + 54, 572),
                num_rows="fixed",
            )

            # Persistir valores editados en session_state para próximo render
            new_fluir = edited["Fluir (MW)"].tolist()
            st.session_state[skey] = new_fluir

            # Calcular totales correctos desde el editor actual
            tot_fluir  = sum(new_fluir)
            tot_diff   = tot_asig - tot_fluir
            diff_color = COL_POS if tot_diff == 0 else (COL_RT if tot_diff < 0 else COL_DART)

            kc1, kc2, kc3 = st.columns(3)
            kc1.markdown(kpi("Total Asignado", f"{tot_asig:.0f} MW",  "", COL_DA),        unsafe_allow_html=True)
            kc2.markdown(kpi("Total Fluir",    f"{tot_fluir:.0f} MW", "", COL_POS),        unsafe_allow_html=True)
            kc3.markdown(kpi("Diferencia",     f"{tot_diff:+.0f} MW", "", diff_color),     unsafe_allow_html=True)

        summary_rows.append({
            "Nodo":             clave,
            "Tipo":             tipo,
            "Asignado (MWh)":   f"{tot_asig:.0f}",
            "Fluir (MWh)":      f"{tot_fluir:.0f}",
            "Diferencia (MWh)": f"{tot_diff:+.0f}",
        })

    # ── Resumen global ─────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### Resumen por Nodo")
    st.dataframe(
        pd.DataFrame(summary_rows),
        use_container_width=True,
        hide_index=True,
        height=min(len(summary_rows) * 38 + 54, 360),
    )


# ── Footer ─────────────────────────────────────────────────────────────────────
st.markdown(
    "<div style='margin-top:32px; text-align:center; color:#2d3350; font-size:0.65rem; "
    "border-top:1px solid #1e2540; padding-top:12px;'>"
    "XTS Afternoon Platform v1.0.0 · XIIX Trading Solutions</div>",
    unsafe_allow_html=True,
)
