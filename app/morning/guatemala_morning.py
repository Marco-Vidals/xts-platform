"""
Morning Dashboard Guatemala (AMM) — XTS Energy Portal
Correr con: streamlit run app/morning/guatemala_morning.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, date, timedelta
import io, json, urllib.request, requests, time, warnings
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

_XTS_IMG = f'<img src="{_xts_logo_uri(44)}" alt="XTS" style="height:44px;display:block;"/>'

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Morning Guatemala — XTS",
    page_icon="🇬🇹",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Session state ──────────────────────────────────────────────────────────────
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

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
        .block-container { padding-top: 0 !important; max-width: 100% !important; }
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
    </style>""", unsafe_allow_html=True)

    st.markdown(
        "<div style='position:fixed;top:16px;left:28px;z-index:999;display:flex;align-items:center;gap:10px;'>"
        + _XTS_IMG
        + "<div style='color:#4a5478;font-size:0.58rem;letter-spacing:2.5px;text-transform:uppercase;"
        "font-family:Segoe UI,sans-serif;align-self:flex-end;padding-bottom:5px;'>Energy Portal</div></div>",
        unsafe_allow_html=True,
    )
    st.markdown("<div style='height:28vh'></div>", unsafe_allow_html=True)
    st.markdown('<p style="text-align:center;color:#c0c4cc;font-size:1.2rem;font-family:Segoe UI;letter-spacing:0.4px;margin-bottom:20px;">Welcome to XTS Energy Portal</p>', unsafe_allow_html=True)

    _, col_form, _ = st.columns([1, 1.8, 1])
    with col_form:
        with st.form("login_form"):
            user = st.text_input("Usuario", placeholder="usuario@xiix.mx")
            pwd  = st.text_input("Contraseña", type="password", placeholder="••••••••")
            ok   = st.form_submit_button("Entrar")
        if ok:
            USERS = {"marco@xiix.mx": "xts2024", "admin@xiix.mx": "xts2024",
                     "mvidals@xiix.mx": "xts2024", "demo": "demo"}
            if USERS.get(user.strip().lower()) == pwd:
                st.session_state.logged_in = True
                st.session_state.auth = user
                st.rerun()
            else:
                st.error("Credenciales incorrectas")
    st.stop()


# ══════════════════════════════════════════════════════════════════════════════
# CSS GLOBAL
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("""<style>
    .stApp { background-color: #1a1e2e !important; }
    #MainMenu, footer, header { visibility: hidden !important; }
    .block-container { padding-top: 1rem !important; padding-bottom: 1rem !important; max-width: 100% !important; }
    html, body, [class*="css"] { color: #c0c4cc !important; font-family: 'Segoe UI', 'Consolas', monospace; }
    h1 { color: #00d4e8 !important; font-size: 1.4rem !important; font-weight: 700 !important;
         letter-spacing: 1.5px !important; text-transform: uppercase !important;
         border-bottom: 1px solid #2d3350 !important; padding-bottom: 0.5rem !important; margin-bottom: 1rem !important; }
    h2, h3, h4 { color: #c0c4cc !important; font-size: 0.95rem !important; letter-spacing: 1px !important; text-transform: uppercase !important; }
    p, span, div, label { color: #c0c4cc !important; }
    [data-testid="stSidebar"] { background-color: #12151f !important; border-right: 1px solid #2d3350 !important; }
    [data-testid="stSidebar"] * { color: #c0c4cc !important; }
    [data-testid="stSidebar"] [data-testid="stSelectbox"] > div > div {
        background-color: #2d3350 !important; border: 1px solid #3d4468 !important; border-radius: 4px !important; }
    [data-testid="stSidebar"] [data-testid="stSelectbox"] > div > div > div,
    [data-testid="stSidebar"] [data-testid="stSelectbox"] span { color: #00d4e8 !important; font-weight: 600 !important; font-size: 0.85rem !important; }
    [data-testid="stSidebar"] [data-testid="stSelectbox"] svg { fill: #00d4e8 !important; }
    [data-testid="stDataFrame"] { background-color: #1e2130 !important; border: 1px solid #2d3350 !important; border-radius: 4px !important; }
    [data-testid="stDataFrame"] * { color: #c0c4cc !important; font-size: 0.82rem !important; font-family: 'Consolas', monospace !important; }
    [data-testid="stDataFrame"] th { background-color: #12151f !important; color: #5a6280 !important; text-transform: uppercase !important; }
    ::-webkit-scrollbar { width: 5px; height: 5px; }
    ::-webkit-scrollbar-track { background: #1a1e2e; }
    ::-webkit-scrollbar-thumb { background: #2d3350; border-radius: 3px; }
    .kpi-card { background: #1e2130; border-radius: 6px; padding: 12px 16px;
                border: 1px solid #2d3350; border-left: 3px solid #00d4e8; }
    .kpi-label { color: #5a6280; font-size: 0.68rem; text-transform: uppercase; letter-spacing: 1.2px; font-weight: 600; }
    .kpi-value { color: #00d4e8; font-size: 1.5rem; font-weight: 700; font-family: Consolas, monospace; margin: 3px 0; }
    .kpi-delta-up   { color: #ff6b6b; font-size: 0.78rem; }
    .kpi-delta-down { color: #34d399; font-size: 0.78rem; }
    .kpi-sub  { color: #5a6280; font-size: 0.74rem; }
    .demo-banner { background: #1e1800; border: 1px solid #7a5c00; border-radius: 4px;
                   padding: 6px 14px; margin-bottom: 10px; color: #c8a200; font-size: 0.82rem; }
</style>""", unsafe_allow_html=True)

