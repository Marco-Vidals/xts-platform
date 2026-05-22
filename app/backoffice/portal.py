"""
XTS Back Office Platform — Liquidaciones, Facturacion y Conciliacion.
Correr con: streamlit run app/backoffice/portal.py --server.port 8503
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

st.set_page_config(
    page_title="XTS Back Office",
    page_icon="📑",
    layout="wide",
    initial_sidebar_state="expanded",
)

if "logged_in" not in st.session_state: st.session_state.logged_in = False
if "auth"      not in st.session_state: st.session_state.auth      = None

# ══════════════════════════════════════════════════════════════════════════════
# LOGIN
# ══════════════════════════════════════════════════════════════════════════════
ENVERUS_USER = os.environ.get("ENVERUS_USER", "mvidals@xiix.mx")
ENVERUS_PASS = os.environ.get("ENVERUS_PASS", "")

def _enverus_login(user, password):
    try:
        r = requests.get(
            "https://api-mosaic-prod.enverus.com/mosaic-api/datasets",
            auth=(user, password), params={"response_type": "csv_wide", "response_info": "base"},
            timeout=15, verify=False,
        )
        return (user, password) if r.status_code == 200 else None
    except Exception:
        return None

if not st.session_state.logged_in:
    st.markdown("""<style>
        .stApp{background:#2d3242!important}
        [data-testid="stSidebar"],[data-testid="collapsedControl"]{display:none!important}
        #MainMenu,footer,header{visibility:hidden!important}
        .block-container{padding-top:0!important;max-width:100%!important}
        .stTextInput>div>div>input{background:#e9ebf0!important;color:#1e2130!important;
            border:none!important;border-radius:3px!important;height:42px!important}
        .stButton>button{background:#1e2130!important;color:#c0c4cc!important;
            border:2px solid #a78bfa!important;border-radius:4px!important;
            font-size:.9rem!important;font-weight:700!important;letter-spacing:1.5px!important;
            text-transform:uppercase!important;width:100%!important;height:44px!important;margin-top:4px!important}
        .stButton>button:hover{background:#a78bfa!important;color:#1e2130!important}
    </style>""", unsafe_allow_html=True)
    st.markdown(
        "<div style='position:fixed;top:16px;left:28px;z-index:999;display:flex;align-items:center;gap:10px;'>"
        + _XTS_IMG
        + "<div style='color:#a78bfa;font-size:.65rem;letter-spacing:2px;text-transform:uppercase;"
        "font-family:Segoe UI,sans-serif;align-self:flex-end;padding-bottom:6px;'>Back Office</div></div>",
        unsafe_allow_html=True,
    )
    st.markdown("<div style='height:28vh'></div>", unsafe_allow_html=True)
    _, col, _ = st.columns([1, 0.9, 1])
    with col:
        st.markdown(
            "<div style='background:#1e2130;border:1px solid #a78bfa40;border-radius:8px;"
            "padding:32px 36px 28px 36px;'>"
            "<div style='color:#a78bfa;font-size:.72rem;letter-spacing:3px;"
            "text-transform:uppercase;margin-bottom:20px;text-align:center;'>Back Office</div>",
            unsafe_allow_html=True,
        )
        user_in = st.text_input("Usuario", value=ENVERUS_USER, key="bo_user")
        pass_in = st.text_input("Contrasena", type="password", key="bo_pass")
        if st.button("ENTRAR", key="bo_btn"):
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
# CSS
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("""<style>
    .stApp{background:#1a1e2e!important}
    #MainMenu,footer,header{visibility:hidden!important}
    .block-container{padding-top:1rem!important;padding-bottom:1rem!important;max-width:100%!important}
    html,body,[class*="css"]{color:#c0c4cc!important;font-family:'Segoe UI','Consolas',monospace}
    h1{color:#a78bfa!important;font-size:1.4rem!important;font-weight:700!important;
       letter-spacing:1.5px!important;text-transform:uppercase!important;
       border-bottom:1px solid #2d3350!important;padding-bottom:.5rem!important;margin-bottom:1rem!important}
    h2,h3,h4{color:#c0c4cc!important;font-size:.95rem!important}
    [data-testid="stSidebar"]{background:#12151f!important;border-right:1px solid #2d3350!important}
    [data-testid="stSidebar"] *{color:#c0c4cc!important}
    [data-testid="stSidebar"] [data-testid="stSelectbox"]>div>div{
        background:#2d3350!important;border:1px solid #3d4468!important;border-radius:4px!important}
    [data-testid="stSidebar"] [data-testid="stSelectbox"]>div>div>div,
    [data-testid="stSidebar"] [data-testid="stSelectbox"] span{color:#a78bfa!important;font-weight:600!important}
    [data-testid="stSidebar"] [data-testid="stSelectbox"] svg{fill:#a78bfa!important}
    [data-testid="stDataFrame"]{background:#1e2130!important;border:1px solid #2d3350!important}
    [data-testid="stDataFrame"] *{color:#c0c4cc!important;font-size:.82rem!important;font-family:Consolas,monospace!important}
    [data-testid="stDataFrame"] th{background:#12151f!important;color:#5a6280!important}
    ::-webkit-scrollbar{width:5px;height:5px}
    ::-webkit-scrollbar-track{background:#1a1e2e}
    ::-webkit-scrollbar-thumb{background:#2d3350;border-radius:3px}
    .kpi-card{background:#1e2130;border-radius:6px;padding:12px 16px;
              border:1px solid #2d3350;border-left:3px solid #a78bfa}
    .kpi-label{color:#5a6280;font-size:.68rem;text-transform:uppercase;letter-spacing:1.2px;font-weight:600}
    .kpi-value{color:#a78bfa;font-size:1.5rem;font-weight:700;font-family:Consolas,monospace;margin:3px 0}
    .kpi-sub{color:#5a6280;font-size:.74rem}
    .badge-vence{background:#3a1a00;color:#fb923c;border:1px solid #fb923c;
                 padding:2px 8px;border-radius:3px;font-size:.72rem;font-weight:600}
    .badge-ok{background:#0d2a1e;color:#34d399;border:1px solid #34d399;
              padding:2px 8px;border-radius:3px;font-size:.72rem;font-weight:600}
</style>""", unsafe_allow_html=True)

PLOT_BG  = "#1e2130"
PAPER_BG = "#1e2130"
GRID_COL = "#2d3350"
FONT_COL = "#c0c4cc"
COL_ACC  = "#a78bfa"
COL_POS  = "#34d399"
COL_NEG  = "#f87171"
COL_WARN = "#fb923c"

ECD_BASE = os.path.join(
    os.path.expanduser("~"),
    "OneDrive - XIIX TRADING SOLUTIONS SAPI DE CV",
    "XTS R&D", "Facturacion",
)


# ── Helpers ───────────────────────────────────────────────────────────────────
def kpi(label, value, sub="", color="#a78bfa"):
    return (
        f'<div class="kpi-card" style="border-left-color:{color};">'
        f'<div class="kpi-label">{label}</div>'
        f'<div class="kpi-value" style="color:{color};">{value}</div>'
        f'<div class="kpi-sub">{sub}</div></div>'
    )

def _fmt(v, fmt=".2f", prefix="", suffix="", na="—"):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return na
    return f"{prefix}{v:{fmt}}{suffix}"

def _mxn(v): return _fmt(v, ",.2f", prefix="$", suffix=" MXN")
def _pct(v): return _fmt(v, "+.1f", suffix="%") if v is not None else "—"

def _plotly_base(title="", height=300):
    fig = go.Figure()
    fig.update_layout(
        title=dict(text=title, font=dict(size=13, color=FONT_COL), x=0.01),
        paper_bgcolor=PAPER_BG, plot_bgcolor=PLOT_BG,
        font=dict(color=FONT_COL, size=11),
        margin=dict(l=52, r=16, t=38, b=36), height=height,
        xaxis=dict(gridcolor=GRID_COL, showgrid=True, zeroline=False, color=FONT_COL),
        yaxis=dict(gridcolor=GRID_COL, showgrid=True, zeroline=False, color=FONT_COL),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                    font=dict(size=10, color="#ffffff")),
    )
    return fig


# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown(
        "<div style='text-align:center;padding:14px 0 4px 0;'>"
        + _XTS_IMG
        + "<div style='color:#a78bfa;font-size:.6rem;letter-spacing:2.5px;text-transform:uppercase;"
        "font-family:Segoe UI,sans-serif;margin-top:6px;'>BACK OFFICE</div></div>",
        unsafe_allow_html=True,
    )
    st.divider()
    page = st.selectbox("Pagina", [
        "Resumen",
        "Liquidaciones ECD",
        "Reliquidaciones",
        "Facturacion",
        "Conciliacion",
        "Descargar ECD",
    ], key="bo_page")
    st.divider()
    fecha_ini_sel = st.date_input("Fecha inicial", value=date.today() - timedelta(days=7), key="bo_ini")
    fecha_fin_sel = st.date_input("Fecha final",   value=date.today(), key="bo_fin")
    st.divider()
    if st.button("Cerrar Sesion", use_container_width=True):
        st.session_state.logged_in = False
        st.rerun()

fecha_ini = fecha_ini_sel
fecha_fin = fecha_fin_sel

# ── Header ─────────────────────────────────────────────────────────────────────
_now_str = datetime.now().strftime("%A %d %B %Y  %H:%M")
st.markdown(
    "<div style='display:flex;align-items:center;justify-content:space-between;"
    "padding:0 4px 12px 4px;border-bottom:1px solid #2d3350;margin-bottom:20px;'>"
    + _XTS_IMG_SM
    + f"<div style='flex:1;margin-left:14px;'>"
    "<div style='color:#c0c4cc;font-size:1rem;font-weight:700;letter-spacing:1px;'>BACK OFFICE · LIQUIDACIONES & FACTURACION</div>"
    f"<div style='color:#4a5070;font-size:.68rem;'>{_now_str} CT</div>"
    "</div></div>",
    unsafe_allow_html=True,
)


# ══════════════════════════════════════════════════════════════════════════════
# CARGA ECD (con cache por rango de fechas)
# ══════════════════════════════════════════════════════════════════════════════
@st.cache_data(ttl=600, show_spinner=False)
def _load_ecd(ini: date, fin: date) -> dict:
    try:
        from etl.cenace.ecd_parser import parse_ecd_files
        return parse_ecd_files(ini, fin)
    except Exception as e:
        return {"xiix_facturas": pd.DataFrame(), "cenace_facturas": pd.DataFrame(),
                "xiix_reliq": pd.DataFrame(), "cenace_reliq": pd.DataFrame(),
                "files_found": 0, "files_missing": [], "_error": str(e)}


def _load_trades() -> pd.DataFrame:
    try:
        import pyodbc
        DB = ("DRIVER={ODBC Driver 17 for SQL Server};"
              "SERVER=100.70.216.12;DATABASE=XTS;"
              "UID=sa;PWD=XTS_operations.XiiX;Connection Timeout=10;")
        conn = pyodbc.connect(DB)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            df = pd.read_sql(
                "SELECT * FROM trading.trades WHERE fecha_operacion BETWEEN ? AND ? ORDER BY fecha_operacion, hora",
                conn, params=[fecha_ini, fecha_fin],
            )
        conn.close()
        return df
    except Exception:
        return pd.DataFrame()


# ══════════════════════════════════════════════════════════════════════════════
# UTILIDADES ECD
# ══════════════════════════════════════════════════════════════════════════════
def _sum_total(df: pd.DataFrame) -> float:
    if df.empty or "TOTAL" not in df.columns:
        return 0.0
    return pd.to_numeric(df["TOTAL"], errors="coerce").sum()

def _count_files() -> int:
    n = 0
    cur = fecha_ini
    while cur <= fecha_fin:
        d = os.path.join(ECD_BASE, cur.strftime("%Y"), cur.strftime("%m"), cur.strftime("%d"))
        if os.path.isdir(d):
            n += len([f for f in os.listdir(d) if f.endswith(".csv")])
        cur += timedelta(days=1)
    return n

def _list_missing_files() -> list:
    from etl.cenace.ecd_parser import file_list
    expected_all = []
    cur = fecha_ini
    _cuentas = ["BCA-M024ERO","BCA-M024ETJ","BCA-M024IRO","BCA-M024ITJ",
                "SIN-M024ELA","SIN-M024ERD","SIN-M024EGT","SIN-M024IGT"]
    while cur <= fecha_fin:
        yr, mm, dd = cur.strftime("%Y"), cur.strftime("%m"), cur.strftime("%d")
        for c in _cuentas:
            expected_all.append(os.path.join(ECD_BASE, yr, mm, dd, f"EC{yr}{mm}{dd}{c}.csv"))
        cur += timedelta(days=1)
    return [f for f in expected_all if not os.path.exists(f)]


# ══════════════════════════════════════════════════════════════════════════════
# PÁGINA: RESUMEN
# ══════════════════════════════════════════════════════════════════════════════
if page == "Resumen":
    with st.spinner("Leyendo ECDs..."):
        ecd = _load_ecd(fecha_ini, fecha_fin)

    n_files   = ecd.get("files_found", 0)
    n_missing = len(ecd.get("files_missing", []))

    total_xiix_fact    = _sum_total(ecd["xiix_facturas"])
    total_cenace_fact  = _sum_total(ecd["cenace_facturas"])
    total_xiix_reliq   = _sum_total(ecd["xiix_reliq"])
    total_cenace_reliq = _sum_total(ecd["cenace_reliq"])
    neto_fact          = total_xiix_fact - total_cenace_fact
    neto_reliq         = total_xiix_reliq - total_cenace_reliq

    k1, k2, k3, k4 = st.columns(4)
    with k1: st.markdown(kpi("Facturado XiiX",     _mxn(total_xiix_fact),   "Facturas originales", COL_POS), unsafe_allow_html=True)
    with k2: st.markdown(kpi("A pagar CENACE",      _mxn(total_cenace_fact), "Facturas originales", COL_NEG), unsafe_allow_html=True)
    with k3: st.markdown(kpi("Neto Facturas",       _mxn(neto_fact),         "XiiX – CENACE", COL_POS if neto_fact >= 0 else COL_NEG), unsafe_allow_html=True)
    with k4: st.markdown(kpi("Neto Reliquidaciones", _mxn(neto_reliq),       f"Rango: {fecha_ini} a {fecha_fin}", COL_WARN), unsafe_allow_html=True)

    st.markdown("<div style='height:10px;'></div>", unsafe_allow_html=True)

    k5, k6, k7 = st.columns(3)
    with k5: st.markdown(kpi("Archivos ECD encontrados", str(n_files),   f"En carpeta Facturacion", COL_ACC), unsafe_allow_html=True)
    with k6: st.markdown(kpi("Archivos faltantes",       str(n_missing), "ECDs no descargados", COL_WARN if n_missing else COL_POS), unsafe_allow_html=True)
    with k7: st.markdown(kpi("Registros XiiX",           str(len(ecd["xiix_facturas"]) + len(ecd["xiix_reliq"])), "Facturas + reliquidaciones", COL_ACC), unsafe_allow_html=True)

    # Grafica barras: Facturas vs Reliquidaciones
    if not ecd["xiix_facturas"].empty or not ecd["xiix_reliq"].empty:
        fig = _plotly_base("Resumen Liquidaciones (MXN)", height=280)
        cats = ["Facturas XiiX", "Facturas CENACE", "Reliq XiiX", "Reliq CENACE"]
        vals = [total_xiix_fact, total_cenace_fact, total_xiix_reliq, total_cenace_reliq]
        cols = [COL_POS, COL_NEG, COL_WARN, "#5a6280"]
        fig.add_trace(go.Bar(x=cats, y=vals, marker_color=cols,
                             text=[_mxn(v) for v in vals], textposition="outside"))
        fig.update_layout(yaxis_title="MXN", showlegend=False)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    # Top conceptos
    if not ecd["xiix_facturas"].empty and "CONCEPTO_DE_PAGO" in ecd["xiix_facturas"].columns:
        st.markdown("#### Top Conceptos — Facturas XiiX")
        top = (ecd["xiix_facturas"]
               .groupby("CONCEPTO_DE_PAGO")["TOTAL"]
               .sum().sort_values(ascending=False).head(10)
               .reset_index())
        top.columns = ["Concepto", "Total (MXN)"]
        top["Total (MXN)"] = top["Total (MXN)"].apply(lambda v: f"${v:,.2f}")
        st.dataframe(top, use_container_width=True, hide_index=True, height=260)


# ══════════════════════════════════════════════════════════════════════════════
# PÁGINA: LIQUIDACIONES ECD
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Liquidaciones ECD":
    st.markdown("# Liquidaciones ECD — Facturas Originales")

    with st.spinner("Leyendo ECDs..."):
        ecd = _load_ecd(fecha_ini, fecha_fin)

    tab1, tab2 = st.tabs(["XiiX (lo que cobramos)", "CENACE (lo que pagamos)"])

    for tab, df_key, label, color in [
        (tab1, "xiix_facturas",   "XiiX",   COL_POS),
        (tab2, "cenace_facturas", "CENACE", COL_NEG),
    ]:
        with tab:
            df = ecd[df_key]
            total = _sum_total(df)

            k1, k2, k3 = st.columns(3)
            with k1: st.markdown(kpi(f"Total {label}", _mxn(total), "Suma facturas originales", color), unsafe_allow_html=True)
            with k2:
                iva = pd.to_numeric(df.get("IVA", pd.Series()), errors="coerce").sum() if not df.empty else 0
                st.markdown(kpi("IVA", _mxn(iva), "16% IVA incluido", COL_ACC), unsafe_allow_html=True)
            with k3:
                sub = pd.to_numeric(df.get("IMPORTE", pd.Series()), errors="coerce").sum() if not df.empty else 0
                st.markdown(kpi("Subtotal", _mxn(sub), "Sin IVA", FONT_COL), unsafe_allow_html=True)

            st.markdown("<div style='height:6px;'></div>", unsafe_allow_html=True)

            if df.empty:
                st.info(f"No hay facturas {label} para el rango seleccionado. Verifica que los ECDs esten descargados.")
            else:
                # Grafica por concepto
                if "CONCEPTO_DE_PAGO" in df.columns:
                    agg = df.groupby("CONCEPTO_DE_PAGO")["TOTAL"].sum().sort_values()
                    fig = _plotly_base(f"Facturas {label} por Concepto (MXN)", height=300)
                    bar_cols = [COL_POS if v >= 0 else COL_NEG for v in agg.values]
                    fig.add_trace(go.Bar(y=agg.index.tolist(), x=agg.values.tolist(),
                                        orientation="h", marker_color=bar_cols))
                    fig.update_layout(xaxis_title="MXN")
                    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

                # Tabla
                disp_cols = [c for c in ["_file", "FUF", "CONCEPTO_DE_PAGO", "PRECIO", "CANTIDAD", "IMPORTE", "IVA", "TOTAL"]
                             if c in df.columns]
                st.dataframe(df[disp_cols], use_container_width=True, hide_index=True, height=380)

                # Exportar
                csv_bytes = df[disp_cols].to_csv(index=False, encoding="utf-8").encode("utf-8")
                st.download_button(
                    label=f"Descargar CSV — Facturas {label}",
                    data=csv_bytes,
                    file_name=f"facturas_{label.lower()}_{fecha_ini}_{fecha_fin}.csv",
                    mime="text/csv",
                )


# ══════════════════════════════════════════════════════════════════════════════
# PÁGINA: RELIQUIDACIONES
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Reliquidaciones":
    st.markdown("# Reliquidaciones")

    with st.spinner("Leyendo ECDs..."):
        ecd = _load_ecd(fecha_ini, fecha_fin)

    tab1, tab2, tab3 = st.tabs(["XiiX reliq", "CENACE reliq", "Notas credito/debito"])

    with tab1:
        df = ecd["xiix_reliq"]
        total = _sum_total(df)
        k1, k2 = st.columns(2)
        with k1: st.markdown(kpi("Total reliq XiiX", _mxn(total), "Ajuste a facturas originales", COL_WARN), unsafe_allow_html=True)
        with k2: st.markdown(kpi("Registros", str(len(df)), f"Rango {fecha_ini} a {fecha_fin}", COL_ACC), unsafe_allow_html=True)
        if df.empty:
            st.info("Sin reliquidaciones XiiX en el rango seleccionado.")
        else:
            st.dataframe(df, use_container_width=True, hide_index=True, height=400)
            csv_bytes = df.to_csv(index=False).encode("utf-8")
            st.download_button("Descargar CSV", csv_bytes, f"reliq_xiix_{fecha_ini}_{fecha_fin}.csv", "text/csv")

    with tab2:
        df = ecd["cenace_reliq"]
        total = _sum_total(df)
        k1, k2 = st.columns(2)
        with k1: st.markdown(kpi("Total reliq CENACE", _mxn(total), "Ajuste a facturas CENACE", COL_WARN), unsafe_allow_html=True)
        with k2: st.markdown(kpi("Registros", str(len(df)), f"Rango {fecha_ini} a {fecha_fin}", COL_ACC), unsafe_allow_html=True)
        if df.empty:
            st.info("Sin reliquidaciones CENACE en el rango seleccionado.")
        else:
            st.dataframe(df, use_container_width=True, hide_index=True, height=400)
            csv_bytes = df.to_csv(index=False).encode("utf-8")
            st.download_button("Descargar CSV", csv_bytes, f"reliq_cenace_{fecha_ini}_{fecha_fin}.csv", "text/csv")

    with tab3:
        st.markdown("#### Notas de Credito/Debito — Formato Facturacion")
        try:
            from etl.cenace.ecd_parser import build_facturas_format
            df_fact, df_notas = build_facturas_format(ecd["xiix_facturas"], ecd["xiix_reliq"])
            if df_notas.empty:
                st.info("Sin notas de credito/debito disponibles en el rango.")
            else:
                k1, k2, k3 = st.columns(3)
                deb = df_notas[df_notas.get("Tipo", pd.Series()) == "Debito"]["TOTAL"].sum() if "TOTAL" in df_notas.columns else 0
                cre = df_notas[df_notas.get("Tipo", pd.Series()) == "Credito"]["TOTAL"].sum() if "TOTAL" in df_notas.columns else 0
                with k1: st.markdown(kpi("Notas Debito",   _mxn(deb), f"{(df_notas.get('Tipo',pd.Series())=='Debito').sum()} notas", COL_NEG), unsafe_allow_html=True)
                with k2: st.markdown(kpi("Notas Credito",  _mxn(cre), f"{(df_notas.get('Tipo',pd.Series())=='Credito').sum()} notas", COL_POS), unsafe_allow_html=True)
                with k3: st.markdown(kpi("Neto Ajuste",    _mxn(deb - cre), "Debito - Credito", COL_WARN), unsafe_allow_html=True)
                st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
                st.dataframe(df_notas, use_container_width=True, hide_index=True, height=380)
                csv_bytes = df_notas.to_csv(index=False).encode("utf-8")
                st.download_button("Descargar Notas CSV", csv_bytes, f"notas_{fecha_ini}_{fecha_fin}.csv", "text/csv")
        except Exception as e:
            st.error(f"Error generando notas: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# PÁGINA: FACTURACION
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Facturacion":
    st.markdown("# Facturacion — Estado de Cuentas por Cobrar")

    # Cargar CSVs de referencia
    facturas_path = os.path.join(ECD_BASE, "XiiXFacturas.csv")
    notas_path    = os.path.join(ECD_BASE, "XiiXNotas.csv")
    cenace_path   = os.path.join(ECD_BASE, "CENACEfacturas.csv")

    def _load_csv_safe(path, label):
        if os.path.exists(path):
            try:
                return pd.read_csv(path, encoding="windows-1252")
            except Exception:
                try:
                    return pd.read_csv(path, encoding="utf-8")
                except Exception as e:
                    st.warning(f"Error leyendo {label}: {e}")
        return pd.DataFrame()

    df_fact  = _load_csv_safe(facturas_path, "XiiXFacturas")
    df_notas = _load_csv_safe(notas_path, "XiiXNotas")
    df_cenace = _load_csv_safe(cenace_path, "CENACEfacturas")

    # KPIs
    def _total_col(df, col="TOTAL"):
        if df.empty or col not in df.columns:
            return 0.0
        return pd.to_numeric(df[col], errors="coerce").sum()

    total_facturado = _total_col(df_fact)
    total_notas     = _total_col(df_notas, "TOTAL")
    total_cenace    = _total_col(df_cenace)
    n_fact = len(df_fact)
    n_nota = len(df_notas)

    k1, k2, k3, k4 = st.columns(4)
    with k1: st.markdown(kpi("Total Facturado", _mxn(total_facturado), f"{n_fact} facturas XiiX", COL_POS), unsafe_allow_html=True)
    with k2: st.markdown(kpi("Notas Cred/Deb",  _mxn(total_notas),    f"{n_nota} notas", COL_WARN), unsafe_allow_html=True)
    with k3: st.markdown(kpi("Neto por Cobrar",  _mxn(total_facturado - total_notas), "Facturas – Ajustes", COL_ACC), unsafe_allow_html=True)
    with k4: st.markdown(kpi("A pagar CENACE",   _mxn(total_cenace), "Facturas CENACE", COL_NEG), unsafe_allow_html=True)

    st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs(["Facturas XiiX", "Notas Cred/Deb", "Facturas CENACE"])

    with tab1:
        if df_fact.empty:
            st.info(f"Archivo no encontrado: {facturas_path}\nGenera los CSVs desde Reliquidaciones > Notas.")
        else:
            # Aging si hay fecha limite
            fecha_lim_col = next((c for c in df_fact.columns if "fecha" in c.lower() and "pago" in c.lower()), None)
            if fecha_lim_col:
                df_fact["_dias"] = (pd.to_datetime(df_fact[fecha_lim_col], dayfirst=True, errors="coerce") -
                                    pd.Timestamp.today()).dt.days
                df_fact["_estado"] = df_fact["_dias"].apply(
                    lambda d: "VENCIDA" if d < 0 else ("<7 dias" if d < 7 else "OK"))

                aging = df_fact.groupby("_estado")["TOTAL"].agg(["sum", "count"]).reset_index()
                aging.columns = ["Estado", "Total MXN", "Facturas"]
                aging["Total MXN"] = aging["Total MXN"].apply(lambda v: f"${v:,.2f}")
                st.dataframe(aging, use_container_width=True, hide_index=True, height=120)

            st.dataframe(df_fact.drop(columns=["_dias", "_estado"], errors="ignore"),
                         use_container_width=True, hide_index=True, height=380)
            st.download_button("Descargar", df_fact.to_csv(index=False).encode("utf-8"),
                               "XiiXFacturas.csv", "text/csv")

    with tab2:
        if df_notas.empty:
            st.info(f"Archivo no encontrado: {notas_path}")
        else:
            st.dataframe(df_notas, use_container_width=True, hide_index=True, height=420)
            st.download_button("Descargar", df_notas.to_csv(index=False).encode("utf-8"),
                               "XiiXNotas.csv", "text/csv")

    with tab3:
        if df_cenace.empty:
            st.info(f"Archivo no encontrado: {cenace_path}")
        else:
            st.dataframe(df_cenace, use_container_width=True, hide_index=True, height=420)


# ══════════════════════════════════════════════════════════════════════════════
# PÁGINA: CONCILIACION
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Conciliacion":
    st.markdown("# Conciliacion — Trades vs ECD CENACE")

    with st.spinner("Cargando datos..."):
        ecd    = _load_ecd(fecha_ini, fecha_fin)
        trades = _load_trades()

    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown("#### Trades registrados")
        if trades.empty:
            st.info("Sin trades en el rango. Registra trades en Afternoon Platform.")
        else:
            t_disp = trades[["fecha_operacion", "mercado", "direccion", "nodo", "hora", "mw",
                              "precio_da", "precio_rt"]].copy()
            t_disp.columns = ["Fecha", "Mercado", "Direcc.", "Nodo", "Hora", "MW", "Precio DA", "Precio RT"]
            st.dataframe(t_disp, use_container_width=True, hide_index=True, height=380)

            # P&L estimado
            if "precio_da" in trades.columns and "precio_rt" in trades.columns:
                trades["pnl"] = (
                    (pd.to_numeric(trades["precio_rt"], errors="coerce") -
                     pd.to_numeric(trades["precio_da"], errors="coerce")) *
                    pd.to_numeric(trades["mw"], errors="coerce")
                )
                pnl_total = trades["pnl"].sum()
                col_pnl = COL_POS if pnl_total >= 0 else COL_NEG
                st.markdown(kpi("P&L Estimado", f"${pnl_total:+,.0f} USD",
                                "Basado en DA vs RT registrados", col_pnl), unsafe_allow_html=True)

    with col_b:
        st.markdown("#### ECD Facturas XiiX (CENACE settlement)")
        df = ecd["xiix_facturas"]
        if df.empty:
            st.info("Sin ECDs procesados en el rango. Descarga los ECDs primero.")
        else:
            total = _sum_total(df)
            st.markdown(kpi("Total liquidado por CENACE", _mxn(total),
                            f"{len(df)} conceptos", COL_ACC), unsafe_allow_html=True)
            st.markdown("<div style='height:6px;'></div>", unsafe_allow_html=True)
            disp_cols = [c for c in ["CONCEPTO_DE_PAGO", "PRECIO", "CANTIDAD", "IMPORTE", "IVA", "TOTAL"]
                         if c in df.columns]
            st.dataframe(df[disp_cols], use_container_width=True, hide_index=True, height=340)

    # Nota de conciliacion
    st.markdown("""
    <div style='background:#1e1800;border:1px solid #7a5c00;border-radius:4px;
                padding:10px 14px;margin-top:12px;color:#c8a200;font-size:.82rem;'>
    <strong>Conciliacion manual:</strong> Compara los MW y conceptos de los trades registrados
    contra los conceptos en los ECDs. Los conceptos CENACE usan codigos tipo
    <code>ELA</code> (exportacion LAA), <code>ERD</code> (exportacion RRD),
    <code>IGT</code> (importacion GT), etc.
    </div>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# PÁGINA: DESCARGAR ECD
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Descargar ECD":
    st.markdown("# Descargar ECDs — CENACE SOAP API")

    st.markdown("""
    <div style='background:#1a1e2e;border:1px solid #2d3350;border-radius:6px;padding:12px 16px;margin-bottom:16px;'>
    <div style='color:#a78bfa;font-size:.78rem;font-weight:600;margin-bottom:6px;'>CREDENCIALES CENACE</div>
    <div style='font-size:.8rem;color:#5a6280;'>
    Usuario BCA: <code style='color:#c0c4cc;'>EnriqueXTSBCA</code> &nbsp;|&nbsp;
    Usuario SIN: <code style='color:#c0c4cc;'>EnriqueXTSSIN</code> &nbsp;|&nbsp;
    Password: <code style='color:#c0c4cc;'>XTSENPV1</code>
    </div>
    <div style='font-size:.78rem;color:#5a6280;margin-top:4px;'>
    Destino: <code style='color:#c0c4cc;'>Facturacion/{ano}/{mes}/{dia}/EC{fecha}{sistema}-M024{subcuenta}.csv</code>
    </div>
    </div>
    """, unsafe_allow_html=True)

    # Estado de archivos en el rango
    try:
        missing = _list_missing_files()
    except Exception:
        missing = []

    n_total  = (fecha_fin - fecha_ini).days + 1
    archivos_esperados = n_total * 8  # 4 BCA + 4 SIN subcuentas
    n_missing = len(missing)
    n_ok      = archivos_esperados - n_missing

    k1, k2, k3 = st.columns(3)
    with k1: st.markdown(kpi("Esperados", str(archivos_esperados), f"{n_total} dias x 8 subcuentas", COL_ACC), unsafe_allow_html=True)
    with k2: st.markdown(kpi("Encontrados", str(n_ok),      "Ya en carpeta local", COL_POS), unsafe_allow_html=True)
    with k3: st.markdown(kpi("Faltantes",   str(n_missing), "Por descargar", COL_WARN if n_missing else COL_POS), unsafe_allow_html=True)

    if missing:
        st.markdown("#### Archivos faltantes")
        st.dataframe(pd.DataFrame({"Archivo": [os.path.basename(f) for f in missing],
                                   "Fecha": [os.path.basename(os.path.dirname(f)) for f in missing]}),
                     use_container_width=True, hide_index=True, height=200)

    st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        sistema_dl = st.selectbox("Sistema a descargar", ["BCA", "SIN", "Ambos"], key="dl_sistema")
    with col2:
        skip_existing = st.checkbox("Saltar archivos ya descargados", value=True, key="dl_skip")

    if st.button("Descargar ECDs", type="primary", use_container_width=True):
        sistemas = ["BCA", "SIN"] if sistema_dl == "Ambos" else [sistema_dl]
        progress = st.progress(0, text="Iniciando descarga...")
        log_area = st.empty()
        logs = []

        try:
            from etl.cenace.ecd_extractor import download_ecd
            total_dias = (fecha_fin - fecha_ini).days + 1 * len(sistemas)
            done = 0
            for sis in sistemas:
                resultado = download_ecd(fecha_ini, fecha_fin, sis, skip_existing=skip_existing)
                done += total_dias
                progress.progress(min(done / (total_dias * len(sistemas)), 1.0))
                logs.append(f"[{sis}] OK: {len(resultado['ok'])} | Skip: {len(resultado['skipped'])} | Error: {len(resultado['error'])}")
                if resultado["error"]:
                    logs.append(f"  Fechas con error: {resultado['error']}")
            log_area.code("\n".join(logs))
            st.success("Descarga completada. Recarga la pagina para ver el nuevo estado.")
            st.cache_data.clear()
        except ImportError:
            st.error("Modulo 'zeep' no instalado. Ejecuta: pip install zeep")
        except Exception as e:
            st.error(f"Error en descarga: {e}")


# ── Footer ─────────────────────────────────────────────────────────────────────
st.markdown(
    "<div style='margin-top:32px;text-align:center;color:#2d3350;font-size:.65rem;"
    "border-top:1px solid #1e2540;padding-top:12px;'>"
    "XTS Back Office v1.0.0 · XIIX Trading Solutions</div>",
    unsafe_allow_html=True,
)
