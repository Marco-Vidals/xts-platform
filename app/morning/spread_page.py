"""
Spread Frontera — ERCOT RT vs CENACE MDA (USD)
Integrado en XTS Morning Portal como página 5_Spread.py
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import date, timedelta

from app.morning.data_loader import load_spread_data, load_tipo_cambio

# ── CSS global (mismo tema trader terminal) ───────────────────────────────────
st.markdown("""
<style>
    header, [data-testid="stHeader"], [data-testid="stToolbar"],
    [data-testid="stDecoration"], footer, #MainMenu { display: none !important; }
    html, body, .stApp { background-color: #1a1e2e !important; }
    .block-container { padding-top: 1.2rem !important; max-width: 100% !important; background-color: #1a1e2e !important; }
    html, body, [class*="css"] { color: #c0c4cc !important; font-family: 'Segoe UI', 'Consolas', monospace; }
    h1 { color: #00d4e8 !important; font-size: 1.4rem !important; font-weight: 700 !important;
         letter-spacing: 1.5px !important; text-transform: uppercase !important;
         border-bottom: 1px solid #2d3350 !important; padding-bottom: 0.5rem !important; }
    h2, h3 { color: #c0c4cc !important; font-size: 0.95rem !important;
              letter-spacing: 1px !important; text-transform: uppercase !important; }
    [data-testid="stSidebar"] { background-color: #12151f !important; border-right: 1px solid #2d3350 !important; }
    [data-testid="stMetricValue"] { color: #00d4e8 !important; font-size: 1.4rem !important; font-weight: 700 !important; }
    [data-testid="stMetricLabel"] { color: #5a6280 !important; font-size: 0.72rem !important; letter-spacing: 1px !important; text-transform: uppercase !important; }
    [data-testid="stDataFrame"] { background-color: #1e2130 !important; }
    div[data-testid="stSelectbox"] > div { background-color: #1e2130 !important; border: 1px solid #2d3350 !important; border-radius: 4px !important; }
</style>
""", unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────────────────────────
_BASE = os.path.join(os.path.dirname(__file__), "..", "..")
import base64 as _b64

def _xts_logo_uri(h=33):
    w = int(h * 2.45)
    svg = (f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg">'
           '<defs><linearGradient id="g" x1="0%" y1="0%" x2="100%" y2="0%">'
           '<stop offset="0%" stop-color="#00eed8"/><stop offset="40%" stop-color="#008888"/>'
           '<stop offset="100%" stop-color="#1c2b58"/></linearGradient></defs>'
           f'<text x="1" y="{int(h*0.9)}" font-family="Arial Black,sans-serif" '
           f'font-weight="900" font-size="{h}" letter-spacing="-2" fill="url(#g)">XTS</text></svg>')
    enc = _b64.b64encode(svg.encode()).decode()
    return f"data:image/svg+xml;base64,{enc}"

with st.sidebar:
    st.markdown(
        f"<div style='text-align:center;padding:14px 0 4px 0;'>"
        f"<img src='{_xts_logo_uri(33)}' style='height:33px;display:block;margin:0 auto;'/>"
        f"<div style='color:#4a5478;font-size:0.6rem;letter-spacing:2.5px;text-transform:uppercase;"
        f"font-family:Segoe UI,sans-serif;margin-top:6px;'>SPREAD FRONTERA</div></div>",
        unsafe_allow_html=True,
    )
    st.divider()
    st.markdown("<div style='color:#5a6280;font-size:0.7rem;letter-spacing:1.5px;text-transform:uppercase;margin-bottom:6px;'>Mercados</div>", unsafe_allow_html=True)
    st.page_link("pages/1_ERCOT.py",     label="⚡ ERCOT Morning")
    st.page_link("pages/2_CAISO.py",     label="☀️ CAISO Morning")
    st.page_link("pages/3_CENACE.py",    label="🇲🇽 CENACE Morning")
    st.page_link("pages/4_Guatemala.py", label="🇬🇹 Guatemala Morning")
    st.divider()
    st.markdown("<div style='color:#5a6280;font-size:0.7rem;letter-spacing:1.5px;text-transform:uppercase;margin-bottom:6px;'>Operaciones</div>", unsafe_allow_html=True)
    st.page_link("pages/5_Ofertas.py",     label="📋 Ofertas Morning")
    st.page_link("pages/6_Afternoon.py",   label="🌅 Afternoon")
    st.page_link("pages/7_Trading.py",     label="📊 Trading / P&L")
    st.page_link("pages/8_Facturacion.py", label="📋 Facturación")
    st.divider()
    if st.button("Cerrar Sesión", use_container_width=True, key="spread_logout"):
        st.session_state.logged_in = False
        st.session_state.auth = None
        st.rerun()

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("# 🔁 Spread Frontera")
st.markdown(
    "<div style='color:#5a6280;font-size:0.8rem;margin-bottom:16px;'>"
    "ERCOT RT (tiempo real) menos CENACE MDA (día en adelanto) convertido a USD usando tipo de cambio diario FIX"
    "</div>",
    unsafe_allow_html=True,
)

# ── Selectores ────────────────────────────────────────────────────────────────
col_sel1, col_sel2, _ = st.columns([1, 1, 3])
with col_sel1:
    nodo = st.selectbox("Nodo frontera", ["DC_L — Laredo", "DC_R — Río Grande"], key="spread_nodo")
with col_sel2:
    periodo = st.selectbox("Período", ["Semana (7d)", "Mes (30d)", "3 Meses (90d)"], index=1, key="spread_periodo")

nodo_key    = "DC_L" if "DC_L" in nodo else "DC_R"
nodo_cenace = "06LAA-138" if nodo_key == "DC_L" else "06RRD-138"
dias_map    = {"Semana (7d)": 7, "Mes (30d)": 30, "3 Meses (90d)": 90}
dias        = dias_map[periodo]

# ── Datos ─────────────────────────────────────────────────────────────────────
with st.spinner("Cargando datos de spread..."):
    df, is_live, err_msg = load_spread_data(nodo_cenace, nodo_key, dias)

if not is_live or df.empty:
    st.warning("Sin datos para el período y nodo seleccionados.")
    if err_msg:
        st.error(f"Detalle: `{err_msg}`")
    st.stop()

# ── Métricas ──────────────────────────────────────────────────────────────────
avg_spread = df["spread"].mean()
max_spread = df["spread"].max()
min_spread = df["spread"].min()
pos_days   = (df["spread"] > 0).sum()
total_days = len(df)
tc_hoy, _  = load_tipo_cambio()

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Spread Promedio",  f"${avg_spread:+.2f}/MWh")
m2.metric("Spread Máximo",    f"${max_spread:.2f}/MWh")
m3.metric("Spread Mínimo",    f"${min_spread:.2f}/MWh")
m4.metric("Días positivos",   f"{pos_days}/{total_days}  ({pos_days/total_days*100:.0f}%)")
m5.metric("TC hoy",           f"{tc_hoy:.4f} MXN/USD")

st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

# ── Gráfica de barras ─────────────────────────────────────────────────────────
fig = go.Figure()
fig.add_trace(go.Bar(
    x=df["fecha_dia"],
    y=df["spread"],
    marker_color=df["spread"].apply(lambda v: "#2ecc71" if v >= 0 else "#e74c3c"),
    name="Spread diario",
    hovertemplate="<b>%{x|%d %b %Y}</b><br>Spread: $%{y:.2f}/MWh<extra></extra>",
))
fig.add_hline(
    y=avg_spread,
    line_dash="dash", line_color="#f39c12", line_width=1.5,
    annotation_text=f"Prom ${avg_spread:+.2f}",
    annotation_font_color="#f39c12",
    annotation_position="top right",
)
fig.add_hline(y=0, line_color="rgba(255,255,255,0.15)", line_width=1)
fig.update_layout(
    title=dict(text=f"Spread ERCOT RT − CENACE MDA (USD) · {nodo_key} · {periodo}", font=dict(size=14, color="#c0c4cc")),
    xaxis=dict(gridcolor="#1e2540", tickfont=dict(color="#5a6280")),
    yaxis=dict(gridcolor="#1e2540", zeroline=False, tickfont=dict(color="#5a6280"), tickprefix="$"),
    plot_bgcolor="#12151f", paper_bgcolor="#1a1e2e",
    font=dict(color="#c0c4cc"),
    height=380, showlegend=False,
    margin=dict(t=50, b=40, l=60, r=40),
)
st.plotly_chart(fig, use_container_width=True)

# ── Helper: tabla HTML oscura con colores XTS ─────────────────────────────────
def _dark_table(rows: list[dict], spread_col: str = "Spread") -> str:
    if not rows:
        return ""
    headers = list(rows[0].keys())
    th = "".join(
        f"<th style='padding:8px 14px;text-align:left;color:#5a6280;"
        f"font-size:0.72rem;letter-spacing:1px;text-transform:uppercase;"
        f"border-bottom:1px solid #2d3350;font-weight:600;white-space:nowrap;'>{h}</th>"
        for h in headers
    )
    body = ""
    for i, row in enumerate(rows):
        bg = "#1a1e2e" if i % 2 == 0 else "#1e2130"
        cells = ""
        for k, v in row.items():
            # Color spread positivo/negativo
            color = "#c0c4cc"
            if k == spread_col:
                try:
                    color = "#2ecc71" if float(str(v).replace("$","").replace("+","")) >= 0 else "#e74c3c"
                except Exception:
                    pass
            cells += (
                f"<td style='padding:7px 14px;color:{color};"
                f"font-size:0.82rem;border-bottom:1px solid #1e2540;'>{v}</td>"
            )
        body += f"<tr style='background:{bg};'>{cells}</tr>"
    return (
        "<div style='overflow-x:auto;border:1px solid #2d3350;border-radius:6px;'>"
        f"<table style='width:100%;border-collapse:collapse;background:#1a1e2e;'>"
        f"<thead><tr style='background:#12151f;'>{th}</tr></thead>"
        f"<tbody>{body}</tbody></table></div>"
    )


def _to_rows(sub_df, cols, col_names):
    t = sub_df[cols].copy()
    t.columns = col_names
    return t.to_dict("records")


# ── Tabla completa: todas las columnas ───────────────────────────────────────
st.markdown("### Tabla de Precios y Spread")
full = df.sort_values("fecha_dia", ascending=False).copy()
rows_full = _to_rows(full,
    ["fecha_dia", "pml_mxn", "tipo_cambio", "pml_usd", "rt_usd", "spread"],
    ["Fecha", "CENACE MDA (MXN)", "TC", "CENACE MDA (USD)", "ERCOT RT (USD)", "Spread"]
)
for r in rows_full:
    r["Fecha"]             = r["Fecha"].strftime("%d %b %Y") if hasattr(r["Fecha"], "strftime") else str(r["Fecha"])[:10]
    r["CENACE MDA (MXN)"]  = f"${r['CENACE MDA (MXN)']:.2f}"
    r["TC"]                = f"{r['TC']:.4f}"
    r["CENACE MDA (USD)"]  = f"${r['CENACE MDA (USD)']:.2f}"
    r["ERCOT RT (USD)"]    = f"${r['ERCOT RT (USD)']:.2f}"
    r["Spread"]            = f"${r['Spread']:+.2f}"
st.markdown(_dark_table(rows_full), unsafe_allow_html=True)

st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

# ── Top 10 / Bottom 10 ────────────────────────────────────────────────────────
col_top, col_bot = st.columns(2)

def _top_rows(sub_df):
    t = sub_df[["fecha_dia", "rt_usd", "pml_usd", "tipo_cambio", "spread"]].copy()
    rows = []
    for _, row in t.iterrows():
        rows.append({
            "Fecha":      row["fecha_dia"].strftime("%d %b %Y"),
            "ERCOT RT":   f"${row['rt_usd']:.2f}",
            "CENACE MDA": f"${row['pml_usd']:.2f}",
            "TC":         f"{row['tipo_cambio']:.4f}",
            "Spread":     f"${row['spread']:+.2f}",
        })
    return rows

with col_top:
    st.markdown("### Top 10 — Mayor Spread")
    st.markdown(_dark_table(_top_rows(df.nlargest(10, "spread"))), unsafe_allow_html=True)

with col_bot:
    st.markdown("### Top 10 — Menor Spread")
    st.markdown(_dark_table(_top_rows(df.nsmallest(10, "spread"))), unsafe_allow_html=True)