# ── Colores ────────────────────────────────────────────────────────────────────
PLOT_BG  = "#1e2130"
PAPER_BG = "#1e2130"
GRID_COL = "#2d3350"
FONT_COL = "#c0c4cc"

COL_POE = "#f59e0b"   # amber — POE AMM
COL_LBR = "#34d399"   # green — LBR CENACE
COL_REF = "#5a6280"   # muted gray — reference lines


# ══════════════════════════════════════════════════════════════════════════════
# CONSTANTES AMM / CENACE
# ══════════════════════════════════════════════════════════════════════════════
_MESES = {
    "01": "ENERO",   "02": "FEBRERO",  "03": "MARZO",
    "04": "ABRIL",   "05": "MAYO",     "06": "JUNIO",
    "07": "JULIO",   "08": "AGOSTO",   "09": "SEPTIEMBRE",
    "10": "OCTUBRE", "11": "NOVIEMBRE","12": "DICIEMBRE",
}
CENACE_BASE = "https://ws01.cenace.gob.mx:8082/SWPML/SIM"
NODO_LBR    = "09LBR-230"


# ══════════════════════════════════════════════════════════════════════════════
# FETCH LIVE — AMM POE
# ══════════════════════════════════════════════════════════════════════════════
def _amm_url(d: date) -> str:
    mm  = d.strftime("%m")
    return (
        f"https://www.amm.org.gt/pdfs2/programas_despacho/"
        f"01_PROGRAMAS_DE_DESPACHO_DIARIO/{d.year}/"
        f"01_PROGRAMAS_DE_DESPACHO_DIARIO/{mm}_{_MESES[mm]}/"
        f"WEB{d.strftime('%d%m%Y')}.xlsx"
    )


@st.cache_data(ttl=900, show_spinner=False)
def live_poe(d: date) -> list:
    """24 valores POE (USD/MWh) para la fecha dada. None si no disponible."""
    url = _amm_url(d)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
        df = pd.read_excel(io.BytesIO(data), sheet_name="POE", skiprows=8, header=None)
        poe = pd.to_numeric(df.iloc[0:24, 4], errors="coerce")
        return [float(v) if pd.notna(v) else None for v in poe.tolist()]
    except Exception as e:
        return [None] * 24


# ══════════════════════════════════════════════════════════════════════════════
# FETCH LIVE — CENACE LBR
# ══════════════════════════════════════════════════════════════════════════════
@st.cache_data(ttl=900, show_spinner=False)
def live_lbr(d: date) -> list:
    """24 valores PML MDA del nodo 09LBR-230 (MXN/MWh). None si no disponible."""
    url = (f"{CENACE_BASE}/SIN/MDA/{NODO_LBR}/"
           f"{d.year}/{d.month:02d}/{d.day:02d}/"
           f"{d.year}/{d.month:02d}/{d.day:02d}/JSON")
    try:
        resp = requests.get(url, timeout=30, verify=False)
        valores = resp.json()["Resultados"][0]["Valores"]
        vals = [float(v["pml"]) for v in valores]
        # pad/trim to 24
        while len(vals) < 24:
            vals.append(None)
        return vals[:24]
    except Exception:
        return [None] * 24


# ══════════════════════════════════════════════════════════════════════════════
# CARGA HISTORICA DB
# ══════════════════════════════════════════════════════════════════════════════
@st.cache_data(ttl=600, show_spinner=False)
def load_gtm_hist(days: int = 14) -> tuple[pd.DataFrame, bool]:
    """Retorna (df, is_live). Columnas: fecha, PPOE, LBR."""
    try:
        from etl.common.db_connection import get_connection
        conn = get_connection("XTS")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            df = pd.read_sql(
                f"SELECT TOP {days * 24} fecha, PPOE, LBR FROM dbo.GTM ORDER BY fecha DESC",
                conn,
            )
        conn.close()
        df["fecha"] = pd.to_datetime(df["fecha"])
        df = df.sort_values("fecha").reset_index(drop=True)
        if not df.empty:
            return df, True
    except Exception as e:
        pass
    return pd.DataFrame(columns=["fecha", "PPOE", "LBR"]), False


