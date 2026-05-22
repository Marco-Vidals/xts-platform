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
import re
import requests
import time
import io
import urllib3
import base64

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ── XTS logo base64 ────────────────────────────────────────────────────────────
def _b64_img(path: str) -> str:
    try:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except Exception:
        return ""

_XTS_LOGO_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "static", "logoxts_transparent.png")
_XTS_B64 = _b64_img(_XTS_LOGO_PATH)

def _xts_logo_uri(height_px: int = 44) -> str:
    """SVG XTS logo como data URI base64 — el parser markdown nunca ve el '>'."""
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
    enc = base64.b64encode(svg.encode('utf-8')).decode('ascii')
    return f"data:image/svg+xml;base64,{enc}"

_XTS_IMG = f'<img src="{_xts_logo_uri(44)}" alt="XTS" style="height:44px;display:block;"/>'

from app.morning.data_loader import load_ercot, load_temperaturas, load_tipo_cambio, load_spread_data

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
    st.markdown(
        "<div style='position:fixed;top:16px;left:28px;z-index:999;display:flex;align-items:center;gap:10px;'>"
        + _XTS_IMG
        + "<div style='color:#4a5478;font-size:0.58rem;letter-spacing:2.5px;text-transform:uppercase;"
        "font-family:Segoe UI,sans-serif;align-self:flex-end;padding-bottom:5px;'>Energy Portal</div></div>",
        unsafe_allow_html=True,
    )

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

    /* Todos los selectboxes — caja cerrada */
    [data-testid="stSelectbox"] > div > div {
        background-color: #2d3350 !important;
        border: 1px solid #3d4468 !important;
        border-radius: 4px !important;
    }
    [data-testid="stSelectbox"] > div > div > div,
    [data-testid="stSelectbox"] span {
        color: #00d4e8 !important;
        font-weight: 600 !important;
        font-size: 0.85rem !important;
        letter-spacing: 0.5px !important;
    }
    [data-testid="stSelectbox"] svg {
        fill: #00d4e8 !important;
    }
    /* Label de selectbox */
    [data-testid="stSelectbox"] label {
        color: #5a6280 !important;
        font-size: 0.72rem !important;
        text-transform: uppercase !important;
        letter-spacing: 1px !important;
        font-weight: 600 !important;
    }

    /* Dropdown desplegado (popover global) */
    [data-testid="stSelectboxVirtualDropdown"],
    div[data-baseweb="popover"] ul,
    div[data-baseweb="menu"] {
        background-color: #1e2130 !important;
        border: 1px solid #2d3350 !important;
        border-radius: 6px !important;
    }
    div[data-baseweb="menu"] li,
    [data-testid="stSelectboxVirtualDropdown"] li {
        background-color: #1e2130 !important;
        color: #00d4e8 !important;
        font-size: 0.85rem !important;
        font-weight: 500 !important;
    }
    div[data-baseweb="menu"] li:hover,
    [data-testid="stSelectboxVirtualDropdown"] li:hover {
        background-color: #2d3350 !important;
        color: #00d4e8 !important;
    }
    div[data-baseweb="menu"] li[aria-selected="true"],
    [data-testid="stSelectboxVirtualDropdown"] li[aria-selected="true"] {
        background-color: #0d1a2e !important;
        color: #00d4e8 !important;
        font-weight: 700 !important;
    }

    /* ── Inputs globales (text, number, date) ── */
    [data-testid="stTextInput"] input,
    [data-testid="stNumberInput"] input,
    [data-testid="stDateInput"] input {
        background-color: #2d3350 !important;
        color: #00d4e8 !important;
        border: 1px solid #3d4468 !important;
        border-radius: 4px !important;
        font-family: 'Segoe UI', sans-serif !important;
        font-size: 0.88rem !important;
        font-weight: 600 !important;
    }
    [data-testid="stTextInput"] input:focus,
    [data-testid="stNumberInput"] input:focus,
    [data-testid="stDateInput"] input:focus {
        border-color: #00d4e8 !important;
        box-shadow: 0 0 0 1px #00d4e8 !important;
        outline: none !important;
    }
    [data-testid="stTextInput"] input::placeholder,
    [data-testid="stNumberInput"] input::placeholder {
        color: #4a5478 !important;
    }
    /* Labels de inputs */
    [data-testid="stTextInput"] label,
    [data-testid="stNumberInput"] label,
    [data-testid="stDateInput"] label {
        color: #5a6280 !important;
        font-size: 0.72rem !important;
        text-transform: uppercase !important;
        letter-spacing: 1px !important;
        font-weight: 600 !important;
    }
    /* Botones +/- del number input */
    [data-testid="stNumberInput"] button {
        background-color: #2d3350 !important;
        border-color: #3d4468 !important;
        color: #00d4e8 !important;
    }
    [data-testid="stNumberInput"] button:hover {
        background-color: #3d4468 !important;
        border-color: #00d4e8 !important;
    }
    /* Date input */
    [data-testid="stDateInput"] > div > div {
        background-color: #2d3350 !important;
        border: 1px solid #3d4468 !important;
        border-radius: 4px !important;
    }
    [data-testid="stDateInput"] span {
        color: #00d4e8 !important;
        font-weight: 600 !important;
    }
    /* Radio buttons */
    [data-testid="stRadio"] label {
        color: #c0c4cc !important;
        font-size: 0.85rem !important;
    }
    [data-testid="stRadio"] [data-testid="stMarkdownContainer"] p {
        color: #c0c4cc !important;
    }
    /* Slider */
    [data-testid="stSlider"] label {
        color: #5a6280 !important;
        font-size: 0.72rem !important;
        text-transform: uppercase !important;
        letter-spacing: 1px !important;
        font-weight: 600 !important;
    }
    /* File uploader */
    [data-testid="stFileUploader"] {
        background-color: #1e2130 !important;
        border: 1px dashed #3d4468 !important;
        border-radius: 6px !important;
    }
    [data-testid="stFileUploader"] label {
        color: #5a6280 !important;
        font-size: 0.72rem !important;
        text-transform: uppercase !important;
        letter-spacing: 1px !important;
        font-weight: 600 !important;
    }
    [data-testid="stFileUploaderDropzone"] {
        background-color: #1e2130 !important;
        border: 1px dashed #3d4468 !important;
        border-radius: 6px !important;
    }
    [data-testid="stFileUploaderDropzone"] p,
    [data-testid="stFileUploaderDropzone"] span {
        color: #5a6280 !important;
    }
    [data-testid="stFileUploaderDropzoneInstructions"] button,
    [data-testid="stFileUploader"] button {
        background-color: #2d3350 !important;
        color: #00d4e8 !important;
        border: 1px solid #00d4e8 !important;
        border-radius: 4px !important;
        font-weight: 700 !important;
        letter-spacing: 1px !important;
    }
    [data-testid="stFileUploaderDropzoneInstructions"] button:hover,
    [data-testid="stFileUploader"] button:hover {
        background-color: #00d4e8 !important;
        color: #1e2130 !important;
    }

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
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=10, color="#ffffff")),
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


def _db_conn():
    try:
        from etl.common.db_connection import get_connection
        return get_connection("XTS")
    except Exception:
        return None


def _db_to_dayvals(df_db, fecha_col, value_col):
    """Convierte filas (fecha datetime, valor) al formato que espera day_vals."""
    df = df_db[[fecha_col, value_col]].copy()
    df[fecha_col] = pd.to_datetime(df[fecha_col])
    df["deliveryDate"] = df[fecha_col].dt.strftime("%Y-%m-%d")
    df["hourEnding"]   = df[fecha_col].dt.hour + 1    # hourEnding es 1-based
    df["value"]        = pd.to_numeric(df[value_col], errors="coerce")
    return df[["deliveryDate", "hourEnding", "value"]]


def _ercot_get(url, date_from, date_to, gen_col=None, size=1000, extra_params=None,
               date_params=("deliveryDateFrom", "deliveryDateTo"), req_timeout=25):
    """
    Descarga datos de un endpoint ERCOT (maneja formato lista-de-listas + fields).
    date_params: tuple con nombres de parametros de fecha (default: deliveryDateFrom/To).
    extra_params: dict de parametros adicionales.
    """
    try:
        token = _ercot_token()
        if not token:
            return None
        headers = {
            "Authorization": f"Bearer {token}",
            "Ocp-Apim-Subscription-Key": ERCOT_KEY,
            "Accept": "application/json",
        }
        params = {date_params[0]: date_from, date_params[1]: date_to,
                  "size": size, "page": 1}
        if extra_params:
            params.update(extra_params)

        all_rows, col_names = [], None
        while True:
            for attempt in range(3):
                r = requests.get(url, headers=headers, params=params, timeout=req_timeout)
                if r.status_code == 429:
                    time.sleep(10 * (attempt + 1))
                    continue
                break
            if r.status_code != 200:
                return None
            js = r.json()

            if col_names is None:
                fields = js.get("fields", [])
                if fields and isinstance(fields[0], dict):
                    col_names = [f["name"] for f in fields]

            data = js.get("data", [])
            all_rows.extend(data)
            meta = js.get("_meta", {})
            if params["page"] >= meta.get("totalPages", 1):
                break
            params["page"] += 1

        if not all_rows:
            return None

        if col_names and isinstance(all_rows[0], list):
            df = pd.DataFrame(all_rows, columns=col_names)
        else:
            df = pd.DataFrame(all_rows)

        # Ordenar por fecha/hora si existen las columnas
        sort_cols = [c for c in ["deliveryDate", "hourEnding"] if c in df.columns]
        if sort_cols:
            df = df.sort_values(sort_cols).reset_index(drop=True)

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
    """Load forecast — igual que original, una sola llamada al API."""
    df = _ercot_get(
        "https://api.ercot.com/api/public-reports/np3-565-cd/lf_by_model_weather_zone",
        d0, d1,
    )
    if df is None:
        return None
    if "model" in df.columns:
        for m in ["STLF", "MTLF"]:
            if m in df["model"].values:
                df = df[df["model"] == m]; break
    cm = {c.lower(): c for c in df.columns}
    for cn in ["systemtotal", "total"]:
        if cn in cm:
            df["value"] = pd.to_numeric(df[cm[cn]], errors="coerce"); break
    return df


@st.cache_data(ttl=300, show_spinner=False)
def live_load_actual(d0, d1):
    """Carga real por hora (np6-345-cd) — solo días completos publicados."""
    df = _ercot_get(
        "https://api.ercot.com/api/public-reports/np6-345-cd/act_sys_load_by_wzn",
        d0, d1,
        date_params=("operatingDayFrom", "operatingDayTo"),
    )
    if df is None:
        return None
    if "total" in df.columns:
        df["value"] = pd.to_numeric(df["total"], errors="coerce")
    return df


@st.cache_data(ttl=300, show_spinner=False)
def live_wind_all(d0, d1):
    """Viento: una sola llamada al API, extrae zonas y sistema total."""
    df_api = _ercot_get(
        "https://api.ercot.com/api/public-reports/np4-732-cd/wpp_hrly_avrg_actl_fcast",
        d0, d1, gen_col=None,
    )

    def _extract(col_name):
        if df_api is None:
            return None
        cm = {c.lower(): c for c in df_api.columns}
        col = cm.get(col_name.lower())
        if not col:
            return None
        d = df_api.copy()
        d["value"] = pd.to_numeric(d[col], errors="coerce")
        return d

    df_south = _extract("STWPFLoadZoneSouthHouston")
    df_west  = _extract("STWPFLoadZoneWest")
    _dn = _extract("STWPFLoadZoneNoarth")
    df_north = _dn if _dn is not None else _extract("STWPFLoadZoneNorth")

    # Sistema total: columna dedicada primero, después suma zonas (sin duplicar North)
    _ds = _extract("STWPFSystemWide")
    df_system = _ds if _ds is not None else _extract("STWPFSystem")
    if df_system is None and df_api is not None:
        cm = {c.lower(): c for c in df_api.columns}
        south_c = cm.get("stwpfloadzonesouthhouston")
        west_c  = cm.get("stwpfloadzonewest")
        north_c = cm.get("stwpfloadzonenoarth") or cm.get("stwpfloadzonenorth")
        zone_cols = [c for c in [south_c, west_c, north_c] if c]
        if zone_cols:
            d = df_api.copy()
            d["value"] = d[zone_cols].apply(pd.to_numeric, errors="coerce").sum(axis=1)
            df_system = d

    return df_south, df_west, df_north, df_system


