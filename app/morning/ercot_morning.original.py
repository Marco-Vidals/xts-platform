"""
Morning Dashboard ERCOT — XTS Energy Portal
Correr con: streamlit run app/morning/ercot_morning.py
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from datetime import datetime, date, timedelta
import math
import random
import bisect
import requests
import io
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from app.morning.data_loader import load_ercot, load_temperaturas, load_tipo_cambio

# ── Página ────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Morning ERCOT — XTS",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Session state ─────────────────────────────────────────────────────────────
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "auth" not in st.session_state:
    st.session_state.auth = None

# ══════════════════════════════════════════════════════════════════════════════
# LOGIN
# ══════════════════════════════════════════════════════════════════════════════
if not st.session_state.logged_in:
    st.markdown("""
    <style>
        .stApp { background-color: #2d3242 !important; }
        [data-testid="stSidebar"]        { display: none !important; }
        [data-testid="collapsedControl"] { display: none !important; }
        #MainMenu, footer, header        { visibility: hidden !important; }
        .block-container { padding-top: 0 !important; padding-bottom: 0 !important; max-width: 100% !important; }
        .stTextInput > div > div > input {
            background-color: #e9ebf0 !important; color: #1e2130 !important;
            border: none !important; border-radius: 3px !important;
            height: 42px !important; font-size: 0.92rem !important;
        }
        .stTextInput label { color: #8a90aa !important; font-size: 0.78rem !important; }
        .stButton > button {
            background-color: #1e2130 !important; color: #c0c4cc !important;
            border: 2px solid #00d4e8 !important; border-radius: 4px !important;
            font-size: 0.9rem !important; font-weight: 700 !important;
            letter-spacing: 1.5px !important; text-transform: uppercase !important;
            width: 100% !important; height: 44px !important; margin-top: 4px !important;
        }
        .stButton > button:hover { background-color: #00d4e8 !important; color: #1e2130 !important; }
    </style>
    """, unsafe_allow_html=True)

    # Logo
    st.markdown("""
    <div style="position:fixed; top:16px; left:28px; z-index:999; display:flex; align-items:center; gap:10px;">
        <svg width="130" height="48" viewBox="0 0 130 48" xmlns="http://www.w3.org/2000/svg">
            <defs>
                <linearGradient id="lg-login" x1="0%" y1="0%" x2="100%" y2="0%">
                    <stop offset="0%"   stop-color="#00e5c0"/>
                    <stop offset="50%"  stop-color="#0094cc"/>
                    <stop offset="100%" stop-color="#1a2e70"/>
                </linearGradient>
            </defs>
            <text x="2" y="44" font-family="'Segoe UI Black','Arial Black','Impact',sans-serif"
                  font-weight="900" font-size="50" letter-spacing="3" fill="url(#lg-login)">XTS</text>
        </svg>
        <div style="color:#4a5478; font-size:0.58rem; letter-spacing:2.5px; text-transform:uppercase;
                    font-family:'Segoe UI',sans-serif; align-self:flex-end; padding-bottom:5px;">
            Energy Portal
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<div style='height: 28vh'></div>", unsafe_allow_html=True)
    st.markdown('<p style="text-align:center; color:#c0c4cc; font-size:1.2rem; font-family:Segoe UI; letter-spacing:0.4px; margin-bottom:20px;">Welcome to XTS Energy Portal</p>', unsafe_allow_html=True)

    _, col_form, _ = st.columns([1, 1.8, 1])
    with col_form:
        with st.form("login_form", clear_on_submit=False):
            col_u, col_p, col_btn = st.columns([4, 4, 2])
            with col_u:
                username = st.text_input("Usuario", placeholder="Username", key="inp_user")
            with col_p:
                password = st.text_input("Contraseña", placeholder="Password", type="password", key="inp_pass")
            with col_btn:
                st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
                submitted = st.form_submit_button("LOG IN", use_container_width=True)

        if submitted:
            if username and password:
                with st.spinner("Verificando credenciales…"):
                    try:
                        _test = requests.get(
                            "https://api-mosaic-prod.enverus.com/mosaic-api/datasets",
                            auth=(username, password),
                            params={"response_type": "csv_wide", "response_info": "base"},
                            timeout=15, verify=False,
                        )
                        if _test.status_code == 401:
                            st.error("❌ Usuario o contraseña incorrectos.")
                        elif _test.status_code >= 400:
                            st.error(f"❌ Error de autenticación ({_test.status_code}).")
                        else:
                            st.session_state.auth      = (username, password)
                            st.session_state.logged_in = True
                            st.rerun()
                    except Exception as _e:
                        st.error(f"❌ No se pudo conectar: {_e}")
            else:
                st.error("Ingresa usuario y contraseña.")

    st.markdown('<p style="text-align:center; color:#4a5070; font-size:0.72rem; margin-top:16px;">v1.1.0 · Morning ERCOT</p>', unsafe_allow_html=True)
    st.stop()

# ══════════════════════════════════════════════════════════════════════════════
# CSS GLOBAL (trader terminal)
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<style>
    header, [data-testid="stHeader"], [data-testid="stToolbar"],
    [data-testid="stDecoration"], footer, #MainMenu { display: none !important; }

    html, body                       { background-color: #1a1e2e !important; }
    .stApp                           { background-color: #1a1e2e !important; }
    .block-container                 { padding-top: 1.2rem !important; background-color: #1a1e2e !important; max-width: 100% !important; }
    [data-testid="stAppViewContainer"],
    [data-testid="stMain"]           { background-color: #1a1e2e !important; }

    html, body, [class*="css"]       { color: #c0c4cc !important; font-family: 'Segoe UI', 'Consolas', monospace; }
    h1 { color: #00d4e8 !important; font-size: 1.4rem !important; font-weight: 700 !important;
         letter-spacing: 1.5px !important; text-transform: uppercase !important;
         border-bottom: 1px solid #2d3350 !important; padding-bottom: 0.5rem !important; margin-bottom: 1rem !important; }
    h2, h3, h4 { color: #c0c4cc !important; font-size: 0.95rem !important;
                 letter-spacing: 1px !important; text-transform: uppercase !important; }
    p, span, div, label             { color: #c0c4cc !important; }

    [data-testid="stSidebar"]        { background-color: #12151f !important; border-right: 1px solid #2d3350 !important; }
    [data-testid="stSidebar"] *      { color: #c0c4cc !important; }

    [data-testid="stSidebar"] [data-testid="stRadio"] label {
        background-color: #1e2130 !important; border: 1px solid #2d3350 !important;
        border-radius: 4px !important; padding: 6px 10px !important; margin: 3px 0 !important;
        font-size: 0.82rem !important; letter-spacing: 0.5px !important;
    }
    [data-testid="stSidebar"] [data-testid="stRadio"] label:hover { border-color: #00d4e8 !important; }

    label, [data-testid="stWidgetLabel"] p {
        color: #5a6280 !important; font-size: 0.72rem !important;
        letter-spacing: 1px !important; text-transform: uppercase !important; font-weight: 600 !important;
    }

    [data-testid="stMetric"]           { background-color: #1e2130 !important; border: 1px solid #2d3350 !important; border-radius: 4px !important; padding: 10px 14px !important; }
    [data-testid="stMetricLabel"] *    { color: #5a6280 !important; font-size: 0.72rem !important; text-transform: uppercase !important; }
    [data-testid="stMetricValue"] *    { color: #00d4e8 !important; font-family: 'Consolas', monospace !important; }

    [data-testid="stDataFrame"]        { background-color: #1e2130 !important; border: 1px solid #2d3350 !important; border-radius: 4px !important; }
    [data-testid="stDataFrame"] *      { color: #c0c4cc !important; font-size: 0.82rem !important; font-family: 'Consolas', monospace !important; }
    [data-testid="stDataFrame"] th     { background-color: #12151f !important; color: #5a6280 !important; text-transform: uppercase !important; letter-spacing: 0.8px !important; }

    [data-testid="stAlert"]            { background-color: #1e2130 !important; border-radius: 4px !important; border-left: 3px solid #00d4e8 !important; }
    [data-testid="stExpander"]         { background-color: #1e2130 !important; border: 1px solid #2d3350 !important; border-radius: 4px !important; }

    .stButton > button {
        background-color: #222639 !important; color: #c0c4cc !important;
        border: 1px solid #2d3350 !important; border-radius: 3px !important;
        font-size: 0.8rem !important; letter-spacing: 0.5px !important;
    }
    .stButton > button:hover { border-color: #00d4e8 !important; color: #00d4e8 !important; }
    .stButton > button[kind="primary"] {
        background: linear-gradient(90deg, #00b8cc, #00d4e8) !important;
        color: #0d0f18 !important; font-weight: 800 !important;
        letter-spacing: 1.5px !important; text-transform: uppercase !important;
        border: none !important; border-radius: 3px !important;
    }

    hr { border-color: #2d3350 !important; margin: 8px 0 !important; }

    ::-webkit-scrollbar              { width: 5px; height: 5px; }
    ::-webkit-scrollbar-track        { background: #1a1e2e; }
    ::-webkit-scrollbar-thumb        { background: #2d3350; border-radius: 3px; }
    ::-webkit-scrollbar-thumb:hover  { background: #00d4e8; }

    .kpi-card {
        background: #1e2130; border-radius: 6px; padding: 12px 16px;
        border: 1px solid #2d3350; border-left: 3px solid #00d4e8;
    }
    .kpi-label { color: #5a6280; font-size: 0.68rem; text-transform: uppercase; letter-spacing: 1.2px; font-weight: 600; }
    .kpi-value { color: #00d4e8; font-size: 1.5rem; font-weight: 700; font-family: Consolas, monospace; margin: 3px 0; }
    .kpi-delta-up   { color: #ff6b6b; font-size: 0.78rem; }
    .kpi-delta-down { color: #00d4e8; font-size: 0.78rem; }
    .kpi-sub  { color: #5a6280; font-size: 0.74rem; }

    .demo-banner {
        background: #1e1800; border: 1px solid #7a5c00; border-radius: 4px;
        padding: 6px 14px; margin-bottom: 10px; color: #c8a200; font-size: 0.82rem;
    }
</style>
""", unsafe_allow_html=True)

AUTH = st.session_state.auth

# ── Constantes de estilo para gráficas ───────────────────────────────────────
PLOT_BG   = "#1e2130"
PAPER_BG  = "#1e2130"
GRID_COL  = "#2d3242"
FONT_COL  = "#c0c4cc"
C_AYER    = "#6FA0D8"
C_HOY     = "#00d4e8"
C_MANANA  = "#FF6B35"
C_DA      = "#B7D433"
C_RT      = "#FF6B35"
C_DART    = "#a78bfa"

def _plotly_base(height=400, title=""):
    return dict(
        plot_bgcolor=PLOT_BG, paper_bgcolor=PAPER_BG,
        font=dict(color=FONT_COL, size=11),
        height=height,
        title=dict(text=title, font=dict(size=13, color=FONT_COL)),
        xaxis=dict(gridcolor=GRID_COL, showgrid=True),
        yaxis=dict(gridcolor=GRID_COL, showgrid=True),
        hovermode="x unified",
        margin=dict(l=60, r=20, t=50, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font_size=10),
    )

# ── APIs ERCOT en vivo ────────────────────────────────────────────────────────
ERCOT_USERNAME  = os.environ.get("ERCOT_USERNAME", "mvidals@xiix.mx")
ERCOT_PASSWORD  = os.environ.get("ERCOT_PASSWORD", "")
ERCOT_KEY       = os.environ.get("ERCOT_KEY", "8908c0fc88284dfdbaed3d01955dc934")
ERCOT_CLIENT_ID = "fec253ea-0d06-4272-a5e6-b478baeecd70"
ERCOT_TOKEN_URL = (
    "https://ercotb2c.b2clogin.com/ercotb2c.onmicrosoft.com"
    "/B2C_1_PUBAPI-ROPC-FLOW/oauth2/v2.0/token"
)
MU_ROOT = "https://api1.marginalunit.com/pr-forecast"

_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


@st.cache_data(ttl=3300, show_spinner=False)
def _ercot_token() -> str | None:
    try:
        resp = requests.post(
            ERCOT_TOKEN_URL,
            data={
                "username": ERCOT_USERNAME, "password": ERCOT_PASSWORD,
                "grant_type": "password",
                "scope": f"openid {ERCOT_CLIENT_ID} offline_access",
                "client_id": ERCOT_CLIENT_ID, "response_type": "id_token",
            },
            headers={"User-Agent": _BROWSER_UA},
            timeout=20,
        )
        if not resp.ok:
            return None
        js = resp.json()
        return js.get("id_token") or js.get("access_token")
    except Exception:
        return None


def _ercot_get(url, date_from, date_to, gen_col=None, size=1000):
    try:
        import cloudscraper
        token = _ercot_token()
        if not token:
            return None
        scraper = cloudscraper.create_scraper(browser={"browser": "chrome", "platform": "windows"})
        headers = {
            "Authorization": f"Bearer {token}",
            "Ocp-Apim-Subscription-Key": ERCOT_KEY,
            "Accept": "application/json",
        }
        r = scraper.get(url, headers=headers,
                        params={"deliveryDateFrom": date_from, "deliveryDateTo": date_to, "size": size},
                        timeout=30)
        if r.status_code != 200:
            return None
        rows = r.json().get("data", [])
        if not rows:
            return None
        df = pd.DataFrame(rows)
        df = df.sort_values(["deliveryDate", "hourEnding"]).reset_index(drop=True)
        if gen_col:
            col_map = {c.lower(): c for c in df.columns}
            actual  = col_map.get(gen_col.lower())
            if actual:
                df = df.rename(columns={actual: "value"})
                df["value"] = pd.to_numeric(df["value"], errors="coerce")
        return df
    except Exception:
        return None


@st.cache_data(ttl=300, show_spinner=False)
def live_load(d0, d1):
    df = _ercot_get("https://api.ercot.com/api/public-reports/np3-565-cd/lf_by_model_weather_zone", d0, d1)
    if df is None:
        return None
    if "model" in df.columns:
        for m in ["STLF", "MTLF"]:
            if m in df["model"].values:
                df = df[df["model"] == m]; break
    for c in ["systemTotal", "total", "systemtotal"]:
        if c in df.columns:
            df["value"] = pd.to_numeric(df[c], errors="coerce"); break
    return df


@st.cache_data(ttl=300, show_spinner=False)
def live_wind_south(d0, d1):
    return _ercot_get("https://api.ercot.com/api/public-reports/np4-732-cd/wpp_hrly_avrg_actl_fcast",
                      d0, d1, "STWPFLoadZoneSouthHouston")


@st.cache_data(ttl=300, show_spinner=False)
def live_wind_west(d0, d1):
    return _ercot_get("https://api.ercot.com/api/public-reports/np4-732-cd/wpp_hrly_avrg_actl_fcast",
                      d0, d1, "STWPFLoadZoneWest")


@st.cache_data(ttl=300, show_spinner=False)
def live_solar(d0, d1):
    return _ercot_get("https://api.ercot.com/api/public-reports/np4-737-cd/spp_hrly_avrg_actl_fcast",
                      d0, d1, "STPPFSystemWide")


@st.cache_data(ttl=300, show_spinner=False)
def mu_synthetic(dataset, entity, version="latest"):
    try:
        df_meta = pd.read_csv(
            io.StringIO(requests.get(MU_ROOT + "/synthetic/forecasts", auth=AUTH, timeout=30).text)
        )
        mask = (df_meta["org"] == "ercot") & (df_meta["dataset"] == dataset)
        if version == "latest":
            mask &= df_meta["is_latest"] == 1
        ver = df_meta.loc[mask, "version"].tolist()
        if not ver:
            return None
        v = ver[-1]
        df_ao = pd.read_csv(io.StringIO(
            requests.get(f"{MU_ROOT}/synthetic/ercot/{dataset}/{v}/as_ofs",
                         auth=AUTH, params={"entities": entity}, timeout=30).text
        ))
        df_ao["dt"] = pd.to_datetime(df_ao["as_of"], utc=True)
        latest_ao = df_ao.sort_values("dt").iloc[-1]["as_of"]
        df = pd.read_csv(io.StringIO(
            requests.get(f"{MU_ROOT}/synthetic/ercot/{dataset}/{v}/report",
                         auth=AUTH, params={"entities": entity, "as_of": latest_ao}, timeout=30).text
        ))
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        return df
    except Exception:
        return None


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="text-align:center; padding:18px 0 4px 0;">
        <svg width="150" height="56" viewBox="0 0 150 56" xmlns="http://www.w3.org/2000/svg" style="display:block; margin:0 auto;">
            <defs>
                <linearGradient id="lg-sb" x1="0%" y1="0%" x2="100%" y2="0%">
                    <stop offset="0%"   stop-color="#00e5c0"/>
                    <stop offset="50%"  stop-color="#0094cc"/>
                    <stop offset="100%" stop-color="#1a2e70"/>
                </linearGradient>
            </defs>
            <text x="4" y="50" font-family="'Segoe UI Black','Arial Black','Impact',sans-serif"
                  font-weight="900" font-size="54" letter-spacing="6" fill="url(#lg-sb)">XTS</text>
        </svg>
        <div style="color:#4a5478; font-size:0.6rem; letter-spacing:2.5px; text-transform:uppercase;
                    font-family:'Segoe UI',sans-serif; margin-top:4px;">MORNING ERCOT</div>
    </div>
    """, unsafe_allow_html=True)
    st.divider()

    page = st.radio(
        "nav",
        ["⚡ Load & Renewables", "📈 DA / RT Precios", "📊 DART Spread",
         "🔮 Synthetic Forecast", "🌡️ Temperaturas", "🎲 Monte Carlo"],
        label_visibility="collapsed",
    )

    st.divider()
    dias_hist = st.slider("Días histórico (BD)", 3, 30, 7)
    st.divider()

    if st.button("Cerrar Sesión", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.auth      = None
        st.rerun()

    st.markdown(f"<div style='color:#2d3350; font-size:0.65rem; margin-top:8px; text-align:center;'>{datetime.now().strftime('%d/%m/%Y %H:%M')}</div>", unsafe_allow_html=True)


# ── Datos BD (histórico) ──────────────────────────────────────────────────────
df_hist, live_db   = load_ercot(dias_hist)
df_temps, _        = load_temperaturas(3)
tc, live_tc        = load_tipo_cambio()

if not live_db:
    st.markdown('<div class="demo-banner">⚠️ <b>Modo demo</b> — Sin conexión a BD. Datos históricos son sintéticos.</div>', unsafe_allow_html=True)

# Rango para APIs en vivo
today_dt  = date.today()
d0 = (today_dt - timedelta(days=1)).strftime("%Y-%m-%d")
d1 = (today_dt + timedelta(days=1)).strftime("%Y-%m-%d")

hours = list(range(1, 25))

def day_vals(df, col, day_idx):
    if df is None or col not in df.columns:
        return [0] * 24
    vals = df[col].iloc[day_idx * 24: day_idx * 24 + 24].tolist()
    return vals if len(vals) == 24 else vals + [0] * (24 - len(vals))

def three_day_chart(title, y_label, y0, y1, y2):
    yday = (today_dt - timedelta(days=1)).strftime("%b %d")
    tday = today_dt.strftime("%b %d")
    tmrw = (today_dt + timedelta(days=1)).strftime("%b %d")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=hours, y=y0, mode="lines", name=f"Ayer {yday}",   line=dict(color=C_AYER, width=2.5)))
    fig.add_trace(go.Scatter(x=hours, y=y1, mode="lines", name=f"Hoy {tday}",    line=dict(color=C_HOY,  width=3)))
    fig.add_trace(go.Scatter(x=hours, y=y2, mode="lines", name=f"Mañana {tmrw}", line=dict(color=C_MANANA, width=2.5, dash="dash")))
    fig.update_layout(**_plotly_base(380, title), xaxis_title="Hora", yaxis_title=y_label,
                      xaxis=dict(gridcolor=GRID_COL, tickvals=list(range(1, 25, 2))))
    return fig


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 1: Load & Renewables  (datos en vivo de ERCOT API)
# ══════════════════════════════════════════════════════════════════════════════
if page == "⚡ Load & Renewables":
    st.title("⚡ Load & Renewables")

    with st.spinner("Cargando datos ERCOT…"):
        df_load = live_load(d0, d1)
        df_ws   = live_wind_south(d0, d1)
        df_ww   = live_wind_west(d0, d1)
        df_sol  = live_solar(d0, d1)

    has_load  = df_load is not None and "value" in df_load.columns
    has_wind  = df_ws is not None and df_ww is not None
    has_solar = df_sol is not None

    # Net load
    if has_load and has_wind and has_solar:
        ld_y, ld_d, ld_t   = (day_vals(df_load, "value", i) for i in range(3))
        ws_y, ws_d, ws_t   = (day_vals(df_ws,   "value", i) for i in range(3))
        ww_y, ww_d, ww_t   = (day_vals(df_ww,   "value", i) for i in range(3))
        sol_y, sol_d, sol_t = (day_vals(df_sol,  "value", i) for i in range(3))

        nl_y = [l - a - b - s for l, a, b, s in zip(ld_y, ws_y, ww_y, sol_y)]
        nl_d = [l - a - b - s for l, a, b, s in zip(ld_d, ws_d, ww_d, sol_d)]
        nl_t = [l - a - b - s for l, a, b, s in zip(ld_t, ws_t, ww_t, sol_t)]
        st.plotly_chart(three_day_chart("Net Load Forecast", "Net Load (MW)", nl_y, nl_d, nl_t),
                        use_container_width=True)

    c1, c2 = st.columns(2)
    with c1:
        if has_load:
            ld_y, ld_d, ld_t = (day_vals(df_load, "value", i) for i in range(3))
            st.plotly_chart(three_day_chart("Load Forecast", "Load (MW)", ld_y, ld_d, ld_t),
                            use_container_width=True)
        else:
            st.warning("Load no disponible")
    with c2:
        if has_wind:
            ws_y, ws_d, ws_t = (day_vals(df_ws, "value", i) for i in range(3))
            st.plotly_chart(three_day_chart("Wind South Forecast", "Generation (MW)", ws_y, ws_d, ws_t),
                            use_container_width=True)

    if has_wind:
        c3, c4 = st.columns(2)
        ww_y, ww_d, ww_t = (day_vals(df_ww, "value", i) for i in range(3))
        with c3:
            st.plotly_chart(three_day_chart("Wind West Forecast", "Generation (MW)", ww_y, ww_d, ww_t),
                            use_container_width=True)
        with c4:
            if has_solar:
                sol_y, sol_d, sol_t = (day_vals(df_sol, "value", i) for i in range(3))
                st.plotly_chart(three_day_chart("Solar Forecast", "Generation (MW)", sol_y, sol_d, sol_t),
                                use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 2: Precios DA / RT (desde BD)
# ══════════════════════════════════════════════════════════════════════════════
elif page == "📈 DA / RT Precios":
    st.title("📈 DA / RT Precios")

    # KPIs
    ultima  = df_hist.iloc[-1]
    ante    = df_hist.iloc[-2] if len(df_hist) > 1 else ultima

    def kpi(label, val, ref, color="#00d4e8"):
        d = val - ref
        arrow = "▲" if d > 0 else "▼"
        dcls  = "kpi-delta-up" if d > 0 else "kpi-delta-down"
        return f"""<div class="kpi-card" style="border-left-color:{color}">
            <div class="kpi-label">{label}</div>
            <div class="kpi-value" style="color:{color}">${val:.2f}</div>
            <span class="{dcls}">{arrow} {abs(d):.2f}</span>
        </div>"""

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.markdown(kpi("DA DCL", ultima.get("DA_DCL", 0), ante.get("DA_DCL", 0), "#B7D433"), unsafe_allow_html=True)
    c2.markdown(kpi("RT DCL", ultima.get("RT_DCL", 0), ante.get("RT_DCL", 0), "#FF6B35"), unsafe_allow_html=True)
    dart = ultima.get("DA_DCL", 0) - ultima.get("RT_DCL", 0)
    dart_ref = ante.get("DA_DCL", 0) - ante.get("RT_DCL", 0)
    c3.markdown(kpi("DART DCL", dart, dart_ref, "#a78bfa"), unsafe_allow_html=True)
    c4.markdown(kpi("DA DCR", ultima.get("DA_DCR", 0), ante.get("DA_DCR", 0), "#00d4e8"), unsafe_allow_html=True)
    c5.markdown(f"""<div class="kpi-card" style="border-left-color:#34d399">
        <div class="kpi-label">USD/MXN</div>
        <div class="kpi-value" style="color:#34d399">{tc:.4f}</div>
        <span class="kpi-sub">{'live' if live_tc else 'demo'}</span>
    </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    for nodo in ["DC_L", "DC_R"]:
        da_c  = f"DA_{nodo.replace('-','_')}"
        rt_c  = f"RT_{nodo.replace('-','_')}"
        da_fc = da_c + "_FCST"
        rt_fc = rt_c + "_FCST"

        fig = go.Figure()
        if da_c in df_hist.columns:
            fig.add_trace(go.Scatter(x=df_hist["fecha"], y=df_hist[da_c], name=f"DA {nodo}",
                                     line=dict(color=C_DA, width=2)))
        if rt_c in df_hist.columns:
            fig.add_trace(go.Scatter(x=df_hist["fecha"], y=df_hist[rt_c], name=f"RT {nodo}",
                                     line=dict(color=C_RT, width=2)))
        if da_fc in df_hist.columns:
            fig.add_trace(go.Scatter(x=df_hist["fecha"], y=df_hist[da_fc], name=f"DA Fcst {nodo}",
                                     line=dict(color=C_DA, width=1, dash="dot"), opacity=0.6))
        if rt_fc in df_hist.columns:
            fig.add_trace(go.Scatter(x=df_hist["fecha"], y=df_hist[rt_fc], name=f"RT Fcst {nodo}",
                                     line=dict(color=C_RT, width=1, dash="dot"), opacity=0.6))

        fig.update_layout(**_plotly_base(360, f"Nodo {nodo}  —  $/MWh"),
                          yaxis_title="$/MWh")
        st.plotly_chart(fig, use_container_width=True)

    # Tabla diaria
    df_d = df_hist.copy()
    df_d["dia"] = df_d["fecha"].dt.date
    agg_cols = {c: "mean" for c in ["DA_DCL", "DA_DCR", "RT_DCL", "RT_DCR", "LOAD_ERCOT", "WIND_ERCOT"]
                if c in df_d.columns}
    df_agg = df_d.groupby("dia").agg(agg_cols).reset_index()
    if "DA_DCL" in df_agg and "RT_DCL" in df_agg:
        df_agg["DART_DCL"] = df_agg["DA_DCL"] - df_agg["RT_DCL"]
    if "DA_DCR" in df_agg and "RT_DCR" in df_agg:
        df_agg["DART_DCR"] = df_agg["DA_DCR"] - df_agg["RT_DCR"]

    float_cols = [c for c in df_agg.columns if c != "dia"]
    st.dataframe(df_agg.sort_values("dia", ascending=False)
                       .style.format({c: "{:.2f}" for c in float_cols}),
                 use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 3: DART Spread
# ══════════════════════════════════════════════════════════════════════════════
elif page == "📊 DART Spread":
    st.title("📊 DART Spread  (DA − RT)")

    df_d = df_hist.copy()
    df_d["hora"] = df_d["fecha"].dt.hour + 1
    df_d["dia"]  = df_d["fecha"].dt.date

    if "DA_DCL" in df_d.columns and "RT_DCL" in df_d.columns:
        df_d["DART_DCL"] = df_d["DA_DCL"] - df_d["RT_DCL"]
        pivot = df_d.pivot_table(index="hora", columns="dia", values="DART_DCL", aggfunc="mean")
        pivot.columns = [str(c) for c in pivot.columns]

        fig_hm = px.imshow(pivot, color_continuous_scale="RdYlGn",
                           color_continuous_midpoint=0, aspect="auto",
                           labels=dict(x="Día", y="Hora (HE)", color="DART $/MWh"),
                           title="DART DCL — Heatmap (Hora × Día)")
        fig_hm.update_layout(**_plotly_base(450))
        st.plotly_chart(fig_hm, use_container_width=True)

    c1, c2 = st.columns(2)
    for nodo, col in zip(["DCL", "DCR"], [c1, c2]):
        if f"DART_{nodo}" in df_d.columns or (f"DA_{nodo}" in df_d.columns and f"RT_{nodo}" in df_d.columns):
            if f"DART_{nodo}" not in df_d.columns:
                df_d[f"DART_{nodo}"] = df_d[f"DA_{nodo}"] - df_d[f"RT_{nodo}"]
            perfil = df_d.groupby("hora")[f"DART_{nodo}"].mean().reset_index()
            fig_p = go.Figure(go.Bar(
                x=perfil["hora"], y=perfil[f"DART_{nodo}"],
                marker_color=["#ff6b6b" if v > 0 else "#00d4e8" for v in perfil[f"DART_{nodo}"]],
            ))
            fig_p.add_hline(y=0, line_dash="dash", line_color="white", opacity=0.4)
            fig_p.update_layout(**_plotly_base(320, f"Perfil DART {nodo}"),
                                xaxis_title="Hora (HE)", yaxis_title="$/MWh")
            col.plotly_chart(fig_p, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 4: Synthetic Forecast (MarginalUnit)
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🔮 Synthetic Forecast":
    st.title("🔮 Synthetic Forecast")

    c1, c2, c3 = st.columns(3)
    with c1:
        sel_ds  = st.selectbox("Dataset", ["lmp_da", "lmp_rt"], index=1)
    with c2:
        sel_ent = st.text_input("PNode", value="DC_L")
    with c3:
        show_days = st.number_input("Días", 1, 7, 2)

    if st.button("Obtener Forecast", type="primary", use_container_width=True):
        with st.spinner("Descargando…"):
            df_fc = mu_synthetic(sel_ds, sel_ent)

        if df_fc is None:
            st.error("No se pudo obtener el forecast. Verifica el PNode o el dataset.")
        else:
            tomorrow = date.today() + timedelta(days=1)
            df_fc = df_fc[df_fc["timestamp"].dt.date >= tomorrow].iloc[: show_days * 24]

            pfx = "synthetic"
            cols_need = [f"{pfx}_0_05", f"{pfx}_0_33", f"{pfx}_0_5", f"{pfx}_0_66", f"{pfx}_0_95"]

            if not all(c in df_fc.columns for c in cols_need):
                st.warning("Columnas de percentiles no encontradas.")
                st.dataframe(df_fc.head(24))
            else:
                xs = df_fc["timestamp"].tolist()
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=xs + xs[::-1],
                    y=df_fc[f"{pfx}_0_95"].tolist() + df_fc[f"{pfx}_0_05"].tolist()[::-1],
                    fill="toself", fillcolor="rgba(0,212,232,0.12)",
                    line=dict(color="rgba(0,0,0,0)"), name="5th–95th",
                ))
                fig.add_trace(go.Scatter(
                    x=xs + xs[::-1],
                    y=df_fc[f"{pfx}_0_66"].tolist() + df_fc[f"{pfx}_0_33"].tolist()[::-1],
                    fill="toself", fillcolor="rgba(0,212,232,0.30)",
                    line=dict(color="rgba(0,0,0,0)"), name="33rd–66th",
                ))
                fig.add_trace(go.Scatter(
                    x=xs, y=df_fc[f"{pfx}_0_5"], mode="lines",
                    name="Mediana", line=dict(color=C_HOY, width=2),
                ))
                fig.update_layout(**_plotly_base(500, f"{sel_ent}  ·  {sel_ds.upper()}"),
                                  xaxis_title="Fecha / Hora", yaxis_title="$/MWh")
                st.plotly_chart(fig, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 5: Temperaturas
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🌡️ Temperaturas":
    st.title("🌡️ Temperaturas")

    ciudades = {"LRD": "Laredo TX", "RYN": "Reynosa", "MCA": "McAllen",
                "NLR": "Nuevo Laredo", "TIJ": "Tijuana", "SND": "San Diego"}
    colores  = [C_RT, "#fbbf24", C_HOY, "#a78bfa", C_AYER, "#34d399"]

    fig_t = go.Figure()
    for i, (col, label) in enumerate(ciudades.items()):
        if col in df_temps.columns:
            fig_t.add_trace(go.Scatter(x=df_temps["fecha"], y=df_temps[col],
                                       name=label, line=dict(color=colores[i], width=1.5)))
    fig_t.update_layout(**_plotly_base(400, "Temperaturas últimas 72h"),
                        yaxis_title="°C")
    st.plotly_chart(fig_t, use_container_width=True)

    # Actuales
    ultima_t = df_temps.iloc[-1]
    cols_t = st.columns(len(ciudades))
    for idx, (col, label) in enumerate(ciudades.items()):
        if col in df_temps.columns:
            cols_t[idx].metric(label, f"{ultima_t[col]:.1f}°C")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 6: Monte Carlo
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🎲 Monte Carlo":
    st.title("🎲 Monte Carlo  —  RT DCL")

    # Tipo de cambio (live)
    @st.cache_data(ttl=3600, show_spinner=False)
    def get_live_tc():
        try:
            r = requests.get(
                "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/usd.json",
                timeout=10, verify=False,
            )
            r.raise_for_status()
            return float(r.json()["usd"]["mxn"])
        except Exception:
            return None

    with st.spinner("Obteniendo TC…"):
        auto_tc = get_live_tc()

    col_tc, _ = st.columns([1, 3])
    with col_tc:
        tc_mc = st.number_input(
            "Tipo de cambio MXN/USD" + ("  ✓ auto" if auto_tc else "  ⚠ manual"),
            value=auto_tc or tc, step=0.01, format="%.4f",
        )

    c1, c2, c3 = st.columns(3)
    costo_mw   = c1.number_input("Costo por MW (USD)", value=5.0, format="%.2f")
    hora_sel   = c2.selectbox("Hora a analizar (HE)", list(range(1, 25)), index=15)
    precio_asig = c3.number_input("Precio asignado (MXN/MWh)", value=700.0, format="%.2f")

    df_mc = df_hist.dropna(subset=["RT_DCL"]).copy()
    df_mc["hora"] = df_mc["fecha"].dt.hour + 1
    precios_hist = df_mc[df_mc["hora"] == hora_sel]["RT_DCL"].dropna().tolist()

    if len(precios_hist) < 10:
        st.warning("Pocos datos. Aumenta el período histórico en el sidebar.")
    else:
        n_sim = 10_000
        sim   = np.random.choice(precios_hist, size=n_sim, replace=True)
        sim  += np.random.normal(0, np.std(precios_hist) * 0.1, n_sim)

        precio_be  = precio_asig / tc_mc - costo_mw
        profits    = precio_be - sim
        prob_p     = (profits > 0).mean() * 100
        exp_p      = np.mean(profits)
        var_5      = np.percentile(profits, 5)

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Prob. de profit",       f"{prob_p:.1f}%")
        m2.metric("P&L esperado (USD/MW)", f"${exp_p:.2f}")
        m3.metric("VaR 5% (USD/MW)",       f"${var_5:.2f}")
        m4.metric("Break-even (USD/MWh)",  f"${precio_be:.2f}")

        fig_mc = go.Figure()
        fig_mc.add_trace(go.Histogram(x=sim, nbinsx=50, name="Simulado",
                                      marker_color=C_HOY, opacity=0.7))
        fig_mc.add_trace(go.Histogram(x=precios_hist, nbinsx=50, name="Histórico",
                                      marker_color="#fbbf24", opacity=0.5))
        fig_mc.add_vline(x=precio_be, line_dash="dash", line_color="#ff6b6b",
                         annotation_text=f"Break-even ${precio_be:.2f}",
                         annotation_position="top right")
        fig_mc.update_layout(**_plotly_base(400, f"RT DCL — Hora {hora_sel} HE"),
                             barmode="overlay",
                             xaxis_title="$/MWh", yaxis_title="Frecuencia")
        st.plotly_chart(fig_mc, use_container_width=True)

        # Perfil de probabilidad por hora
        st.subheader("Probabilidad de profit por hora")
        prob_por_hora = []
        for h in range(1, 25):
            ph = df_mc[df_mc["hora"] == h]["RT_DCL"].dropna()
            if len(ph) < 5:
                prob_por_hora.append({"Hora": h, "Prob (%)": 0})
                continue
            sh = np.random.choice(ph.tolist(), size=2000, replace=True)
            sh += np.random.normal(0, ph.std() * 0.1, 2000)
            prob_por_hora.append({"Hora": h, "Prob (%)": ((precio_be - sh) > 0).mean() * 100})

        df_prob = pd.DataFrame(prob_por_hora)
        fig_p = go.Figure(go.Bar(
            x=df_prob["Hora"], y=df_prob["Prob (%)"],
            marker_color=["#00d4e8" if v >= 50 else "#ff6b6b" for v in df_prob["Prob (%)"]],
        ))
        fig_p.add_hline(y=50, line_dash="dash", line_color="white", opacity=0.4)
        fig_p.update_layout(**_plotly_base(320, f"Prob. profit — Precio asig {precio_asig:.0f} MXN"),
                            xaxis_title="Hora (HE)", yaxis_title="%")
        st.plotly_chart(fig_p, use_container_width=True)

# ── Footer ─────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    f"<div style='color:#2d3350; font-size:0.68rem; text-align:center;'>"
    f"XTS Energy Portal · Morning ERCOT · "
    f"{'🔴 Demo' if not live_db else '🟢 Live'} · "
    f"{datetime.now().strftime('%d/%m/%Y %H:%M:%S')}</div>",
    unsafe_allow_html=True,
)