# ══════════════════════════════════════════════════════════════════════════════
# PLOTLY BASE
# ══════════════════════════════════════════════════════════════════════════════
def _plotly_base(title: str = "", height: int = 320) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(
        title=dict(text=title, font=dict(size=13, color=FONT_COL), x=0.01),
        paper_bgcolor=PAPER_BG,
        plot_bgcolor=PLOT_BG,
        font=dict(color=FONT_COL, size=11),
        margin=dict(l=48, r=16, t=36, b=36),
        height=height,
        xaxis=dict(gridcolor=GRID_COL, showgrid=True, zeroline=False, color=FONT_COL),
        yaxis=dict(gridcolor=GRID_COL, showgrid=True, zeroline=False, color=FONT_COL),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                    font=dict(size=10, color="#ffffff")),
    )
    return fig


HOURS = [f"{h:02d}:00" for h in range(24)]


# ══════════════════════════════════════════════════════════════════════════════
# CHARTS — POE HOY (solid pasado / punteado futuro)
# ══════════════════════════════════════════════════════════════════════════════
def poe_today_chart(poe_ayer: list, poe_hoy: list, poe_manana: list) -> go.Figure:
    now_h = datetime.now().hour  # horas ya transcurridas hoy

    # Hoy: solid hasta now_h, punteado desde now_h
    solid = [poe_hoy[i] if i < now_h and poe_hoy[i] is not None else None for i in range(24)]
    dash  = [poe_hoy[i] if i >= now_h and poe_hoy[i] is not None else None for i in range(24)]
    # Conectar solid → dash: incluir now_h en solid si existe
    if now_h < 24 and poe_hoy[now_h] is not None:
        solid[now_h] = poe_hoy[now_h]

    fig = _plotly_base("POE — Precio de Oferta de Energía (USD/MWh)", height=340)

    # Ayer
    fig.add_trace(go.Scatter(
        x=HOURS, y=poe_ayer, name="Ayer",
        line=dict(color=COL_REF, width=1.5, dash="dot"),
        connectgaps=False, opacity=0.6,
    ))
    # Hoy sólido
    fig.add_trace(go.Scatter(
        x=HOURS, y=solid, name="Hoy (real)",
        line=dict(color=COL_POE, width=2.5),
        connectgaps=False,
    ))
    # Hoy punteado
    fig.add_trace(go.Scatter(
        x=HOURS, y=dash, name="Hoy (programa)",
        line=dict(color=COL_POE, width=2, dash="dot"),
        connectgaps=False, showlegend=False,
    ))
    # Mañana
    if any(v is not None for v in poe_manana):
        fig.add_trace(go.Scatter(
            x=HOURS, y=poe_manana, name="Mañana",
            line=dict(color="#60a5fa", width=1.8, dash="dot"),
            connectgaps=False,
        ))

    # Línea "ahora"
    if 0 < now_h < 24:
        fig.add_vline(x=HOURS[now_h], line_dash="dot", line_color="#5a6280", line_width=1)

    fig.update_layout(yaxis_title="USD/MWh")
    return fig


# ══════════════════════════════════════════════════════════════════════════════
# CHART — LBR HOY
# ══════════════════════════════════════════════════════════════════════════════
def lbr_today_chart(lbr_ayer: list, lbr_hoy: list) -> go.Figure:
    now_h = datetime.now().hour
    solid = [lbr_hoy[i] if i < now_h and lbr_hoy[i] is not None else None for i in range(24)]
    dash  = [lbr_hoy[i] if i >= now_h and lbr_hoy[i] is not None else None for i in range(24)]
    if now_h < 24 and lbr_hoy[now_h] is not None:
        solid[now_h] = lbr_hoy[now_h]

    fig = _plotly_base("LBR CENACE — Nodo 09LBR-230 PML MDA (MXN/MWh)", height=340)

    fig.add_trace(go.Scatter(
        x=HOURS, y=lbr_ayer, name="Ayer",
        line=dict(color=COL_REF, width=1.5, dash="dot"),
        connectgaps=False, opacity=0.6,
    ))
    fig.add_trace(go.Scatter(
        x=HOURS, y=solid, name="Hoy (real)",
        line=dict(color=COL_LBR, width=2.5),
        connectgaps=False,
    ))
    fig.add_trace(go.Scatter(
        x=HOURS, y=dash, name="Hoy (MDA)",
        line=dict(color=COL_LBR, width=2, dash="dot"),
        connectgaps=False, showlegend=False,
    ))

    if 0 < now_h < 24:
        fig.add_vline(x=HOURS[now_h], line_dash="dot", line_color="#5a6280", line_width=1)

    fig.update_layout(yaxis_title="MXN/MWh")
    return fig


