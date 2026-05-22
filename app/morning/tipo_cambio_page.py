"""
Página: Tipo de Cambio — MXN / USD (FIX Banxico)
"""
import sys, os
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, _ROOT)

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import date, timedelta

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

def _get_conn(database="XTS"):
    try:
        from etl.common.db_connection import get_connection
        return get_connection(database)
    except Exception:
        return None

# ── helpers ──────────────────────────────────────────────────────────────────
def _plotly_base(h, title):
    return dict(
        height=h, title=title,
        plot_bgcolor="#131722", paper_bgcolor="#131722",
        font=dict(color="#c0c4cc", family="Consolas,monospace", size=11),
        title_font=dict(color="#00d4e8", size=13),
        xaxis=dict(gridcolor="#1e2540", showgrid=True, zeroline=False),
        yaxis=dict(gridcolor="#1e2540", showgrid=True, zeroline=False),
        margin=dict(l=50, r=20, t=40, b=40),
    )

def _kpi(label, value, fmt="{:.4f}", color="#00d4e8"):
    val_str = fmt.format(value) if value is not None else "—"
    return f"""
    <div style="background:#1e2130;border:1px solid #2d3350;border-radius:8px;
                padding:16px;text-align:center;">
        <div style="color:#5a6280;font-size:0.72rem;letter-spacing:1.5px;
                    text-transform:uppercase;margin-bottom:6px;">{label}</div>
        <div style="color:{color};font-size:1.5rem;font-weight:700;
                    font-family:Consolas,monospace;">{val_str}</div>
    </div>"""

def load_tc_history(dias: int) -> pd.DataFrame:
    fecha_ini = date.today() - timedelta(days=dias)
    conn = _get_conn("XTS")
    if conn is None:
        return pd.DataFrame()
    try:
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            df = pd.read_sql(
                "SELECT CAST(fecha AS DATE) AS fecha, TC "
                "FROM dbo.TIPO_CAMBIO WHERE fecha >= ? ORDER BY fecha",
                conn, params=[fecha_ini],
            )
        conn.close()
        if not df.empty:
            df["fecha"] = pd.to_datetime(df["fecha"])
        return df
    except Exception as e:
        st.error(f"Error cargando tipo de cambio: {e}")
        return pd.DataFrame()

def load_tc_current() -> tuple[float, bool]:
    try:
        import requests
        from bs4 import BeautifulSoup
        r = requests.get(
            "https://www.banxico.org.mx/tipcamb/tipCamMIAction.do",
            headers={"User-Agent": "Mozilla/5.0"}, timeout=10,
        )
        soup = BeautifulSoup(r.text, "html.parser")
        for row in soup.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) >= 3:
                try:
                    val = float(cells[2].get_text(strip=True).replace(",", "."))
                    if 10 < val < 30:
                        return val, True
                except Exception:
                    pass
    except Exception:
        pass
    conn = _get_conn("XTS")
    if conn:
        try:
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                df = pd.read_sql("SELECT TOP 1 TC FROM dbo.TIPO_CAMBIO ORDER BY fecha DESC", conn)
            conn.close()
            if not df.empty:
                return float(df.iloc[0]["TC"]), True
        except Exception:
            pass
    return 17.50, False

# ── page ─────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
html,body,[class*="css"]{color:#c0c4cc!important;font-family:'Segoe UI','Consolas',monospace;}
[data-testid="stSidebar"]{background-color:#131722!important;border-right:1px solid #1e2540!important;}
</style>
""", unsafe_allow_html=True)

st.markdown(
    "<h2 style='color:#00d4e8;letter-spacing:2px;margin-bottom:0;'>💱 TIPO DE CAMBIO — MXN / USD</h2>"
    "<p style='color:#5a6280;font-size:0.8rem;margin-top:4px;'>FIX Banxico · Para solventar obligaciones</p>",
    unsafe_allow_html=True,
)
st.divider()

# slider
dias = st.slider("Días histórico", min_value=1, max_value=90, value=30, step=1)

# datos
tc_actual, is_live = load_tc_current()
df = load_tc_history(dias)

# KPIs
c1, c2, c3, c4 = st.columns(4)
badge = "🟢 LIVE" if is_live else "⚠ DEMO"
c1.markdown(_kpi("TC Actual", tc_actual, "{:.4f}", "#B7D433"), unsafe_allow_html=True)
if not df.empty:
    c2.markdown(_kpi(f"Mínimo {dias}d", df["TC"].min(), "{:.4f}", "#00d4e8"), unsafe_allow_html=True)
    c3.markdown(_kpi(f"Máximo {dias}d", df["TC"].max(), "{:.4f}", "#ff6b6b"), unsafe_allow_html=True)
    c4.markdown(_kpi(f"Promedio {dias}d", df["TC"].mean(), "{:.4f}", "#a78bfa"), unsafe_allow_html=True)

st.markdown("<div style='margin-top:16px;'></div>", unsafe_allow_html=True)

# gráfica
if df.empty:
    st.warning("Sin datos históricos disponibles.")
else:
    fig = go.Figure()

    # área sombreada
    # rango dinámico con margen del 20% del spread
    rng = df["TC"].max() - df["TC"].min()
    margen = max(rng * 0.3, 0.05)
    y_min = df["TC"].min() - margen
    y_max = df["TC"].max() + margen

    # base invisible para fill relativo
    fig.add_trace(go.Scatter(
        x=df["fecha"], y=[y_min] * len(df),
        line=dict(color="rgba(0,0,0,0)"), showlegend=False,
        hoverinfo="skip",
    ))

    fig.add_trace(go.Scatter(
        x=df["fecha"], y=df["TC"],
        fill="tonexty", fillcolor="rgba(0,212,232,0.10)",
        line=dict(color="#00d4e8", width=2),
        name="TC FIX",
        hovertemplate="<b>%{x|%d %b %Y}</b><br>TC: $%{y:.4f}<extra></extra>",
    ))

    avg = df["TC"].mean()
    fig.add_hline(
        y=avg, line_dash="dot", line_color="#a78bfa", line_width=1,
        annotation_text=f"Prom: {avg:.4f}",
        annotation_font_color="#a78bfa", annotation_position="top right",
    )
    fig.add_hline(
        y=tc_actual, line_dash="dash", line_color="#B7D433", line_width=1.5,
        annotation_text=f"Actual: {tc_actual:.4f}",
        annotation_font_color="#B7D433", annotation_position="bottom right",
    )

    fig.update_layout(**_plotly_base(420, f"Tipo de Cambio FIX — últimos {dias} días  (MXN/USD)"))
    fig.update_xaxes(tickformat="%d %b")
    fig.update_yaxes(tickprefix="$", range=[y_min, y_max])
    st.plotly_chart(fig, use_container_width=True)

    # tabla compacta
    with st.expander("Ver datos"):
        tbl = df[["fecha", "TC"]].copy()
        tbl["fecha"] = tbl["fecha"].dt.strftime("%d %b %Y")
        tbl = tbl.rename(columns={"fecha": "Fecha", "TC": "TC (MXN/USD)"})
        tbl = tbl.sort_values("Fecha", ascending=False).reset_index(drop=True)
        st.dataframe(tbl, use_container_width=True, hide_index=True)

st.markdown(
    f"<div style='margin-top:12px;color:#5a6280;font-size:0.72rem;'>Fuente: Banxico SIE · {badge}</div>",
    unsafe_allow_html=True,
)
