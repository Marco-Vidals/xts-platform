"""
Trading / P&L — Registro de operaciones DART/PTP
Integrado en XTS Morning Portal como página 6_Trading.py
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, date
import base64 as _b64

from app.morning.data_loader import load_trades, _get_conn

# ── Helper tabla HTML oscura ──────────────────────────────────────────────────
def _dark_table(rows: list[dict], pnl_col: str = "P&L") -> str:
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
            color = "#c0c4cc"
            if k == pnl_col:
                try:
                    color = "#2ecc71" if float(str(v).replace("$","").replace("+","").replace(",","")) >= 0 else "#e74c3c"
                except Exception:
                    pass
            elif k == "Dir.":
                color = "#2ecc71" if str(v).upper() == "COMPRA" else "#e74c3c"
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

# ── CSS ───────────────────────────────────────────────────────────────────────
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
    .stForm { background-color: #1e2130 !important; border: 1px solid #2d3350 !important; border-radius: 8px !important; padding: 16px !important; }
    .stTextInput > div > div > input,
    .stNumberInput > div > div > input,
    .stSelectbox > div > div { background-color: #12151f !important; border: 1px solid #2d3350 !important; color: #c0c4cc !important; }
    .pnl-pos { color: #2ecc71 !important; font-weight: 700 !important; }
    .pnl-neg { color: #e74c3c !important; font-weight: 700 !important; }
</style>
""", unsafe_allow_html=True)


# ── Sidebar ───────────────────────────────────────────────────────────────────
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
        f"font-family:Segoe UI,sans-serif;margin-top:6px;'>TRADING / P&L</div></div>",
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
    if st.button("Cerrar Sesión", use_container_width=True, key="trading_logout"):
        st.session_state.logged_in = False
        st.session_state.auth = None
        st.rerun()

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("# 📊 Trading / P&L")