# ══════════════════════════════════════════════════════════════════════════════
# CHART — HISTORICO MULTI-DIA
# ══════════════════════════════════════════════════════════════════════════════
def hist_chart(df: pd.DataFrame, col: str, title: str, color: str,
               y_label: str, height: int = 300) -> go.Figure:
    if df.empty or col not in df.columns:
        fig = _plotly_base(title, height)
        return fig

    sub = df[["fecha", col]].dropna()
    fig = _plotly_base(title, height)
    fig.add_trace(go.Scatter(
        x=sub["fecha"], y=sub[col], name=col,
        line=dict(color=color, width=1.8),
        fill="tozeroy", fillcolor=color.replace(")", ",0.08)").replace("rgb", "rgba"),
        connectgaps=False,
    ))
    fig.update_layout(yaxis_title=y_label)
    return fig


def hist_dual_chart(df: pd.DataFrame, title: str, tc: float = 17.5, height: int = 320) -> go.Figure:
    """POE + LBR (convertido a USD) en el mismo eje para comparación directa."""
    fig = _plotly_base(title, height)
    if df.empty:
        return fig

    sub_poe = df[["fecha", "PPOE"]].dropna()
    sub_lbr = df[["fecha", "LBR"]].dropna().copy()
    sub_lbr["LBR_USD"] = sub_lbr["LBR"] / tc

    if not sub_poe.empty:
        fig.add_trace(go.Scatter(
            x=sub_poe["fecha"], y=sub_poe["PPOE"], name="POE (USD/MWh)",
            line=dict(color=COL_POE, width=1.8),
        ))
    if not sub_lbr.empty:
        fig.add_trace(go.Scatter(
            x=sub_lbr["fecha"], y=sub_lbr["LBR_USD"], name="LBR (USD/MWh equiv.)",
            line=dict(color=COL_LBR, width=1.8),
        ))

    fig.update_layout(
        yaxis=dict(title="USD/MWh", gridcolor=GRID_COL, color=FONT_COL),
    )
    return fig


# ══════════════════════════════════════════════════════════════════════════════
# KPI CARD HELPER
# ══════════════════════════════════════════════════════════════════════════════
def kpi(label: str, value: str, sub: str = "", delta: str = "", up: bool | None = None) -> str:
    delta_cls = ""
    if up is True:   delta_cls = "kpi-delta-up"
    if up is False:  delta_cls = "kpi-delta-down"
    delta_html = f'<div class="{delta_cls}">{delta}</div>' if delta else ""
    return (
        f'<div class="kpi-card">'
        f'<div class="kpi-label">{label}</div>'
        f'<div class="kpi-value">{value}</div>'
        f'{delta_html}'
        f'<div class="kpi-sub">{sub}</div>'
        f'</div>'
    )


def _safe_avg(vals: list) -> float | None:
    v = [x for x in vals if x is not None]
    return sum(v) / len(v) if v else None


def _fmt(v, fmt=".2f", na="—"):
    return f"{v:{fmt}}" if v is not None else na


# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    # Guatemala flag SVG
    flag_svg = (
        '<svg width="32" height="22" viewBox="0 0 32 22" xmlns="http://www.w3.org/2000/svg">'
        '<rect width="11" height="22" fill="#4997D0"/>'
        '<rect x="11" width="10" height="22" fill="#FFFFFF"/>'
        '<rect x="21" width="11" height="22" fill="#4997D0"/>'
        '</svg>'
    )
    flag_b64 = _b64c.b64encode(flag_svg.encode()).decode()
    flag_uri = f"data:image/svg+xml;base64,{flag_b64}"

    st.markdown(
        f"<div style='text-align:center;padding:14px 0 4px 0;'>"
        + _XTS_IMG
        + f"<div style='display:flex;align-items:center;justify-content:center;gap:8px;margin-top:8px;'>"
        f"<img src='{flag_uri}' style='height:18px;border-radius:2px;'/>"
        "<div style='color:#4a5478;font-size:0.6rem;letter-spacing:2.5px;text-transform:uppercase;"
        "font-family:Segoe UI,sans-serif;'>GUATEMALA · AMM</div>"
        f"</div></div>",
        unsafe_allow_html=True,
    )
    st.divider()

    page = st.selectbox(
        "Página",
        ["Resumen", "POE — AMM", "LBR — CENACE"],
        key="gtm_page",
    )

    st.divider()
    if st.button("Cerrar Sesión", use_container_width=True):
        st.session_state.logged_in = False
        st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# CARGA DE DATOS
# ══════════════════════════════════════════════════════════════════════════════
hoy    = date.today()
ayer   = hoy - timedelta(days=1)
manana = hoy + timedelta(days=1)

with st.spinner("Cargando datos Guatemala..."):
    poe_hoy_vals    = live_poe(hoy)
    poe_ayer_vals   = live_poe(ayer)
    poe_manana_vals = live_poe(manana)
    lbr_hoy_vals    = live_lbr(hoy)
    lbr_ayer_vals   = live_lbr(ayer)
    df_hist, is_live = load_gtm_hist(90)
    try:
        from app.morning.data_loader import load_tipo_cambio as _load_tc
        tc, _ = _load_tc()
    except Exception:
        tc = 17.50

