"""
Morning Dashboard CAISO — XTS Energy Portal
Correr con: streamlit run app/morning/caiso_morning.py
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, date, timedelta
import requests
import time
import io
import urllib3
import base64 as _b64c
import re
import zipfile

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

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
    enc = _b64c.b64encode(svg.encode('utf-8')).decode('ascii')
    return f"data:image/svg+xml;base64,{enc}"

_XTS_IMG = f'<img src="{_xts_logo_uri(44)}" alt="XTS" style="height:44px;display:block;"/>'

from app.morning.data_loader import load_caiso, load_temperaturas, load_tipo_cambio

# ── Pagina ─────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Morning CAISO — XTS",
    page_icon="☀️",
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
                password = st.text_input("Contrasena", placeholder="Password", type="password", key="inp_pass")
            with col_btn:
                st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
                submitted = st.form_submit_button("LOG IN", use_container_width=True)

        if submitted:
            if username and password:
                with st.spinner("Verificando credenciales..."):
                    try:
                        _test = requests.get(
                            "https://api-mosaic-prod.enverus.com/mosaic-api/datasets",
                            auth=(username, password),
                            params={"response_type": "csv_wide", "response_info": "base"},
                            timeout=15, verify=False,
                        )
                        if _test.status_code == 401:
                            st.error("Usuario o contrasena incorrectos.")
                        elif _test.status_code >= 400:
                            st.error(f"Error de autenticacion ({_test.status_code}).")
                        else:
                            st.session_state.auth      = (username, password)
                            st.session_state.logged_in = True
                            st.rerun()
                    except Exception as _e:
                        st.error(f"No se pudo conectar: {_e}")
            else:
                st.error("Ingresa usuario y contrasena.")

    st.markdown('<p style="text-align:center; color:#4a5070; font-size:0.72rem; margin-top:16px;">v1.0.0 · Morning CAISO</p>', unsafe_allow_html=True)
    st.stop()

# ══════════════════════════════════════════════════════════════════════════════
# CSS GLOBAL
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
    [data-testid="stDataFrame"] th     { background-color: #12151f !important; color: #5a6280 !important; text-transform: uppercase !important; }

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

    /* Selectbox de navegación en sidebar — caja cerrada */
    [data-testid="stSidebar"] [data-testid="stSelectbox"] > div > div {
        background-color: #2d3350 !important;
        border: 1px solid #3d4468 !important;
        border-radius: 4px !important;
    }
    [data-testid="stSidebar"] [data-testid="stSelectbox"] > div > div > div,
    [data-testid="stSidebar"] [data-testid="stSelectbox"] span {
        color: #00d4e8 !important;
        font-weight: 600 !important;
        font-size: 0.85rem !important;
        letter-spacing: 0.5px !important;
    }
    [data-testid="stSidebar"] [data-testid="stSelectbox"] svg {
        fill: #00d4e8 !important;
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
    .tag-usd { background:#1a3a2a; color:#34d399; padding:2px 6px; border-radius:3px; font-size:0.7rem; }
    .tag-mxn { background:#3a1a2a; color:#f87171; padding:2px 6px; border-radius:3px; font-size:0.7rem; }
</style>
""", unsafe_allow_html=True)

# ── Colores ────────────────────────────────────────────────────────────────────
PLOT_BG  = "#1e2130"
PAPER_BG = "#1e2130"
GRID_COL = "#2d3242"
FONT_COL = "#c0c4cc"
C_ROA    = "#00d4e8"
C_TJI    = "#B7D433"
C_IVY    = "#FF6B35"
C_OMS    = "#a78bfa"
C_DA     = "#00d4e8"
C_FMM    = "#FF6B35"
C_SOLAR  = "#fbbf24"
C_LOAD   = "#6FA0D8"
# 3-day chart colors (same as ERCOT)
C_AYER   = "#5a6280"
C_HOY    = "#00d4e8"
C_MANANA = "#B7D433"


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


def kpi(label, val, ref, fmt="${:.2f}", color="#00d4e8", tag=""):
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


# ── KPI helper (ERCOT-style, sin delta) ──────────────────────────────────────
def _kpi_c(label, val, ref=None, color="#00d4e8"):
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


# ── Helper: extrae vector de 24 horas de df_hist para una fecha ──────────────
def _day_vals_c(df, col, target_date):
    if df is None or df.empty or col not in df.columns:
        return [None] * 24
    sub = df[df["fecha"].dt.date == target_date].sort_values("fecha")
    if sub.empty:
        return [None] * 24
    vals = [None] * 24
    for _, row in sub.iterrows():
        h = row["fecha"].hour
        if 0 <= h < 24:
            v = row[col]
            vals[h] = float(v) if pd.notna(v) else None
    return vals


# ── Chart helpers (mismo formato que ERCOT) ───────────────────────────────────
def _three_day_chart_c(title, y_label, y0, y1, y2, yd_lbl, td_lbl, tm_lbl):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=list(range(1, 25)), y=y0, mode="lines",
                             name=f"Yesterday  {yd_lbl}", line=dict(color=C_AYER, width=2.5)))
    fig.add_trace(go.Scatter(x=list(range(1, 25)), y=y1, mode="lines",
                             name=f"Today  {td_lbl}", line=dict(color=C_HOY, width=3)))
    fig.add_trace(go.Scatter(x=list(range(1, 25)), y=y2, mode="lines",
                             name=f"Tomorrow  {tm_lbl}", line=dict(color=C_MANANA, width=2.5, dash="dash"),
                             connectgaps=False))
    fig.update_layout(**_plotly_base(380, title), xaxis_title="Hour Ending", yaxis_title=y_label)
    fig.update_xaxes(tickvals=list(range(1, 25, 2)))
    return fig


def _load_chart_c(yday_act, today_vals, tmrw_vals, yd_lbl, td_lbl, tm_lbl):
    """Load: ayer sólido, hoy sólido hasta hora actual + punteado resto, mañana punteado."""
    last_h = datetime.now().hour  # 0-23
    today_solid = [today_vals[i] if (i + 1) <= last_h else None for i in range(24)]
    today_dash  = [today_vals[i] if (i + 1) >= last_h else None for i in range(24)]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=list(range(1, 25)), y=yday_act, mode="lines",
                             name=f"Yesterday  {yd_lbl}", line=dict(color=C_AYER, width=2.5)))
    fig.add_trace(go.Scatter(x=list(range(1, 25)), y=today_solid, mode="lines",
                             name=f"Today  {td_lbl}", line=dict(color=C_HOY, width=3), connectgaps=False))
    fig.add_trace(go.Scatter(x=list(range(1, 25)), y=today_dash, mode="lines",
                             name="Today Fcst", line=dict(color=C_HOY, width=2, dash="dot"),
                             showlegend=False, connectgaps=False))
    fig.add_trace(go.Scatter(x=list(range(1, 25)), y=tmrw_vals, mode="lines",
                             name=f"Tomorrow  {tm_lbl}", line=dict(color=C_MANANA, width=2.5, dash="dash"),
                             connectgaps=False))
    fig.update_layout(**_plotly_base(380, "Load Forecast CAISO"),
                      xaxis_title="Hour Ending", yaxis_title="Load (MW)")
    fig.update_xaxes(tickvals=list(range(1, 25, 2)))
    return fig


def _solar_chart_c(yday_act, today_vals, tmrw_vals, yd_lbl, td_lbl, tm_lbl):
    last_h = datetime.now().hour
    today_solid = [today_vals[i] if (i + 1) <= last_h else None for i in range(24)]
    today_dash  = [today_vals[i] if (i + 1) >= last_h else None for i in range(24)]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=list(range(1, 25)), y=yday_act, mode="lines",
                             name=f"Yesterday  {yd_lbl}", line=dict(color=C_AYER, width=2.5)))
    fig.add_trace(go.Scatter(x=list(range(1, 25)), y=today_solid, mode="lines",
                             name=f"Today  {td_lbl}", line=dict(color=C_SOLAR, width=3), connectgaps=False))
    fig.add_trace(go.Scatter(x=list(range(1, 25)), y=today_dash, mode="lines",
                             name="Today Fcst", line=dict(color=C_SOLAR, width=2, dash="dot"),
                             showlegend=False, connectgaps=False))
    fig.add_trace(go.Scatter(x=list(range(1, 25)), y=tmrw_vals, mode="lines",
                             name=f"Tomorrow  {tm_lbl}", line=dict(color=C_MANANA, width=2.5, dash="dash"),
                             connectgaps=False))
    fig.update_layout(**_plotly_base(380, "Solar Generation CAISO"),
                      xaxis_title="Hour Ending", yaxis_title="Solar (MW)")
    fig.update_xaxes(tickvals=list(range(1, 25, 2)))
    return fig


def _wind_chart_c(yday_act, today_vals, tmrw_vals, yd_lbl, td_lbl, tm_lbl):
    last_h = datetime.now().hour
    today_solid = [today_vals[i] if (i + 1) <= last_h else None for i in range(24)]
    today_dash  = [today_vals[i] if (i + 1) >= last_h else None for i in range(24)]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=list(range(1, 25)), y=yday_act, mode="lines",
                             name=f"Yesterday  {yd_lbl}", line=dict(color=C_AYER, width=2.5)))
    fig.add_trace(go.Scatter(x=list(range(1, 25)), y=today_solid, mode="lines",
                             name=f"Today  {td_lbl}", line=dict(color=C_LOAD, width=3), connectgaps=False))
    fig.add_trace(go.Scatter(x=list(range(1, 25)), y=today_dash, mode="lines",
                             name="Today Fcst", line=dict(color=C_LOAD, width=2, dash="dot"),
                             showlegend=False, connectgaps=False))
    fig.add_trace(go.Scatter(x=list(range(1, 25)), y=tmrw_vals, mode="lines",
                             name=f"Tomorrow  {tm_lbl}", line=dict(color=C_MANANA, width=2.5, dash="dash"),
                             connectgaps=False))
    fig.update_layout(**_plotly_base(380, "Wind Generation CAISO"),
                      xaxis_title="Hour Ending", yaxis_title="Wind (MW)")
    fig.update_xaxes(tickvals=list(range(1, 25, 2)))
    return fig