tab_historial, tab_nuevo, tab_pnl = st.tabs(["Historial de Trades", "Registrar Trade", "P&L por Período"])

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 — Historial
# ═══════════════════════════════════════════════════════════════════════════════
with tab_historial:
    dias_sel = st.selectbox("Mostrar últimos", [30, 60, 90, 180, 365], index=2,
                            format_func=lambda x: f"{x} días", key="trades_dias")
    with st.spinner("Cargando trades..."):
        df, is_live = load_trades(dias_sel)

    if not is_live:
        st.warning("Sin conexión a base de datos.")
        st.stop()

    if df.empty:
        st.info("No hay trades registrados en el período seleccionado.")
    else:
        # KPIs
        pnl_total = df["pnl"].sum()
        trades_pos = (df["pnl"] > 0).sum()
        trades_neg = (df["pnl"] < 0).sum()
        win_rate   = trades_pos / len(df) * 100 if len(df) else 0
        avg_pnl    = df["pnl"].mean()

        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("P&L Total",      f"${pnl_total:+,.0f}")
        m2.metric("Trades",         f"{len(df)}")
        m3.metric("Win Rate",       f"{win_rate:.0f}%")
        m4.metric("P&L Promedio",   f"${avg_pnl:+.0f}/trade")
        m5.metric("Mejor Trade",    f"${df['pnl'].max():+,.0f}")

        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

        # Tabla oscura
        rows = []
        for _, row in df.iterrows():
            rows.append({
                "Fecha":      row["fecha_operacion"].strftime("%d/%m/%Y"),
                "Mercado":    row["mercado"],
                "Nodo":       row["nodo"],
                "Dir.":       row["direccion"],
                "Hora":       int(row["hora"]) if pd.notna(row["hora"]) else "",
                "MW":         f"{row['mw']:,.1f}",
                "Precio DA":  f"${row['precio_da']:.2f}",
                "Precio RT":  f"${row['precio_rt']:.2f}",
                "P&L":        f"${row['pnl']:+,.0f}",
                "Contraparte": row["contraparte"] or "",
                "Notas":      (row["notas"] or "")[:40],
            })
        st.markdown(_dark_table(rows), unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 — Registrar nuevo trade
# ═══════════════════════════════════════════════════════════════════════════════
with tab_nuevo:
    st.markdown("### Registrar nueva operación")

    with st.form("form_nuevo_trade", clear_on_submit=True):
        r1c1, r1c2, r1c3 = st.columns(3)
        with r1c1:
            t_fecha = st.date_input("Fecha operación", value=date.today(), key="nt_fecha")
            t_mercado = st.selectbox("Mercado", ["ERCOT_DART", "ERCOT_PTP", "CENACE", "CAISO", "GTM"], key="nt_mercado")
        with r1c2:
            t_nodo = st.text_input("Nodo", placeholder="ej. DC_L, HB_NORTH", key="nt_nodo")
            t_dir  = st.selectbox("Dirección", ["COMPRA", "VENTA"], key="nt_dir",
                                  help="COMPRA = long (ganas si RT > DA) · VENTA = short (ganas si DA > RT)")
        with r1c3:
            t_hora       = st.number_input("Hora (HE)", min_value=1, max_value=24, value=8, key="nt_hora")
            t_contraparte = st.text_input("Contraparte", key="nt_contraparte")

        r2c1, r2c2, r2c3 = st.columns(3)
        with r2c1:
            t_mw       = st.number_input("MW", min_value=0.0, step=1.0, value=10.0, key="nt_mw")
        with r2c2:
            t_precio_da = st.number_input("Precio DA ($/MWh)", min_value=0.0, step=0.01, value=30.0, key="nt_pda")
        with r2c3:
            t_precio_rt = st.number_input("Precio RT ($/MWh)", min_value=0.0, step=0.01, value=35.0, key="nt_prt")

        t_notas = st.text_area("Notas", height=60, key="nt_notas")

        # Preview P&L
        sign = 1 if t_dir == "COMPRA" else -1
        preview_pnl = sign * (t_precio_rt - t_precio_da) * t_mw
        st.markdown(
            f"<div style='color:{'#2ecc71' if preview_pnl >= 0 else '#e74c3c'};"
            f"font-size:1rem;font-weight:700;margin:8px 0;'>"
            f"P&L estimado: ${preview_pnl:+,.2f}</div>",
            unsafe_allow_html=True,
        )

        submitted = st.form_submit_button("Guardar Trade", use_container_width=True)

    if submitted:
        conn = _get_conn("XTS")
        if conn:
            try:
                c = conn.cursor()
                c.execute(
                    "INSERT INTO trading.trades "
                    "(fecha_operacion, mercado, direccion, nodo, hora, mw, precio_da, precio_rt, contraparte, notas) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (str(t_fecha), t_mercado, t_dir, t_nodo.upper(), int(t_hora),
                     float(t_mw), float(t_precio_da), float(t_precio_rt),
                     t_contraparte, t_notas),
                )
                conn.commit()
                conn.close()
                st.success(f"Trade guardado. P&L: ${preview_pnl:+,.2f}")
                st.rerun()
            except Exception as e:
                st.error(f"Error al guardar: {e}")
        else:
            st.error("Sin conexión a base de datos.")


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3 — P&L por período
# ═══════════════════════════════════════════════════════════════════════════════
with tab_pnl:
    with st.spinner("Cargando P&L..."):
        df_all, is_live_all = load_trades(365)

    if not is_live_all or df_all.empty:
        st.info("Sin datos de trades para mostrar P&L.")
    else:
        agrup = st.selectbox("Agrupar por", ["Día", "Semana", "Mes"], key="pnl_agrup")

        df_all["fecha_op"] = df_all["fecha_operacion"].dt.date

        if agrup == "Día":
            grp = df_all.groupby("fecha_op")["pnl"].sum().reset_index()
            grp.columns = ["periodo", "pnl"]
            grp["periodo"] = pd.to_datetime(grp["periodo"])
        elif agrup == "Semana":
            df_all["periodo"] = df_all["fecha_operacion"].dt.to_period("W").dt.start_time
            grp = df_all.groupby("periodo")["pnl"].sum().reset_index()
        else:
            df_all["periodo"] = df_all["fecha_operacion"].dt.to_period("M").dt.start_time
            grp = df_all.groupby("periodo")["pnl"].sum().reset_index()

        grp = grp.sort_values("periodo")
        grp["pnl_acum"] = grp["pnl"].cumsum()

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=grp["periodo"], y=grp["pnl"],
            marker_color=grp["pnl"].apply(lambda v: "#2ecc71" if v >= 0 else "#e74c3c"),
            name="P&L período",
            hovertemplate="<b>%{x}</b><br>P&L: $%{y:+,.0f}<extra></extra>",
        ))
        fig.add_trace(go.Scatter(
            x=grp["periodo"], y=grp["pnl_acum"],
            mode="lines", name="P&L acumulado",
            line=dict(color="#00d4e8", width=2),
            hovertemplate="Acum: $%{y:+,.0f}<extra></extra>",
            yaxis="y2",
        ))
        fig.update_layout(
            title=dict(text=f"P&L por {agrup}", font=dict(size=14, color="#c0c4cc")),
            xaxis=dict(gridcolor="#1e2540", tickfont=dict(color="#5a6280")),
            yaxis=dict(gridcolor="#1e2540", tickfont=dict(color="#5a6280"), tickprefix="$", title="P&L período"),
            yaxis2=dict(overlaying="y", side="right", tickfont=dict(color="#00d4e8"),
                        tickprefix="$", title="P&L acumulado", showgrid=False),
            plot_bgcolor="#12151f", paper_bgcolor="#1a1e2e",
            font=dict(color="#c0c4cc"),
            height=380, legend=dict(x=0.01, y=0.99, font=dict(size=10)),
            margin=dict(t=50, b=40, l=70, r=70),
        )
        st.plotly_chart(fig, use_container_width=True)

        # P&L por nodo
        if "nodo" in df_all.columns:
            st.markdown("### P&L por Nodo")
            by_nodo = df_all.groupby("nodo")["pnl"].agg(["sum", "count", "mean"]).reset_index()
            by_nodo = by_nodo.sort_values("sum", ascending=False)
            nodo_rows = [{
                "Nodo":        r["nodo"],
                "P&L Total":   f"${r['sum']:+,.0f}",
                "# Trades":    int(r["count"]),
                "P&L Promedio": f"${r['mean']:+,.0f}",
            } for _, r in by_nodo.iterrows()]
            st.markdown(_dark_table(nodo_rows, pnl_col="P&L Total"), unsafe_allow_html=True)