# ── Header ─────────────────────────────────────────────────────────────────────
_now_str = datetime.now().strftime("%A %d %B %Y  %H:%M")
st.markdown(
    "<div style='display:flex;align-items:center;justify-content:space-between;"
    "padding:0 4px 12px 4px;border-bottom:1px solid #1e2540;margin-bottom:20px;'>"
    "<div style='color:#c0c4cc;font-size:1rem;font-weight:700;letter-spacing:1px;'>🇬🇹 GUATEMALA — AMM Morning</div>"
    + f"<div style='color:#4a5070;font-size:0.68rem;'>{_now_str} CT</div></div>",
    unsafe_allow_html=True,
)

if not is_live:
    st.markdown('<div class="demo-banner">⚠ BD no disponible — datos históricos no cargados</div>',
                unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# PÁGINA: RESUMEN
# ══════════════════════════════════════════════════════════════════════════════
if page == "Resumen":
    _tl, _tr = st.columns([4, 1])
    with _tr:
        dias_hist = st.slider("Días histórico", 1, 90, 30, key="gtm_res_dias")
    _cutoff  = pd.Timestamp.now().normalize() - pd.Timedelta(days=dias_hist)
    df_hist  = df_hist[df_hist["fecha"] >= _cutoff]

    # ── KPIs ─────────────────────────────────────────────────────────────────
    avg_poe_hoy  = _safe_avg(poe_hoy_vals)
    avg_poe_ayer = _safe_avg(poe_ayer_vals)
    avg_lbr_hoy  = _safe_avg(lbr_hoy_vals)
    avg_lbr_ayer = _safe_avg(lbr_ayer_vals)

    # Última hora con dato para POE y LBR
    now_h = datetime.now().hour
    last_poe = next((poe_hoy_vals[h] for h in range(min(now_h, 23), -1, -1)
                     if poe_hoy_vals[h] is not None), None)
    last_lbr = next((lbr_hoy_vals[h] for h in range(min(now_h, 23), -1, -1)
                     if lbr_hoy_vals[h] is not None), None)

    # Delta POE
    if avg_poe_hoy and avg_poe_ayer:
        d_poe_pct = (avg_poe_hoy - avg_poe_ayer) / avg_poe_ayer * 100
        d_poe_str = f"{'▲' if d_poe_pct >= 0 else '▼'} {abs(d_poe_pct):.1f}% vs ayer"
        poe_up    = d_poe_pct >= 0
    else:
        d_poe_str, poe_up = "", None

    if avg_lbr_hoy and avg_lbr_ayer:
        d_lbr_pct = (avg_lbr_hoy - avg_lbr_ayer) / avg_lbr_ayer * 100
        d_lbr_str = f"{'▲' if d_lbr_pct >= 0 else '▼'} {abs(d_lbr_pct):.1f}% vs ayer"
        lbr_up    = d_lbr_pct >= 0
    else:
        d_lbr_str, lbr_up = "", None

    # Mañana programa
    avg_poe_man = _safe_avg(poe_manana_vals)

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.markdown(kpi("POE Hoy — Prom",
                        f"${_fmt(avg_poe_hoy)} USD/MWh",
                        f"Última hora: ${_fmt(last_poe)}",
                        d_poe_str, poe_up), unsafe_allow_html=True)
    with k2:
        st.markdown(kpi("POE Mañana — Prom",
                        f"${_fmt(avg_poe_man)} USD/MWh",
                        "Programa de despacho AMM",
                        "", None), unsafe_allow_html=True)
    with k3:
        st.markdown(kpi("LBR Hoy — Prom",
                        f"${_fmt(avg_lbr_hoy)} MXN/MWh",
                        f"Nodo 09LBR-230 · CENACE MDA",
                        d_lbr_str, lbr_up), unsafe_allow_html=True)
    with k4:
        poe_h = poe_hoy_vals[min(now_h, 23)]
        lbr_h = lbr_hoy_vals[min(now_h, 23)]
        if poe_h is not None and lbr_h is not None:
            spread_usd = poe_h - lbr_h / tc
            spread_str = f"${spread_usd:+.2f} USD/MWh"
        else:
            spread_str = "—"
        st.markdown(kpi("Spread POE – LBR",
                        spread_str,
                        f"Hora {now_h:02d}:00 CT · LBR÷TC",
                        "", None), unsafe_allow_html=True)

    st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)

    # ── Gráficas HOY ─────────────────────────────────────────────────────────
    col_a, col_b = st.columns(2)
    with col_a:
        st.plotly_chart(
            poe_today_chart(poe_ayer_vals, poe_hoy_vals, poe_manana_vals),
            use_container_width=True, config={"displayModeBar": False},
        )
    with col_b:
        st.plotly_chart(
            lbr_today_chart(lbr_ayer_vals, lbr_hoy_vals),
            use_container_width=True, config={"displayModeBar": False},
        )

    # ── Histórico dual ────────────────────────────────────────────────────────
    if not df_hist.empty:
        st.plotly_chart(
            hist_dual_chart(df_hist, f"POE & LBR — Últimos {dias_hist} días", tc=tc),
            use_container_width=True, config={"displayModeBar": False},
        )

    # ── Tabla de hoy ──────────────────────────────────────────────────────────
    st.markdown("#### Programa de Despacho — Hoy")
    rows = []
    for h in range(24):
        lbr_v  = lbr_hoy_vals[h]
        rows.append({
            "Hora":             f"{h:02d}:00",
            "POE (USD/MWh)":    f"${poe_hoy_vals[h]:.2f}" if poe_hoy_vals[h] is not None else "—",
            "LBR (MXN/MWh)":   f"${lbr_v:.2f}" if lbr_v is not None else "—",
            "LBR (USD/MWh)":   f"${lbr_v/tc:.2f}" if lbr_v is not None else "—",
            "Spread (USD/MWh)": f"${poe_hoy_vals[h] - lbr_v/tc:+.2f}"
                                if poe_hoy_vals[h] is not None and lbr_v is not None else "—",
            "POE Mañana":       f"${poe_manana_vals[h]:.2f}" if poe_manana_vals[h] is not None else "—",
        })
    df_tabla = pd.DataFrame(rows)
    st.dataframe(df_tabla, use_container_width=True, hide_index=True, height=360)