# ── CAISO OASIS — fetch live Load / Solar / Wind para un dia ─────────────────
# Funcion completamente autonoma: no importa de caiso_api.py para evitar
# problemas de cache de modulos de Python en Streamlit.
@st.cache_data(ttl=900, show_spinner=False)
def _fetch_caiso_live_day(date_str: str) -> dict:
    """
    Descarga Load, Solar y Wind desde CAISO OASIS (SLD_FCST + SLD_REN_FCST CSV).
    Retorna {'load': list[24], 'solar': list[24], 'wind': list[24]}.
    Levanta RuntimeError si no hay datos (para no cachear vacios).
    """
    import urllib3 as _u3
    _u3.disable_warnings()

    OASIS = "https://oasis.caiso.com/oasisapi/SingleZip"
    d0 = date_str
    d1 = (date.fromisoformat(date_str) + timedelta(days=1)).strftime("%Y-%m-%d")
    # T07:00-0000 = medianoche PPT en verano (PDT = UTC-7)
    sdt = f"{d0.replace('-','')}T07:00-0000"
    edt = f"{d1.replace('-','')}T07:00-0000"

    def _get_csv(qname, **kw):
        p = {"queryname": qname, "startdatetime": sdt, "enddatetime": edt,
             "version": "1", "market_run_id": "DAM", "resultformat": 6}
        p.update(kw)
        for attempt in range(3):
            r = requests.get(OASIS, params=p, timeout=60, verify=False)
            if r.status_code == 429:
                time.sleep(15 * (attempt + 1))
                continue
            r.raise_for_status()
            break
        with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
            fn = next((n for n in zf.namelist() if n.endswith(".csv")), None)
            if not fn:
                return pd.DataFrame()
            df = pd.read_csv(zf.open(fn))
            df.columns = [c.strip().upper() for c in df.columns]
            return df

    def _to_vec(df, ren_type=None, mw_opts=None, tac_area=None, label_filter=None, agg="mean"):
        if df is None or df.empty:
            return [None] * 24
        d = df.copy()
        # Filtrar por tipo renovable (SOLAR/WIND)
        if ren_type:
            tc = next((c for c in ["RENEWABLE_TYPE", "FUEL_TYPE"] if c in d.columns), None)
            if tc:
                d = d[d[tc].str.upper().str.contains(ren_type, na=False)]
            if d.empty:
                return [None] * 24
        # Filtrar por TAC area (ej. "CA ISO-TAC" para total sistema)
        if tac_area:
            tc2 = next((c for c in ["TAC_AREA_NAME", "TAC_AREA", "ZONE_NAME"] if c in d.columns), None)
            if tc2:
                d = d[d[tc2].str.upper().str.contains(tac_area.upper(), na=False)]
        # Filtrar por LABEL (ej. "SYS_FCST_MW" para carga total)
        if label_filter:
            lc = next((c for c in ["LABEL", "DATA_ITEM"] if c in d.columns), None)
            if lc:
                d = d[d[lc].str.upper().str.contains(label_filter.upper(), na=False)]
        if d.empty:
            return [None] * 24
        hr = next((c for c in ["OPR_HR", "HE", "HOUR_ID"] if c in d.columns), None)
        mw = next((c for c in (mw_opts or ["MW", "LOAD_MW", "VALUE"]) if c in d.columns), None)
        if hr is None or mw is None:
            return [None] * 24
        d = d.copy()
        d["_h"]  = pd.to_numeric(d[hr], errors="coerce").sub(1).astype("Int64")
        d["_mw"] = pd.to_numeric(d[mw], errors="coerce")
        d = d[(d["_h"] >= 0) & (d["_h"] < 24) & d["_mw"].notna()]
        if d.empty:
            return [None] * 24
        fn  = d.groupby("_h")["_mw"].sum if agg == "sum" else d.groupby("_h")["_mw"].mean
        agg_s = fn()
        return [float(agg_s[h]) if h in agg_s.index else None for h in range(24)]

    errors = []
    load_vec  = [None] * 24
    solar_vec = [None] * 24
    wind_vec  = [None] * 24

    try:
        df_load  = _get_csv("SLD_FCST")
        # Filtrar al area total CA ISO-TAC y label SYS_FCST para evitar sub-areas/otros labels
        load_vec = _to_vec(df_load, mw_opts=["MW", "LOAD_MW", "TOTAL"],
                           tac_area="CA ISO-TAC", label_filter="SYS_FCST", agg="mean")
        # Si CA ISO-TAC no existe en este CSV, reintentar sin filtros de area
        if not any(v for v in load_vec if v):
            load_vec = _to_vec(df_load, mw_opts=["MW", "LOAD_MW", "TOTAL"], agg="mean")
    except Exception as _e:
        errors.append(f"Load: {_e}")
    try:
        df_ren    = _get_csv("SLD_REN_FCST")
        solar_vec = _to_vec(df_ren, ren_type="SOLAR", mw_opts=["RENEWABLE_FORECAST_MW", "MW", "LOAD_MW"], agg="sum")
        wind_vec  = _to_vec(df_ren, ren_type="WIND",  mw_opts=["RENEWABLE_FORECAST_MW", "MW", "LOAD_MW"], agg="sum")
    except Exception as _e:
        errors.append(f"Renewables: {_e}")

    if not any(v for v in load_vec if v):
        raise RuntimeError("CAISO sin datos" + (f": {'; '.join(errors)}" if errors else ""))

    return {"load": load_vec, "solar": solar_vec, "wind": wind_vec}


# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="text-align:center; padding:14px 0 4px 0;">
        <svg width="185" height="62" viewBox="0 0 185 62" xmlns="http://www.w3.org/2000/svg" style="display:block;margin:0 auto;">
          <defs>
            <radialGradient id="sky-cg" cx="45%" cy="35%" r="60%">
              <stop offset="0%" stop-color="#c8d8e8"/>
              <stop offset="100%" stop-color="#5888b0"/>
            </radialGradient>
            <radialGradient id="land-cg" cx="50%" cy="80%" r="60%">
              <stop offset="0%" stop-color="#90c040"/>
              <stop offset="100%" stop-color="#4a8020"/>
            </radialGradient>
            <clipPath id="globe-cg">
              <circle cx="30" cy="31" r="27"/>
            </clipPath>
          </defs>
          <!-- Sky background -->
          <circle cx="30" cy="31" r="27" fill="url(#sky-cg)"/>
          <!-- Sun dot -->
          <circle cx="30" cy="13" r="3.5" fill="white" clip-path="url(#globe-cg)"/>
          <!-- Sun rays -->
          <g clip-path="url(#globe-cg)" stroke="white" stroke-width="1.8" stroke-linecap="round">
            <line x1="30" y1="7" x2="30" y2="4"/>
            <line x1="36" y1="9" x2="39" y2="6"/>
            <line x1="40" y1="14" x2="43" y2="13"/>
            <line x1="24" y1="9" x2="21" y2="6"/>
            <line x1="20" y1="14" x2="17" y2="13"/>
            <line x1="38" y1="19" x2="41" y2="19"/>
            <line x1="22" y1="19" x2="19" y2="19"/>
          </g>
          <!-- Orange wave band -->
          <path d="M 3,35 Q 16,26 30,33 Q 44,40 57,33" fill="none" stroke="#e07828" stroke-width="9" clip-path="url(#globe-cg)" stroke-linecap="round"/>
          <!-- Green land -->
          <rect x="3" y="43" width="54" height="20" fill="url(#land-cg)" clip-path="url(#globe-cg)"/>
          <!-- Globe border -->
          <circle cx="30" cy="31" r="27" fill="none" stroke="#88a0b8" stroke-width="1.5"/>
          <!-- CAISO text -->
          <text x="66" y="43" font-family="'Segoe UI','Helvetica','Arial',sans-serif"
                font-weight="700" font-size="32" fill="#5a6878" letter-spacing="2">CAISO</text>
        </svg>
    </div>
    """, unsafe_allow_html=True)
    st.divider()

    page = st.selectbox(
        "Página",
        ["Load & Solar", "DA / FMM Prices",
         "Spread México", "Monte Carlo IMP/EXP", "Temperaturas"],
        label_visibility="collapsed",
    )

    st.divider()

    if st.button("Cerrar Sesion", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.auth      = None
        st.rerun()

    st.markdown(
        f"<div style='color:#2d3350; font-size:0.65rem; margin-top:8px; text-align:center;'>"
        f"{datetime.now().strftime('%d/%m/%Y %H:%M')}</div>",
        unsafe_allow_html=True,
    )

# ── Datos BD ──────────────────────────────────────────────────────────────────
df_hist, live_db = load_caiso(90)
df_temps, _      = load_temperaturas(3)
tc, live_tc      = load_tipo_cambio()

if not live_db:
    st.markdown(
        '<div class="demo-banner">⚠️ <b>Modo demo</b> — Sin conexion a BD. Datos son sinteticos.</div>',
        unsafe_allow_html=True,
    )

# Fechas y rangos
today_dt = date.today()
yday_dt  = today_dt - timedelta(days=1)
tmrw_dt  = today_dt + timedelta(days=1)
yday_s   = yday_dt.strftime("%b %d")
tday_s   = today_dt.strftime("%b %d")
tmrw_s   = tmrw_dt.strftime("%b %d")
hours_c  = list(range(1, 25))


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 1: DA / FMM Precios (CAISO USD/MWh)
# ══════════════════════════════════════════════════════════════════════════════
if page == "DA / FMM Prices":
    tday_str = today_dt.strftime("%A %B %d, %Y")
    st.title(f"DA / FMM Prices  —  {tday_str}")

    # ── Selectores ────────────────────────────────────────────────────────────
    cs1, cs2 = st.columns([2, 1])
    with cs1:
        sel_nodo_da = st.selectbox("Nodo", ["ROA — Rosarito", "TJI — Tijuana"], key="caiso_da_nodo")
    with cs2:
        _date_opts_da = {
            f"Yesterday  ({yday_s})": yday_dt,
            f"Today  ({tday_s})":     today_dt,
            f"Tomorrow  ({tmrw_s})":  tmrw_dt,
        }
        sel_date_da_lbl = st.selectbox("Date", list(_date_opts_da.keys()), index=1, key="caiso_da_date")
        sel_date_da     = _date_opts_da[sel_date_da_lbl]
        sel_date_da_s   = sel_date_da.strftime("%b %d")

    nodo_key_da = "ROA" if "ROA" in sel_nodo_da else "TJI"
    da_col_da   = f"DA_{nodo_key_da}"
    fmm_col_da  = f"FMM_{nodo_key_da}"

    # ── Extraer vectores horarios ─────────────────────────────────────────────
    da_real   = _day_vals_c(df_hist, da_col_da,  sel_date_da)
    fmm_real  = _day_vals_c(df_hist, fmm_col_da, sel_date_da)
    # FMM no disponible para mañana (es RT)
    if sel_date_da == tmrw_dt:
        fmm_real = [None] * 24

    da_is_live  = [v is not None for v in da_real]
    fmm_is_live = [v is not None for v in fmm_real]

    dfmm_vec = [
        round(da - fmm, 4)
        if da is not None and fmm is not None else None
        for da, fmm in zip(da_real, fmm_real)
    ]

    # ── KPIs ──────────────────────────────────────────────────────────────────
    avg_da   = float(np.mean([v for v in da_real  if v is not None])) if any(v is not None for v in da_real)  else None
    avg_fmm  = float(np.mean([v for v in fmm_real if v is not None])) if any(v is not None for v in fmm_real) else None
    avg_dfmm = float(np.mean([v for v in dfmm_vec if v is not None])) if any(v is not None for v in dfmm_vec) else None

    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(_kpi_c(f"Avg DA  {nodo_key_da}  ({sel_date_da_s})",   avg_da,   None,    "#B7D433"), unsafe_allow_html=True)
    c2.markdown(_kpi_c(f"Avg FMM  {nodo_key_da}  ({sel_date_da_s})",  avg_fmm,  avg_da,  "#FF6B35"), unsafe_allow_html=True)
    c3.markdown(_kpi_c(f"Avg D-FMM  {nodo_key_da}  ({sel_date_da_s})", avg_dfmm, None,   "#a78bfa"), unsafe_allow_html=True)
    c4.markdown(
        f'<div class="kpi-card" style="border-left-color:#34d399">'
        f'<div class="kpi-label">USD/MXN</div>'
        f'<div class="kpi-value" style="color:#34d399">{tc:.4f}</div>'
        f'<span class="kpi-sub">{"live" if live_tc else "demo"}</span></div>',
        unsafe_allow_html=True,
    )

    if sel_date_da == tmrw_dt:
        st.caption("FMM (RT) not available for tomorrow  —  DA only")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Gráfica: sólido = con datos, punteado = sin datos ────────────────────
    def _split_traces_c(vec, is_live_flags, color, name_live, name_none):
        live_y = [vec[i] if is_live_flags[i]     else float("nan") for i in range(24)]
        none_y = [vec[i] if not is_live_flags[i] else float("nan") for i in range(24)]
        for i in range(24):
            if not is_live_flags[i] and i > 0 and is_live_flags[i-1] and vec[i-1] is not None:
                none_y[i-1] = vec[i-1]
            if is_live_flags[i] and i > 0 and not is_live_flags[i-1] and vec[i-1] is not None:
                live_y[i-1] = vec[i-1]
        return [
            go.Scatter(x=hours_c, y=live_y, name=name_live,
                       mode="lines", line=dict(color=color, width=2.5), connectgaps=False),
            go.Scatter(x=hours_c, y=none_y, name=name_none,
                       mode="lines", line=dict(color=color, width=2.5, dash="dot"),
                       connectgaps=False, showlegend=any(v is not None and not np.isnan(v) for v in none_y)),
        ]

    fig_da = go.Figure()
    for tr in _split_traces_c(da_real,  da_is_live,  "#B7D433",
                               f"DA {nodo_key_da}", f"DA {nodo_key_da} (no data)"):
        fig_da.add_trace(tr)
    for tr in _split_traces_c(fmm_real, fmm_is_live, "#FF6B35",
                               f"FMM {nodo_key_da}", f"FMM {nodo_key_da} (no data)"):
        fig_da.add_trace(tr)
    fig_da.update_layout(**_plotly_base(420, f"DA & FMM Prices — {nodo_key_da}  ·  {sel_date_da_s}  $/MWh"),
                         yaxis_title="$/MWh", xaxis_title="Hour Ending")
    fig_da.update_xaxes(tickvals=list(range(1, 25, 2)))
    st.plotly_chart(fig_da, use_container_width=True)

    # ── Top 5 / Bottom 5 D-FMM ───────────────────────────────────────────────
    dfmm_avail = [(h, v) for h, v in zip(hours_c, dfmm_vec) if v is not None]
    if dfmm_avail:
        top5_da = sorted(dfmm_avail, key=lambda x: x[1], reverse=True)[:5]
        bot5_da = sorted(dfmm_avail, key=lambda x: x[1])[:5]

        def _dfmm_mini_html(title, rows_data, color):
            hdr = "".join(
                f'<th style="background:#12151f;color:{color};padding:6px 16px;'
                f'text-transform:uppercase;letter-spacing:1px;font-size:0.72rem;'
                f'border-bottom:2px solid {color};">{h}</th>'
                for h in ["HE", "D-FMM $/MWh"]
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

        st.markdown(f"### D-FMM  {nodo_key_da}  —  Top / Bottom 5  ({sel_date_da_s})")
        col_t_da, col_b_da = st.columns(2)
        with col_t_da:
            st.markdown(_dfmm_mini_html("Highest D-FMM (HE)", top5_da, "#B7D433"), unsafe_allow_html=True)
        with col_b_da:
            st.markdown(_dfmm_mini_html("Lowest D-FMM (HE)",  bot5_da, "#FF6B35"), unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

    # ── Tabla horaria: HE | DA | FMM | D-FMM ────────────────────────────────
    st.markdown(f"### Hourly Prices — {sel_date_da_lbl.split('(')[0].strip()}  ({sel_date_da_s})")
    hdrs_da = ["HE", f"DA $/MWh", "FMM $/MWh", "D-FMM $/MWh"]
    hdr_cells_da = "".join(
        f'<th style="background:#12151f;color:#00d4e8;padding:7px 12px;'
        f'text-transform:uppercase;letter-spacing:1.2px;font-size:0.72rem;'
        f'border-bottom:2px solid #00d4e8;font-family:Segoe UI,sans-serif;">{h}</th>'
        for h in hdrs_da
    )
    rows_html_da = ""
    for i, h in enumerate(hours_c):
        bg    = "#1e2130" if h % 2 == 0 else "#12151f"
        da_v  = f"${da_real[i]:.2f}"   if da_real[i]  is not None else "—"
        fmm_v = f"${fmm_real[i]:.2f}"  if fmm_real[i] is not None else "—"
        dfmm_v = f"${dfmm_vec[i]:.2f}" if dfmm_vec[i] is not None else "—"
        dr_c  = ("#B7D433" if dfmm_vec[i] is not None and dfmm_vec[i] > 0
                 else "#FF6B35" if dfmm_vec[i] is not None and dfmm_vec[i] < 0
                 else "#5a6280")
        rows_html_da += (
            f'<tr>'
            f'<td style="background:{bg};color:#00d4e8;font-weight:700;padding:5px 12px;'
            f'border-bottom:1px solid #2d3350;font-family:Consolas,monospace;">{h}</td>'
            f'<td style="background:{bg};color:#B7D433;font-weight:600;padding:5px 12px;'
            f'border-bottom:1px solid #2d3350;font-family:Consolas,monospace;">{da_v}</td>'
            f'<td style="background:{bg};color:#FF6B35;font-weight:600;padding:5px 12px;'
            f'border-bottom:1px solid #2d3350;font-family:Consolas,monospace;">{fmm_v}</td>'
            f'<td style="background:{bg};color:{dr_c};font-weight:700;padding:5px 12px;'
            f'border-bottom:1px solid #2d3350;font-family:Consolas,monospace;">{dfmm_v}</td>'
            f'</tr>'
        )
    st.markdown(
        f'<div style="overflow-x:auto;border:1px solid #2d3350;border-radius:6px;'
        f'max-height:560px;overflow-y:auto;">'
        f'<table style="width:100%;border-collapse:collapse;">'
        f'<thead><tr>{hdr_cells_da}</tr></thead>'
        f'<tbody>{rows_html_da}</tbody>'
        f'</table></div>',
        unsafe_allow_html=True,
    )


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 2: PML CENACE BCA (IVY / OMS - MXN/MWh)
# ══════════════════════════════════════════════════════════════════════════════
elif page == "PML CENACE (IVY / OMS)":
    st.title("PML CENACE BCA  (MXN/MWh)")
    st.caption("Nodos: 07IVY-230 (Imperial Valley) y 07OMS-230 (Otay Mesa) · Sistema BCA · Mercado MDA")

    tag_mxn = '<span class="tag-mxn">MXN</span>'
    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(kpi("PML IVY", ultima.get("PML_IVY"), ante.get("PML_IVY"),
                    fmt="${:.2f}", color=C_IVY, tag=tag_mxn), unsafe_allow_html=True)
    c2.markdown(kpi("PML OMS", ultima.get("PML_OMS"), ante.get("PML_OMS"),
                    fmt="${:.2f}", color=C_OMS, tag=tag_mxn), unsafe_allow_html=True)

    # Equivalente en USD
    ivy_usd = ultima.get("PML_IVY", 0) / tc if tc else None
    oms_usd = ultima.get("PML_OMS", 0) / tc if tc else None
    c3.markdown(kpi("PML IVY (USD equiv)", ivy_usd, None,
                    fmt="${:.3f}", color=C_IVY, tag=tag_mxn), unsafe_allow_html=True)
    c4.markdown(kpi("PML OMS (USD equiv)", oms_usd, None,
                    fmt="${:.3f}", color=C_OMS, tag=tag_mxn), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Serie temporal IVY y OMS
    fig = go.Figure()
    if "PML_IVY" in df_hist.columns:
        fig.add_trace(go.Scatter(x=df_hist["fecha"], y=df_hist["PML_IVY"],
                                 name="IVY (Imperial Valley)", line=dict(color=C_IVY, width=2)))
    if "PML_OMS" in df_hist.columns:
        fig.add_trace(go.Scatter(x=df_hist["fecha"], y=df_hist["PML_OMS"],
                                 name="OMS (Otay Mesa)", line=dict(color=C_OMS, width=2)))
    fig.update_layout(**_plotly_base(380, "PML CENACE BCA  —  MXN/MWh"), yaxis_title="MXN/MWh")
    st.plotly_chart(fig, use_container_width=True)

    # Perfil horario promedio
    df_p = df_hist.copy()
    df_p["hora"] = df_p["fecha"].dt.hour + 1
    c1, c2 = st.columns(2)
    for col, nodo, color, cx in [("PML_IVY", "IVY", C_IVY, c1), ("PML_OMS", "OMS", C_OMS, c2)]:
        if col in df_p.columns:
            perfil = df_p.groupby("hora")[col].mean().reset_index()
            fig_p = go.Figure(go.Bar(
                x=perfil["hora"], y=perfil[col],
                marker_color=color, opacity=0.85,
                name=f"PML {nodo} prom.",
            ))
            fig_p.update_layout(**_plotly_base(280, f"Perfil horario — PML {nodo}"),
                                xaxis_title="Hora (HE)", yaxis_title="MXN/MWh")
            cx.plotly_chart(fig_p, use_container_width=True)

    # Tabla diaria
    df_d = df_hist.copy()
    df_d["dia"] = df_d["fecha"].dt.date
    agg = {c: "mean" for c in ["PML_IVY", "PML_OMS"] if c in df_d.columns}
    if agg:
        df_agg = df_d.groupby("dia").agg(agg).reset_index()
        df_agg["IVY_USD"] = df_agg["PML_IVY"] / tc
        df_agg["OMS_USD"] = df_agg["PML_OMS"] / tc
        float_cols = [c for c in df_agg.columns if c != "dia"]
        st.dataframe(
            df_agg.sort_values("dia", ascending=False)
                  .style.format({c: "{:.2f}" for c in float_cols}),
            use_container_width=True, hide_index=True,
        )


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 3: Spread DA - FMM
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Spread DA-FMM":
    st.title("Spread DA - FMM  (USD/MWh)")

    df_d = df_hist.copy()
    df_d["hora"] = df_d["fecha"].dt.hour + 1
    df_d["dia"]  = df_d["fecha"].dt.date

    if "DA_ROA" in df_d.columns and "FMM_ROA" in df_d.columns:
        df_d["SPREAD_ROA"] = df_d["DA_ROA"] - df_d["FMM_ROA"]
    if "DA_TJI" in df_d.columns and "FMM_TJI" in df_d.columns:
        df_d["SPREAD_TJI"] = df_d["DA_TJI"] - df_d["FMM_TJI"]

    # Heatmap ROA
    if "SPREAD_ROA" in df_d.columns:
        pivot = df_d.pivot_table(index="hora", columns="dia", values="SPREAD_ROA", aggfunc="mean")
        pivot.columns = [str(c) for c in pivot.columns]
        fig_hm = px.imshow(
            pivot, color_continuous_scale="RdYlGn", color_continuous_midpoint=0,
            aspect="auto", labels=dict(x="Dia", y="Hora (HE)", color="Spread USD/MWh"),
            title="Spread DA-FMM ROA — Heatmap (Hora x Dia)",
        )
        fig_hm.update_layout(**_plotly_base(420))
        st.plotly_chart(fig_hm, use_container_width=True)

    c1, c2 = st.columns(2)
    for nodo, col_sp, color, cx in [
        ("ROA", "SPREAD_ROA", C_ROA, c1),
        ("TJI", "SPREAD_TJI", C_TJI, c2),
    ]:
        if col_sp in df_d.columns:
            perfil = df_d.groupby("hora")[col_sp].mean().reset_index()
            fig_p = go.Figure(go.Bar(
                x=perfil["hora"], y=perfil[col_sp],
                marker_color=["#ff6b6b" if v > 0 else "#00d4e8" for v in perfil[col_sp]],
            ))
            fig_p.add_hline(y=0, line_dash="dash", line_color="white", opacity=0.4)
            fig_p.update_layout(**_plotly_base(300, f"Perfil Spread {nodo}"),
                                xaxis_title="Hora (HE)", yaxis_title="USD/MWh")
            cx.plotly_chart(fig_p, use_container_width=True)

    # Serie temporal spread
    fig_s = go.Figure()
    for col_sp, color, label in [("SPREAD_ROA", C_ROA, "Spread ROA"), ("SPREAD_TJI", C_TJI, "Spread TJI")]:
        if col_sp in df_d.columns:
            fig_s.add_trace(go.Scatter(x=df_d["fecha"], y=df_d[col_sp],
                                       name=label, line=dict(color=color, width=1.5)))
    fig_s.add_hline(y=0, line_dash="dash", line_color="white", opacity=0.3)
    fig_s.update_layout(**_plotly_base(300, "Serie temporal Spread DA-FMM"), yaxis_title="USD/MWh")
    st.plotly_chart(fig_s, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 4: Load & Solar CAISO
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Load & Solar":
    st.title(f"Load & Solar CAISO  —  {today_dt.strftime('%A %B %d, %Y')}")

    _hdr, _btn_col = st.columns([8, 1])
    with _btn_col:
        if st.button("Refrescar", use_container_width=True):
            _fetch_caiso_live_day.clear()
            st.rerun()

    # ── Yesterday: desde BD ───────────────────────────────────────────────────
    load_yd = _day_vals_c(df_hist, "LOAD_CAISO",  yday_dt)
    sol_yd  = _day_vals_c(df_hist, "SOLAR_CAISO", yday_dt)
    wind_yd = _day_vals_c(df_hist, "WIND_CAISO",  yday_dt)
    # Si wind de ayer no está en BD (columna nueva), traer de OASIS live
    if not any(v for v in wind_yd if v):
        try:
            _live_yd = _fetch_caiso_live_day(yday_dt.strftime("%Y-%m-%d"))
            wind_yd  = _live_yd["wind"]
        except Exception:
            pass

    # ── Today y Tomorrow: siempre OASIS live, BD como fallback ───────────────
    with st.spinner("Descargando datos CAISO…"):
        _oasis_err = []
        try:
            _live_td = _fetch_caiso_live_day(today_dt.strftime("%Y-%m-%d"))
            load_td  = _live_td["load"]
            sol_td   = _live_td["solar"]
            wind_td  = _live_td["wind"]
        except Exception as _e:
            _oasis_err.append(f"Today: {_e}")
            load_td = _day_vals_c(df_hist, "LOAD_CAISO",  today_dt)
            sol_td  = _day_vals_c(df_hist, "SOLAR_CAISO", today_dt)
            wind_td = _day_vals_c(df_hist, "WIND_CAISO",  today_dt)

        try:
            _live_tm = _fetch_caiso_live_day(tmrw_dt.strftime("%Y-%m-%d"))
            load_tm  = _live_tm["load"]
            sol_tm   = _live_tm["solar"]
            wind_tm  = _live_tm["wind"]
        except Exception as _e:
            _oasis_err.append(f"Tomorrow: {_e}")
            load_tm = _day_vals_c(df_hist, "LOAD_CAISO",  tmrw_dt)
            sol_tm  = _day_vals_c(df_hist, "SOLAR_CAISO", tmrw_dt)
            wind_tm = _day_vals_c(df_hist, "WIND_CAISO",  tmrw_dt)

        if _oasis_err:
            st.warning("OASIS: " + " | ".join(_oasis_err))

    # ── Net Load (Load - Solar - Wind) ────────────────────────────────────────
    def _net_load(l, s, w):
        result = []
        for li, si, wi in zip(l, s, w):
            if li is None:
                result.append(None)
            else:
                net = li
                if si is not None:
                    net -= si
                if wi is not None:
                    net -= wi
                result.append(net)
        return result

    st.plotly_chart(_three_day_chart_c(
        "Net Load Forecast CAISO", "Net Load (MW)",
        _net_load(load_yd, sol_yd, wind_yd),
        _net_load(load_td, sol_td, wind_td),
        _net_load(load_tm, sol_tm, wind_tm),
        yday_s, tday_s, tmrw_s,
    ), use_container_width=True)

    # ── Load Forecast 3 dias ──────────────────────────────────────────────────
    if any(v for v in load_td if v):
        st.plotly_chart(_load_chart_c(load_yd, load_td, load_tm, yday_s, tday_s, tmrw_s),
                        use_container_width=True)
    else:
        st.warning("Load CAISO no disponible en OASIS (intenta refrescar)")

    # ── Solar + Wind lado a lado ──────────────────────────────────────────────
    _sc1, _sc2 = st.columns(2)
    with _sc1:
        if any(v for v in sol_td if v):
            st.plotly_chart(_solar_chart_c(sol_yd, sol_td, sol_tm, yday_s, tday_s, tmrw_s),
                            use_container_width=True)
        else:
            st.warning("Solar CAISO no disponible en OASIS")
    with _sc2:
        if any(v for v in wind_td if v):
            st.plotly_chart(_wind_chart_c(wind_yd, wind_td, wind_tm, yday_s, tday_s, tmrw_s),
                            use_container_width=True)
        else:
            st.warning("Wind CAISO no disponible en OASIS")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 5: Conversion MXN (CAISO USD -> MXN)
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Conversion MXN":
    st.title("Conversion  CAISO USD  →  MXN/MWh")

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

    with st.spinner("Obteniendo TC live..."):
        auto_tc = get_live_tc()

    col_tc, _ = st.columns([1, 3])
    with col_tc:
        tc_conv = st.number_input(
            "Tipo de cambio MXN/USD" + ("  (auto)" if auto_tc else "  (manual)"),
            value=float(auto_tc or tc), step=0.01, format="%.4f",
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # Conversion de DA_ROA y FMM_ROA a MXN
    df_conv = df_hist.copy()
    for c_usd, c_mxn in [("DA_ROA", "DA_ROA_MXN"), ("FMM_ROA", "FMM_ROA_MXN"),
                          ("DA_TJI", "DA_TJI_MXN"), ("FMM_TJI", "FMM_TJI_MXN")]:
        if c_usd in df_conv.columns:
            df_conv[c_mxn] = df_conv[c_usd] * tc_conv

    # Grafica comparativa CAISO(MXN) vs PML CENACE
    c1, c2 = st.columns(2)
    for da_mxn, pml_col, fmm_mxn, nodo, cx in [
        ("DA_ROA_MXN", "PML_IVY", "FMM_ROA_MXN", "ROA vs IVY", c1),
        ("DA_TJI_MXN", "PML_OMS", "FMM_TJI_MXN", "TJI vs OMS", c2),
    ]:
        fig = go.Figure()
        if da_mxn in df_conv.columns:
            fig.add_trace(go.Scatter(x=df_conv["fecha"], y=df_conv[da_mxn],
                                     name=f"DA {da_mxn[:6]} (MXN)", line=dict(color=C_DA, width=2)))
        if fmm_mxn in df_conv.columns:
            fig.add_trace(go.Scatter(x=df_conv["fecha"], y=df_conv[fmm_mxn],
                                     name=f"FMM {fmm_mxn[:7]} (MXN)", line=dict(color=C_FMM, width=1.5, dash="dot")))
        if pml_col in df_conv.columns:
            color_pml = C_IVY if "IVY" in pml_col else C_OMS
            fig.add_trace(go.Scatter(x=df_conv["fecha"], y=df_conv[pml_col],
                                     name=f"PML {pml_col[-3:]} CENACE", line=dict(color=color_pml, width=2)))
        fig.update_layout(**_plotly_base(340, f"{nodo}  —  MXN/MWh"), yaxis_title="MXN/MWh")
        cx.plotly_chart(fig, use_container_width=True)

    # Tabla de diferencias CAISO vs CENACE en MXN
    st.subheader("Diferencial CAISO vs CENACE (MXN/MWh)")
    if "DA_ROA_MXN" in df_conv.columns and "PML_IVY" in df_conv.columns:
        df_conv["DIFF_IVY"] = df_conv["DA_ROA_MXN"] - df_conv["PML_IVY"]
        df_conv["DIFF_OMS"] = df_conv["DA_TJI_MXN"] - df_conv["PML_OMS"]
        df_d2 = df_conv.copy()
        df_d2["dia"] = df_d2["fecha"].dt.date
        agg = {c: "mean" for c in ["DA_ROA_MXN", "PML_IVY", "DIFF_IVY",
                                    "DA_TJI_MXN", "PML_OMS", "DIFF_OMS"] if c in df_d2.columns}
        df_agg2 = df_d2.groupby("dia").agg(agg).reset_index()
        float_cols = [c for c in df_agg2.columns if c != "dia"]
        st.dataframe(
            df_agg2.sort_values("dia", ascending=False)
                   .style.format({c: "{:.2f}" for c in float_cols}),
            use_container_width=True, hide_index=True,
        )


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 6: Monte Carlo (DA ROA)
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Monte Carlo IMP/EXP":
    st.title("Monte Carlo  —  Simulación P&L Interconexión CAISO")

    from etl.caiso.caiso_api import get_pml_cenace

    # ── TC en vivo ────────────────────────────────────────────────────────────
    @st.cache_data(ttl=3600, show_spinner=False)
    def _get_live_tc_mc():
        try:
            r = requests.get(
                "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/usd.json",
                timeout=10, verify=False)
            r.raise_for_status()
            return float(r.json()["usd"]["mxn"])
        except Exception:
            return None

    with st.spinner("Obteniendo TC…"):
        auto_tc_mc = _get_live_tc_mc()

    # ══ SECCIÓN 1: Configuración ══════════════════════════════════════════════
    st.markdown("### Configuración")
    cfg1, cfg2, cfg3, cfg4 = st.columns(4)
    with cfg1:
        tc_mc = st.number_input(
            "TC MXN/USD" + ("  ✓ auto" if auto_tc_mc else "  ⚠ manual"),
            value=float(auto_tc_mc or tc), step=0.01, format="%.4f")
    with cfg2:
        tz_option_c = st.radio("Zona horaria CAISO vs México",
                               ["Misma hora (BCA - Pacífico)", "CAISO 2h atrás de SIN (-2)"],
                               index=0)
        tz_offset_c = 0 if "Misma" in tz_option_c else -2
    with cfg3:
        costo_impo_c = st.number_input("Costo Importación (USD/MWh)", value=17.0, format="%.2f", key="c_impo")
        costo_expo_c = st.number_input("Costo Exportación (USD/MWh)", value=17.0, format="%.2f", key="c_expo")
    with cfg4:
        _CAISO_TO_CENACE = {"ROA": "07IVY-230", "TJI": "07OMS-230"}
        nodo_caiso_mc = st.selectbox("Nodo CAISO", ["ROA", "TJI"], key="mc_nodo_caiso")
        _cenace_default_c = _CAISO_TO_CENACE.get(nodo_caiso_mc, "07IVY-230")
        nodo_cenace_c  = st.text_input("Nodo CENACE (MDA)", value=_cenace_default_c, key="mc_nodo_cenace")
        sistema_cenace_c = st.selectbox("Sistema CENACE", ["BCA", "SIN", "BCS"], index=0, key="mc_sis")

    # ── Lookback histórico ────────────────────────────────────────────────────
    _lookback_opts_c = {"30 días": 30, "90 días": 90, "6 meses": 180, "1 año": 365}
    lookback_label_c = st.selectbox("Días históricos para simulación",
                                    list(_lookback_opts_c.keys()), index=3, key="mc_lookback")
    lookback_days_c  = _lookback_opts_c[lookback_label_c]

    # ══ SECCIÓN 2: Carga de asignación de MW ══════════════════════════════════
    st.markdown("### Asignación de MW")
    uploaded_c = st.file_uploader("Subir Excel de asignación (HORARIO)", type=["xlsx", "xls"], key="mc_upload")

    df_asig_c   = None
    hour_cols_c = []
    he_from_col_c: dict = {}

    if uploaded_c:
        try:
            df_raw_c = pd.read_excel(uploaded_c, header=None)
            hdr_row_c = 1
            for idx in range(min(6, len(df_raw_c))):
                vals = [str(v).strip().lower() for v in df_raw_c.iloc[idx].values]
                if "sistema" in vals or "clave" in vals:
                    hdr_row_c = idx
                    break
            df_asig_c = pd.read_excel(uploaded_c, header=hdr_row_c)
            df_asig_c.columns = [str(c).strip().replace("\n", " ") for c in df_asig_c.columns]
            df_asig_c = df_asig_c.dropna(how="all").reset_index(drop=True)

            HOUR_PAT_C = re.compile(r"^(\d{1,2})\s*[\s\n\-/]+\s*(\d{1,2})$")
            for c in df_asig_c.columns:
                m = HOUR_PAT_C.match(c)
                if m:
                    he = int(m.group(2))
                    hour_cols_c.append(c)
                    he_from_col_c[c] = he

            if not hour_cols_c:
                meta_kw = {"sistema", "clave", "tipo", "total", "flujo"}
                meta_c  = [c for c in df_asig_c.columns if any(k in c.lower() for k in meta_kw)]
                first_d = len(meta_c)
                cands   = df_asig_c.columns[first_d: first_d + 24].tolist()
                if len(cands) == 24:
                    hour_cols_c = cands
                    for i, c in enumerate(cands):
                        he_from_col_c[c] = i + 1
                    st.warning("Columnas de hora detectadas por posición. Verifica que el orden sea correcto.")

            for hc in hour_cols_c:
                df_asig_c[hc] = pd.to_numeric(df_asig_c[hc], errors="coerce").fillna(0)
            st.success(f"Archivo cargado: {len(df_asig_c)} filas, {len(hour_cols_c)} columnas de hora")
            if not hour_cols_c:
                with st.expander("Debug — columnas leídas"):
                    st.write(list(df_asig_c.columns))
        except Exception as _e:
            st.error(f"Error leyendo Excel: {_e}")

    if df_asig_c is None or not hour_cols_c:
        st.info("Sube el Excel de asignación para continuar.")
        st.stop()

    # ── Selector de Clave ─────────────────────────────────────────────────────
    clave_col_c = next((c for c in df_asig_c.columns if c.lower() == "clave"), None)
    tipo_col_c  = next((c for c in df_asig_c.columns if c.lower() == "tipo"),  None)
    if clave_col_c is None:
        st.error("No se encontró columna 'Clave' en el Excel.")
        st.stop()

    claves_c    = df_asig_c[clave_col_c].dropna().astype(str).tolist()
    sel_clave_c = st.selectbox("Clave / Nodo de interconexión", claves_c, key="mc_clave")
    row_sel_c   = df_asig_c[df_asig_c[clave_col_c].astype(str) == sel_clave_c].iloc[0]
    tipo_c      = str(row_sel_c[tipo_col_c]).strip().upper() if tipo_col_c else "EXP"
    costo_mw_c  = costo_impo_c if tipo_c == "IMP" else costo_expo_c

    mw_by_he_mx_c = {}
    for hc in hour_cols_c:
        he_mx = he_from_col_c.get(hc)
        if he_mx is None:
            continue
        mw = float(row_sel_c[hc])
        if mw != 0:
            mw_by_he_mx_c[he_mx] = mw

    if not mw_by_he_mx_c:
        st.warning(f"La clave {sel_clave_c} no tiene horas con MW asignados.")
        st.stop()

    mw_by_he_caiso_c = {}
    for he_mx, mw in mw_by_he_mx_c.items():
        he_ca = he_mx + tz_offset_c
        if 1 <= he_ca <= 24:
            mw_by_he_caiso_c[he_ca] = mw

    hora_opts_c = {
        f"HE {he_ca}  ({'MX ' + str(he_ca - tz_offset_c)})  —  {mw:.0f} MW  [{tipo_c}]": he_ca
        for he_ca, mw in sorted(mw_by_he_caiso_c.items())
    }
    sel_hora_lbl_c = st.selectbox("Hora asignada (CAISO HE)", list(hora_opts_c.keys()), key="mc_hora")
    he_ca_sel      = hora_opts_c[sel_hora_lbl_c]
    mw_sel_c       = mw_by_he_caiso_c[he_ca_sel]

    with st.expander("Ver tabla completa de MW asignados", expanded=False):
        tbl_rows_c = []
        for he_mx, mw in sorted(mw_by_he_mx_c.items()):
            he_ca = he_mx + tz_offset_c
            tbl_rows_c.append({"HE México": he_mx,
                                "HE CAISO": he_ca if 1 <= he_ca <= 24 else "—",
                                "MW": mw, "Tipo": tipo_c})
        st.dataframe(pd.DataFrame(tbl_rows_c), use_container_width=True, hide_index=True)

    # ══ SECCIÓN 3: Precios MDA CENACE ═════════════════════════════════════════
    st.markdown("### Precio MDA CENACE")
    tmrw_mc_c  = today_dt + timedelta(days=1)
    fecha_mda_c = st.date_input("Fecha MDA", value=tmrw_mc_c, key="mc_fecha_mda")
    he_mx_sel_c = he_ca_sel - tz_offset_c

    @st.cache_data(ttl=600, show_spinner=False)
    def _fetch_cenace_mda_c(nodo, sistema, fecha_s):
        return get_pml_cenace(fecha_s, fecha_s, nodo, sistema=sistema, mercado="MDA")

    with st.spinner(f"Descargando MDA CENACE {nodo_cenace_c}…"):
        df_mda_c = _fetch_cenace_mda_c(nodo_cenace_c, sistema_cenace_c,
                                       fecha_mda_c.strftime("%Y-%m-%d"))

    mda_no_pub_c = df_mda_c is None or df_mda_c.empty
    if mda_no_pub_c and fecha_mda_c >= today_dt:
        st.warning(f"MDA CENACE para {fecha_mda_c.strftime('%d/%m/%Y')} aún no publicado "
                   f"({nodo_cenace_c} · {sistema_cenace_c}). Ingresa el precio manualmente.")

    pml_hora_c = None
    if not mda_no_pub_c:
        hora_match_c = df_mda_c[df_mda_c["fecha"].dt.hour + 1 == he_mx_sel_c]
        if not hora_match_c.empty:
            pml_hora_c = float(hora_match_c["pml"].iloc[0])

    if not mda_no_pub_c:
        df_mda_show_c = df_mda_c.copy()
        df_mda_show_c["HE"]       = df_mda_show_c["fecha"].dt.hour + 1
        df_mda_show_c["PML (MXN)"] = df_mda_show_c["pml"].round(2)
        df_mda_show_c["PML (USD)"] = (df_mda_show_c["pml"] / tc_mc).round(4)
        if tipo_c == "IMP":
            df_mda_show_c["Break Even"] = (df_mda_show_c["pml"] / tc_mc - costo_impo_c).round(4)
        else:
            df_mda_show_c["Break Even"] = (df_mda_show_c["pml"] / tc_mc + costo_expo_c).round(4)

        hdrs_mda_c = ["HE", "PML (MXN)", "PML (USD)", "Break Even (USD)"]
        hdr_mda_html_c = "".join(
            f'<th style="background:#12151f;color:#00d4e8;padding:6px 14px;'
            f'text-transform:uppercase;letter-spacing:1px;font-size:0.72rem;'
            f'border-bottom:2px solid #00d4e8;">{h}</th>'
            for h in hdrs_mda_c
        )
        rows_mda_html_c = ""
        for _, r in df_mda_show_c.sort_values("HE").iterrows():
            is_sel_c = int(r["HE"]) == he_mx_sel_c
            bg_c     = "#2d3350" if is_sel_c else ("#1e2130" if int(r["HE"]) % 2 == 0 else "#12151f")
            brd_c    = "2px solid #B7D433" if is_sel_c else "1px solid #2d3350"
            be_c_v   = r["Break Even"]
            be_col_c = "#B7D433" if be_c_v > 0 else "#FF6B35"
            rows_mda_html_c += (
                f'<tr>'
                f'<td style="background:{bg_c};color:#00d4e8;font-weight:700;'
                f'padding:5px 14px;border-bottom:{brd_c};font-family:Consolas,monospace;">{int(r["HE"])}</td>'
                f'<td style="background:{bg_c};color:#B7D433;font-weight:600;'
                f'padding:5px 14px;border-bottom:{brd_c};font-family:Consolas,monospace;">${r["PML (MXN)"]:.2f}</td>'
                f'<td style="background:{bg_c};color:#c0c4cc;font-weight:600;'
                f'padding:5px 14px;border-bottom:{brd_c};font-family:Consolas,monospace;">${r["PML (USD)"]:.4f}</td>'
                f'<td style="background:{bg_c};color:{be_col_c};font-weight:700;'
                f'padding:5px 14px;border-bottom:{brd_c};font-family:Consolas,monospace;">${be_c_v:.4f}</td>'
                f'</tr>'
            )
        st.markdown(
            f'<div style="overflow-y:auto;max-height:300px;border:1px solid #2d3350;border-radius:6px;">'
            f'<table style="width:100%;border-collapse:collapse;">'
            f'<thead><tr>{hdr_mda_html_c}</tr></thead>'
            f'<tbody>{rows_mda_html_c}</tbody></table></div>',
            unsafe_allow_html=True,
        )
    elif nodo_cenace_c:
        pml_hora_c = st.number_input("PML no disponible — ingresa manualmente (MXN/MWh)",
                                     value=700.0, format="%.2f", key="mc_pml_manual")

    # ══ SECCIÓN 4: Monte Carlo ════════════════════════════════════════════════
    st.markdown("### Simulación Monte Carlo")

    if pml_hora_c is None:
        st.info("Sin precio MDA para la hora seleccionada. Ingresa el precio manualmente arriba.")
        st.stop()

    # Datos históricos CAISO FMM — carga independiente con lookback propio
    @st.cache_data(ttl=1800, show_spinner=False)
    def _load_caiso_mc(days: int):
        return load_caiso(days)

    df_mc_raw_c, _ = _load_caiso_mc(lookback_days_c)
    fmm_col_mc = f"FMM_{nodo_caiso_mc}"
    if fmm_col_mc not in df_mc_raw_c.columns:
        fmm_col_mc = "FMM_ROA"
    df_mc_c = df_mc_raw_c.copy()
    df_mc_c["hora"] = df_mc_c["fecha"].dt.hour + 1
    precios_hist_c  = [round(p, 2) for p in df_mc_c[df_mc_c["hora"] == he_ca_sel][fmm_col_mc].dropna().tolist()]

    if len(precios_hist_c) < 10:
        st.warning(f"Pocos datos históricos para HE{he_ca_sel} en los últimos {lookback_days_c} días. Amplía el lookback.")
        st.stop()

    # Break-even CAISO FMM
    pml_usd_c = pml_hora_c / tc_mc
    if tipo_c == "IMP":
        precio_be_c  = pml_usd_c - costo_mw_c
        label_be_c   = f"BE (IMP): PML/TC − Costo = ${precio_be_c:.2f}"
        profits_fn_c = lambda sim: precio_be_c - sim
    else:
        precio_be_c  = pml_usd_c + costo_mw_c
        label_be_c   = f"BE (EXP): PML/TC + Costo = ${precio_be_c:.2f}"
        profits_fn_c = lambda sim: sim - precio_be_c

    n_sim_c   = 10_000
    sim_c     = np.random.choice(precios_hist_c, size=n_sim_c, replace=True).astype(float)
    sim_c    += np.random.normal(0, np.std(precios_hist_c) * 0.1, n_sim_c)
    profits_c = profits_fn_c(sim_c)

    prob_p_c  = float((profits_c > 0).mean() * 100)
    exp_p_c   = float(np.mean(profits_c))
    var_5_c   = float(np.percentile(profits_c, 5))
    es_5_c    = float(np.mean(profits_c[profits_c <= var_5_c]))
    exp_pnl_c = exp_p_c * mw_sel_c

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Prob. de profit",                    f"{prob_p_c:.1f}%")
    m2.metric("P&L esp. (USD/MWh)",                 f"${exp_p_c:.2f}")
    m3.metric(f"P&L esp. total ({mw_sel_c:.0f} MW)", f"${exp_pnl_c:.0f}")
    m4.metric("VaR 5% (USD/MWh)",                   f"${var_5_c:.2f}")
    m5.metric(f"ES 5% total ({mw_sel_c:.0f} MW)",    f"${es_5_c * mw_sel_c:.0f}")

    st.caption(f"{tipo_c} · {label_be_c}  |  Nodo CAISO: {fmm_col_mc}  |  Lookback: {lookback_days_c} días  |  {len(precios_hist_c)} obs")

    # ── Histograma ────────────────────────────────────────────────────────────
    fig_mc_c = go.Figure()
    fig_mc_c.add_trace(go.Histogram(x=sim_c, nbinsx=60, name="FMM Simulado",
                                    marker_color=C_HOY, opacity=0.7))
    fig_mc_c.add_trace(go.Histogram(x=precios_hist_c, nbinsx=60, name="FMM Histórico",
                                    marker_color="#fbbf24", opacity=0.45))
    fig_mc_c.add_vline(x=precio_be_c, line_dash="dash", line_color="#ff6b6b",
                       annotation_text=label_be_c, annotation_position="top right",
                       annotation_font_color="#ff6b6b")
    fig_mc_c.update_layout(**_plotly_base(400, f"Distribución FMM CAISO — HE{he_ca_sel}  ({tipo_c} {sel_clave_c})"),
                           barmode="overlay", xaxis_title="$/MWh", yaxis_title="Frecuencia")
    st.plotly_chart(fig_mc_c, use_container_width=True)

    # ── Probabilidad por hora asignada ────────────────────────────────────────
    if len(mw_by_he_caiso_c) > 1:
        st.markdown("### Probabilidad de profit — todas las horas asignadas")
        prob_horas_c = []
        for he_ca, mw in sorted(mw_by_he_caiso_c.items()):
            ph = df_mc_c[df_mc_c["hora"] == he_ca][fmm_col_mc].dropna()
            if len(ph) < 5:
                prob_horas_c.append({"HE CAISO": he_ca, "MW": mw, "Prob (%)": 0.0, "P&L esp (USD/MWh)": 0.0})
                continue
            sh = np.random.choice(ph.tolist(), size=3000, replace=True)
            sh += np.random.normal(0, ph.std() * 0.1, 3000)
            pf = profits_fn_c(sh)
            prob_horas_c.append({
                "HE CAISO": he_ca, "MW": mw,
                "Prob (%)": round(float((pf > 0).mean() * 100), 1),
                "P&L esp (USD/MWh)": round(float(np.mean(pf)), 2),
            })
        df_ph_c = pd.DataFrame(prob_horas_c)
        fig_ph_c = go.Figure(go.Bar(
            x=df_ph_c["HE CAISO"], y=df_ph_c["Prob (%)"],
            marker_color=["#00d4e8" if v >= 50 else "#ff6b6b" for v in df_ph_c["Prob (%)"]],
            text=[f"{v:.0f}%" for v in df_ph_c["Prob (%)"]],
            textposition="outside",
        ))
        fig_ph_c.add_hline(y=50, line_dash="dash", line_color="white", opacity=0.4)
        fig_ph_c.update_layout(**_plotly_base(320, "Prob. profit por hora asignada"),
                               xaxis_title="HE CAISO", yaxis_title="%")
        st.plotly_chart(fig_ph_c, use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════
# PAGE: Spread México — CAISO vs CENACE (USD/MWh)
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Spread México":
    st.title("Spread México — CAISO vs CENACE (USD/MWh)")

    _NODO_MAP_C = {
        "ROA ↔ IVY  (07IVY-230)": {"caiso": "ROA", "cenace": "07IVY-230", "sistema": "BCA",
                                    "da_col": "DA_ROA", "fmm_col": "FMM_ROA", "pml_col": "PML_IVY"},
        "TJI ↔ OMS  (07OMS-230)": {"caiso": "TJI", "cenace": "07OMS-230", "sistema": "BCA",
                                    "da_col": "DA_TJI", "fmm_col": "FMM_TJI", "pml_col": "PML_OMS"},
    }
    col_nodo_c, col_dias_c = st.columns([3, 1])
    with col_nodo_c:
        sel_pair_c = st.selectbox("Nodo frontera", list(_NODO_MAP_C.keys()))
    with col_dias_c:
        dias_spr_c = st.slider("Días histórico", 1, 90, 30, key="spr_dias_c")
    pair_c = _NODO_MAP_C[sel_pair_c]

    @st.cache_data(ttl=900, show_spinner=False)
    def _cenace_vec_c(nodo: str, sistema: str, d: "date") -> list:
        url = (f"https://ws01.cenace.gob.mx:8082/SWPML/SIM/{sistema}/MDA/{nodo}/"
               f"{d.year}/{d.month:02d}/{d.day:02d}/"
               f"{d.year}/{d.month:02d}/{d.day:02d}/JSON")
        try:
            import urllib3 as _u3; _u3.disable_warnings()
            import requests as _req
            resp = _req.get(url, timeout=30, verify=False)
            valores = resp.json()["Resultados"][0]["Valores"]
            vals = [float(v["pml"]) for v in valores]
            while len(vals) < 24:
                vals.append(None)
            return vals[:24]
        except Exception:
            return [None] * 24

    hoy_c   = date.today()
    ayer_c  = hoy_c - timedelta(days=1)
    HRS_C   = [f"{h:02d}:00" for h in range(24)]
    now_h_c = datetime.now().hour

    with st.spinner("Cargando CENACE..."):
        cen_hoy_c = _cenace_vec_c(pair_c["cenace"], pair_c["sistema"], hoy_c)

    def _hist_vec_c(col, d):
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

    da_hoy_c  = _hist_vec_c(pair_c["da_col"],  hoy_c)
    fmm_hoy_c = _hist_vec_c(pair_c["fmm_col"], hoy_c)

    cen_usd_hoy_c = [v / tc if v is not None else None for v in cen_hoy_c]

    def _avg_c(vals):
        v = [x for x in vals if x is not None]
        return sum(v) / len(v) if v else None

    avg_da_c     = _avg_c(da_hoy_c)
    avg_fmm_c    = _avg_c(fmm_hoy_c)
    avg_cen_mx_c = _avg_c(cen_hoy_c)
    avg_cen_us_c = avg_cen_mx_c / tc if avg_cen_mx_c else None

    last_fmm_idx = max((h for h in range(24) if fmm_hoy_c[h] is not None), default=-1)
    last_fmm_c   = fmm_hoy_c[last_fmm_idx] if last_fmm_idx >= 0 else None
    last_cen_c   = next((cen_usd_hoy_c[h] for h in range(min(now_h_c, 23), -1, -1) if cen_usd_hoy_c[h] is not None), None)
    spr_now_c    = last_fmm_c - last_cen_c if last_fmm_c is not None and last_cen_c is not None else None

    COL_US_C  = "#f59e0b"
    COL_MX_C  = "#34d399"
    COL_SPR_C = "#a78bfa"

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.markdown(kpi("DA CAISO Prom",     avg_da_c,     None, color=COL_US_C),                   unsafe_allow_html=True)
    k2.markdown(kpi("RT/FMM CAISO Prom", avg_fmm_c,    None, color=C_FMM),                      unsafe_allow_html=True)
    k3.markdown(kpi("PML CENACE (MXN)",  avg_cen_mx_c, None, fmt="${:.2f}", color=COL_MX_C),     unsafe_allow_html=True)
    k4.markdown(kpi("PML CENACE (USD)",  avg_cen_us_c, None, fmt="${:.3f}", color=COL_MX_C),     unsafe_allow_html=True)
    k5.markdown(kpi("Spread RT–CENACE",  spr_now_c,    None, color=COL_SPR_C),                   unsafe_allow_html=True)

    st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)

    # ── Gráficas lado a lado: CAISO | CENACE ────────────────────────────────
    col_a, col_b = st.columns(2)
    with col_a:
        # FMM: sólido = horas publicadas, punteado = sin dato (igual que RT en ERCOT)
        fmm_solid = [fmm_hoy_c[i] for i in range(24)]
        fmm_dash  = [None] * 24
        if last_fmm_idx >= 0 and last_fmm_idx < 23:
            fmm_dash[last_fmm_idx] = fmm_hoy_c[last_fmm_idx]  # punto de unión

        fig_ca = go.Figure()
        fig_ca.add_trace(go.Scatter(x=HRS_C, y=da_hoy_c, name="DA Hoy",
            line=dict(color=COL_US_C, width=2.5), connectgaps=False))
        fig_ca.add_trace(go.Scatter(x=HRS_C, y=fmm_solid, name="RT/FMM Hoy (real)",
            line=dict(color=C_FMM, width=2.5), connectgaps=False))
        fig_ca.add_trace(go.Scatter(x=HRS_C, y=fmm_dash, name="RT/FMM Forecast",
            line=dict(color=C_FMM, width=1.8, dash="dot"), connectgaps=False))
        if 0 < last_fmm_idx < 23:
            fig_ca.add_vline(x=HRS_C[last_fmm_idx], line_dash="dot", line_color="#5a6280", line_width=1)
        fig_ca.update_layout(**_plotly_base(340, f"CAISO {pair_c['caiso']}  (USD/MWh)"),
                             yaxis_title="USD/MWh")
        st.plotly_chart(fig_ca, use_container_width=True, config={"displayModeBar": False})

    with col_b:
        fig_cb = go.Figure()
        fig_cb.add_trace(go.Scatter(x=HRS_C, y=cen_hoy_c, name="PML MDA Hoy",
            line=dict(color=COL_MX_C, width=2.5), connectgaps=False))
        if 0 < last_fmm_idx < 23:
            fig_cb.add_vline(x=HRS_C[last_fmm_idx], line_dash="dot", line_color="#5a6280", line_width=1)
        fig_cb.update_layout(**_plotly_base(340, f"CENACE {pair_c['cenace']} PML MDA  (MXN/MWh)"),
                             yaxis_title="MXN/MWh")
        st.plotly_chart(fig_cb, use_container_width=True, config={"displayModeBar": False})

    # ── Gráfica combinada mismo eje USD/MWh ──────────────────────────────────
    fig_comb_c = go.Figure()
    fig_comb_c.add_trace(go.Scatter(x=HRS_C, y=da_hoy_c,
        name=f"DA {pair_c['caiso']} (USD/MWh)",
        line=dict(color=COL_US_C, width=2), connectgaps=False))
    fig_comb_c.add_trace(go.Scatter(x=HRS_C, y=fmm_solid,
        name=f"RT/FMM {pair_c['caiso']} (USD/MWh)",
        line=dict(color=C_FMM, width=2.5), connectgaps=False))
    fig_comb_c.add_trace(go.Scatter(x=HRS_C, y=fmm_dash,
        name="RT/FMM Forecast",
        line=dict(color=C_FMM, width=1.8, dash="dot"), connectgaps=False, showlegend=False))
    fig_comb_c.add_trace(go.Scatter(x=HRS_C, y=cen_usd_hoy_c,
        name=f"CENACE {pair_c['cenace']} MDA (USD equiv.)",
        line=dict(color=COL_MX_C, width=2), connectgaps=False))
    if 0 < last_fmm_idx < 23:
        fig_comb_c.add_vline(x=HRS_C[last_fmm_idx], line_dash="dot", line_color="#5a6280", line_width=1)
    fig_comb_c.update_layout(**_plotly_base(320,
        f"CAISO vs CENACE — mismo eje USD/MWh  ·  TC {tc:.4f}"), yaxis_title="USD/MWh")
    st.plotly_chart(fig_comb_c, use_container_width=True, config={"displayModeBar": False})

    # ── Spread horario (barras) ───────────────────────────────────────────────
    spr_hoy_c = [rt - c if rt is not None and c is not None else None
                 for rt, c in zip(fmm_hoy_c, cen_usd_hoy_c)]
    fig_spr_c = go.Figure(go.Bar(
        x=HRS_C, y=spr_hoy_c,
        marker_color=[COL_SPR_C if (v is not None and v >= 0) else "#ff6b6b" for v in spr_hoy_c],
        name="Spread RT–CENACE",
    ))
    fig_spr_c.add_hline(y=0, line_dash="dash", line_color="white", line_width=1, opacity=0.4)
    fig_spr_c.update_layout(**_plotly_base(260, "Spread  RT CAISO – PML CENACE  (USD/MWh)"),
                            yaxis_title="USD/MWh")
    st.plotly_chart(fig_spr_c, use_container_width=True, config={"displayModeBar": False})

    # ── Histórico diario agregado ─────────────────────────────────────────────
    fmm_col_h = pair_c["fmm_col"]
    pml_col_h = pair_c["pml_col"]
    if not df_hist.empty and fmm_col_h in df_hist.columns and pml_col_h in df_hist.columns:
        df_h2 = df_hist.dropna(subset=[fmm_col_h, pml_col_h]).copy()
        df_h2["CENACE_USD"] = df_h2[pml_col_h] / tc
        df_h2["SPREAD"]     = df_h2[fmm_col_h] - df_h2["CENACE_USD"]
        df_h2["fecha_dia"]  = df_h2["fecha"].dt.date
        df_day = (df_h2.groupby("fecha_dia")
                  .agg(rt_usd=(fmm_col_h, "mean"), pml_usd=("CENACE_USD", "mean"), spread=("SPREAD", "mean"))
                  .reset_index())
        # filter to dias_spr_c
        cutoff_c = hoy_c - timedelta(days=dias_spr_c)
        df_day = df_day[df_day["fecha_dia"] >= cutoff_c]

        fig_sh_c = go.Figure()
        fig_sh_c.add_trace(go.Scatter(x=df_day["fecha_dia"], y=df_day["rt_usd"],
            name=f"RT/FMM {pair_c['caiso']} (USD/MWh)", line=dict(color=C_FMM, width=1.8)))
        fig_sh_c.add_trace(go.Scatter(x=df_day["fecha_dia"], y=df_day["pml_usd"],
            name=f"CENACE {pair_c['cenace']} (USD/MWh)", line=dict(color=COL_MX_C, width=1.8)))
        fig_sh_c.update_layout(**_plotly_base(300,
            f"Histórico {dias_spr_c} días — RT vs CENACE (USD/MWh)"), yaxis_title="USD/MWh")
        st.plotly_chart(fig_sh_c, use_container_width=True, config={"displayModeBar": False})

        fig_shspr_c = go.Figure(go.Scatter(
            x=df_day["fecha_dia"], y=df_day["spread"],
            name="Spread RT–CENACE", line=dict(color=COL_SPR_C, width=1.5),
            fill="tozeroy", fillcolor="rgba(167,139,250,0.07)",
        ))
        fig_shspr_c.add_hline(y=0, line_dash="dash", line_color="white", line_width=1, opacity=0.3)
        fig_shspr_c.update_layout(**_plotly_base(240,
            "Spread Histórico  RT–CENACE  (USD/MWh diario)"), yaxis_title="USD/MWh")
        st.plotly_chart(fig_shspr_c, use_container_width=True, config={"displayModeBar": False})

    # ── Tabla horaria hoy ────────────────────────────────────────────────────
    st.markdown("#### Detalle horario — Hoy")
    rows_c = []
    for h in range(24):
        c_mx = cen_hoy_c[h]
        c_us = c_mx / tc if c_mx is not None else None
        da_v = da_hoy_c[h]
        fm_v = fmm_hoy_c[h]
        spr  = fm_v - c_us if fm_v is not None and c_us is not None else None
        rows_c.append({
            "Hora":                                  f"{h:02d}:00",
            f"DA {pair_c['caiso']} (USD/MWh)":        f"${da_v:.2f}"  if da_v is not None else "—",
            f"RT/FMM {pair_c['caiso']} (USD/MWh)":    f"${fm_v:.2f}"  if fm_v is not None else "—",
            f"PML {pair_c['cenace']} (MXN/MWh)":      f"${c_mx:.2f}"  if c_mx is not None else "—",
            f"PML {pair_c['cenace']} (USD/MWh)":       f"${c_us:.2f}" if c_us is not None else "—",
            "Spread RT–CENACE (USD/MWh)":              f"${spr:+.2f}" if spr is not None else "—",
        })
    st.dataframe(pd.DataFrame(rows_c), use_container_width=True, hide_index=True, height=360)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: Temperaturas
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Temperaturas":
    st.title("Temperaturas")

    ciudades_ca = {"TIJ": "Tijuana", "SND": "San Diego"}
    colores_ca  = [C_FMM, "#34d399"]

    @st.cache_data(ttl=1800, show_spinner=False)
    def _fetch_temps_caiso(_today_str: str) -> pd.DataFrame:
        CIUDADES_APP = {
            "TIJ": (32.5149, -117.0382),
            "SND": (32.7157, -117.1611),
        }
        FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
        dfs = []
        for ciudad, (lat, lon) in CIUDADES_APP.items():
            try:
                params = {
                    "latitude":      lat,
                    "longitude":     lon,
                    "hourly":        "temperature_2m",
                    "timezone":      "America/Los_Angeles",
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
        _fetch_temps_caiso.clear()

    with st.spinner("Cargando temperaturas..."):
        _df_live_ca = _fetch_temps_caiso(today_dt.strftime("%Y-%m-%d"))

    _use_live_ca = (not _df_live_ca.empty and
                    _df_live_ca["fecha"].max() >= pd.Timestamp(today_dt - timedelta(days=1)))
    df_t_ca = _df_live_ca if _use_live_ca else pd.DataFrame()
    _src_ca = "Open-Meteo live" if _use_live_ca else "Sin datos disponibles"

    _cutoff_ca = pd.Timestamp(today_dt - timedelta(days=2))
    df_t72_ca  = df_t_ca[df_t_ca["fecha"] >= _cutoff_ca].copy() if not df_t_ca.empty else df_t_ca

    fig_t_ca = go.Figure()
    for i, (col, label) in enumerate(ciudades_ca.items()):
        if col in df_t72_ca.columns:
            fig_t_ca.add_trace(go.Scatter(x=df_t72_ca["fecha"], y=df_t72_ca[col],
                                          name=label, line=dict(color=colores_ca[i], width=1.5)))
    fig_t_ca.update_layout(**_plotly_base(400, "Temperaturas ultimas 72h"), yaxis_title="°C")
    st.plotly_chart(fig_t_ca, use_container_width=True)
    st.caption(f"Fuente: {_src_ca}")

    if not df_t72_ca.empty:
        ultima_t_ca = df_t72_ca.iloc[-1]
        cols_t_ca = st.columns(len(ciudades_ca))
        for idx, (col, label) in enumerate(ciudades_ca.items()):
            if col in df_t72_ca.columns:
                val_t = ultima_t_ca[col]
                cols_t_ca[idx].metric(label, f"{val_t:.1f}°C" if val_t is not None and pd.notna(val_t) else "—")
    else:
        st.warning("Sin datos de temperatura disponibles.")


# ── Footer ─────────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    f"<div style='color:#2d3350; font-size:0.68rem; text-align:center;'>"
    f"XTS Energy Portal · Morning CAISO · "
    f"{'🔴 Demo' if not live_db else '🟢 Live'} · "
    f"{datetime.now().strftime('%d/%m/%Y %H:%M:%S')}</div>",
    unsafe_allow_html=True,
)