def live_wind_south(d0, d1): return live_wind_all(d0, d1)[0]
def live_wind_west(d0, d1):  return live_wind_all(d0, d1)[1]
def live_wind_north(d0, d1): return live_wind_all(d0, d1)[2]


@st.cache_data(ttl=300, show_spinner=False)
def live_solar(d0, d1):
    """Solar: una sola llamada al API, extrae actual y pronóstico."""
    df = _ercot_get(
        "https://api.ercot.com/api/public-reports/np4-737-cd/spp_hrly_avrg_actl_fcast",
        d0, d1, gen_col=None,
    )
    if df is None:
        return None
    cm = {c.lower(): c for c in df.columns}
    # Generación real (actual disponible para horas pasadas)
    actual_col = cm.get("gensystemwide")
    if actual_col:
        df["value"] = pd.to_numeric(df[actual_col], errors="coerce")
    # Pronóstico sistema (disponible para todas las horas)
    fcst_col = cm.get("stppfsystemwide") or cm.get("stppfsystem")
    if fcst_col:
        df["fcst_value"] = pd.to_numeric(df[fcst_col], errors="coerce")
    # Si no hay columna actual, usar pronóstico como value
    if "value" not in df.columns and fcst_col:
        df["value"] = df["fcst_value"]
    return df


def _hour_ending_to_ts(df):
    """Detecta automáticamente columnas de fecha y hora y construye timestamp."""
    # Detectar columna de fecha
    date_col = next((c for c in df.columns if c.lower() in ("deliverydate", "date")), None)
    if date_col is None:
        return None
    # Detectar columna de hora (hourEnding o deliveryHour)
    hour_col = next((c for c in df.columns
                     if c.lower() in ("hourending", "deliveryhour", "hour", "hour_ending")), None)
    if hour_col is None:
        return None
    base = pd.to_datetime(df[date_col])
    raw  = df[hour_col].astype(str)
    if raw.str.contains(":").any():
        horas = raw.str.split(":").str[0].astype(int) - 1
    else:
        horas = pd.to_numeric(raw, errors="coerce").fillna(1).astype(int) - 1
    return base + pd.to_timedelta(horas, unit="h")


@st.cache_data(ttl=300, show_spinner=False)
def live_da_price(d0, d1, node="DC_L"):
    """DA Settlement Point Prices desde ERCOT API (np4-190-cd).
    Lanza ValueError si no hay datos — st.cache_data no cachea excepciones,
    así el siguiente intento siempre reintenta cuando el dato aún no está publicado.
    """
    df = _ercot_get(
        "https://api.ercot.com/api/public-reports/np4-190-cd/dam_stlmnt_pnt_prices",
        d0, d1, extra_params={"settlementPoint": node},
    )
    if df is None or df.empty:
        raise ValueError(f"DA no disponible: {node} {d0}")
    price_col = next((c for c in df.columns if "settlementpointprice" in c.lower()), None)
    if price_col is None:
        raise ValueError(f"Columna price no encontrada: {list(df.columns)}")
    ts = _hour_ending_to_ts(df)
    if ts is None:
        raise ValueError("No se pudo construir timestamp")
    df["fecha"] = ts
    df["price"] = pd.to_numeric(df[price_col], errors="coerce")
    df = df.dropna(subset=["fecha", "price"]).sort_values("fecha").reset_index(drop=True)
    if df.empty:
        raise ValueError(f"DA vacío tras limpieza: {node} {d0}")
    return df[["fecha", "price"]]


@st.cache_data(ttl=300, show_spinner=False)
def live_rt_price(d0, d1, node="DC_L"):
    """RT Settlement Point Prices desde ERCOT API (np6-905-cd) promediado por hora."""
    df = _ercot_get(
        "https://api.ercot.com/api/public-reports/np6-905-cd/spp_node_zone_hub",
        d0, d1, extra_params={"settlementPoint": node},
    )
    if df is None or df.empty:
        return None
    price_col = next((c for c in df.columns if "settlementpointprice" in c.lower()), None)
    if price_col is None:
        return None
    ts = _hour_ending_to_ts(df)
    if ts is None:
        return None
    df["fecha"] = ts
    df["price"] = pd.to_numeric(df[price_col], errors="coerce")
    df = (df.dropna(subset=["fecha", "price"])
            .groupby("fecha")["price"].mean()
            .reset_index()
            .sort_values("fecha"))
    return df


def mu_get(path: str, auth: tuple, **params) -> pd.DataFrame:
    resp = requests.get(MU_ROOT + path, auth=auth, params=params, timeout=30)
    resp.raise_for_status()
    return pd.read_csv(io.StringIO(resp.text))


@st.cache_data(ttl=300, show_spinner=False)
def mu_catalog(auth: tuple) -> pd.DataFrame:
    return mu_get("/synthetic/forecasts", auth)