# ══════════════════════════════════════════════════════════════════════════════
# PÁGINA: POE AMM
# ══════════════════════════════════════════════════════════════════════════════
elif page == "POE — AMM":
    _tl, _tr = st.columns([4, 1])
    with _tl:
        st.markdown("# POE — Programa de Despacho Diario (AMM)")
    with _tr:
        dias_hist = st.slider("Días histórico", 1, 90, 30, key="gtm_poe_dias")
    _cutoff  = pd.Timestamp.now().normalize() - pd.Timedelta(days=dias_hist)
    df_hist  = df_hist[df_hist["fecha"] >= _cutoff]

    # ── Gráfica hoy ───────────────────────────────────────────────────────────
    st.plotly_chart(
        poe_today_chart(poe_ayer_vals, poe_hoy_vals, poe_manana_vals),
        use_container_width=True, config={"displayModeBar": False},
    )

    # ── KPIs horarios ─────────────────────────────────────────────────────────
    peak_h = max(range(24), key=lambda i: poe_hoy_vals[i] or 0)
    off_h  = min(range(24), key=lambda i: poe_hoy_vals[i] or 9999 if poe_hoy_vals[i] else 9999)
    k1, k2, k3 = st.columns(3)
    with k1:
        st.markdown(kpi("POE Pico",
                        f"${_fmt(poe_hoy_vals[peak_h])} USD/MWh",
                        f"Hora {peak_h:02d}:00"), unsafe_allow_html=True)
    with k2:
        st.markdown(kpi("POE Valle",
                        f"${_fmt(poe_hoy_vals[off_h])} USD/MWh",
                        f"Hora {off_h:02d}:00"), unsafe_allow_html=True)
    with k3:
        st.markdown(kpi("POE Mañana Prom",
                        f"${_fmt(_safe_avg(poe_manana_vals))} USD/MWh",
                        "Programa de despacho AMM"), unsafe_allow_html=True)

    st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)

    # ── Histórico POE ─────────────────────────────────────────────────────────
    if not df_hist.empty and "PPOE" in df_hist.columns:
        fig_h = _plotly_base(f"POE Histórico — Últimos {dias_hist} días", height=280)
        sub = df_hist[["fecha", "PPOE"]].dropna()
        fig_h.add_trace(go.Scatter(
            x=sub["fecha"], y=sub["PPOE"], name="POE",
            line=dict(color=COL_POE, width=1.8),
            fill="tozeroy",
            fillcolor="rgba(245,158,11,0.07)",
        ))
        fig_h.update_layout(yaxis_title="USD/MWh")
        st.plotly_chart(fig_h, use_container_width=True, config={"displayModeBar": False})

        # Stats
        sub_vals = sub["PPOE"]
        s1, s2, s3, s4 = st.columns(4)
        with s1: st.markdown(kpi("Promedio", f"${sub_vals.mean():.2f} USD/MWh", f"Últimos {dias_hist} días"), unsafe_allow_html=True)
        with s2: st.markdown(kpi("Máximo",   f"${sub_vals.max():.2f} USD/MWh", f"{sub.loc[sub_vals.idxmax(), 'fecha'].strftime('%d %b %H:00')}"), unsafe_allow_html=True)
        with s3: st.markdown(kpi("Mínimo",   f"${sub_vals.min():.2f} USD/MWh", f"{sub.loc[sub_vals.idxmin(), 'fecha'].strftime('%d %b %H:00')}"), unsafe_allow_html=True)
        with s4: st.markdown(kpi("Volatilidad", f"${sub_vals.std():.2f}", "Desv. estándar"), unsafe_allow_html=True)
    else:
        st.info("No hay datos históricos disponibles en BD.")

    # ── Mapa de calor POE por día/hora ────────────────────────────────────────
    if not df_hist.empty and "PPOE" in df_hist.columns:
        st.markdown("#### Mapa de calor — POE por Día y Hora")
        df_h = df_hist[["fecha", "PPOE"]].dropna().copy()
        df_h["dia"]  = df_h["fecha"].dt.date
        df_h["hora"] = df_h["fecha"].dt.hour
        pivot = df_h.pivot_table(index="hora", columns="dia", values="PPOE", aggfunc="mean")
        dias_str = [str(d) for d in pivot.columns]

        fig_hm = go.Figure(go.Heatmap(
            z=pivot.values,
            x=dias_str,
            y=[f"{h:02d}:00" for h in pivot.index],
            colorscale="YlOrRd",
            colorbar=dict(title="USD/MWh", tickfont=dict(color=FONT_COL), titlefont=dict(color=FONT_COL)),
        ))
        fig_hm.update_layout(
            paper_bgcolor=PAPER_BG, plot_bgcolor=PLOT_BG,
            font=dict(color=FONT_COL, size=10),
            margin=dict(l=60, r=10, t=20, b=40),
            height=380,
            xaxis=dict(color=FONT_COL),
            yaxis=dict(color=FONT_COL, autorange="reversed"),
        )
        st.plotly_chart(fig_hm, use_container_width=True, config={"displayModeBar": False})


