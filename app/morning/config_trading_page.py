"""
Configuración de Trading — Contrapartes, Fees y Verificador de Cálculo
XTS Morning Portal — página 9_Config.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import streamlit as st
import base64 as _b64

from app.morning.data_loader import (
    load_counterparties, load_fees, load_tipo_cambio,
    save_counterparty, save_fee, calc_offer_prices,
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    header, [data-testid="stHeader"], [data-testid="stToolbar"],
    [data-testid="stDecoration"], footer, #MainMenu { display: none !important; }
    html, body, .stApp { background-color: #1a1e2e !important; }
    .block-container { padding-top: 1.2rem !important; max-width: 100% !important;
                       background-color: #1a1e2e !important; }
    html, body, [class*="css"] { color: #c0c4cc !important;
                                  font-family: 'Segoe UI', 'Consolas', monospace; }
    h1 { color: #00d4e8 !important; font-size: 1.4rem !important; font-weight: 700 !important;
         letter-spacing: 1.5px !important; text-transform: uppercase !important;
         border-bottom: 1px solid #2d3350 !important; padding-bottom: 0.5rem !important; }
    h2, h3 { color: #c0c4cc !important; font-size: 0.95rem !important;
              letter-spacing: 1px !important; text-transform: uppercase !important; }
    [data-testid="stSidebar"] { background-color: #12151f !important;
                                 border-right: 1px solid #2d3350 !important; }
    [data-testid="stMetricValue"] { color: #00d4e8 !important; font-size: 1.4rem !important;
                                     font-weight: 700 !important; }
    [data-testid="stMetricLabel"] { color: #5a6280 !important; font-size: 0.72rem !important;
                                     letter-spacing: 1px !important; text-transform: uppercase !important; }
    .stTextInput > div > div > input,
    .stNumberInput > div > div > input,
    .stSelectbox > div > div { background-color: #12151f !important;
                                border: 1px solid #2d3350 !important; color: #c0c4cc !important; }
    .stForm { background-color: #1e2130 !important; border: 1px solid #2d3350 !important;
              border-radius: 8px !important; padding: 16px !important; }
    div[data-testid="stRadio"] label { color: #c0c4cc !important; }
</style>
""", unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────────────────────────
def _logo(h=33):
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
        f"<img src='{_logo(33)}' style='height:33px;display:block;margin:0 auto;'/>"
        f"<div style='color:#4a5478;font-size:0.6rem;letter-spacing:2.5px;text-transform:uppercase;"
        f"font-family:Segoe UI,sans-serif;margin-top:6px;'>CONFIG TRADING</div></div>",
        unsafe_allow_html=True,
    )
    st.divider()
    st.markdown("<div style='color:#5a6280;font-size:0.7rem;letter-spacing:1.5px;"
                "text-transform:uppercase;margin-bottom:6px;'>Mercados</div>", unsafe_allow_html=True)
    st.page_link("pages/1_ERCOT.py",     label="⚡ ERCOT Morning")
    st.page_link("pages/2_CAISO.py",     label="☀️ CAISO Morning")
    st.page_link("pages/3_CENACE.py",    label="🇲🇽 CENACE Morning")
    st.page_link("pages/4_Guatemala.py", label="🇬🇹 Guatemala Morning")
    st.divider()
    st.markdown("<div style='color:#5a6280;font-size:0.7rem;letter-spacing:1.5px;"
                "text-transform:uppercase;margin-bottom:6px;'>Operaciones</div>", unsafe_allow_html=True)
    st.page_link("pages/5_Ofertas.py",     label="📋 Ofertas Morning")
    st.page_link("pages/6_Afternoon.py",   label="🌅 Afternoon")
    st.page_link("pages/7_Trading.py",     label="📊 Trading / P&L")
    st.page_link("pages/8_Facturacion.py", label="📋 Facturación")
    st.divider()
    st.markdown("<div style='color:#5a6280;font-size:0.7rem;letter-spacing:1.5px;"
                "text-transform:uppercase;margin-bottom:6px;'>Sistema</div>", unsafe_allow_html=True)
    st.page_link("pages/9_Config.py", label="⚙️ Config Trading")
    st.divider()
    if st.button("Cerrar Sesión", use_container_width=True, key="cfg_logout"):
        st.session_state.logged_in = False
        st.session_state.auth = None
        st.rerun()

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("# ⚙️ Configuración de Trading")
st.markdown(
    "<div style='color:#5a6280;font-size:0.8rem;margin-bottom:16px;'>"
    "Gestión de contrapartes, fees y verificador de cálculo de precios"
    "</div>",
    unsafe_allow_html=True,
)

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_cp, tab_fees, tab_calc = st.tabs(["👥 Contrapartes", "💰 Fees", "🧮 Verificar Cálculo"])


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 — Contrapartes
# ═══════════════════════════════════════════════════════════════════════════════
def _dark_table(rows: list[dict]) -> str:
    if not rows:
        return "<div style='color:#5a6280;font-size:0.85rem;padding:12px;'>Sin datos.</div>"
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
        cells = "".join(
            f"<td style='padding:7px 14px;color:#c0c4cc;"
            f"font-size:0.82rem;border-bottom:1px solid #1e2540;'>{v}</td>"
            for v in row.values()
        )
        body += f"<tr style='background:{bg};'>{cells}</tr>"
    return (
        "<div style='overflow-x:auto;border:1px solid #2d3350;border-radius:6px;'>"
        f"<table style='width:100%;border-collapse:collapse;background:#1a1e2e;'>"
        f"<thead><tr style='background:#12151f;'>{th}</tr></thead>"
        f"<tbody>{body}</tbody></table></div>"
    )


