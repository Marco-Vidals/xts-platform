"""
Morning Dashboard CENACE — XTS Energy Portal
Correr con: streamlit run app/morning/cenace_morning.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, date, timedelta
import requests, time
import urllib3, base64 as _b64c

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
    enc = _b64c.b64encode(svg.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{enc}"

_XTS_IMG = f'<img src="{_xts_logo_uri(44)}" alt="XTS" style="height:44px;display:block;"/>'

from app.morning.data_loader import load_caiso, load_tipo_cambio

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Morning CENACE — XTS",
    page_icon="🇲🇽",
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
    .kpi-delta-down { color: #00d4e8; font-size: 0.78rem; }
    .kpi-sub  { color: #5a6280; font-size: 0.74rem; }
    .demo-banner { background: #1e1800; border: 1px solid #7a5c00; border-radius: 4px;
                   padding: 6px 14px; margin-bottom: 10px; color: #c8a200; font-size: 0.82rem; }
    .tag-mxn { background:#3a1a2a; color:#f87171; padding:2px 6px; border-radius:3px; font-size:0.7rem; }
    .tag-usd { background:#1a3a2a; color:#34d399; padding:2px 6px; border-radius:3px; font-size:0.7rem; }
</style>""", unsafe_allow_html=True)

# ── Colores ────────────────────────────────────────────────────────────────────
PLOT_BG  = "#1e2130"
PAPER_BG = "#1e2130"
GRID_COL = "#2d3350"
FONT_COL = "#c0c4cc"
C_DCL    = "#00d4e8"
C_DCR    = "#FF6B35"
C_IVY    = "#6FA0D8"
C_OMS    = "#B7D433"
C_MDA    = "#00d4e8"
C_MTR    = "#FF6B35"


def _plotly_base(height=380, title=""):
    return dict(
        plot_bgcolor=PLOT_BG, paper_bgcolor=PAPER_BG,
        font=dict(color=FONT_COL, size=11),
        height=height,
        title=dict(text=title, font=dict(size=13, color=FONT_COL)),
        xaxis=dict(gridcolor=GRID_COL, showgrid=True),
        yaxis=dict(gridcolor=GRID_COL, showgrid=True),
        hovermode="x unified",
        margin=dict(l=60, r=20, t=50, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                    font=dict(size=10, color="#ffffff")),
    )


def kpi(label, val, prev=None, fmt="${:.2f}", color=C_DCL, tag=""):
    if val is None or (isinstance(val, float) and np.isnan(val)):
        v_str = "—"
        delta_html = ""
    else:
        v_str = fmt.format(val)
        if prev is not None and not (isinstance(prev, float) and np.isnan(prev)) and prev != 0:
            d = val - prev
            pct = d / abs(prev) * 100
            cls = "kpi-delta-up" if d > 0 else "kpi-delta-down"
            delta_html = f'<span class="{cls}">{"▲" if d>0 else "▼"} {abs(pct):.1f}%</span>'
        else:
            delta_html = ""
    return (
        f'<div class="kpi-card" style="border-left-color:{color}">'
        f'<div class="kpi-label">{label} {tag}</div>'
        f'<div class="kpi-value" style="color:{color}">{v_str}</div>'
        f'{delta_html}</div>'
    )


# ── CENACE API (JSON) ──────────────────────────────────────────────────────────
CENACE_URL = "https://ws01.cenace.gob.mx:8082/SWPML/SIM/{sistema}/{proceso}/{nodo}/{ai}/{mi}/{di}/{af}/{mf}/{df}/JSON"