# ══════════════════════════════════════════════════════════════════════════════
# PÁGINA: LBR CENACE
# ══════════════════════════════════════════════════════════════════════════════
elif page == "LBR — CENACE":
    _tl, _tr = st.columns([4, 1])
    with _tl:
        st.markdown("# LBR — Nodo 09LBR-230 · PML MDA CENACE (SIN)")
    with _tr:
        dias_hist = st.slider("Días histórico", 1, 90, 30, key="gtm_lbr_dias")
    _cutoff  = pd.Timestamp.now().normalize() - pd.Timedelta(days=dias_hist)
    df_hist  = df_hist[df_hist["fecha"] >= _cutoff]

    # ── Gráfica hoy ───────────────────────────────────────────────────────────
    st.plotly_chart(
        lbr_today_chart(lbr_ayer_vals, lbr_hoy_vals),
        use_container_width=True, config={"displayModeBar": False},
    )

    # ── KPIs ──────────────────────────────────────────────────────────────────
    valid_lbr = [v for v in lbr_hoy_vals if v is not None]
    peak_lbr  = max(range(24), key=lambda i: lbr_hoy_vals[i] or 0) if valid_lbr else 0
    off_lbr   = min(range(24), key=lambda i: lbr_hoy_vals[i] or 9999 if lbr_hoy_vals[i] else 9999) if valid_lbr else 0
    k1, k2, k3 = st.columns(3)
    with k1:
        st.markdown(kpi("LBR Pico",
                        f"${_fmt(lbr_hoy_vals[peak_lbr])} MXN/MWh",
                        f"Hora {peak_lbr:02d}:00"), unsafe_allow_html=True)
    with k2:
        st.markdown(kpi("LBR Valle",
                        f"${_fmt(lbr_hoy_vals[off_lbr])} MXN/MWh",
                        f"Hora {off_lbr:02d}:00"), unsafe_allow_html=True)
    with k3:
        avg_lbr = _safe_avg(lbr_hoy_vals)
        try:
            from app.morning.data_loader import load_tipo_cambio
            tc, _ = load_tipo_cambio()
            lbr_usd = f"≈ ${avg_lbr/tc:.2f} USD/MWh" if avg_lbr else "—"
        except Exception:
            lbr_usd = "—"
        st.markdown(kpi("LBR Prom (USD equiv.)",
                        lbr_usd,
                        "Tipo cambio Banxico"), unsafe_allow_html=True)

    st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)

    # ── Histórico LBR ─────────────────────────────────────────────────────────
    if not df_hist.empty and "LBR" in df_hist.columns:
        fig_h = _plotly_base(f"LBR Histórico — Últimos {dias_hist} días", height=280)
        sub = df_hist[["fecha", "LBR"]].dropna()
        fig_h.add_trace(go.Scatter(
            x=sub["fecha"], y=sub["LBR"], name="LBR",
            line=dict(color=COL_LBR, width=1.8),
            fill="tozeroy",
            fillcolor="rgba(52,211,153,0.07)",
        ))
        fig_h.update_layout(yaxis_title="MXN/MWh")
        st.plotly_chart(fig_h, use_container_width=True, config={"displayModeBar": False})

        sub_vals = sub["LBR"]
        s1, s2, s3, s4 = st.columns(4)
        with s1: st.markdown(kpi("Promedio", f"${sub_vals.mean():.2f} MXN/MWh", f"Últimos {dias_hist} días"), unsafe_allow_html=True)
        with s2: st.markdown(kpi("Máximo",   f"${sub_vals.max():.2f} MXN/MWh", f"{sub.loc[sub_vals.idxmax(), 'fecha'].strftime('%d %b %H:00')}"), unsafe_allow_html=True)
        with s3: st.markdown(kpi("Mínimo",   f"${sub_vals.min():.2f} MXN/MWh", f"{sub.loc[sub_vals.idxmin(), 'fecha'].strftime('%d %b %H:00')}"), unsafe_allow_html=True)
        with s4: st.markdown(kpi("Volatilidad", f"${sub_vals.std():.2f}", "Desv. estándar"), unsafe_allow_html=True)
    else:
        st.info("No hay datos históricos disponibles en BD.")

    # ── Componentes LBR ─────────────────────────────────────────────────────
    st.markdown("#### Componentes del PML — Nodo 09LBR-230 (hoy)")

    @st.cache_data(ttl=900, show_spinner=False)
    def live_lbr_components(d: date) -> pd.DataFrame:
        url = (f"{CENACE_BASE}/SIN/MDA/{NODO_LBR}/"
               f"{d.year}/{d.month:02d}/{d.day:02d}/"
               f"{d.year}/{d.month:02d}/{d.day:02d}/JSON")
        try:
            resp = requests.get(url, timeout=30, verify=False)
            valores = resp.json()["Resultados"][0]["Valores"]
            rows = []
            for v in valores:
                rows.append({
                    "hora":    int(v.get("hora", 0)) - 1,
                    "pz":      float(v.get("pml",     0) or 0),
                    "pz_ene":  float(v.get("pml_ene", 0) or 0),
                    "pz_per":  float(v.get("pml_per", 0) or 0),
                    "pz_cng":  float(v.get("pml_cng", 0) or 0),
                })
            return pd.DataFrame(rows).sort_values("hora")
        except Exception:
            return pd.DataFrame()

    df_comp = live_lbr_components(hoy)
    if not df_comp.empty:
        fig_comp = _plotly_base("Componentes PML — ENE / PER / CNG", height=300)
        hours_comp = [f"{int(h):02d}:00" for h in df_comp["hora"]]
        fig_comp.add_trace(go.Bar(x=hours_comp, y=df_comp["pz_ene"], name="Energía",
                                   marker_color="#60a5fa"))
        fig_comp.add_trace(go.Bar(x=hours_comp, y=df_comp["pz_per"], name="Pérdidas",
                                   marker_color=COL_POE))
        fig_comp.add_trace(go.Bar(x=hours_comp, y=df_comp["pz_cng"], name="Congestión",
                                   marker_color="#f87171"))
        fig_comp.add_trace(go.Scatter(x=hours_comp, y=df_comp["pz"], name="PML Total",
                                       line=dict(color=COL_LBR, width=2.5)))
        fig_comp.update_layout(barmode="stack", yaxis_title="MXN/MWh")
        st.plotly_chart(fig_comp, use_container_width=True, config={"displayModeBar": False})
    else:
        st.info("Componentes no disponibles — API CENACE sin datos para hoy.")

    # ── Mapa de calor LBR ─────────────────────────────────────────────────────
    if not df_hist.empty and "LBR" in df_hist.columns:
        st.markdown("#### Mapa de calor — LBR por Día y Hora")
        df_h = df_hist[["fecha", "LBR"]].dropna().copy()
        df_h["dia"]  = df_h["fecha"].dt.date
        df_h["hora"] = df_h["fecha"].dt.hour
        pivot = df_h.pivot_table(index="hora", columns="dia", values="LBR", aggfunc="mean")
        dias_str = [str(d) for d in pivot.columns]

        fig_hm = go.Figure(go.Heatmap(
            z=pivot.values,
            x=dias_str,
            y=[f"{h:02d}:00" for h in pivot.index],
            colorscale="Teal",
            colorbar=dict(title="MXN/MWh", tickfont=dict(color=FONT_COL), titlefont=dict(color=FONT_COL)),
        ))
        fig_hm.update_layout(
            paper_bgcolor=PAPER_BG, plot_bgcolor=PLOT_BG,
            font=dict(color=FONT_COL, size=10),
            margin=dict(l=60, r=10, t=20, b=40),
            height=380,
            xaxis=dict(color=FONT_COL),
            yaxis=dict(color=FONT_COL, autorange="reversed"),
        )
        st.plotly_chart(fig_hm, use_container_width=True, config={"displayModeBar": False})