@st.cache_data(ttl=300, show_spinner=False)
def mu_syn_p50(dataset_hint: str, node: str, day: "date", auth: tuple) -> list:
    """Devuelve vector P50 [24] del synthetic MarginalUnit para un nodo y día.
    Retorna [None]*24 si falla o no hay datos."""
    try:
        df_meta = mu_catalog(auth)
        ercot = df_meta[df_meta["org"] == "ercot"] if "ercot" in df_meta["org"].values else df_meta
        match = ercot[ercot["dataset"].str.lower() == dataset_hint]
        if match.empty:
            match = ercot[ercot["dataset"].str.contains(dataset_hint, case=False)]
        if match.empty:
            return [None] * 24
        latest = match[match["is_latest"] == 1]
        row = latest.iloc[0] if not latest.empty else match.iloc[0]
        _org, _ds, _ver = row["org"], row["dataset"], row["version"]
        df_asofs = mu_get(f"/synthetic/{_org}/{_ds}/{_ver}/as_ofs", auth, entities=node)
        if df_asofs.empty:
            return [None] * 24
        asof = df_asofs.sort_values("as_of", ascending=False).iloc[0]["as_of"]
        df_fc = mu_get(f"/synthetic/{_org}/{_ds}/{_ver}/report", auth,
                       entities=node, as_of=asof)
        df_fc["timestamp"] = (
            pd.to_datetime(df_fc["timestamp"], utc=True)
            .dt.tz_convert("America/Chicago").dt.tz_localize(None)
        )
        df_fc = df_fc[df_fc["timestamp"].dt.date == day].sort_values("timestamp")
        df_fc.columns = [c.lower() for c in df_fc.columns]
        if "synthetic_0_5" not in df_fc.columns:
            return [None] * 24
        return (df_fc["synthetic_0_5"].tolist() + [None] * 24)[:24]
    except Exception:
        return [None] * 24


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="text-align:center; padding:14px 0 4px 0;">
        <svg width="188" height="66" viewBox="0 0 188 66" xmlns="http://www.w3.org/2000/svg" style="display:block;margin:0 auto;">
          <text x="2" y="50" font-family="'Arial Rounded MT Bold','Helvetica Neue','Arial',sans-serif"
                font-weight="800" font-style="italic" font-size="46" fill="#5a6878">ercot</text>
          <!-- Arc 1 -->
          <path d="M 140,10 C 149,3 163,7 166,18" fill="none" stroke="#00b5cc" stroke-width="4" stroke-linecap="round"/>
          <!-- Arc 2 -->
          <path d="M 137,23 C 147,15 162,20 163,31" fill="none" stroke="#00b5cc" stroke-width="4" stroke-linecap="round"/>
          <!-- Lightning bolt -->
          <path d="M 164,35 L 152,54 L 160,52 L 150,66 L 175,48 L 166,49 L 177,35 Z" fill="#00b5cc"/>
        </svg>
    </div>
    """, unsafe_allow_html=True)
    st.divider()

    page = st.selectbox(
        "Página",
        ["Load & Renewables", "Synthetic Forecast", "Temperaturas",
         "DA / RT Prices", "Spread México",
         "Monte Carlo IMP/EXP", "Monte Carlo Hubs"],
        label_visibility="collapsed",
    )

    st.divider()

    if st.button("Cerrar Sesión", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.auth      = None
        st.rerun()

    st.markdown(f"<div style='color:#2d3350; font-size:0.65rem; margin-top:8px; text-align:center;'>{datetime.now().strftime('%d/%m/%Y %H:%M')}</div>", unsafe_allow_html=True)


# ── Datos BD (histórico) ──────────────────────────────────────────────────────
df_hist, live_db   = load_ercot(14)   # 14 días para páginas de análisis reciente
df_temps, _        = load_temperaturas(3)
tc, live_tc        = load_tipo_cambio()

if not live_db:
    st.markdown('<div class="demo-banner">⚠️ <b>Modo demo</b> — Sin conexión a BD. Datos históricos son sintéticos.</div>', unsafe_allow_html=True)

# Rango para APIs en vivo
today_dt  = date.today()
d0 = (today_dt - timedelta(days=1)).strftime("%Y-%m-%d")
d1 = (today_dt + timedelta(days=1)).strftime("%Y-%m-%d")

hours = list(range(1, 25))
yday_dt = today_dt - timedelta(days=1)
tmrw_dt = today_dt + timedelta(days=1)

def day_vals(df, col, target_date):
    """Extrae 24 valores horarios para una fecha específica. Busca columna de fecha automáticamente."""
    if df is None or col not in df.columns:
        return [0] * 24
    date_col = next((c for c in ["deliveryDate", "operatingDay", "date"] if c in df.columns), None)
    if date_col is None:
        return [0] * 24
    d_str = target_date.strftime("%Y-%m-%d") if hasattr(target_date, "strftime") else str(target_date)
    mask = df[date_col].astype(str).str.startswith(d_str)
    sub = df[mask].copy()
    if sub.empty:
        return [0] * 24
    hour_col = next((c for c in ["hourEnding", "deliveryHour", "hour"] if c in sub.columns), None)
    if hour_col:
        # Sort numérico: "1","10","11"... (forecast) y "01:00","02:00"... (actual) ordenan igual
        sub["_h"] = sub[hour_col].apply(
            lambda x: int(str(x).split(":")[0]) if ":" in str(x) else int(float(str(x)))
        )
        # Agrupar por hora tomando el máximo — evita spikes cuando hay múltiples filas por hora
        grp = sub.groupby("_h")[col].apply(lambda x: pd.to_numeric(x, errors="coerce").max())
        return [float(grp.get(h, 0) or 0) for h in range(1, 25)]
    vals = pd.to_numeric(sub[col], errors="coerce").fillna(0).tolist()
    return (vals + [0] * 24)[:24]

def load_chart(yday_act, today_act, today_fcst, tmrw_fcst):
    """
    Load chart: ayer=sólido, hoy=sólido(actual)+punteado(forecast), mañana=punteado.
    """
    yday = yday_dt.strftime("%b %d")
    tday = today_dt.strftime("%b %d")
    tmrw = tmrw_dt.strftime("%b %d")

    # Última hora con dato real de hoy (actual endpoint)
    last_h_act = 0
    for i, v in enumerate(today_act):
        if v and v > 0:
            last_h_act = i + 1

    if last_h_act > 0:
        # Tenemos datos reales → sólido=actual, punteado=forecast
        last_h = last_h_act
        today_solid = [today_act[i] if (i + 1) <= last_h else None for i in range(24)]
    else:
        # Sin datos reales (endpoint solo publica días completos) →
        # partir por hora actual del sistema: sólido=horas pasadas del forecast, punteado=horas futuras
        last_h = datetime.now().hour  # hora local 0-23; hourEnding 1-24
        today_solid = [today_fcst[i] if (i + 1) <= last_h else None for i in range(24)]

    # Hoy punteado: forecast desde last_h en adelante (un punto de overlap para conectar)
    today_dash = [today_fcst[i] if (i + 1) >= last_h else None for i in range(24)]

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=hours, y=yday_act,    mode="lines", name=f"Yesterday  {yday}",
                             line=dict(color=C_AYER, width=2.5)))
    fig.add_trace(go.Scatter(x=hours, y=today_solid, mode="lines", name=f"Today  {tday}",
                             line=dict(color=C_HOY, width=3), connectgaps=False))
    fig.add_trace(go.Scatter(x=hours, y=today_dash,  mode="lines", name=f"Today Fcst",
                             line=dict(color=C_HOY, width=2, dash="dot"),
                             showlegend=False, connectgaps=False))
    fig.add_trace(go.Scatter(x=hours, y=tmrw_fcst,   mode="lines", name=f"Tomorrow  {tmrw}",
                             line=dict(color=C_MANANA, width=2.5, dash="dash")))
    fig.update_layout(**_plotly_base(380, "Load Forecast"), xaxis_title="Hour Ending", yaxis_title="Load (MW)")
    fig.update_xaxes(tickvals=list(range(1, 25, 2)))
    return fig


def gen_forecast_chart(title, y_label, yday, today, tmrw):
    """
    Gráfica genérica para renovables (wind, etc.) con una sola columna de datos.
    Ayer=sólido, Hoy=sólido(horas pasadas)+punteado(futuras), Mañana=punteado.
    """
    yday_lbl = yday_dt.strftime("%b %d")
    tday_lbl = today_dt.strftime("%b %d")
    tmrw_lbl = tmrw_dt.strftime("%b %d")

    last_h = datetime.now().hour  # 0-23; horas 1..last_h ya ocurrieron
    today_solid = [today[i] if (i + 1) <= last_h else None for i in range(24)]
    today_dash  = [today[i] if (i + 1) >= last_h else None for i in range(24)]

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=hours, y=yday,        mode="lines", name=f"Yesterday  {yday_lbl}",
                             line=dict(color=C_AYER, width=2.5)))
    fig.add_trace(go.Scatter(x=hours, y=today_solid, mode="lines", name=f"Today  {tday_lbl}",
                             line=dict(color=C_HOY, width=3), connectgaps=False))
    fig.add_trace(go.Scatter(x=hours, y=today_dash,  mode="lines", name=f"Today Fcst",
                             line=dict(color=C_HOY, width=2, dash="dot"),
                             showlegend=False, connectgaps=False))
    fig.add_trace(go.Scatter(x=hours, y=tmrw,        mode="lines", name=f"Tomorrow  {tmrw_lbl}",
                             line=dict(color=C_MANANA, width=2.5, dash="dash")))
    fig.update_layout(**_plotly_base(380, title), xaxis_title="Hour Ending", yaxis_title=y_label)
    fig.update_xaxes(tickvals=list(range(1, 25, 2)))
    return fig


def solar_chart(yday_act, today_act, today_fcst, tmrw_fcst):
    """Solar chart: ayer=sólido, hoy=sólido(actual)+punteado(forecast), mañana=punteado."""
    yday = yday_dt.strftime("%b %d")
    tday = today_dt.strftime("%b %d")
    tmrw = tmrw_dt.strftime("%b %d")

    last_h_act = 0
    for i, v in enumerate(today_act):
        if v and v > 0:
            last_h_act = i + 1

    if last_h_act > 0:
        last_h = last_h_act
        today_solid = [today_act[i] if (i + 1) <= last_h else None for i in range(24)]
    else:
        last_h = datetime.now().hour
        today_solid = [today_fcst[i] if (i + 1) <= last_h else None for i in range(24)]

    today_dash = [today_fcst[i] if (i + 1) >= last_h else None for i in range(24)]

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=hours, y=yday_act,    mode="lines", name=f"Yesterday  {yday}",
                             line=dict(color=C_AYER, width=2.5)))
    fig.add_trace(go.Scatter(x=hours, y=today_solid, mode="lines", name=f"Today  {tday}",
                             line=dict(color=C_HOY, width=3), connectgaps=False))
    fig.add_trace(go.Scatter(x=hours, y=today_dash,  mode="lines", name=f"Today Fcst",
                             line=dict(color=C_HOY, width=2, dash="dot"),
                             showlegend=False, connectgaps=False))
    fig.add_trace(go.Scatter(x=hours, y=tmrw_fcst,   mode="lines", name=f"Tomorrow  {tmrw}",
                             line=dict(color=C_MANANA, width=2.5, dash="dash")))
    fig.update_layout(**_plotly_base(380, "Solar Generation Forecast"),
                      xaxis_title="Hour Ending", yaxis_title="Solar Generation (MW)")
    fig.update_xaxes(tickvals=list(range(1, 25, 2)))
    return fig


def three_day_chart(title, y_label, y0, y1, y2):
    yday = yday_dt.strftime("%b %d")
    tday = today_dt.strftime("%b %d")
    tmrw = tmrw_dt.strftime("%b %d")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=hours, y=y0, mode="lines", name=f"Yesterday  {yday}", line=dict(color=C_AYER, width=2.5)))
    fig.add_trace(go.Scatter(x=hours, y=y1, mode="lines", name=f"Today  {tday}",     line=dict(color=C_HOY,  width=3)))
    fig.add_trace(go.Scatter(x=hours, y=y2, mode="lines", name=f"Tomorrow  {tmrw}",  line=dict(color=C_MANANA, width=2.5, dash="dash")))
    fig.update_layout(**_plotly_base(380, title), xaxis_title="Hour Ending", yaxis_title=y_label)
    fig.update_xaxes(tickvals=list(range(1, 25, 2)))
    return fig



def _kpi_spread(label, val, ref, fmt="${:.2f}", color="#00d4e8", tag=""):
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return f"""<div class="kpi-card" style="border-left-color:{color}">
            <div class="kpi-label">{label} {tag}</div>
            <div class="kpi-value" style="color:{color}">—</div>
        </div>"""
    d = val - ref if ref is not None and not np.isnan(ref) else 0
    arrow = "▲" if d > 0 else "▼"
    dcls  = "kpi-delta-up" if d > 0 else "kpi-delta-down"
    return f"""<div class="kpi-card" style="border-left-color:{color}">
        <div class="kpi-label">{label} {tag}</div>
        <div class="kpi-value" style="color:{color}">{fmt.format(val)}</div>
        <span class="{dcls}">{arrow} {fmt.format(abs(d))}</span>
    </div>"""


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 1: Load & Renewables  (datos en vivo de ERCOT API)
# ══════════════════════════════════════════════════════════════════════════════
if page == "Load & Renewables":
    st.title(f"Load & Renewables  —  {today_dt.strftime('%A %B %d, %Y')}")

    with st.spinner("Cargando datos ERCOT…"):
        df_load                    = live_load(d0, d1)
        df_load_act                = live_load_actual(d0, d1)
        df_ws, df_ww, df_wn, df_wt = live_wind_all(d0, d1)
        df_sol                     = live_solar(d0, d1)

    has_load  = df_load is not None and "value" in df_load.columns
    has_ws    = df_ws is not None and "value" in df_ws.columns
    has_ww    = df_ww is not None and "value" in df_ww.columns
    has_wn    = df_wn is not None and "value" in df_wn.columns
    has_wt    = df_wt is not None and "value" in df_wt.columns
    has_solar = df_sol is not None and "value" in df_sol.columns

    # ── Net Load Forecast ─────────────────────────────────────────────────────
    if has_load and has_wt and has_solar:
        ld_y, ld_d, ld_t = (day_vals(df_load,"value",yday_dt),
                             day_vals(df_load,"value",today_dt),
                             day_vals(df_load,"value",tmrw_dt))
        # Sistema total: evita contar zonas duplicadas
        wt_y = day_vals(df_wt, "value", yday_dt)
        wt_d = day_vals(df_wt, "value", today_dt)
        wt_t = day_vals(df_wt, "value", tmrw_dt)

        def _solar_best(target):
            act  = day_vals(df_sol, "value",      target)
            fcst = day_vals(df_sol, "fcst_value", target) if "fcst_value" in df_sol.columns else [0]*24
            return [a if a > 0 else f for a, f in zip(act, fcst)]

        sol_y = _solar_best(yday_dt)
        sol_d = _solar_best(today_dt)
        sol_t = _solar_best(tmrw_dt)
        nl_y = [l - w - s for l, w, s in zip(ld_y, wt_y, sol_y)]
        nl_d = [l - w - s for l, w, s in zip(ld_d, wt_d, sol_d)]
        nl_t = [l - w - s for l, w, s in zip(ld_t, wt_t, sol_t)]
        st.plotly_chart(three_day_chart("Net Load Forecast", "Net Load (MW)", nl_y, nl_d, nl_t),
                        use_container_width=True)

    # ── Load Forecast ─────────────────────────────────────────────────────────
    if has_load:
        # Ayer: usar actual si está disponible, sino forecast
        ld_y_act = day_vals(df_load_act, "value", yday_dt) if df_load_act is not None and "value" in df_load_act.columns else [0]*24
        ld_y = ld_y_act if any(v > 0 for v in ld_y_act) else day_vals(df_load, "value", yday_dt)
        # Hoy: actual (parcial) + forecast
        ld_d_act  = day_vals(df_load_act, "value", today_dt) if df_load_act is not None and "value" in df_load_act.columns else [0]*24
        ld_d_fcst = day_vals(df_load, "value", today_dt)
        # Mañana: forecast
        ld_t = day_vals(df_load, "value", tmrw_dt)
        st.plotly_chart(load_chart(ld_y, ld_d_act, ld_d_fcst, ld_t),
                        use_container_width=True)
    else:
        st.warning("Load no disponible")

    # ── Wind West | Wind North ─────────────────────────────────────────────────
    c1, c2 = st.columns(2)
    with c1:
        if has_ww:
            st.plotly_chart(gen_forecast_chart("Wind West Generation Forecast", "Wind Generation (MW)",
                day_vals(df_ww,"value",yday_dt), day_vals(df_ww,"value",today_dt), day_vals(df_ww,"value",tmrw_dt)),
                use_container_width=True)
    with c2:
        if has_wn:
            st.plotly_chart(gen_forecast_chart("Wind North Generation Forecast", "Wind Generation (MW)",
                day_vals(df_wn,"value",yday_dt), day_vals(df_wn,"value",today_dt), day_vals(df_wn,"value",tmrw_dt)),
                use_container_width=True)

    # ── Wind South | Solar ────────────────────────────────────────────────────
    c3, c4 = st.columns(2)
    with c3:
        if has_ws:
            st.plotly_chart(gen_forecast_chart("Wind South Generation Forecast", "Wind Generation (MW)",
                day_vals(df_ws,"value",yday_dt), day_vals(df_ws,"value",today_dt), day_vals(df_ws,"value",tmrw_dt)),
                use_container_width=True)
    with c4:
        if has_solar:
            sol_y_act  = day_vals(df_sol, "value",      yday_dt)
            sol_d_act  = day_vals(df_sol, "value",      today_dt)
            sol_d_fcst = day_vals(df_sol, "fcst_value", today_dt)
            sol_t_fcst = day_vals(df_sol, "fcst_value", tmrw_dt)
            st.plotly_chart(solar_chart(sol_y_act, sol_d_act, sol_d_fcst, sol_t_fcst),
                            use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 2: Precios DA / RT (vista por nodo y fecha)
# ══════════════════════════════════════════════════════════════════════════════
elif page == "DA / RT Prices":
    tday_str = today_dt.strftime("%A %B %d, %Y")
    st.title(f"DA / RT Prices  —  {tday_str}")

    yday_dt = today_dt - timedelta(days=1)
    tmrw_dt = today_dt + timedelta(days=1)
    yday_s  = yday_dt.strftime("%b %d")
    tday_s  = today_dt.strftime("%b %d")
    tmrw_s  = tmrw_dt.strftime("%b %d")

    # ── Selectores ────────────────────────────────────────────────────────────
    cs1, cs2 = st.columns([2, 1])
    with cs1:
        sel_node = st.text_input("Node / Hub", value="DC_L",
                                 placeholder="Ej: DC_L, HB_NORTH, HB_HOUSTON…")
    with cs2:
        _date_opts = {
            f"Yesterday  ({yday_s})": yday_dt,
            f"Today  ({tday_s})":     today_dt,
            f"Tomorrow  ({tmrw_s})":  tmrw_dt,
        }
        sel_date_lbl = st.selectbox("Date", list(_date_opts.keys()), index=1)
        sel_date = _date_opts[sel_date_lbl]
        sel_date_s = sel_date.strftime("%b %d")

    api_node = sel_node.upper().replace(" ", "_")

    # ── KPI helper ────────────────────────────────────────────────────────────
    def _kpi(label, val, ref, color="#00d4e8"):
        if val is None or (isinstance(val, float) and np.isnan(val)):
            return (f'<div class="kpi-card" style="border-left-color:{color}">'
                    f'<div class="kpi-label">{label}</div>'
                    f'<div class="kpi-value" style="color:{color}">—</div></div>')
        ref = ref if ref is not None and not (isinstance(ref, float) and np.isnan(ref)) else val
        d = val - ref; arrow = "▲" if d > 0 else "▼"
        dcls = "kpi-delta-up" if d > 0 else "kpi-delta-down"
        return (f'<div class="kpi-card" style="border-left-color:{color}">'
                f'<div class="kpi-label">{label}</div>'
                f'<div class="kpi-value" style="color:{color}">${val:.2f}</div>'
                f'<span class="{dcls}">{arrow} {abs(d):.2f}</span></div>')

    # ── Fetch DA y RT reales desde ERCOT API ──────────────────────────────────
    _fetch_d0 = sel_date.strftime("%Y-%m-%d")
    _fetch_d1 = (sel_date + timedelta(days=1)).strftime("%Y-%m-%d")
    with st.spinner(f"Loading DA & RT — {api_node}…"):
        try:
            df_da_real = live_da_price(_fetch_d0, _fetch_d1, api_node)
        except Exception:
            df_da_real = None
        df_rt_real = live_rt_price(_fetch_d0, _fetch_d1, api_node)

    def _price_vec(df, day):
        if df is None or df.empty:
            return [None] * 24
        sub = df[df["fecha"].dt.date == day].sort_values("fecha")
        vals = sub["price"].tolist()
        return (vals + [None] * 24)[:24]

    da_real = _price_vec(df_da_real, sel_date)   # None = no publicado aún
    rt_real = _price_vec(df_rt_real, sel_date)   # None = no publicado aún

    # np6-905-cd no devuelve datos completos para DC ties en fechas históricas.
    # Merge: df_hist llena huecos que la API dejó (y viceversa).
    if sel_date <= yday_dt and api_node in ("DC_L", "DC_R"):
        _sfx = api_node.replace("_", "")
        _rt_hist_col = f"RT_{_sfx}"
        if _rt_hist_col in df_hist.columns:
            _sub_rt = df_hist[df_hist["fecha"].dt.date == sel_date].sort_values("fecha")
            if not _sub_rt.empty:
                _hist_rt = [None] * 24
                for _, _r in _sub_rt.iterrows():
                    _h = _r["fecha"].hour
                    if 0 <= _h < 24:
                        _v = _r[_rt_hist_col]
                        _hist_rt[_h] = float(_v) if pd.notna(_v) else None
                # Combinar: df_hist donde tenga valor, API donde df_hist no tiene
                rt_real = [_hist_rt[i] if _hist_rt[i] is not None else rt_real[i] for i in range(24)]

    # ── Fetch Synthetic (MU) para horas faltantes ─────────────────────────────
    def _fetch_syn_vec(dataset_hint, day):
        """Devuelve (p50_vec[24], p5_vec[24], p95_vec[24], asof) usando MU API."""
        _none24 = [None] * 24
        try:
            df_meta = mu_catalog(AUTH)
            ercot = df_meta[df_meta["org"] == "ercot"] if "ercot" in df_meta["org"].values else df_meta
            match = ercot[ercot["dataset"].str.lower() == dataset_hint]
            if match.empty:
                match = ercot[ercot["dataset"].str.contains(dataset_hint, case=False)]
            if match.empty:
                return _none24, _none24, _none24, None
            latest = match[match["is_latest"] == 1]
            row = latest.iloc[0] if not latest.empty else match.iloc[0]
            _org, _ds, _ver = row["org"], row["dataset"], row["version"]
            df_asofs = mu_get(f"/synthetic/{_org}/{_ds}/{_ver}/as_ofs", AUTH, entities=api_node)
            if df_asofs.empty:
                return _none24, _none24, _none24, None
            # Iterate as_ofs newest→oldest until we find one covering the target day.
            # MU forecasts cover ~48h ahead, so 1-2 as_ofs cover today; for yesterday
            # we may need to look back up to ~20 as_ofs (one per 6h → 5 days).
            df_asofs_sorted = df_asofs.sort_values("as_of", ascending=False).head(20)
            df_fc = pd.DataFrame()
            asof = None
            for _, _arow in df_asofs_sorted.iterrows():
                _asof_try = _arow["as_of"]
                try:
                    _df_try = mu_get(f"/synthetic/{_org}/{_ds}/{_ver}/report",
                                     AUTH, entities=api_node, as_of=_asof_try)
                    _df_try["timestamp"] = (
                        pd.to_datetime(_df_try["timestamp"], utc=True)
                        .dt.tz_convert("America/Chicago").dt.tz_localize(None)
                    )
                    _filtered = _df_try[_df_try["timestamp"].dt.date == day]
                    if not _filtered.empty:
                        df_fc = _filtered.sort_values("timestamp")
                        asof = _asof_try
                        break
                except Exception:
                    continue
            if df_fc.empty:
                return _none24, _none24, _none24, None
            df_fc.columns = [c.lower() for c in df_fc.columns]
            if "synthetic_0_5" not in df_fc.columns:
                return _none24, _none24, _none24, asof
            p50 = (df_fc["synthetic_0_5"].tolist()  + [None]*24)[:24]
            p5  = (df_fc["synthetic_0_05"].tolist() + [None]*24)[:24] if "synthetic_0_05" in df_fc.columns else _none24
            p95 = (df_fc["synthetic_0_95"].tolist() + [None]*24)[:24] if "synthetic_0_95" in df_fc.columns else _none24
            return p50, p5, p95, asof
        except Exception:
            return _none24, _none24, _none24, None

    # Solo busca synthetic si hay horas sin publicar
    need_da_syn = any(v is None for v in da_real)
    need_rt_syn = any(v is None for v in rt_real)

    syn_da_p50 = syn_da_p5 = syn_da_p95 = [None] * 24
    syn_rt_p50 = syn_rt_p5 = syn_rt_p95 = [None] * 24
    syn_da_asof = syn_rt_asof = None

    if need_da_syn or need_rt_syn:
        with st.spinner("Cargando synthetic (MU) para horas sin publicar…"):
            if need_da_syn:
                syn_da_p50, syn_da_p5, syn_da_p95, syn_da_asof = _fetch_syn_vec("lmp_da", sel_date)
            if need_rt_syn:
                syn_rt_p50, syn_rt_p5, syn_rt_p95, syn_rt_asof = _fetch_syn_vec("lmp_rt", sel_date)

    # Vector final hora por hora: real si existe, synthetic P50 si no
    da_final  = [da_real[i] if da_real[i] is not None else syn_da_p50[i] for i in range(24)]
    rt_final  = [rt_real[i] if rt_real[i] is not None else syn_rt_p50[i] for i in range(24)]
    # Qué tipo de dato es cada hora
    da_is_real = [da_real[i] is not None for i in range(24)]
    rt_is_real = [rt_real[i] is not None for i in range(24)]

    dart_vec = [
        round(da_final[i] - rt_final[i], 4)
        if da_final[i] is not None and rt_final[i] is not None else None
        for i in range(24)
    ]

    # ── KPIs: Avg DA | Avg RT | Avg DART | USD/MXN ───────────────────────────
    avg_da   = float(np.mean([v for v in da_final  if v is not None])) if any(v is not None for v in da_final)  else None
    avg_rt   = float(np.mean([v for v in rt_final  if v is not None])) if any(v is not None for v in rt_final)  else None
    avg_dart = float(np.mean([v for v in dart_vec  if v is not None])) if any(v is not None for v in dart_vec)  else None

    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(_kpi(f"Avg DA  {sel_node}  ({sel_date_s})",   avg_da,   None,   "#B7D433"), unsafe_allow_html=True)
    c2.markdown(_kpi(f"Avg RT  {sel_node}  ({sel_date_s})",   avg_rt,   avg_da, "#FF6B35"), unsafe_allow_html=True)
    c3.markdown(_kpi(f"Avg DART  {sel_node}  ({sel_date_s})", avg_dart, None,   "#a78bfa"), unsafe_allow_html=True)
    c4.markdown(
        f'<div class="kpi-card" style="border-left-color:#34d399">'
        f'<div class="kpi-label">USD/MXN</div>'
        f'<div class="kpi-value" style="color:#34d399">{tc:.4f}</div>'
        f'<span class="kpi-sub">{"live" if live_tc else "demo"}</span></div>',
        unsafe_allow_html=True,
    )
    # Caption si hay horas con synthetic
    captions = []
    if need_da_syn and syn_da_asof:
        captions.append(f"DA Synthetic as of **{syn_da_asof}**")
    if need_rt_syn and syn_rt_asof:
        captions.append(f"RT Synthetic as of **{syn_rt_asof}**")
    if captions:
        st.caption("Horas sin publicar usan MU Synthetic P50  —  " + "  |  ".join(captions))

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Gráfica: línea continua = real, triángulos = synthetic ───────────────
    def _split_traces(real_vec, final_vec, is_real_flags, color, name_real, name_syn):
        """Línea continua: sólida en horas reales, punteada en horas synthetic."""
        real_y = [final_vec[i] if is_real_flags[i]     else float("nan") for i in range(24)]
        syn_y  = [final_vec[i] if not is_real_flags[i] else float("nan") for i in range(24)]
        # Para que la línea punteada conecte con la sólida, añadir el punto de transición
        for i in range(24):
            if not is_real_flags[i] and i > 0 and is_real_flags[i - 1] and final_vec[i - 1] is not None:
                syn_y[i - 1] = final_vec[i - 1]
            if is_real_flags[i] and i > 0 and not is_real_flags[i - 1] and final_vec[i - 1] is not None:
                real_y[i - 1] = final_vec[i - 1]
        traces = [
            go.Scatter(x=hours, y=real_y, name=name_real,
                       mode="lines", line=dict(color=color, width=2.5), connectgaps=False),
            go.Scatter(x=hours, y=syn_y, name=name_syn,
                       mode="lines", line=dict(color=color, width=2.5, dash="dot"),
                       connectgaps=False, showlegend=any(v == v for v in syn_y if v == v)),
        ]
        return traces

    fig = go.Figure()
    for tr in _split_traces(da_real, da_final, da_is_real, C_DA,
                            f"DA Real  {api_node}", f"DA Synthetic  {api_node}"):
        fig.add_trace(tr)
    for tr in _split_traces(rt_real, rt_final, rt_is_real, C_RT,
                            f"RT Real  {api_node}", f"RT Synthetic  {api_node}"):
        fig.add_trace(tr)

    fig.update_layout(**_plotly_base(420, f"DA & RT Prices — {api_node}  ·  {sel_date_s}  $/MWh"),
                      yaxis_title="$/MWh", xaxis_title="Hour Ending")
    fig.update_xaxes(tickvals=list(range(1, 25, 2)))
    st.plotly_chart(fig, use_container_width=True)

    # ── Top 5 / Bottom 5 DART hours ───────────────────────────────────────────
    dart_avail = [(h, v) for h, v in zip(hours, dart_vec) if v is not None]
    if dart_avail:
        top5 = sorted(dart_avail, key=lambda x: x[1], reverse=True)[:5]
        bot5 = sorted(dart_avail, key=lambda x: x[1])[:5]

        def _dart_mini_html(title, rows_data, color):
            hdr = "".join(
                f'<th style="background:#12151f;color:{color};padding:6px 16px;'
                f'text-transform:uppercase;letter-spacing:1px;font-size:0.72rem;'
                f'border-bottom:2px solid {color};">{h}</th>'
                for h in ["HE", "DART $/MWh"]
            )
            body = ""
            for he, v in rows_data:
                bg = "#1e2130" if he % 2 == 0 else "#12151f"
                body += (
                    f'<tr>'
                    f'<td style="background:{bg};color:#00d4e8;font-weight:700;'
                    f'padding:5px 16px;border-bottom:1px solid #2d3350;'
                    f'font-family:Consolas,monospace;">{he}</td>'
                    f'<td style="background:{bg};color:{color};font-weight:700;'
                    f'padding:5px 16px;border-bottom:1px solid #2d3350;'
                    f'font-family:Consolas,monospace;">${v:.2f}</td>'
                    f'</tr>'
                )
            return (
                f'<div style="font-size:0.8rem;color:{color};font-weight:700;margin-bottom:6px;">{title}</div>'
                f'<div style="border:1px solid #2d3350;border-radius:6px;overflow:hidden;">'
                f'<table style="width:100%;border-collapse:collapse;">'
                f'<thead><tr>{hdr}</tr></thead><tbody>{body}</tbody></table></div>'
            )

        st.markdown(f"### DART  {api_node}  —  Top / Bottom 5  ({sel_date_s})")
        col_t, col_b = st.columns(2)
        with col_t:
            st.markdown(_dart_mini_html("Highest DART (HE)", top5, "#B7D433"), unsafe_allow_html=True)
        with col_b:
            st.markdown(_dart_mini_html("Lowest DART (HE)", bot5, "#FF6B35"), unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

    # ── Tabla horaria: HE | DA | RT | DART  (★ = synthetic) ─────────────────
    st.markdown(f"### Hourly Prices — {sel_date_lbl.split('(')[0].strip()}  ({sel_date_s})")
    any_syn = need_da_syn or need_rt_syn
    if any_syn:
        st.caption("★ = precio sintético (MU P50) — dato real no publicado aún")

    hdrs_t = ["HE", "DA $/MWh", "RT $/MWh", "DART $/MWh"]
    hdr_cells_t = "".join(
        f'<th style="background:#12151f;color:#00d4e8;padding:7px 12px;'
        f'text-transform:uppercase;letter-spacing:1.2px;font-size:0.72rem;'
        f'border-bottom:2px solid #00d4e8;font-family:Segoe UI,sans-serif;">{h}</th>'
        for h in hdrs_t
    )
    rows_html_t = ""
    for i, h in enumerate(hours):
        bg    = "#1e2130" if h % 2 == 0 else "#12151f"
        da_v  = (f'${da_final[i]:.2f}' if da_final[i] is not None else "—")
        rt_v  = (f'${rt_final[i]:.2f}' if rt_final[i] is not None else "—")
        dr_v  = (f'${dart_vec[i]:.2f}' if dart_vec[i] is not None else "—")
        # Añadir ★ si es synthetic
        if da_final[i] is not None and not da_is_real[i]:
            da_v = "★ " + da_v
        if rt_final[i] is not None and not rt_is_real[i]:
            rt_v = "★ " + rt_v
        if dart_vec[i] is not None and (not da_is_real[i] or not rt_is_real[i]):
            dr_v = "★ " + dr_v
        dr_c = ("#B7D433" if dart_vec[i] is not None and dart_vec[i] > 0
                else "#FF6B35" if dart_vec[i] is not None and dart_vec[i] < 0
                else "#5a6280")
        rows_html_t += (
            f'<tr>'
            f'<td style="background:{bg};color:#00d4e8;font-weight:700;padding:5px 12px;'
            f'border-bottom:1px solid #2d3350;font-family:Consolas,monospace;">{h}</td>'
            f'<td style="background:{bg};color:#B7D433;font-weight:600;padding:5px 12px;'
            f'border-bottom:1px solid #2d3350;font-family:Consolas,monospace;">{da_v}</td>'
            f'<td style="background:{bg};color:#FF6B35;font-weight:600;padding:5px 12px;'
            f'border-bottom:1px solid #2d3350;font-family:Consolas,monospace;">{rt_v}</td>'
            f'<td style="background:{bg};color:{dr_c};font-weight:700;padding:5px 12px;'
            f'border-bottom:1px solid #2d3350;font-family:Consolas,monospace;">{dr_v}</td>'
            f'</tr>'
        )
    st.markdown(
        f'<div style="overflow-x:auto;border:1px solid #2d3350;border-radius:6px;'
        f'max-height:560px;overflow-y:auto;">'
        f'<table style="width:100%;border-collapse:collapse;">'
        f'<thead><tr>{hdr_cells_t}</tr></thead>'
        f'<tbody>{rows_html_t}</tbody>'
        f'</table></div>',
        unsafe_allow_html=True,
    )




# ══════════════════════════════════════════════════════════════════════════════
# PAGE 4: Synthetic Forecast (MarginalUnit)
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Synthetic Forecast":
    st.title("Synthetic Forecast")

    # ── Catálogo ──────────────────────────────────────────────────────────────
    try:
        with st.spinner("Cargando catálogo…"):
            df_meta = mu_catalog(AUTH)
    except Exception as _e:
        st.error(f"Error conectando a la API: {_e}")
        st.stop()

    # ── Selectores Org / Dataset / Version ────────────────────────────────────
    c1, c2, c3 = st.columns(3)
    with c1:
        orgs    = sorted(df_meta["org"].unique().tolist())
        sel_org = st.selectbox("Org", orgs, index=orgs.index("ercot") if "ercot" in orgs else 0)
    with c2:
        dsets  = df_meta.loc[df_meta["org"] == sel_org, "dataset"].unique().tolist()
        def_ds = dsets.index("lmp_rt") if "lmp_rt" in dsets else 0
        sel_ds = st.selectbox("Dataset", dsets, index=def_ds)
    with c3:
        vmask  = (df_meta["org"] == sel_org) & (df_meta["dataset"] == sel_ds)
        vers   = df_meta.loc[vmask, "version"].tolist()
        latest_vers = df_meta.loc[vmask & (df_meta["is_latest"] == 1), "version"].tolist()
        def_v  = vers.index(latest_vers[0]) if latest_vers else len(vers) - 1
        sel_ver = st.selectbox("Version", vers, index=def_v)

    # ── PNode + As Of + Días ─────────────────────────────────────────────────
    c4, c5, c6 = st.columns([2, 3, 1])
    with c4:
        sel_ent = st.text_input("PNode", value="DC_L", placeholder="Ej: DC_L, HB_NORTH…")
    with c5:
        try:
            df_asofs = mu_get(f"/synthetic/{sel_org}/{sel_ds}/{sel_ver}/as_ofs",
                              AUTH, entities=sel_ent)
            asof_list = df_asofs.sort_values("as_of", ascending=False)["as_of"].tolist()
        except Exception:
            asof_list = []
        if asof_list:
            sel_asof = st.selectbox("As Of  (fecha de generación del forecast)", asof_list)
        else:
            st.warning(f"Sin fechas disponibles para {sel_ent} · {sel_ds}. Cambia el PNode o Dataset.")
            sel_asof = None
    with c6:
        show_days = st.number_input("Días", 1, 7, 1)

    run_fc = st.button("Obtener Forecast", type="primary", use_container_width=True)

    if run_fc and sel_asof:
        with st.spinner(f"Descargando {sel_ent} · {sel_ds.upper()} · as_of {sel_asof}…"):
            try:
                df_fc = mu_get(f"/synthetic/{sel_org}/{sel_ds}/{sel_ver}/report",
                               AUTH, entities=sel_ent, as_of=sel_asof)
            except Exception as _e:
                st.error(f"Error descargando forecast: {_e}")
                st.stop()

        # API devuelve UTC → convertir a CT (ERCOT time)
        df_fc["timestamp"] = pd.to_datetime(df_fc["timestamp"], utc=True, errors="coerce")
        df_fc["timestamp"] = df_fc["timestamp"].dt.tz_convert("America/Chicago").dt.tz_localize(None)

        tomorrow = date.today() + timedelta(days=1)
        df_fc = df_fc[df_fc["timestamp"].dt.date >= tomorrow].iloc[: show_days * 24].copy()

        # Normalizar columnas a minúsculas
        df_fc.columns = [c.lower() for c in df_fc.columns]
        pfx = "synthetic"
        cols_need = [f"{pfx}_0_05", f"{pfx}_0_33", f"{pfx}_0_5", f"{pfx}_0_66", f"{pfx}_0_95"]

        if not all(c in df_fc.columns for c in cols_need):
            st.warning("Columnas de percentiles no encontradas en la respuesta.")
            st.dataframe(df_fc.head(24))
        else:
            st.caption(f"As Of: **{sel_asof}**  |  Org: {sel_org}  |  Version: {sel_ver}")

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
                name="Median", line=dict(color=C_HOY, width=2.5),
            ))
            fig.update_layout(**_plotly_base(480, f"{sel_ent}  ·  {sel_ds.upper()}  —  Synthetic Forecast"),
                              xaxis_title="Date / Hour (CT)", yaxis_title="$/MWh")
            st.plotly_chart(fig, use_container_width=True)

            # ── Tabla HTML con colores XTS ────────────────────────────────────
            st.markdown(f"### Forecast Table — {sel_ent}  ·  {sel_ds.upper()}")
            df_tbl_fc = df_fc[["timestamp",
                                f"{pfx}_0_05", f"{pfx}_0_33", f"{pfx}_0_5",
                                f"{pfx}_0_66", f"{pfx}_0_95"]].copy()
            df_tbl_fc["DATE"] = df_tbl_fc["timestamp"].dt.strftime("%Y-%m-%d")
            df_tbl_fc["HE"]   = df_tbl_fc["timestamp"].dt.hour + 1
            df_tbl_fc = df_tbl_fc.drop(columns=["timestamp"])

            hdrs = ["DATE", "HE", "P5", "P33", "P50", "P66", "P95"]
            p_cols = [f"{pfx}_0_05", f"{pfx}_0_33", f"{pfx}_0_5", f"{pfx}_0_66", f"{pfx}_0_95"]

            rows_html = ""
            for i, r in df_tbl_fc.iterrows():
                bg = "#1e2130" if int(r["HE"]) % 2 == 0 else "#12151f"
                vals = [r["DATE"], int(r["HE"])] + [f"{r[c]:.4f}" for c in p_cols]
                cells = ""
                for j, v in enumerate(vals):
                    color = "#00d4e8" if j in (0, 1, 4) else "#c0c4cc"  # DATE, HE, P50 en cian
                    fw    = "700" if j in (0, 1, 4) else "400"
                    cells += f'<td style="background:{bg};color:{color};font-weight:{fw};padding:5px 10px;border-bottom:1px solid #2d3350;font-family:Consolas,monospace;font-size:0.82rem;">{v}</td>'
                rows_html += f"<tr>{cells}</tr>"

            hdr_cells = "".join(
                f'<th style="background:#12151f;color:#00d4e8;padding:7px 10px;text-transform:uppercase;'
                f'letter-spacing:1.2px;font-size:0.72rem;border-bottom:2px solid #00d4e8;'
                f'font-family:Segoe UI,sans-serif;">{h}</th>'
                for h in hdrs
            )

            st.markdown(
                f'<div style="overflow-x:auto;border:1px solid #2d3350;border-radius:6px;">'
                f'<table style="width:100%;border-collapse:collapse;">'
                f'<thead><tr>{hdr_cells}</tr></thead>'
                f'<tbody>{rows_html}</tbody>'
                f'</table></div>',
                unsafe_allow_html=True,
            )


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 5: Temperaturas
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Temperaturas":
    st.title("Temperaturas")

    ciudades = {"LRD": "Laredo TX", "RYN": "Reynosa", "MCA": "McAllen", "NLR": "Nuevo Laredo"}
    colores  = [C_RT, "#fbbf24", C_HOY, "#a78bfa"]

    @st.cache_data(ttl=1800, show_spinner=False)
    def _fetch_temps_live(_today_str: str) -> pd.DataFrame:
        """
        Jala temperatura horaria de Open-Meteo para las últimas 72h + mañana.
        Usa SOLO el forecast API con past_days=3 para evitar el gap
        entre archive (2-day delay) y forecast.
        """
        CIUDADES_APP = {
            "LRD": ( 27.5306,  -99.4803),
            "RYN": ( 26.0844,  -98.2943),
            "MCA": ( 26.2034,  -98.2301),
            "NLR": ( 27.4760,  -99.5164),
        }
        FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
        dfs = []
        for ciudad, (lat, lon) in CIUDADES_APP.items():
            try:
                params = {
                    "latitude":      lat,
                    "longitude":     lon,
                    "hourly":        "temperature_2m",
                    "timezone":      "America/Chicago",
                    "past_days":     3,
                    "forecast_days": 2,
                }
                r = requests.get(FORECAST_URL, params=params, timeout=15)
                r.raise_for_status()
                js = r.json()
                df_c = pd.DataFrame({
                    "fecha": pd.to_datetime(js["hourly"]["time"]),
                    ciudad:  js["hourly"]["temperature_2m"],
                })
                dfs.append(df_c)
            except Exception:
                pass
        if not dfs:
            return pd.DataFrame()
        from functools import reduce
        df_out = reduce(lambda a, b: a.merge(b, on="fecha", how="outer"), dfs)
        return df_out.sort_values("fecha").reset_index(drop=True)

    if st.button("Refrescar temperaturas"):
        _fetch_temps_live.clear()

    with st.spinner("Cargando temperaturas..."):
        _df_live = _fetch_temps_live(today_dt.strftime("%Y-%m-%d"))

    # Usar live si tiene datos recientes; si no, caer a BD
    _use_live = (not _df_live.empty and
                 _df_live["fecha"].max() >= pd.Timestamp(today_dt - timedelta(days=1)))
    df_t = _df_live if _use_live else df_temps
    _src = "Open-Meteo live" if _use_live else "BD (puede estar desactualizada)"

    # Filtrar últimas 72h
    _cutoff = pd.Timestamp(today_dt - timedelta(days=2))
    df_t72  = df_t[df_t["fecha"] >= _cutoff].copy() if not df_t.empty else df_t

    fig_t = go.Figure()
    for i, (col, label) in enumerate(ciudades.items()):
        if col in df_t72.columns:
            fig_t.add_trace(go.Scatter(x=df_t72["fecha"], y=df_t72[col],
                                       name=label, line=dict(color=colores[i], width=1.5)))
    fig_t.update_layout(**_plotly_base(400, "Temperaturas ultimas 72h"),
                        yaxis_title="°C")
    st.plotly_chart(fig_t, use_container_width=True)
    st.caption(f"Fuente: {_src}")

    # Actuales: última fila disponible
    if not df_t72.empty:
        ultima_t = df_t72.iloc[-1]
        cols_t = st.columns(len(ciudades))
        for idx, (col, label) in enumerate(ciudades.items()):
            if col in df_t72.columns:
                val_t = ultima_t[col]
                cols_t[idx].metric(label, f"{val_t:.1f}°C" if val_t is not None and pd.notna(val_t) else "—")
    else:
        st.warning("Sin datos de temperatura disponibles.")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 6: Monte Carlo
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Monte Carlo IMP/EXP":
    st.title("Monte Carlo  —  Simulación P&L Interconexión")

    from etl.caiso.caiso_api import get_pml_cenace

    # ── Tipo de cambio ─────────────────────────────────────────────────────────
    @st.cache_data(ttl=3600, show_spinner=False)
    def get_live_tc():
        try:
            r = requests.get(
                "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/usd.json",
                timeout=10, verify=False)
            r.raise_for_status()
            return float(r.json()["usd"]["mxn"])
        except Exception:
            return None

    with st.spinner("Obteniendo TC…"):
        auto_tc = get_live_tc()

    # ══ SECCIÓN 1: Configuración ══════════════════════════════════════════════
    st.markdown("### Configuración")
    cfg1, cfg2, cfg3, cfg4 = st.columns(4)
    with cfg1:
        tc_mc = st.number_input(
            "TC MXN/USD" + ("  ✓ auto" if auto_tc else "  ⚠ manual"),
            value=float(auto_tc or tc), step=0.01, format="%.4f")
    with cfg2:
        tz_option = st.radio("Zona horaria Texas vs México",
                             ["Misma hora", "ERCOT 1 hora adelantado (+1)"],
                             index=1)
        tz_offset = 0 if tz_option == "Misma hora" else +1
    with cfg3:
        costo_impo = st.number_input("Costo Importación (USD/MWh)", value=17.0, format="%.2f")
        costo_expo = st.number_input("Costo Exportación (USD/MWh)", value=17.0, format="%.2f")
    with cfg4:
        _ERCOT_TO_CENACE = {"DC_L": "06LAA-138", "DC_R": "06RRD-138"}
        nodo_ercot_mc = st.text_input("Nodo ERCOT", value="DC_L",
                                      placeholder="Ej: DC_L, DC_R…")
        _cenace_default = _ERCOT_TO_CENACE.get(nodo_ercot_mc.upper().strip(), "06LAA-138")
        nodo_cenace = st.text_input("Nodo CENACE (MDA)", value=_cenace_default)
        sistema_cenace = st.selectbox("Sistema CENACE", ["SIN", "BCA", "BCS"], index=0)

    # ── Lookback histórico ────────────────────────────────────────────────────
    _lookback_opts = {"30 días": 30, "90 días": 90, "6 meses": 180, "1 año": 365}
    lookback_label = st.selectbox("Días históricos para simulación", list(_lookback_opts.keys()), index=3)
    lookback_days  = _lookback_opts[lookback_label]
    cutoff_date = today_dt - timedelta(days=lookback_days)

    # ══ SECCIÓN 2: Carga de asignación de MW ══════════════════════════════════
    st.markdown("### Asignación de MW")
    uploaded = st.file_uploader("Subir Excel de asignación (HORARIO)", type=["xlsx", "xls"])

    df_asig   = None
    hour_cols = []   # columnas de hora, en orden HE 1-24
    # he_from_col[col_name] → HE México (1-24)
    he_from_col: dict = {}

    if uploaded:
        try:
            df_raw = pd.read_excel(uploaded, header=None)

            # 1) Buscar la fila con "Sistema" o "Clave"
            hdr_row = 1
            for idx in range(min(6, len(df_raw))):
                vals = [str(v).strip().lower() for v in df_raw.iloc[idx].values]
                if "sistema" in vals or "clave" in vals:
                    hdr_row = idx
                    break

            df_asig = pd.read_excel(uploaded, header=hdr_row)
            # Normalizar nombres: quitar espacios y saltos de línea
            df_asig.columns = [str(c).strip().replace("\n", " ") for c in df_asig.columns]
            df_asig = df_asig.dropna(how="all").reset_index(drop=True)

            # 2) Detectar columnas de hora — varios formatos posibles:
            #    "0 1", "0\n1", "1", "1.0", "Unnamed: 4" (positional fallback)
            HOUR_PAT = re.compile(r"^(\d{1,2})\s*[\s\n\-/]+\s*(\d{1,2})$")
            for c in df_asig.columns:
                m = HOUR_PAT.match(c)
                if m:
                    he = int(m.group(2))   # "16 17" → HE 17
                    hour_cols.append(c)
                    he_from_col[c] = he

            # Fallback posicional: si no detectó nada pero hay ≥ 28 columnas,
            # asumir que las columnas después de "Total" son las 24 horas
            if not hour_cols:
                meta_keywords = {"sistema", "clave", "tipo", "total", "flujo"}
                meta_cols = [c for c in df_asig.columns
                             if any(k in c.lower() for k in meta_keywords)]
                first_data = len(meta_cols)
                candidate = df_asig.columns[first_data: first_data + 24].tolist()
                if len(candidate) == 24:
                    hour_cols = candidate
                    for i, c in enumerate(candidate):
                        he_from_col[c] = i + 1   # HE 1..24
                    st.warning("Columnas de hora detectadas por posición (no por nombre). "
                               "Verifica que el orden sea correcto.")

            for hc in hour_cols:
                df_asig[hc] = pd.to_numeric(df_asig[hc], errors="coerce").fillna(0)

            st.success(f"Archivo cargado: {len(df_asig)} filas, {len(hour_cols)} columnas de hora")

            # Debug: mostrar nombres de columnas si 0 horas detectadas
            if not hour_cols:
                with st.expander("Debug — nombres de columnas leídos"):
                    st.write(list(df_asig.columns))

        except Exception as _e:
            st.error(f"Error leyendo Excel: {_e}")

    if df_asig is None or not hour_cols:
        st.info("Sube el Excel de asignación para continuar.")
        st.stop()

    # ── Selector de Clave ─────────────────────────────────────────────────────
    clave_col = next((c for c in df_asig.columns if c.lower() == "clave"), None)
    tipo_col  = next((c for c in df_asig.columns if c.lower() == "tipo"),  None)

    if clave_col is None:
        st.error("No se encontró columna 'Clave' en el Excel.")
        st.stop()

    claves = df_asig[clave_col].dropna().astype(str).tolist()
    sel_clave = st.selectbox("Clave / Nodo de interconexión", claves)
    row_sel = df_asig[df_asig[clave_col].astype(str) == sel_clave].iloc[0]
    tipo    = str(row_sel[tipo_col]).strip().upper() if tipo_col else "EXP"
    costo_mw = costo_impo if tipo == "IMP" else costo_expo

    # ── Tabla de MW asignados por hora ────────────────────────────────────────
    mw_by_he_mx = {}   # {he_mexico (1-24): mw}
    for hc in hour_cols:
        he_mx = he_from_col.get(hc)
        if he_mx is None:
            continue
        mw = float(row_sel[hc])
        if mw != 0:
            mw_by_he_mx[he_mx] = mw

    if not mw_by_he_mx:
        st.warning(f"La clave {sel_clave} no tiene horas con MW asignados (todo cero).")
        st.stop()

    # Ajuste de zona horaria: Texas HE = México HE + offset
    mw_by_he_tx = {}
    for he_mx, mw in mw_by_he_mx.items():
        he_tx = he_mx + tz_offset
        if 1 <= he_tx <= 24:
            mw_by_he_tx[he_tx] = mw

    # ── Dropdown solo con horas asignadas (Texas HE) ──────────────────────────
    hora_opts = {f"HE {he_tx}  ({'MX ' + str(he_tx - tz_offset)})  —  {mw:.0f} MW  [{tipo}]": he_tx
                 for he_tx, mw in sorted(mw_by_he_tx.items())}
    sel_hora_lbl = st.selectbox("Hora asignada (ERCOT HE)", list(hora_opts.keys()))
    he_tx_sel    = hora_opts[sel_hora_lbl]
    mw_sel       = mw_by_he_tx[he_tx_sel]

    # ── Tabla resumen de asignación ───────────────────────────────────────────
    with st.expander("Ver tabla completa de MW asignados", expanded=False):
        tbl_rows = []
        for he_mx, mw in sorted(mw_by_he_mx.items()):
            he_tx = he_mx + tz_offset
            tbl_rows.append({"HE México": he_mx, "HE Texas (ERCOT)": he_tx if 1 <= he_tx <= 24 else "—",
                              "MW": mw, "Tipo": tipo})
        st.dataframe(pd.DataFrame(tbl_rows), use_container_width=True, hide_index=True)

    # ══ SECCIÓN 3: Precios MDA CENACE ═════════════════════════════════════════
    st.markdown("### Precio MDA CENACE")
    # MDA publica los precios del día siguiente; default = mañana
    tmrw_mc  = today_dt + timedelta(days=1)
    fecha_mda = st.date_input("Fecha MDA", value=tmrw_mc)
    he_mx_sel = he_tx_sel - tz_offset   # hora en tiempo México para buscar en CENACE

    @st.cache_data(ttl=600, show_spinner=False)
    def _fetch_cenace_mda(nodo, sistema, fecha_s):
        return get_pml_cenace(fecha_s, fecha_s, nodo, sistema=sistema, mercado="MDA")

    with st.spinner(f"Descargando MDA CENACE {nodo_cenace}…"):
        df_mda = _fetch_cenace_mda(nodo_cenace, sistema_cenace, fecha_mda.strftime("%Y-%m-%d"))

    # Si no hay datos, verificar si es porque aún no se ha publicado
    mda_no_publicado = df_mda is None or df_mda.empty
    if mda_no_publicado and fecha_mda >= today_dt:
        st.warning(f"MDA CENACE para {fecha_mda.strftime('%d/%m/%Y')} aún no publicado "
                   f"({nodo_cenace} · {sistema_cenace}). Puedes ingresar el precio manualmente.")

    pml_hora = None
    if not mda_no_publicado:
        # Filtrar la hora seleccionada (CENACE usa hora México)
        hora_match = df_mda[df_mda["fecha"].dt.hour + 1 == he_mx_sel]
        if not hora_match.empty:
            pml_hora = float(hora_match["pml"].iloc[0])

    # Mostrar tabla MDA completa + resaltar hora seleccionada
    if not mda_no_publicado:
        df_mda_show = df_mda.copy()
        df_mda_show["HE"] = df_mda_show["fecha"].dt.hour + 1
        df_mda_show["PML (MXN)"] = df_mda_show["pml"].round(2)
        df_mda_show["PML (USD)"] = (df_mda_show["pml"] / tc_mc).round(4)
        # Break-even: IMP = PML/TC - costo, EXP = PML/TC + costo
        if tipo == "IMP":
            df_mda_show["Break Even"] = (df_mda_show["pml"] / tc_mc - costo_impo).round(4)
        else:
            df_mda_show["Break Even"] = (df_mda_show["pml"] / tc_mc + costo_expo).round(4)

        hdrs_mda = ["HE", "PML (MXN)", "PML (USD)", "Break Even (USD)"]
        hdr_mda_html = "".join(
            f'<th style="background:#12151f;color:#00d4e8;padding:6px 14px;'
            f'text-transform:uppercase;letter-spacing:1px;font-size:0.72rem;'
            f'border-bottom:2px solid #00d4e8;">{h}</th>'
            for h in hdrs_mda
        )
        rows_mda_html = ""
        for _, r in df_mda_show.sort_values("HE").iterrows():
            is_sel = int(r["HE"]) == he_mx_sel
            bg     = "#2d3350" if is_sel else ("#1e2130" if int(r["HE"]) % 2 == 0 else "#12151f")
            border = "2px solid #B7D433" if is_sel else "1px solid #2d3350"
            be     = r["Break Even"]
            be_c   = "#B7D433" if be > 0 else "#FF6B35"
            rows_mda_html += (
                f'<tr>'
                f'<td style="background:{bg};color:#00d4e8;font-weight:700;'
                f'padding:5px 14px;border-bottom:{border};font-family:Consolas,monospace;">{int(r["HE"])}</td>'
                f'<td style="background:{bg};color:#B7D433;font-weight:600;'
                f'padding:5px 14px;border-bottom:{border};font-family:Consolas,monospace;">${r["PML (MXN)"]:.2f}</td>'
                f'<td style="background:{bg};color:#c0c4cc;font-weight:600;'
                f'padding:5px 14px;border-bottom:{border};font-family:Consolas,monospace;">${r["PML (USD)"]:.4f}</td>'
                f'<td style="background:{bg};color:{be_c};font-weight:700;'
                f'padding:5px 14px;border-bottom:{border};font-family:Consolas,monospace;">${be:.4f}</td>'
                f'</tr>'
            )
        st.markdown(
            f'<div style="overflow-y:auto;max-height:300px;border:1px solid #2d3350;border-radius:6px;">'
            f'<table style="width:100%;border-collapse:collapse;">'
            f'<thead><tr>{hdr_mda_html}</tr></thead>'
            f'<tbody>{rows_mda_html}</tbody></table></div>',
            unsafe_allow_html=True,
        )
    elif nodo_cenace:
        pml_input = st.number_input("PML no disponible — ingresa manualmente (MXN/MWh)",
                                     value=700.0, format="%.2f")
        pml_hora = pml_input

    # ══ SECCIÓN 4: Monte Carlo ════════════════════════════════════════════════
    st.markdown("### Simulación Monte Carlo")

    if pml_hora is None:
        st.info("Sin precio MDA para la hora seleccionada. Ingresa el precio manualmente arriba.")
        st.stop()

    # Datos históricos ERCOT RT — carga independiente con lookback propio
    @st.cache_data(ttl=1800, show_spinner=False)
    def _load_ercot_mc(days: int):
        return load_ercot(days)

    df_mc_raw, _ = _load_ercot_mc(lookback_days)
    _bd_key = nodo_ercot_mc.upper().replace("_", "").replace("-", "")
    rt_col  = f"RT_{_bd_key}" if f"RT_{_bd_key}" in df_mc_raw.columns else "RT_DCL"
    df_mc = df_mc_raw.copy()
    df_mc["hora"] = df_mc["fecha"].dt.hour + 1
    precios_hist = [round(p) for p in df_mc[df_mc["hora"] == he_tx_sel][rt_col].dropna().tolist()]

    if len(precios_hist) < 10:
        st.warning(f"Pocos datos históricos para HE{he_tx_sel} en los últimos {lookback_days} días. Amplía el lookback.")
        st.stop()

    # Break-even ERCOT RT
    pml_usd = pml_hora / tc_mc
    if tipo == "IMP":
        # IMP: vendo a México al PML, compro en ERCOT al RT → profit si RT < PML/TC − costo
        precio_be  = pml_usd - costo_mw
        label_be   = f"BE (IMP): PML/TC − Costo = ${precio_be:.2f}"
        profits_fn = lambda sim: precio_be - sim
    else:
        # EXP: compro en México al PML, vendo en ERCOT al RT → profit si RT > PML/TC + costo
        precio_be  = pml_usd + costo_mw
        label_be   = f"BE (EXP): PML/TC + Costo = ${precio_be:.2f}"
        profits_fn = lambda sim: sim - precio_be

    n_sim   = 10_000
    sim     = np.random.choice(precios_hist, size=n_sim, replace=True).astype(float)
    sim    += np.random.normal(0, np.std(precios_hist) * 0.1, n_sim)
    profits = profits_fn(sim)

    prob_p  = float((profits > 0).mean() * 100)
    exp_p   = float(np.mean(profits))
    var_5   = float(np.percentile(profits, 5))
    es_5    = float(np.mean(profits[profits <= var_5]))   # Expected Shortfall (CVaR 5%)
    exp_pnl_total = exp_p * mw_sel

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Prob. de profit",                  f"{prob_p:.1f}%")
    m2.metric("P&L esp. (USD/MWh)",               f"${exp_p:.2f}")
    m3.metric(f"P&L esp. total ({mw_sel:.0f} MW)", f"${exp_pnl_total:.0f}")
    m4.metric("VaR 5% (USD/MWh)",                 f"${var_5:.2f}")
    m5.metric(f"ES 5% total ({mw_sel:.0f} MW)",    f"${es_5 * mw_sel:.0f}")

    # ── Fila 2: P&L usando DA como proxy del RT ───────────────────────────────
    _da_d0 = fecha_mda.strftime("%Y-%m-%d")
    _da_d1 = (fecha_mda + timedelta(days=1)).strftime("%Y-%m-%d")
    with st.spinner(f"Cargando DA ERCOT {nodo_ercot_mc}…"):
        try:
            df_da_mc = live_da_price(_da_d0, _da_d1, nodo_ercot_mc.upper().replace(" ", "_"))
        except Exception:
            df_da_mc = None

    da_price_he = None
    if df_da_mc is not None and not df_da_mc.empty:
        da_match = df_da_mc[df_da_mc["fecha"].dt.date == fecha_mda]
        da_match = da_match[da_match["fecha"].dt.hour + 1 == he_tx_sel]
        if not da_match.empty:
            da_price_he = float(da_match["price"].iloc[0])

    if da_price_he is not None:
        # P&L usando DA como proxy: IMP = BE - DA,  EXP = DA - BE
        da_pnl_mwh   = (precio_be - da_price_he) if tipo == "IMP" else (da_price_he - precio_be)
        da_pnl_total = da_pnl_mwh * mw_sel

        st.markdown("<br>", unsafe_allow_html=True)
        d1c, d2c, d3c, d4c, _ = st.columns(5)
        d1c.metric(f"DA HE{he_tx_sel}  {nodo_ercot_mc}",  f"${da_price_he:.2f}")
        d2c.metric("Break Even (USD/MWh)",                 f"${precio_be:.2f}")
        d3c.metric("P&L DA (USD/MWh)",                     f"${da_pnl_mwh:.2f}")
        d4c.metric(f"P&L DA total ({mw_sel:.0f} MW)",      f"${da_pnl_total:.0f}")
    else:
        st.caption(f"DA ERCOT HE{he_tx_sel} no disponible aún para {fecha_mda.strftime('%d/%m')}.")

    st.caption(f"{tipo} · {label_be}  |  Nodo ERCOT: {rt_col}  |  Lookback: {lookback_days} días  |  {len(precios_hist)} obs")

    # ── Histograma de simulación ──────────────────────────────────────────────
    fig_mc = go.Figure()
    fig_mc.add_trace(go.Histogram(x=sim, nbinsx=60, name="RT Simulado",
                                  marker_color=C_HOY, opacity=0.7))
    fig_mc.add_trace(go.Histogram(x=precios_hist, nbinsx=60, name="RT Histórico",
                                  marker_color="#fbbf24", opacity=0.45))
    fig_mc.add_vline(x=precio_be, line_dash="dash", line_color="#ff6b6b",
                     annotation_text=label_be, annotation_position="top right",
                     annotation_font_color="#ff6b6b")
    fig_mc.update_layout(**_plotly_base(400, f"Distribución RT ERCOT — HE{he_tx_sel}  ({tipo} {sel_clave})"),
                         barmode="overlay", xaxis_title="$/MWh", yaxis_title="Frecuencia")
    st.plotly_chart(fig_mc, use_container_width=True)

    # ── Probabilidad de profit por hora asignada ──────────────────────────────
    if len(mw_by_he_tx) > 1:
        st.markdown("### Probabilidad de profit — todas las horas asignadas")
        prob_horas = []
        for he_tx, mw in sorted(mw_by_he_tx.items()):
            ph = df_mc[df_mc["hora"] == he_tx][rt_col].dropna()
            if len(ph) < 5:
                prob_horas.append({"HE TX": he_tx, "MW": mw, "Prob (%)": 0.0, "P&L esp (USD/MWh)": 0.0})
                continue
            sh = np.random.choice(ph.tolist(), size=3000, replace=True)
            sh += np.random.normal(0, ph.std() * 0.1, 3000)
            pf = profits_fn(sh)
            prob_horas.append({
                "HE TX": he_tx, "MW": mw,
                "Prob (%)": round(float((pf > 0).mean() * 100), 1),
                "P&L esp (USD/MWh)": round(float(np.mean(pf)), 2),
            })
        df_ph = pd.DataFrame(prob_horas)
        fig_ph = go.Figure(go.Bar(
            x=df_ph["HE TX"], y=df_ph["Prob (%)"],
            marker_color=["#00d4e8" if v >= 50 else "#ff6b6b" for v in df_ph["Prob (%)"]],
            text=[f"{v:.0f}%" for v in df_ph["Prob (%)"]],
            textposition="outside",
        ))
        fig_ph.add_hline(y=50, line_dash="dash", line_color="white", opacity=0.4)
        fig_ph.update_layout(**_plotly_base(320, "Prob. profit por hora asignada"),
                             xaxis_title="HE Texas", yaxis_title="%")
        st.plotly_chart(fig_ph, use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════
# PAGE 7: Monte Carlo Hubs  (in development)
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Monte Carlo Hubs":
    st.title("Monte Carlo Hubs")
    st.markdown("""
    <div style="display:flex;align-items:center;gap:14px;margin-top:40px;">
        <div style="font-size:2.5rem;">🚧</div>
        <div>
            <div style="color:#00d4e8;font-size:1.1rem;font-weight:700;letter-spacing:1px;">
                IN DEVELOPMENT
            </div>
            <div style="color:#5a6280;font-size:0.88rem;margin-top:4px;">
                Simulación Monte Carlo para hubs en ERCOT (HB_NORTH, HB_HOUSTON, HB_WEST…).
                Próximamente.
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# PAGE: Spread México — ERCOT vs CENACE (USD/MWh)
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Spread México":
    st.title("Spread México — ERCOT vs CENACE (USD/MWh)")

    _NODO_MAP_E = {
        "DC_L ↔ LAA  (06LAA-138)": {"ercot": "DC_L", "cenace": "06LAA-138", "sistema": "SIN"},
        "DC_R ↔ RRD  (06RRD-138)": {"ercot": "DC_R", "cenace": "06RRD-138", "sistema": "SIN"},
    }
    col_nodo_e, col_dias_e = st.columns([3, 1])
    with col_nodo_e:
        sel_pair_e = st.selectbox("Nodo frontera", list(_NODO_MAP_E.keys()))
    with col_dias_e:
        dias_spr_e = st.slider("Días histórico", 1, 90, 30, key="spr_dias_e")
    pair_e = _NODO_MAP_E[sel_pair_e]

    _CENACE_API = "https://ws01.cenace.gob.mx:8082/SWPML/SIM"

    @st.cache_data(ttl=900, show_spinner=False)
    def _cenace_vec(nodo: str, sistema: str, d: "date") -> list:
        url = (f"{_CENACE_API}/{sistema}/MDA/{nodo}/"
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

    HRS = [f"{h:02d}:00" for h in range(24)]
    now_h_e = datetime.now().hour

    try:
        from app.morning.data_loader import load_tipo_cambio as _load_tc
        tc, _ = _load_tc()
    except Exception:
        tc = 17.50

    with st.spinner("Cargando CENACE..."):
        cen_hoy  = _cenace_vec(pair_e["cenace"], pair_e["sistema"], today_dt)
        cen_ayer = _cenace_vec(pair_e["cenace"], pair_e["sistema"], yday_dt)

    d0_e = today_dt.strftime("%Y-%m-%d")
    d1_e = (today_dt + timedelta(days=1)).strftime("%Y-%m-%d")

    # DA: API pública ERCOT np4-190-cd (ties DC sí están publicados)
    with st.spinner(f"Cargando DA ERCOT {pair_e['ercot']}..."):
        try:
            df_da_e = live_da_price(d0_e, d1_e, pair_e["ercot"])
        except Exception:
            df_da_e = None

    def _pvec_da(df, day):
        if df is None or df.empty:
            return [None] * 24
        sub = df[df["fecha"].dt.date == day].sort_values("fecha")
        return (sub["price"].tolist() + [None] * 24)[:24]

    da_hoy_e = _pvec_da(df_da_e, today_dt)

    # RT real: mismo módulo que el ETL usa (np6-905-cd con auth OAuth)
    @st.cache_data(ttl=300, show_spinner=False)
    def _live_rt_etl(node: str, d0: str, d1: str):
        try:
            from etl.ercot.ercot_api import get_rt_prices, get_token as _get_tok
            tok = _get_tok()
            df  = get_rt_prices(tok, d0, d1, node)
            if df is None or df.empty:
                return None
            return df.rename(columns={"precio_hora": "price"})
        except Exception:
            return None

    with st.spinner(f"Cargando RT ERCOT {pair_e['ercot']}..."):
        df_rt_etl = _live_rt_etl(pair_e["ercot"], d0_e, d1_e)

    rt_hoy_e = _pvec_da(df_rt_etl, today_dt)

    # RT Forecast: df_hist (BD) — columna RT_DCL_FCST / RT_DCR_FCST
    _sfx_e         = pair_e["ercot"].replace("_", "")   # "DC_L" → "DCL"
    _rt_fcst_col_e = f"RT_{_sfx_e}_FCST"

    def _hist_vec_e(col, d):
        if col not in df_hist.columns:
            return [None] * 24
        sub = df_hist[df_hist["fecha"].dt.date == d].sort_values("fecha")
        if sub.empty:
            return [None] * 24
        vals = [None] * 24
        for _, row in sub.iterrows():
            h = row["fecha"].hour
            if 0 <= h < 24:
                v = row[col]
                vals[h] = float(v) if pd.notna(v) else None
        return vals

    # RT Forecast: MarginalUnit synthetic P50 (misma fuente que DA/RT Prices page)
    # Fallback a df_hist si MU falla
    with st.spinner("Cargando RT synthetic…"):
        rt_fcst_hoy_e = mu_syn_p50("lmp_rt", pair_e["ercot"], today_dt, AUTH)
    if not any(v is not None for v in rt_fcst_hoy_e):
        rt_fcst_hoy_e = _hist_vec_e(_rt_fcst_col_e, today_dt)

    cen_usd_hoy  = [v / tc if v is not None else None for v in cen_hoy]
    cen_usd_ayer = [v / tc if v is not None else None for v in cen_ayer]

    def _avg_e(vals):
        v = [x for x in vals if x is not None]
        return sum(v) / len(v) if v else None

    avg_da_e   = _avg_e(da_hoy_e)
    avg_rt_e   = _avg_e(rt_hoy_e)
    avg_cen_mx = _avg_e(cen_hoy)
    avg_cen_us = avg_cen_mx / tc if avg_cen_mx else None
    last_da_e  = next((da_hoy_e[h]  for h in range(min(now_h_e, 23), -1, -1) if da_hoy_e[h]  is not None), None)
    last_rt_e  = next((rt_hoy_e[h]  for h in range(min(now_h_e, 23), -1, -1) if rt_hoy_e[h]  is not None), None)
    last_cen_e = next((cen_usd_hoy[h] for h in range(min(now_h_e, 23), -1, -1) if cen_usd_hoy[h] is not None), None)
    spr_now_e  = last_rt_e - last_cen_e if last_rt_e is not None and last_cen_e is not None else None

    COL_US_E  = "#f59e0b"
    COL_MX_E  = "#34d399"
    COL_SPR_E = "#a78bfa"

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.markdown(_kpi_spread("DA ERCOT Prom",    avg_da_e,   None, color=COL_US_E), unsafe_allow_html=True)
    k2.markdown(_kpi_spread("RT ERCOT Prom",    avg_rt_e,   None, color=C_RT),     unsafe_allow_html=True)
    k3.markdown(_kpi_spread("PML CENACE (MXN)", avg_cen_mx, None, fmt="${:.2f}", color=COL_MX_E),  unsafe_allow_html=True)
    k4.markdown(_kpi_spread("PML CENACE (USD)", avg_cen_us, None, fmt="${:.3f}", color=COL_MX_E),  unsafe_allow_html=True)
    k5.markdown(_kpi_spread("Spread RT–CENACE", spr_now_e,  None, color=COL_SPR_E), unsafe_allow_html=True)

    st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)

    # ── Gráficas lado a lado: ERCOT | CENACE ────────────────────────────────
    col_a, col_b = st.columns(2)
    with col_a:
        # Última hora con RT real publicado
        last_rt_idx = max((i for i in range(24) if rt_hoy_e[i] is not None), default=-1)

        # RT sólido = horas con dato real; punteado = forecast para horas sin dato real
        rt_solid = [rt_hoy_e[i] for i in range(24)]   # None donde no hay real
        # Forecast: usar RT_FCST para horas sin RT real; incluir punto de unión
        rt_dash = [None] * 24
        for i in range(24):
            if rt_hoy_e[i] is None and rt_fcst_hoy_e[i] is not None:
                rt_dash[i] = rt_fcst_hoy_e[i]
        if last_rt_idx >= 0 and last_rt_idx < 23:
            rt_dash[last_rt_idx] = rt_hoy_e[last_rt_idx]  # punto de unión sin gap

        fig_a = go.Figure()
        fig_a.add_trace(go.Scatter(x=HRS, y=da_hoy_e, name="DA Hoy",
            line=dict(color=COL_US_E, width=2.5), connectgaps=False))
        fig_a.add_trace(go.Scatter(x=HRS, y=rt_solid, name="RT Hoy (real)",
            line=dict(color=C_RT, width=2.5), connectgaps=False))
        fig_a.add_trace(go.Scatter(x=HRS, y=rt_dash, name="RT Forecast",
            line=dict(color=C_RT, width=1.8, dash="dot"), connectgaps=False))
        if 0 < last_rt_idx < 23:
            fig_a.add_vline(x=HRS[last_rt_idx], line_dash="dot", line_color="#5a6280", line_width=1)
        fig_a.update_layout(**_plotly_base(340, f"ERCOT {pair_e['ercot']}  (USD/MWh)"),
                            yaxis_title="USD/MWh")
        st.plotly_chart(fig_a, use_container_width=True, config={"displayModeBar": False})

    with col_b:
        # CENACE MDA: precio de día en adelanto, 24 horas completas desde publicación
        fig_b = go.Figure()
        fig_b.add_trace(go.Scatter(x=HRS, y=cen_hoy, name="PML MDA Hoy",
            line=dict(color=COL_MX_E, width=2.5), connectgaps=False))
        fig_b.update_layout(**_plotly_base(340, f"CENACE {pair_e['cenace']} PML MDA  (MXN/MWh)"),
                            yaxis_title="MXN/MWh")
        st.plotly_chart(fig_b, use_container_width=True, config={"displayModeBar": False})

    # ── Gráfica combinada mismo eje USD/MWh ──────────────────────────────────
    fig_comb = go.Figure()
    fig_comb.add_trace(go.Scatter(x=HRS, y=da_hoy_e, name=f"DA {pair_e['ercot']} (USD/MWh)",
        line=dict(color=COL_US_E, width=2), connectgaps=False))
    fig_comb.add_trace(go.Scatter(x=HRS, y=rt_solid, name=f"RT {pair_e['ercot']} (USD/MWh)",
        line=dict(color=C_RT, width=2.5), connectgaps=False))
    fig_comb.add_trace(go.Scatter(x=HRS, y=rt_dash, name="RT Forecast",
        line=dict(color=C_RT, width=1.8, dash="dot"), connectgaps=False, showlegend=False))
    fig_comb.add_trace(go.Scatter(x=HRS, y=cen_usd_hoy,
        name=f"CENACE {pair_e['cenace']} MDA (USD equiv.)",
        line=dict(color=COL_MX_E, width=2), connectgaps=False))
    if 0 < last_rt_idx < 23:
        fig_comb.add_vline(x=HRS[last_rt_idx], line_dash="dot", line_color="#5a6280", line_width=1)
    fig_comb.update_layout(**_plotly_base(320,
        f"ERCOT vs CENACE — mismo eje USD/MWh  ·  TC {tc:.4f}"), yaxis_title="USD/MWh")
    st.plotly_chart(fig_comb, use_container_width=True, config={"displayModeBar": False})

    # ── Spread horario (barras) ───────────────────────────────────────────────
    spr_hoy = [rt - c if rt is not None and c is not None else None
               for rt, c in zip(rt_hoy_e, cen_usd_hoy)]
    fig_spr = go.Figure(go.Bar(
        x=HRS, y=spr_hoy,
        marker_color=[COL_SPR_E if (v is not None and v >= 0) else "#ff6b6b" for v in spr_hoy],
        name="Spread RT–CENACE",
    ))
    fig_spr.add_hline(y=0, line_dash="dash", line_color="white", line_width=1, opacity=0.4)
    fig_spr.update_layout(**_plotly_base(260, "Spread  RT ERCOT – CENACE  (USD/MWh)"),
                          yaxis_title="USD/MWh")
    st.plotly_chart(fig_spr, use_container_width=True, config={"displayModeBar": False})

    # ── Histórico diario ─────────────────────────────────────────────────────
    df_spr_hist, spr_live, spr_err = load_spread_data(pair_e["cenace"], pair_e["ercot"], dias=dias_spr_e)
    if not df_spr_hist.empty:
        fig_sh = go.Figure()
        fig_sh.add_trace(go.Scatter(x=df_spr_hist["fecha_dia"], y=df_spr_hist["rt_usd"],
            name=f"RT {pair_e['ercot']} (USD/MWh)", line=dict(color=C_RT, width=1.8)))
        fig_sh.add_trace(go.Scatter(x=df_spr_hist["fecha_dia"], y=df_spr_hist["pml_usd"],
            name=f"CENACE {pair_e['cenace']} (USD/MWh)", line=dict(color=COL_MX_E, width=1.8)))
        fig_sh.update_layout(**_plotly_base(300, f"Histórico {dias_spr_e} días — RT vs CENACE (USD/MWh)"),
                             yaxis_title="USD/MWh")
        st.plotly_chart(fig_sh, use_container_width=True, config={"displayModeBar": False})

        fig_shspr = go.Figure(go.Scatter(
            x=df_spr_hist["fecha_dia"], y=df_spr_hist["spread"],
            name="Spread RT–CENACE", line=dict(color=COL_SPR_E, width=1.5),
            fill="tozeroy", fillcolor="rgba(167,139,250,0.07)",
        ))
        fig_shspr.add_hline(y=0, line_dash="dash", line_color="white", line_width=1, opacity=0.3)
        fig_shspr.update_layout(**_plotly_base(240, "Spread Histórico  RT–CENACE  (USD/MWh diario)"),
                                yaxis_title="USD/MWh")
        st.plotly_chart(fig_shspr, use_container_width=True, config={"displayModeBar": False})

    # ── Tabla horaria hoy ────────────────────────────────────────────────────
    st.markdown("#### Detalle horario — Hoy")
    rows_e = []
    for h in range(24):
        c_mx = cen_hoy[h]
        c_us = c_mx / tc if c_mx is not None else None
        da_v = da_hoy_e[h]
        rt_v = rt_hoy_e[h]
        spr  = rt_v - c_us if rt_v is not None and c_us is not None else None
        rows_e.append({
            "Hora":                              f"{h:02d}:00",
            f"DA {pair_e['ercot']} (USD/MWh)":   f"${da_v:.2f}"  if da_v is not None else "—",
            f"RT {pair_e['ercot']} (USD/MWh)":   f"${rt_v:.2f}"  if rt_v is not None else "—",
            f"PML {pair_e['cenace']} (MXN/MWh)": f"${c_mx:.2f}"  if c_mx is not None else "—",
            f"PML {pair_e['cenace']} (USD/MWh)":  f"${c_us:.2f}" if c_us is not None else "—",
            "Spread RT–CENACE (USD/MWh)":         f"${spr:+.2f}" if spr is not None else "—",
        })
    st.dataframe(pd.DataFrame(rows_e), use_container_width=True, hide_index=True, height=360)


# ── Footer ─────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    f"<div style='color:#2d3350; font-size:0.68rem; text-align:center;'>"
    f"XTS Energy Portal · Morning ERCOT · "
    f"{'🔴 Demo' if not live_db else '🟢 Live'} · "
    f"{datetime.now().strftime('%d/%m/%Y %H:%M:%S')}</div>",
    unsafe_allow_html=True,
)