with tab_cp:
    cps = load_counterparties()

    # Tabla actual
    st.markdown("### Contrapartes activas")
    rows_cp = [
        {
            "Orden": cp["sort_order"],
            "Código": cp["code"],
            "Nombre": cp["name"],
            "Delta USD/MWh": f"${float(cp['price_delta_usd']):+.2f}",
            "Nota IMPO": f"BE + ${float(cp['price_delta_usd']):.0f} + fees",
            "Nota EXPO": f"BE - ${float(cp['price_delta_usd']):.0f} - fees",
        }
        for cp in cps
    ]
    st.markdown(_dark_table(rows_cp), unsafe_allow_html=True)

    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

    # Formulario editar / agregar
    st.markdown("### Editar contraparte")
    opciones = ["➕ Nueva contraparte"] + [f"{cp['code']} — {cp['name']}" for cp in cps]
    sel = st.selectbox("Seleccionar", opciones, key="cfg_cp_sel")

    cp_edit = None
    if sel != "➕ Nueva contraparte":
        cp_code_sel = sel.split(" — ")[0]
        cp_edit = next((c for c in cps if c["code"] == cp_code_sel), None)

    with st.form("form_cp", clear_on_submit=False):
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            f_code = st.text_input("Código", value=cp_edit["code"] if cp_edit else "", key="f_cp_code")
        with c2:
            f_name = st.text_input("Nombre", value=cp_edit["name"] if cp_edit else "", key="f_cp_name")
        with c3:
            f_delta = st.number_input(
                "Delta USD/MWh",
                value=float(cp_edit["price_delta_usd"]) if cp_edit else 0.0,
                step=0.5, format="%.2f", key="f_cp_delta",
                help="Diferencia de precio vs C1. IMPO suma, EXPO resta.",
            )
        with c4:
            f_order = st.number_input(
                "Orden", min_value=1, max_value=10,
                value=int(cp_edit["sort_order"]) if cp_edit else len(cps) + 1,
                step=1, key="f_cp_order",
            )
        guardar = st.form_submit_button("Guardar contraparte", use_container_width=True)

    if guardar:
        cp_id = int(cp_edit["id"]) if cp_edit else None
        ok, msg = save_counterparty(cp_id, f_code, f_name, f_delta, f_order)
        if ok:
            st.success(f"Contraparte guardada.")
            st.rerun()
        else:
            st.error(f"Error: {msg}")


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 — Fees
# ═══════════════════════════════════════════════════════════════════════════════
with tab_fees:
    fees = load_fees()

    st.markdown("### Fees actuales")
    fee_rows = [
        {
            "Fee": ft,
            "USD/MWh": f"${fv:.2f}",
            "Aplica en": "IMPO" if ft == "IMPORT" else ("EXPO" if ft == "EXPORT" else "IMPO + EXPO"),
        }
        for ft, fv in fees.items()
    ]
    st.markdown(_dark_table(fee_rows), unsafe_allow_html=True)

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    fee_total_impo = fees.get("IMPORT", 20) + fees.get("CARBON", 1) + fees.get("SLEEVE", 3)
    fee_total_expo = fees.get("EXPORT", 15) + fees.get("CARBON", 1) + fees.get("SLEEVE", 3)
    m1, m2 = st.columns(2)
    m1.metric("Total fees IMPO", f"${fee_total_impo:.0f}/MWh",
              help="IMPORT + CARBON + SLEEVE")
    m2.metric("Total fees EXPO", f"${fee_total_expo:.0f}/MWh",
              help="EXPORT + CARBON + SLEEVE")

    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
    st.markdown("### Editar fee")

    with st.form("form_fee", clear_on_submit=False):
        fee_types = list(fees.keys())
        sel_fee = st.selectbox("Fee a editar", fee_types, key="f_fee_sel")
        new_val = st.number_input(
            "Nuevo valor (USD/MWh)",
            value=float(fees.get(sel_fee, 0)),
            min_value=0.0, step=0.5, format="%.2f", key="f_fee_val",
        )
        guardar_fee = st.form_submit_button("Actualizar fee", use_container_width=True)

    if guardar_fee:
        ok, msg = save_fee(sel_fee, new_val)
        if ok:
            st.success(f"{sel_fee} actualizado a ${new_val:.2f}/MWh")
            st.rerun()
        else:
            st.error(f"Error: {msg}")


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3 — Verificador de cálculo
# ═══════════════════════════════════════════════════════════════════════════════
with tab_calc:
    st.markdown("### Verificador de precios")
    st.markdown(
        "<div style='color:#5a6280;font-size:0.8rem;margin-bottom:16px;'>"
        "Ingresa un break-even en USD para C1 y verifica los precios MXN calculados "
        "para cada contraparte en ambas direcciones."
        "</div>",
        unsafe_allow_html=True,
    )

    tc_live, tc_live_ok = load_tipo_cambio()
    fees_calc = load_fees()
    cps_calc  = load_counterparties()

    cc1, cc2, cc3 = st.columns(3)
    with cc1:
        be_input = st.number_input(
            "Break-even C1 (USD/MWh)",
            value=25.0, min_value=0.0, step=0.5, format="%.2f", key="vc_be",
        )
    with cc2:
        tdc_input = st.number_input(
            "TDC (MXN/USD)",
            value=round(tc_live, 4), step=0.0001, format="%.4f", key="vc_tdc",
        )
    with cc3:
        direction_sel = st.radio(
            "Dirección", ["IMPO", "EXPO"], horizontal=True, key="vc_dir",
        )

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    # Calcular
    result = calc_offer_prices(be_input, tdc_input, fees_calc, cps_calc, direction_sel)

    # Mostrar fórmula aplicada
    fee_carbon = fees_calc.get("CARBON", 1)
    fee_sleeve = fees_calc.get("SLEEVE", 3)
    if direction_sel == "IMPO":
        fee_dir = fees_calc.get("IMPORT", 20)
        fee_total = fee_dir + fee_carbon + fee_sleeve
        formula = (f"Precio MXN = (BE + delta + {fee_dir:.0f}+{fee_carbon:.0f}+{fee_sleeve:.0f}) × TDC"
                   f"  →  (BE + delta + {fee_total:.0f}) × {tdc_input:.4f}")
    else:
        fee_dir = fees_calc.get("EXPORT", 15)
        fee_total = fee_dir + fee_carbon + fee_sleeve
        formula = (f"Precio MXN = (BE − delta − {fee_dir:.0f}−{fee_carbon:.0f}−{fee_sleeve:.0f}) × TDC"
                   f"  →  (BE − delta − {fee_total:.0f}) × {tdc_input:.4f}")

    st.markdown(
        f"<div style='background:#12151f;border:1px solid #2d3350;border-radius:6px;"
        f"padding:10px 16px;font-family:Consolas,monospace;color:#00d4e8;"
        f"font-size:0.82rem;margin-bottom:12px;'>{formula}</div>",
        unsafe_allow_html=True,
    )

    # Tabla de resultados
    calc_rows = []
    for r in result:
        calc_rows.append({
            "Contraparte": f"{r['code']} — {r['name']}",
            "Delta":       f"${r['delta']:+.2f}",
            "BE (USD)":    f"${r['be_usd']:.4f}",
            "Precio MXN":  f"${r['price_mxn']:,.4f}",
            "Precio MXN (redondeado)": f"${r['price_mxn']:,.2f}",
        })
    st.markdown(_dark_table(calc_rows), unsafe_allow_html=True)

    # Checks de coherencia para IMPO
    if direction_sel == "IMPO" and len(result) >= 2:
        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
        diffs = []
        for i in range(1, len(result)):
            diff = result[i]["price_mxn"] - result[i-1]["price_mxn"]
            diffs.append(diff)
        all_incremental = all(d >= 0 for d in diffs)
        if all_incremental:
            st.success("✓ Precios incrementales (correcto para IMPO)")
        else:
            st.warning("⚠ Los precios no son estrictamente incrementales — revisa los deltas")

    elif direction_sel == "EXPO" and len(result) >= 2:
        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
        diffs = []
        for i in range(1, len(result)):
            diff = result[i]["price_mxn"] - result[i-1]["price_mxn"]
            diffs.append(diff)
        all_decremental = all(d <= 0 for d in diffs)
        if all_decremental:
            st.success("✓ Precios decrementales (correcto para EXPO)")
        else:
            st.warning("⚠ Los precios no son estrictamente decrementales — revisa los deltas")