@st.cache_data(ttl=300, show_spinner=False)
def live_pml(sistema: str, proceso: str, nodo: str, dias: int = 7, end_lag: int = 0) -> pd.DataFrame:
    """Fetch PML CENACE para un nodo. Divide en chunks de 7 dias.
    end_lag: días de retraso en la fecha final (MTR publica con ~3 días de lag)."""
    fin = date.today() - timedelta(days=end_lag)
    ini = fin - timedelta(days=dias - 1)
    frames = []
    cur = ini
    while cur <= fin:
        chunk_fin = min(cur + timedelta(days=6), fin)
        url = CENACE_URL.format(
            sistema=sistema, proceso=proceso, nodo=nodo,
            ai=cur.year,       mi=f"{cur.month:02d}",       di=f"{cur.day:02d}",
            af=chunk_fin.year, mf=f"{chunk_fin.month:02d}", df=f"{chunk_fin.day:02d}",
        )
        try:
            r = requests.get(url, timeout=30, verify=False)
            js = r.json()
            if js.get("status") == "OK":
                for res in js.get("Resultados", []):
                    for v in res.get("Valores", []):
                        try:
                            hora = int(v.get("hora", 1)) - 1
                            fecha = pd.to_datetime(v["fecha"]) + pd.to_timedelta(hora, unit="h")
                            frames.append({
                                "fecha":  fecha,
                                "pz":     float(v.get("pml", 0) or 0),
                                "pz_ene": float(v.get("pml_ene", 0) or 0),
                                "pz_per": float(v.get("pml_per", 0) or 0),
                                "pz_cng": float(v.get("pml_cng", 0) or 0),
                            })
                        except Exception:
                            pass
        except Exception as e:
            pass
        cur = chunk_fin + timedelta(days=1)

    if not frames:
        return pd.DataFrame(columns=["fecha", "pz", "pz_ene", "pz_per", "pz_cng"])
    df = pd.DataFrame(frames).drop_duplicates("fecha").sort_values("fecha").reset_index(drop=True)
    return df


@st.cache_data(ttl=600, show_spinner=False)
def live_zonas_hoy(proceso: str = "MDA") -> pd.DataFrame:
    """Fetch MDA de hoy para todas las zonas de SIN. Retorna df con nodo y pz promedio del dia."""
    from etl.cenace.nodes_list import ZONAS
    from itertools import islice

    def batches(it, n):
        it = iter(it)
        while True:
            b = list(islice(it, n))
            if not b: break
            yield b

    fin = date.today()
    ini = fin - timedelta(days=1)
    rows = []

    for sistema in ["SIN", "BCA", "BCS"]:
        nodos_sis = [z for z, s in ZONAS if s == sistema]
        for batch in batches(nodos_sis, 20):
            nodo_str = ",".join(batch)
            url = CENACE_URL.format(
                sistema=sistema, proceso=proceso, nodo=nodo_str,
                ai=ini.year, mi=f"{ini.month:02d}", di=f"{ini.day:02d}",
                af=fin.year, mf=f"{fin.month:02d}", df=f"{fin.day:02d}",
            )
            try:
                r = requests.get(url, timeout=30, verify=False)
                js = r.json()
                if js.get("status") == "OK":
                    for res in js.get("Resultados", []):
                        nodo = res.get("clv_nodo", "")
                        vals = [float(v.get("pml", 0) or 0) for v in res.get("Valores", []) if v.get("pml")]
                        if vals:
                            rows.append({"nodo": nodo, "sistema": sistema,
                                         "pz_prom": np.mean(vals),
                                         "pz_max":  np.max(vals),
                                         "pz_min":  np.min(vals)})
            except Exception:
                pass
            time.sleep(0.2)

    if not rows:
        return pd.DataFrame(columns=["nodo", "sistema", "pz_prom", "pz_max", "pz_min"])
    return pd.DataFrame(rows).sort_values("pz_prom", ascending=False).reset_index(drop=True)


# ── Sidebar ────────────────────────────────────────────────────────────────────
today_dt = date.today()

with st.sidebar:
    st.markdown(_XTS_IMG, unsafe_allow_html=True)
    st.markdown("<div style='color:#4a5478;font-size:0.58rem;letter-spacing:2.5px;text-transform:uppercase;margin-bottom:16px;'>Energy Portal</div>", unsafe_allow_html=True)
    st.markdown("---")
    page = st.selectbox("Navegación", [
        "Resumen",
        "PML SIN — DC_L / DC_R",
        "PML BCA — IVY / OMS",
    ])
    st.markdown("---")
    st.markdown(f"<div style='color:#5a6280;font-size:0.7rem;'>📅 {today_dt.strftime('%d/%m/%Y')}</div>", unsafe_allow_html=True)
    st.markdown(f"<div style='color:#5a6280;font-size:0.7rem;'>👤 {st.session_state.get('auth','')}</div>", unsafe_allow_html=True)
    if st.button("Cerrar sesión", key="logout"):
        st.session_state.logged_in = False
        st.rerun()

tc, live_tc = load_tipo_cambio()
df_caiso, live_caiso = load_caiso(14)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: Resumen
# ══════════════════════════════════════════════════════════════════════════════
if page == "Resumen":
    st.title(f"CENACE — Morning Summary  {today_dt.strftime('%A %B %d, %Y')}")

    with st.spinner("Cargando precios CENACE…"):
        df_dcl = live_pml("SIN", "MDA", "06LAA-138", dias=3)
        df_dcr = live_pml("SIN", "MDA", "06RRD-138", dias=3)
        df_ivy = live_pml("BCA", "MDA", "07IVY-230", dias=3)
        df_oms = live_pml("BCA", "MDA", "07OMS-230", dias=3)

    def last_val(df):
        if df is None or df.empty: return None, None
        df = df.dropna(subset=["pz"])
        if df.empty: return None, None
        last = float(df.iloc[-1]["pz"])
        prev = float(df.iloc[-2]["pz"]) if len(df) > 1 else None
        return last, prev

    dcl_v, dcl_p = last_val(df_dcl)
    dcr_v, dcr_p = last_val(df_dcr)
    ivy_v, ivy_p = last_val(df_ivy)
    oms_v, oms_p = last_val(df_oms)

    tag_mxn = '<span class="tag-mxn">MXN</span>'
    tag_usd = '<span class="tag-usd">USD</span>'

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.markdown(kpi("PML DC_L (SIN)", dcl_v, dcl_p, color=C_DCL, tag=tag_mxn), unsafe_allow_html=True)
    c2.markdown(kpi("PML DC_R (SIN)", dcr_v, dcr_p, color=C_DCR, tag=tag_mxn), unsafe_allow_html=True)
    c3.markdown(kpi("PML IVY (BCA)",  ivy_v, ivy_p, color=C_IVY, tag=tag_mxn), unsafe_allow_html=True)
    c4.markdown(kpi("PML OMS (BCA)",  oms_v, oms_p, color=C_OMS, tag=tag_mxn), unsafe_allow_html=True)
    c5.markdown(f"""<div class="kpi-card" style="border-left-color:#34d399">
        <div class="kpi-label">USD/MXN FIX {tag_usd}</div>
        <div class="kpi-value" style="color:#34d399">{tc:.4f}</div>
        <span class="kpi-sub">{'Banxico live' if live_tc else 'demo'}</span>
    </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Equivalentes USD
    c1, c2, c3, c4 = st.columns(4)
    for col, val, color, label in [
        (c1, dcl_v, C_DCL, "DC_L (USD equiv)"),
        (c2, dcr_v, C_DCR, "DC_R (USD equiv)"),
        (c3, ivy_v, C_IVY, "IVY (USD equiv)"),
        (c4, oms_v, C_OMS, "OMS (USD equiv)"),
    ]:
        usd = val / tc if (val and tc) else None
        col.markdown(kpi(label, usd, color=color, fmt="${:.3f}", tag=tag_usd), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Mini charts hoy
    c1, c2 = st.columns(2)
    for df, nodo, color, col in [
        (df_dcl, "06LAA-138 (DC_L)", C_DCL, c1),
        (df_dcr, "06RRD-138 (DC_R)", C_DCR, c2),
    ]:
        fig = go.Figure()
        if df is not None and not df.empty:
            hoy = df[df["fecha"].dt.date == today_dt]
            if not hoy.empty:
                fig.add_trace(go.Scatter(x=hoy["fecha"], y=hoy["pz"], mode="lines",
                                         name="MDA", line=dict(color=color, width=2.5)))
        fig.update_layout(**_plotly_base(280, f"PML MDA {nodo} — Hoy"), yaxis_title="MXN/MWh")
        col.plotly_chart(fig, use_container_width=True)

    c3, c4 = st.columns(2)
    for df, nodo, color, col in [
        (df_ivy, "07IVY-230 (IVY)", C_IVY, c3),
        (df_oms, "07OMS-230 (OMS)", C_OMS, c4),
    ]:
        fig = go.Figure()
        if df is not None and not df.empty:
            hoy = df[df["fecha"].dt.date == today_dt]
            if not hoy.empty:
                fig.add_trace(go.Scatter(x=hoy["fecha"], y=hoy["pz"], mode="lines",
                                         name="MDA", line=dict(color=color, width=2.5)))
        fig.update_layout(**_plotly_base(280, f"PML MDA {nodo} — Hoy"), yaxis_title="MXN/MWh")
        col.plotly_chart(fig, use_container_width=True)

    st.markdown(f"<div style='color:#5a6280;font-size:0.65rem;margin-top:8px;text-align:center;'>CENACE · {datetime.now().strftime('%d/%m/%Y %H:%M')}</div>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: PML SIN — DC_L / DC_R
# ══════════════════════════════════════════════════════════════════════════════
elif page == "PML SIN — DC_L / DC_R":
    st.title("PML CENACE — Sistema SIN  (MXN/MWh)")
    st.caption("Nodos: 06LAA-138 (DC_L) y 06RRD-138 (DC_R) · Sistema SIN · MDA y MTR")

    with st.spinner("Cargando PML SIN…"):
        mda_dcl = live_pml("SIN", "MDA", "06LAA-138", dias=7)
        mda_dcr = live_pml("SIN", "MDA", "06RRD-138", dias=7)
        mtr_dcl = live_pml("SIN", "MTR", "06LAA-138", dias=7, end_lag=3)
        mtr_dcr = live_pml("SIN", "MTR", "06RRD-138", dias=7, end_lag=3)

    tag_mxn = '<span class="tag-mxn">MXN</span>'
    tag_usd = '<span class="tag-usd">USD</span>'

    def last_pz(df):
        if df is None or df.empty: return None, None
        d = df.dropna(subset=["pz"])
        if d.empty: return None, None
        return float(d.iloc[-1]["pz"]), float(d.iloc[-2]["pz"]) if len(d) > 1 else None

    c1, c2, c3, c4, c5 = st.columns(5)
    v, p = last_pz(mda_dcl)
    c1.markdown(kpi("MDA DC_L", v, p, color=C_DCL, tag=tag_mxn), unsafe_allow_html=True)
    v, p = last_pz(mda_dcr)
    c2.markdown(kpi("MDA DC_R", v, p, color=C_DCR, tag=tag_mxn), unsafe_allow_html=True)
    v, p = last_pz(mtr_dcl)
    c3.markdown(kpi("MTR DC_L", v, p, color=C_DCL, tag=tag_mxn), unsafe_allow_html=True)
    v, p = last_pz(mtr_dcr)
    c4.markdown(kpi("MTR DC_R", v, p, color=C_DCR, tag=tag_mxn), unsafe_allow_html=True)
    c5.markdown(f"""<div class="kpi-card" style="border-left-color:#34d399">
        <div class="kpi-label">USD/MXN {tag_usd}</div>
        <div class="kpi-value" style="color:#34d399">{tc:.4f}</div>
    </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # MDA 7 días — DC_L vs DC_R
    fig = go.Figure()
    if mda_dcl is not None and not mda_dcl.empty:
        fig.add_trace(go.Scatter(x=mda_dcl["fecha"], y=mda_dcl["pz"], mode="lines",
                                  name="MDA DC_L", line=dict(color=C_DCL, width=2.5)))
    if mda_dcr is not None and not mda_dcr.empty:
        fig.add_trace(go.Scatter(x=mda_dcr["fecha"], y=mda_dcr["pz"], mode="lines",
                                  name="MDA DC_R", line=dict(color=C_DCR, width=2.5)))
    fig.update_layout(**_plotly_base(380, "PML MDA — DC_L vs DC_R (7 días)"), yaxis_title="MXN/MWh")
    st.plotly_chart(fig, use_container_width=True)

    # MTR 7 días
    c1, c2 = st.columns(2)
    for df, nodo, color, col, titulo in [
        (mtr_dcl, "DC_L", C_DCL, c1, "MTR DC_L (06LAA-138)"),
        (mtr_dcr, "DC_R", C_DCR, c2, "MTR DC_R (06RRD-138)"),
    ]:
        fig = go.Figure()
        if df is not None and not df.empty:
            fig.add_trace(go.Scatter(x=df["fecha"], y=df["pz"], mode="lines",
                                      name="MTR", line=dict(color=color, width=2)))
        else:
            fig.add_annotation(text="Sin datos MTR disponibles", xref="paper", yref="paper",
                               x=0.5, y=0.5, showarrow=False,
                               font=dict(color="#5a6280", size=13))
        fig.update_layout(**_plotly_base(300, f"PML MTR — {titulo} (7 días)"), yaxis_title="MXN/MWh")
        col.plotly_chart(fig, use_container_width=True)

    # Componentes PZ = PZ_ENE + PZ_PER + PZ_CNG
    st.markdown("#### Componentes PML MDA — DC_L")
    if mda_dcl is not None and not mda_dcl.empty:
        fig = go.Figure()
        for comp, color, label in [
            ("pz_ene", "#00d4e8", "Energía"),
            ("pz_per", "#FF6B35", "Pérdidas"),
            ("pz_cng", "#B7D433", "Congestión"),
        ]:
            if comp in mda_dcl.columns:
                fig.add_trace(go.Scatter(x=mda_dcl["fecha"], y=mda_dcl[comp], mode="lines",
                                          name=label, line=dict(color=color, width=1.5)))
        fig.update_layout(**_plotly_base(300, "Componentes PZ: ENE + PER + CNG"), yaxis_title="MXN/MWh")
        st.plotly_chart(fig, use_container_width=True)

    # Tabla diaria
    if mda_dcl is not None and not mda_dcl.empty and mda_dcr is not None and not mda_dcr.empty:
        st.markdown("#### Resumen diario")
        dcl_d = mda_dcl.copy(); dcl_d["dia"] = dcl_d["fecha"].dt.date
        dcr_d = mda_dcr.copy(); dcr_d["dia"] = dcr_d["fecha"].dt.date
        agg_dcl = dcl_d.groupby("dia")["pz"].mean().reset_index().rename(columns={"pz": "MDA_DCL"})
        agg_dcr = dcr_d.groupby("dia")["pz"].mean().reset_index().rename(columns={"pz": "MDA_DCR"})
        tbl = agg_dcl.merge(agg_dcr, on="dia", how="outer").sort_values("dia", ascending=False)
        tbl["SPREAD"] = tbl["MDA_DCL"] - tbl["MDA_DCR"]
        tbl["MDA_DCL_USD"] = tbl["MDA_DCL"] / tc
        tbl["MDA_DCR_USD"] = tbl["MDA_DCR"] / tc
        st.dataframe(
            tbl.style.format({"MDA_DCL": "{:.2f}", "MDA_DCR": "{:.2f}", "SPREAD": "{:.2f}",
                               "MDA_DCL_USD": "{:.3f}", "MDA_DCR_USD": "{:.3f}"}),
            use_container_width=True, hide_index=True,
        )


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: PML BCA — IVY / OMS
# ══════════════════════════════════════════════════════════════════════════════
elif page == "PML BCA — IVY / OMS":
    st.title("PML CENACE — Sistema BCA  (MXN/MWh)")
    st.caption("Nodos: 07IVY-230 (Imperial Valley) y 07OMS-230 (Otay Mesa) · BCA · MDA y MTR")

    with st.spinner("Cargando PML BCA…"):
        mda_ivy = live_pml("BCA", "MDA", "07IVY-230", dias=7)
        mda_oms = live_pml("BCA", "MDA", "07OMS-230", dias=7)
        mtr_ivy = live_pml("BCA", "MTR", "07IVY-230", dias=7, end_lag=3)
        mtr_oms = live_pml("BCA", "MTR", "07OMS-230", dias=7, end_lag=3)

    tag_mxn = '<span class="tag-mxn">MXN</span>'
    tag_usd = '<span class="tag-usd">USD</span>'

    def last_pz(df):
        if df is None or df.empty: return None, None
        d = df.dropna(subset=["pz"])
        if d.empty: return None, None
        return float(d.iloc[-1]["pz"]), float(d.iloc[-2]["pz"]) if len(d) > 1 else None

    c1, c2, c3, c4 = st.columns(4)
    v, p = last_pz(mda_ivy)
    c1.markdown(kpi("MDA IVY", v, p, color=C_IVY, tag=tag_mxn), unsafe_allow_html=True)
    v, p = last_pz(mda_oms)
    c2.markdown(kpi("MDA OMS", v, p, color=C_OMS, tag=tag_mxn), unsafe_allow_html=True)
    v, p = last_pz(mtr_ivy)
    c3.markdown(kpi("MTR IVY", v, p, color=C_IVY, tag=tag_mxn), unsafe_allow_html=True)
    v, p = last_pz(mtr_oms)
    c4.markdown(kpi("MTR OMS", v, p, color=C_OMS, tag=tag_mxn), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # MDA 7 días
    fig = go.Figure()
    if mda_ivy is not None and not mda_ivy.empty:
        fig.add_trace(go.Scatter(x=mda_ivy["fecha"], y=mda_ivy["pz"], mode="lines",
                                  name="MDA IVY", line=dict(color=C_IVY, width=2.5)))
    if mda_oms is not None and not mda_oms.empty:
        fig.add_trace(go.Scatter(x=mda_oms["fecha"], y=mda_oms["pz"], mode="lines",
                                  name="MDA OMS", line=dict(color=C_OMS, width=2.5)))
    fig.update_layout(**_plotly_base(380, "PML MDA — IVY vs OMS (7 días)"), yaxis_title="MXN/MWh")
    st.plotly_chart(fig, use_container_width=True)

    # Histórico 14 días desde BD + live
    if df_caiso is not None and not df_caiso.empty and live_caiso:
        st.markdown("#### Histórico 14 días (BD)")
        fig2 = go.Figure()
        if "PML_IVY" in df_caiso.columns:
            fig2.add_trace(go.Scatter(x=df_caiso["fecha"], y=df_caiso["PML_IVY"], mode="lines",
                                       name="PML IVY (BD)", line=dict(color=C_IVY, width=2)))
        if "PML_OMS" in df_caiso.columns:
            fig2.add_trace(go.Scatter(x=df_caiso["fecha"], y=df_caiso["PML_OMS"], mode="lines",
                                       name="PML OMS (BD)", line=dict(color=C_OMS, width=2)))
        fig2.update_layout(**_plotly_base(340, "PML MDA IVY/OMS — Histórico BD"), yaxis_title="MXN/MWh")
        st.plotly_chart(fig2, use_container_width=True)

    # MTR
    c1, c2 = st.columns(2)
    for df, nodo, color, col, titulo in [
        (mtr_ivy, "IVY", C_IVY, c1, "MTR 07IVY-230"),
        (mtr_oms, "OMS", C_OMS, c2, "MTR 07OMS-230"),
    ]:
        fig = go.Figure()
        if df is not None and not df.empty:
            fig.add_trace(go.Scatter(x=df["fecha"], y=df["pz"], mode="lines",
                                      name="MTR", line=dict(color=color, width=2)))
        else:
            fig.add_annotation(text="Sin datos MTR disponibles", xref="paper", yref="paper",
                               x=0.5, y=0.5, showarrow=False,
                               font=dict(color="#5a6280", size=13))
        fig.update_layout(**_plotly_base(300, f"PML MTR — {titulo} (7 días)"), yaxis_title="MXN/MWh")
        col.plotly_chart(fig, use_container_width=True)

    # Tabla diaria
    if mda_ivy is not None and not mda_ivy.empty:
        st.markdown("#### Resumen diario")
        ivy_d = mda_ivy.copy(); ivy_d["dia"] = ivy_d["fecha"].dt.date
        oms_d = mda_oms.copy(); oms_d["dia"] = oms_d["fecha"].dt.date
        agg_ivy = ivy_d.groupby("dia")["pz"].mean().reset_index().rename(columns={"pz": "MDA_IVY"})
        agg_oms = oms_d.groupby("dia")["pz"].mean().reset_index().rename(columns={"pz": "MDA_OMS"})
        tbl = agg_ivy.merge(agg_oms, on="dia", how="outer").sort_values("dia", ascending=False)
        tbl["SPREAD"] = tbl["MDA_IVY"] - tbl["MDA_OMS"]
        tbl["IVY_USD"] = tbl["MDA_IVY"] / tc
        tbl["OMS_USD"] = tbl["MDA_OMS"] / tc
        st.dataframe(
            tbl.style.format({"MDA_IVY": "{:.2f}", "MDA_OMS": "{:.2f}", "SPREAD": "{:.2f}",
                               "IVY_USD": "{:.3f}", "OMS_USD": "{:.3f}"}),
            use_container_width=True, hide_index=True,
        )


