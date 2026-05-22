"""
Ofertas Morning — Captura de break-even y MWs por hora/tier/ruta/dirección
XTS Morning Portal — página 8_Ofertas.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import streamlit as st
import pandas as pd
from datetime import date, timedelta
import base64 as _b64
import datetime as _dt
import requests as _req
import urllib3
from zoneinfo import ZoneInfo
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ── CENACE SOAP constants ──────────────────────────────────────────────────────
_CREDS = {
    "Marco": {
        "SIN": ("MarcoXTSSIN", "Xtsmvb1#",     "6aa97f2fa73efd8852ce6a81de397264c078b2d4"),
        "BCA": ("MarcoXTSBCA", "Xtsmvb1#",     "6aa97f2fa73efd8852ce6a81de397264c078b2d4"),
    },
    "Pedro": {
        "SIN": ("PedroXTSSIN", "L4?El/24-A3l", "643209d422593a13bbe0ca3c724e6efec58e7ae9"),
        "BCA": ("PedroXTSBCA", "L4?El/24-A3l", "643209d422593a13bbe0ca3c724e6efec58e7ae9"),
    },
}
_URL_CE  = "https://ws01.cenace.gob.mx:8082/mxswmem/EnviarOfertaCompraEnergiaService.asmx"
_URL_TE  = "https://ws01.cenace.gob.mx:8082/mxswmem/EnviarOfertaTermica1Service.asmx"
_HDRS_CE = {"Host": "ws01.cenace.gob.mx", "Content-Type": "application/soap+xml; charset=UTF-8",
            "SOAPAction": "http://xmlns.cenace.com/enviarOfertaCompraEnergia"}
_HDRS_TE = {"Host": "ws01.cenace.gob.mx", "Content-Type": "application/soap+xml; charset=UTF-8",
            "SOAPAction": "http://xmlns.cenace.com/enviarOfertaTermica"}
_NODOS_C = {
    "SIN": {"CE": ["M02406LAA01", "M02406RRD01", "M02402GUA01", "M02406EAP01"],
            "TE": ["M02406LAAIMP", "M02406RRDIMP", "M02402GUAIMP", "M02406EAPIMP"]},
    "BCA": {"CE": ["M02407IVY01", "M02407OMS01"],
            "TE": ["M02407IVYIMP", "M02407OMSIMP"]},
}
# mx_node → código CENACE
_NODE_CE  = {"LAA": "M02406LAA01",  "RRD": "M02406RRD01",
             "GUA": "M02402GUA01",  "EAP": "M02406EAP01",
             "IVY": "M02407IVY01",  "OMS": "M02407OMS01"}
_NODE_TE  = {"LAA": "M02406LAAIMP", "RRD": "M02406RRDIMP",
             "GUA": "M02402GUAIMP", "EAP": "M02406EAPIMP",
             "IVY": "M02407IVYIMP", "OMS": "M02407OMSIMP"}
_SISTEMA_NODE = {k: "SIN" for k in ("LAA","RRD","GUA","EAP")}
_SISTEMA_NODE.update({k: "BCA" for k in ("IVY","OMS")})
_AQ_JSON = ('{"ofertaArranque":{"tiempoParoCaliente":1,"costoArranqueCaliente":0.0,'
            '"tiempoParoTibio":0,"costoArranqueTibio":0.0,"tiempoParoFrio":0,'
            '"costoArranqueFrio":0.0,"oaMezclaCalienteGas":0.0,"oaMezclaCalienteCombustoleo":0.0,'
            '"oaMezclaCalienteDiesel":0.0,"oaMezclaCalienteCa":0.0,"oaMezclaCalienteCap":0.0,'
            '"oaMezclaCalienteCas":0.0,"oaMezclaTibioGas":0.0,"oaMezclaTibioCombustoleo":0.0,'
            '"oaMezclaTibioDiesel":0.0,"oaMezclaTibioCa":0.0,"oaMezclaTibioCap":0.0,'
            '"oaMezclaTibioCas":0.0,"oaMezclaFrioGas":0.0,"oaMezclaFrioCombustoleo":0.0,'
            '"oaMezclaFrioDiesel":0.0,"oaMezclaFrioCa":0.0,"oaMezclaFrioCap":0.0,'
            '"oaMezclaFrioCas":0.0,"oiMezcla1Gas":0.0,"oiMezcla1Combustoleo":0.0,'
            '"oiMezcla1Diesel":0.0,"oiMezcla1Ca":0.0,"oiMezcla1Cap":0.0,"oiMezcla1Cas":0.0,'
            '"oiMezcla2Gas":0.0,"oiMezcla2Combustoleo":0.0,"oiMezcla2Diesel":0.0,'
            '"oiMezcla2Ca":0.0,"oiMezcla2Cap":0.0,"oiMezcla2Cas":0.0,"oiMezcla3Gas":0.0,'
            '"oiMezcla3Combustoleo":0.0,"oiMezcla3Diesel":0.0,"oiMezcla3Ca":0.0,'
            '"oiMezcla3Cap":0.0,"oiMezcla3Cas":0}}')

def _soap_ce(user, pwd, hd, sistema, carga, fecha, df):
    horas = ",\n".join(
        f'{{"hora":{h+1},"idSubInt":1,"demandaFijaMw":0.0,'
        f'"oiMw01":{df.iloc[h]["MW1"]},"oiPrecio01":{df.iloc[h]["P1"]},'
        f'"oiMw02":{df.iloc[h]["MW2"]},"oiPrecio02":{df.iloc[h]["P2"]},'
        f'"oiMw03":{df.iloc[h]["MW3"]},"oiPrecio03":{df.iloc[h]["P3"]}}}'
        for h in range(24)
    )
    return (f'<soap12:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
            f'xmlns:xsd="http://www.w3.org/2001/XMLSchema" '
            f'xmlns:soap12="http://www.w3.org/2003/05/soap-envelope">'
            f'<soap12:Header><Authentication xmlns="http://xmlns.cenace.com/">'
            f'<userNameToken>{user}</userNameToken><passwordToken>{pwd}</passwordToken>'
            f'<hd>{hd}</hd></Authentication></soap12:Header><soap12:Body>'
            f'<enviarOfertaCompraEnergia xmlns="http://xmlns.cenace.com/">'
            f'<clvParticipante>M024</clvParticipante>'
            f'<fechaInicial>{fecha}</fechaInicial><fechaFinal>{fecha}</fechaFinal>'
            f'<clvCarga>{carga}</clvCarga><clvSistema>{sistema}</clvSistema>'
            f'<jsonOE>{{"ofertaEconomica":[{horas}]}}</jsonOE>'
            f'</enviarOfertaCompraEnergia></soap12:Body></soap12:Envelope>')

def _soap_te(user, pwd, hd, sistema, central, fecha, df):
    horas = ",\n".join(
        f'{{"mezclaCombustible":"M1","hora":{h+1},"idSubInt":1,'
        f'"limDespEcoMax":{sum(df.iloc[h][f"MW{s}"] for s in range(1,12))},'
        f'"limDespEcoMin":0.0,"costoOpePotenciaMin":0.0,'
        + ",".join(f'"oiMw{s:02d}":{df.iloc[h][f"MW{s}"]},"oiPrecio{s:02d}":{df.iloc[h][f"P{s}"]}'
                   for s in range(1, 12))
        + ',"orgMwRR10":0.0,"orgPrecioRR10":0.0,"orgMwRNR10":0.0,"orgPrecioRNR10":0.0,'
          '"orgMwRRS":0.0,"orgPrecioRRS":0.0,"orgMwRNRS":0.0,"orgPrecioRNRS":0.0,'
          '"orgMwRREG":0.0,"orgPrecioRREG":0.0}'
        for h in range(24)
    )
    return (f'<soap12:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
            f'xmlns:xsd="http://www.w3.org/2001/XMLSchema" '
            f'xmlns:soap12="http://www.w3.org/2003/05/soap-envelope">'
            f'<soap12:Header><Authentication xmlns="http://xmlns.cenace.com/">'
            f'<userNameToken>{user}</userNameToken><passwordToken>{pwd}</passwordToken>'
            f'<hd>{hd}</hd></Authentication></soap12:Header><soap12:Body>'
            f'<enviarOfertaTermica xmlns="http://xmlns.cenace.com/">'
            f'<clvParticipante>M024</clvParticipante>'
            f'<fechaInicial>{fecha}</fechaInicial><fechaFinal>{fecha}</fechaFinal>'
            f'<clvCentral>{central}</clvCentral><clvUnidad>{central}</clvUnidad>'
            f'<clvSistema>{sistema}</clvSistema><estatusAsignacion>2</estatusAsignacion>'
            f'<jsonAQ>{_AQ_JSON}</jsonAQ>'
            f'<jsonOE>{{"ofertaEconomica":[{horas}]}}</jsonOE>'
            f'</enviarOfertaTermica></soap12:Body></soap12:Envelope>')

def _send_soap(url, headers, body):
    try:
        r = _req.post(url, data=body.encode("utf-8"), headers=headers, verify=False, timeout=30)
        return r.status_code, r.content.decode("utf-8", errors="replace")
    except Exception as e:
        return None, str(e)

def _empty_ce():
    return pd.DataFrame({"HE": range(1,25), "MW1":[0.0]*24,"P1":[0.0]*24,
                          "MW2":[0.0]*24,"P2":[0.0]*24,"MW3":[0.0]*24,"P3":[0.0]*24})

def _empty_te():
    d = {"HE": list(range(1,25))}
    for s in range(1,12): d[f"MW{s}"]=[0.0]*24; d[f"P{s}"]=[0.0]*24
    return pd.DataFrame(d)

from app.morning.data_loader import (
    load_tipo_cambio, load_counterparties, load_fees, load_paths,
    load_morning_offers_for_edit, save_morning_offers, load_be_ofertado,
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    header,[data-testid="stHeader"],[data-testid="stToolbar"],
    [data-testid="stDecoration"],footer,#MainMenu{display:none !important;}
    html,body,.stApp{background-color:#1a1e2e !important;}
    .block-container{padding-top:1.2rem !important;max-width:100% !important;
                     background-color:#1a1e2e !important;}
    html,body,[class*="css"]{color:#c0c4cc !important;
                              font-family:'Segoe UI','Consolas',monospace;}
    h1{color:#00d4e8 !important;font-size:1.4rem !important;font-weight:700 !important;
       letter-spacing:1.5px !important;text-transform:uppercase !important;
       border-bottom:1px solid #2d3350 !important;padding-bottom:0.5rem !important;}
    h2,h3{color:#c0c4cc !important;font-size:0.95rem !important;
          letter-spacing:1px !important;text-transform:uppercase !important;}
    [data-testid="stSidebar"]{background-color:#12151f !important;
                               border-right:1px solid #2d3350 !important;}
    [data-testid="stMetricValue"]{color:#00d4e8 !important;font-size:1.4rem !important;
                                   font-weight:700 !important;}
    [data-testid="stMetricLabel"]{color:#5a6280 !important;font-size:0.72rem !important;
                                   letter-spacing:1px !important;text-transform:uppercase !important;}
    .stButton>button{background-color:#1e2130 !important;color:#c0c4cc !important;
                     border:1px solid #2d3350 !important;border-radius:4px !important;}
    .stButton>button:hover{border-color:#00d4e8 !important;color:#00d4e8 !important;}
    /* data_editor */
    [data-testid="stDataEditor"] th{background-color:#12151f !important;
                                     color:#5a6280 !important;font-size:0.72rem !important;}
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
        f"font-family:Segoe UI,sans-serif;margin-top:6px;'>OFERTAS MORNING</div></div>",
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
    st.page_link("pages/9_Config.py",      label="⚙️ Config Trading")
    st.divider()
    if st.button("Cerrar Sesión", use_container_width=True, key="of_logout"):
        st.session_state.logged_in = False
        st.session_state.auth = None
        st.rerun()

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("# 📋 Ofertas Morning")
st.markdown(
    "<div style='color:#5a6280;font-size:0.8rem;margin-bottom:16px;'>"
    "Ingresa break-even (USD) y MWs por hora · 3 tiers · IMPO/EXPO · 4 rutas frontera"
    "</div>",
    unsafe_allow_html=True,
)

# ── Cargar configuración ──────────────────────────────────────────────────────
fees  = load_fees()
cps   = load_counterparties()
paths = load_paths()
tc_live, _ = load_tipo_cambio()

cp_names = [cp["name"] for cp in cps]
cp_codes = [cp["code"] for cp in cps]
_reset_v = st.session_state.get("_of_reset_v", 0)

# ── Offset DST ────────────────────────────────────────────────────────────────
def _auto_dst() -> bool:
    """True si ERCOT (CPT) corre 1h adelante de México (CST) — DST activo."""
    try:
        now = _dt.datetime.now()
        ercot = now.astimezone(ZoneInfo("America/Chicago")).utcoffset().total_seconds()
        mx    = now.astimezone(ZoneInfo("America/Mexico_City")).utcoffset().total_seconds()
        return int((ercot - mx) / 3600) > 0
    except Exception:
        return False

# ── Controles superiores ──────────────────────────────────────────────────────
c_date, c_tdc, c_dst, c_info = st.columns([1, 1, 1, 3])
with c_date:
    trade_date = st.date_input("Fecha operación (DA)", value=date.today() + timedelta(days=1), key="of_date")
with c_tdc:
    tdc = st.number_input("TDC (MXN/USD)", value=round(tc_live, 4),
                          step=0.0001, format="%.4f", key="of_tdc")
with c_dst:
    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
    dst_on = st.checkbox(
        "DST activo (+1h)",
        value=st.session_state.get("of_dst_on", _auto_dst()),
        key="of_dst_on",
        help="ERCOT corre 1h adelante de México (mar–nov). Se detecta automáticamente pero puedes cambiarlo.",
    )
    if st.session_state.get("_of_dst_prev") != dst_on:
        st.session_state["_of_dst_prev"] = dst_on
        for k in list(st.session_state.keys()):
            if k.startswith("_base_editor_"):
                del st.session_state[k]
        st.rerun()

_cpt_off = 1 if dst_on else 0

with c_info:
    fee_ti = fees.get("IMPORT", 20) + fees.get("CARBON", 1) + fees.get("SLEEVE", 3)
    fee_te = fees.get("EXPORT", 15) + fees.get("CARBON", 1) + fees.get("SLEEVE", 3)
    cps_info = " · ".join(
        f"{cp['name']} (Δ${float(cp['price_delta_usd']):+.0f})" for cp in cps
    )
    dst_label = (
        "<b style='color:#f59e0b;'>⚠ DST +1h</b> — ERCOT HE N+1 = CENACE HE N"
        if dst_on else
        "<b style='color:#34d399;'>✓ Sin offset</b> — ERCOT HE = CENACE HE"
    )
    st.markdown(
        f"<div style='padding-top:6px;color:#5a6280;font-size:0.75rem;line-height:1.9;'>"
        f"Fees IMPO: <b style='color:#00d4e8;'>${fee_ti}/MWh</b> &nbsp;|&nbsp; "
        f"Fees EXPO: <b style='color:#00d4e8;'>${fee_te}/MWh</b><br>"
        f"Contrapartes: <b style='color:#c0c4cc;'>{cps_info}</b><br>"
        f"{dst_label}"
        f"</div>",
        unsafe_allow_html=True,
    )

# ── Limpiar estado si cambia la fecha ─────────────────────────────────────────
if st.session_state.get("_of_last_date") != str(trade_date):
    for k in list(st.session_state.keys()):
        if (k.startswith("_of_be_") or k.startswith("_of_mw_") or
                k.startswith("_of_prev_") or k.startswith("_base_editor_")):
            del st.session_state[k]
    st.session_state["_of_last_date"] = str(trade_date)

st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)


# ── Helpers ───────────────────────────────────────────────────────────────────
def _empty_be_grid() -> pd.DataFrame:
    return pd.DataFrame([
        {"HE": he, "HE CPT": he + _cpt_off,
         "T1 BE $": 0.0, "T2 BE $": 0.0, "T3 BE $": 0.0}
        for he in range(1, 25)
    ])

def _empty_mw_grid() -> pd.DataFrame:
    return pd.DataFrame([
        {"HE": he, "T1 MW": 0.0, "T2 MW": 0.0, "T3 MW": 0.0}
        for he in range(1, 25)
    ])

def _be_col_cfg(editable: bool = True) -> dict:
    cfg = {"HE": st.column_config.NumberColumn("HE", disabled=True, width="small", format="%d")}
    for t in [1, 2, 3]:
        cfg[f"T{t} BE $"] = st.column_config.NumberColumn(
            f"T{t} BE $USD", min_value=0.0, step=0.5, format="$%.2f",
            disabled=not editable,
        )
    return cfg

def _mw_col_cfg() -> dict:
    return {
        "HE": st.column_config.NumberColumn("HE", disabled=True, width="small", format="%d"),
        "T1 MW": st.column_config.NumberColumn("T1 MW", min_value=0.0, step=1.0, format="%.1f"),
        "T2 MW": st.column_config.NumberColumn("T2 MW", min_value=0.0, step=1.0, format="%.1f"),
        "T3 MW": st.column_config.NumberColumn("T3 MW", min_value=0.0, step=1.0, format="%.1f"),
    }

def _combined_col_cfg() -> dict:
    """HE | HE CPT | T1 BE $ | T2 BE $ | T3 BE $ | T1 MW | T2 MW | T3 MW — tabla unificada por CP."""
    cfg = {"HE":     st.column_config.NumberColumn("HE CST",  width="small", format="%d")}
    cfg["HE CPT"] = st.column_config.NumberColumn("HE CPT",  width="small", format="%d")
    for t in [1, 2, 3]:
        cfg[f"T{t} BE $"] = st.column_config.NumberColumn(
            f"T{t} BE $USD", step=0.5, format="$%.2f",
        )
    cfg["T1 MW"] = st.column_config.NumberColumn("T1 MW", min_value=0.0, step=1.0, format="%.1f")
    cfg["T2 MW"] = st.column_config.NumberColumn("T2 MW", min_value=0.0, step=1.0, format="%.1f")
    cfg["T3 MW"] = st.column_config.NumberColumn("T3 MW", min_value=0.0, step=1.0, format="%.1f")
    return cfg

def _current_editor_data(base_key: str, editor_key: str) -> pd.DataFrame:
    """Aplica el delta del editor sobre el base para obtener el estado actual."""
    base = st.session_state.get(base_key)
    if base is None:
        return _empty_be_grid()
    df = base.copy()
    delta = st.session_state.get(editor_key, {})
    for row_idx, changes in delta.get("edited_rows", {}).items():
        for col, val in changes.items():
            if col in df.columns:
                df.at[int(row_idx), col] = val
    return df


def _build_priced_rows(editor_df: pd.DataFrame, direction: str,
                       cp: dict, tdc_val: float, fees_val: dict) -> list:
    """Convierte editor DF a lista de 24 dicts {MW1,P1,MW2,P2,MW3,P3} en MXN."""
    fee_c = fees_val.get("CARBON", 1.0)
    fee_s = fees_val.get("SLEEVE", 3.0)
    delta  = float(cp["price_delta_usd"])
    if direction == "IMPO":
        fee_d, sign = fees_val.get("IMPORT", 20.0), 1
    else:
        fee_d, sign = fees_val.get("EXPORT", 15.0), -1
    fee_tot = fee_d + fee_c + fee_s
    rows = []
    for _, row in editor_df.iterrows():
        mw1 = float(row["T1 MW"]); mw2 = float(row["T2 MW"]); mw3 = float(row["T3 MW"])
        rows.append({
            "MW1": mw1,
            "P1":  round((float(row["T1 BE $"]) + sign * (delta + fee_tot)) * tdc_val, 2) if mw1 > 0 else 0.0,
            "MW2": mw2,
            "P2":  round((float(row["T2 BE $"]) + sign * (delta + fee_tot)) * tdc_val, 2) if mw2 > 0 else 0.0,
            "MW3": mw3,
            "P3":  round((float(row["T3 BE $"]) + sign * (delta + fee_tot)) * tdc_val, 2) if mw3 > 0 else 0.0,
        })
    return rows

def _rows_to_ce_df(rows: list) -> pd.DataFrame:
    """CE solo soporta 3 tiers — toma los primeros 3 del dict."""
    return pd.DataFrame({
        "MW1": [float(r.get("MW1", 0.0)) for r in rows],
        "P1":  [float(r.get("P1",  0.0)) for r in rows],
        "MW2": [float(r.get("MW2", 0.0)) for r in rows],
        "P2":  [float(r.get("P2",  0.0)) for r in rows],
        "MW3": [float(r.get("MW3", 0.0)) for r in rows],
        "P3":  [float(r.get("P3",  0.0)) for r in rows],
    })

def _rows_to_te_df(rows: list) -> pd.DataFrame:
    """TE soporta hasta 11 tiers."""
    d = {}
    for s in range(1, 12):
        d[f"MW{s}"] = [float(r.get(f"MW{s}", 0.0)) for r in rows]
        d[f"P{s}"]  = [float(r.get(f"P{s}",  0.0)) for r in rows]
    return pd.DataFrame(d)

def _empty_priced_rows() -> list:
    return [{"MW1":0.0,"P1":0.0,"MW2":0.0,"P2":0.0,"MW3":0.0,"P3":0.0} for _ in range(24)]

def _build_combined_priced_rows(path_code: str, direction: str) -> list:
    """Combina los 3 CPs en un solo set de tiers por hora.
    IMPO (TE): ordenado ascendente por precio — hasta 11 tiers.
    EXPO (CE): ordenado descendente, mismos precios se suman — máx 3 tiers.
    """
    reverse = (direction == "EXPO")
    cp_priced = []
    for ci, cp in enumerate(cps):
        df = _get_editor_df(path_code, direction, ci)
        if "T1 MW" in df.columns:
            cp_priced.append(_build_priced_rows(df, direction, cp, tdc, fees))
        else:
            cp_priced.append(_empty_priced_rows())

    combined = []
    for he_idx in range(24):
        tiers: list[tuple[float, float]] = []
        for cp_rows in cp_priced:
            r = cp_rows[he_idx]
            for t in range(1, 4):
                mw = float(r.get(f"MW{t}", 0.0))
                p  = float(r.get(f"P{t}",  0.0))
                if mw > 0:
                    tiers.append((p, mw))
        tiers.sort(key=lambda x: x[0], reverse=reverse)
        # Fusionar tiers con mismo precio (necesario para CE que solo tiene 3 slots)
        merged: list[list] = []
        for p, mw in tiers:
            if merged and merged[-1][0] == p:
                merged[-1][1] += mw
            else:
                merged.append([p, mw])
        row: dict = {}
        for i, (p, mw) in enumerate(merged, 1):
            row[f"MW{i}"] = mw
            row[f"P{i}"]  = p
        combined.append(row)
    return combined

def _build_save_grid(path_code: str, direction: str) -> pd.DataFrame:
    """Construye grid_df con BEs del primer CP no-cero y MWs por CP para save_morning_offers."""
    n_cps = len(cps)
    rows = [{"HE": he, **{f"T{t} BE $": 0.0 for t in [1,2,3]},
             **{f"T{t} MW C{ci+1}": 0.0 for t in [1,2,3] for ci in range(n_cps)}}
            for he in range(1, 25)]
    grid = pd.DataFrame(rows)
    dfs = [_get_editor_df(path_code, direction, ci) for ci in range(n_cps)]
    # BEs: primer CP que tenga valores no-cero (los BEs son iguales para todos los CPs)
    for t in [1, 2, 3]:
        col = f"T{t} BE $"
        for df in dfs:
            if "T1 BE $" not in df.columns:
                continue
            vals = df[col].values
            if any(v != 0 for v in vals):
                grid[col] = vals
                break
    # MWs: por CP
    for ci, df in enumerate(dfs):
        if "T1 MW" not in df.columns:
            continue
        for t in [1, 2, 3]:
            grid[f"T{t} MW C{ci+1}"] = df[f"T{t} MW"].values
    return grid


def _get_editor_df(path_code: str, direction: str, cp_idx: int) -> pd.DataFrame:
    """Lee estado actual del editor para un path/dirección/CP."""
    key_be = f"_of_be_{path_code}_{direction}"
    ek     = f"editor_{key_be}_c{cp_idx+1}_v{_reset_v}"
    bk     = f"_base_{ek}"
    return _current_editor_data(bk, ek)


def _build_full_grid(be_df: pd.DataFrame, mw_dfs: list) -> pd.DataFrame:
    """Combina BE grid + MW grids en el formato de 13 columnas para guardar."""
    full = be_df.copy()
    for i, mw_df in enumerate(mw_dfs, start=1):
        full[f"T1 MW C{i}"] = mw_df["T1 MW"].values
        full[f"T2 MW C{i}"] = mw_df["T2 MW"].values
        full[f"T3 MW C{i}"] = mw_df["T3 MW"].values
    return full


def _calc_preview(df: pd.DataFrame, direction: str) -> list[dict]:
    """Calcula precios MXN y retorna filas para la tabla de preview."""
    fee_carbon = fees.get("CARBON", 1.0)
    fee_sleeve = fees.get("SLEEVE", 3.0)
    if direction == "IMPO":
        fee_dir, sign = fees.get("IMPORT", 20.0), 1
    else:
        fee_dir, sign = fees.get("EXPORT", 15.0), -1
    fee_total = fee_dir + fee_carbon + fee_sleeve

    rows = []
    for _, row in df.iterrows():
        r = {"HE": int(row["HE"])}
        for t in [1, 2, 3]:
            be = float(row[f"T{t} BE $"])
            for i, cp in enumerate(cps, start=1):
                delta = float(cp["price_delta_usd"])
                be_cp = be + sign * delta
                p_mxn = (be_cp + sign * fee_total) * tdc
                mw = float(row[f"T{t} MW C{i}"])
                r[f"T{t} {cp['name']}"] = f"${p_mxn:,.2f} ({mw:.0f}MW)"
        rows.append(r)
    return rows


def _dark_table(rows: list[dict]) -> str:
    if not rows:
        return ""
    headers = list(rows[0].keys())
    th = "".join(
        f"<th style='padding:6px 10px;text-align:left;color:#5a6280;"
        f"font-size:0.68rem;letter-spacing:1px;text-transform:uppercase;"
        f"border-bottom:1px solid #2d3350;font-weight:600;white-space:nowrap;'>{h}</th>"
        for h in headers
    )
    body = ""
    for i, row in enumerate(rows):
        bg = "#1a1e2e" if i % 2 == 0 else "#1e2130"
        cells = "".join(
            f"<td style='padding:5px 10px;color:#c0c4cc;"
            f"font-size:0.78rem;border-bottom:1px solid #1e2540;white-space:nowrap;'>{v}</td>"
            for v in row.values()
        )
        body += f"<tr style='background:{bg};'>{cells}</tr>"
    return (
        "<div style='overflow-x:auto;border:1px solid #2d3350;border-radius:6px;'>"
        f"<table style='width:100%;border-collapse:collapse;background:#1a1e2e;'>"
        f"<thead><tr style='background:#12151f;'>{th}</tr></thead>"
        f"<tbody>{body}</tbody></table></div>"
    )


def _render_section(path: dict, direction: str, cp_filter: int = 0):
    """Renderiza IMPO o EXPO de una ruta para la contraparte seleccionada."""
    key_be        = f"_of_be_{path['code']}_{direction}"
    key_prev      = f"_of_prev_{path['code']}_{direction}"
    dir_label     = "IMPORTACIÓN" if direction == "IMPO" else "EXPORTACIÓN"
    dir_icon      = "📥" if direction == "IMPO" else "📤"
    fee_total     = fee_ti if direction == "IMPO" else fee_te

    idx           = cp_filter
    cp            = cps[idx]
    editor_key    = f"editor_{key_be}_c{idx+1}_v{_reset_v}"
    base_key      = f"_base_{editor_key}"
    mw_base_key   = f"{base_key}_mw"
    mw_editor_key = f"{editor_key}_mw"

    # ── Controles: dirección card + Tier Spread BE + Tier Spread MW ──────────
    dir_color = "#00d4e8" if direction == "IMPO" else "#f59e0b"
    dir_bg    = "#0a1e2b" if direction == "IMPO" else "#241a06"

    h_info, h_be, h_mw = st.columns([3, 2, 2])

    with h_info:
        st.markdown(
            f"<div style='padding:8px 14px;background:{dir_bg};"
            f"border-left:3px solid {dir_color};border-radius:4px;'>"
            f"<div style='color:{dir_color};font-size:0.78rem;font-weight:700;"
            f"letter-spacing:1.5px;text-transform:uppercase;'>{dir_icon} {dir_label}</div>"
            f"<div style='color:#5a6280;font-size:0.7rem;margin-top:3px;'>"
            f"Fees &nbsp;<b style='color:#c0c4cc;'>${fee_total}/MWh</b></div>"
            f"</div>",
            unsafe_allow_html=True,
        )

    with h_be:
        st.markdown(
            "<div style='color:#5a6280;font-size:0.62rem;text-transform:uppercase;"
            "letter-spacing:1px;margin-bottom:3px;'>Tier Spread BE $</div>",
            unsafe_allow_html=True,
        )
        be_c1, be_c2 = st.columns([1, 1])
        with be_c1:
            be_spread = st.number_input(
                "BE spread", value=5.0, step=0.25, format="%.2f",
                key=f"sp_be_{key_be}", label_visibility="collapsed",
            )
        with be_c2:
            if st.button("Aplicar", key=f"ts_be_{key_be}", use_container_width=True):
                base = _current_editor_data(base_key, editor_key)
                s = 1 if direction == "IMPO" else -1
                base["T2 BE $"] = base["T1 BE $"] + s * be_spread
                base["T3 BE $"] = base["T1 BE $"] + s * 2 * be_spread
                st.session_state[base_key] = base
                if editor_key in st.session_state:
                    del st.session_state[editor_key]
                st.rerun()

    with h_mw:
        st.markdown(
            "<div style='color:#5a6280;font-size:0.62rem;text-transform:uppercase;"
            "letter-spacing:1px;margin-bottom:3px;'>Tier Spread MW</div>",
            unsafe_allow_html=True,
        )
        mw_c1, mw_c2 = st.columns([1, 1])
        with mw_c1:
            mw_spread = st.number_input(
                "MW spread", value=10.0, step=1.0, format="%.1f",
                key=f"sp_mw_{key_be}", label_visibility="collapsed",
            )
        with mw_c2:
            if st.button("Aplicar", key=f"ts_mw_{key_be}", use_container_width=True):
                base = _current_editor_data(base_key, editor_key)
                base["T2 MW"] = (base["T1 MW"] + mw_spread).clip(lower=0)
                base["T3 MW"] = (base["T1 MW"] + 2 * mw_spread).clip(lower=0)
                st.session_state[base_key] = base
                if editor_key in st.session_state:
                    del st.session_state[editor_key]
                st.rerun()

    # ── Inicializar base estable (solo una vez o tras reset explícito) ────────
    if base_key not in st.session_state:
        existing = load_morning_offers_for_edit(str(trade_date), path["id"], direction)
        if not existing.empty:
            be_grid = existing[["HE", "T1 BE $", "T2 BE $", "T3 BE $"]].copy()
            mw_cols = [f"T{t} MW C{idx+1}" for t in [1, 2, 3]]
            if all(c in existing.columns for c in mw_cols):
                mw_grid = existing[["HE"] + mw_cols].rename(columns={
                    f"T1 MW C{idx+1}": "T1 MW",
                    f"T2 MW C{idx+1}": "T2 MW",
                    f"T3 MW C{idx+1}": "T3 MW",
                }).copy()
            else:
                mw_grid = _empty_mw_grid()
        else:
            be_grid = _empty_be_grid()
            mw_grid = _empty_mw_grid()

        display = be_grid.copy()
        display["T1 MW"] = mw_grid["T1 MW"].values
        display["T2 MW"] = mw_grid["T2 MW"].values
        display["T3 MW"] = mw_grid["T3 MW"].values
        if "HE CPT" in display.columns:
            display["HE CPT"] = [he + _cpt_off for he in range(1, 25)]
        else:
            display.insert(1, "HE CPT", [he + _cpt_off for he in range(1, 25)])
        st.session_state[base_key] = display

    # ── Sincronizar HE CPT si el offset cambió (toggle DST) ──────────────────
    if "HE CPT" not in st.session_state[base_key].columns:
        st.session_state[base_key].insert(
            1, "HE CPT", [int(h) + _cpt_off for h in st.session_state[base_key]["HE"]]
        )

    # ── Editor — todo editable para cualquier contraparte (HE y HE CPT bloqueados) ──
    edited = st.data_editor(
        st.session_state[base_key],
        key=editor_key,
        use_container_width=True,
        column_config=_combined_col_cfg(),
        disabled=["HE", "HE CPT"],
        hide_index=True,
        height=510,
    )



# ── Tabs principales ──────────────────────────────────────────────────────────
tab_be, tab_cenace = st.tabs(["📊 Break-even / Precios", "🚀 Enviar a CENACE MDA"])

# ══════════════ TAB 1: Break-even ════════════════════════════════════════════
with tab_be:
    # ── Selectores de mercado y contraparte ───────────────────────────────────
    sf1, sf2, sf3, sf4, sf5, sf6 = st.columns([1, 1, 1, 1, 1, 1])
    with sf1:
        mercado_sel = st.selectbox(
            "Mercado",
            ["ERCOT", "CAISO"],
            key="of_mercado",
        )
    with sf2:
        cp_sel = st.selectbox(
            "Contraparte",
            [cp["name"] for cp in cps],
            key="of_cp",
        )
    with sf4:
        st.markdown("<div style='height:22px'></div>", unsafe_allow_html=True)
        if st.button("📋 Igualar rutas", key="btn_equal_paths", use_container_width=True,
                     help="Copia la primera ruta del mercado a todas las demás (IMPO y EXPO)"):
            _mkt   = st.session_state.get("of_mercado", "ERCOT")
            _fpaths = [p for p in paths if p["market"] == _mkt]
            _cp_name = st.session_state.get("of_cp", cps[0]["name"])
            _cp_idx  = next(i for i, c in enumerate(cps) if c["name"] == _cp_name)
            if len(_fpaths) >= 2:
                src = _fpaths[0]
                for _dir in ["IMPO", "EXPO"]:
                    _src_kbe = f"_of_be_{src['code']}_{_dir}"
                    _src_ek  = f"editor_{_src_kbe}_c{_cp_idx+1}_v{_reset_v}"
                    _src_bk  = f"_base_{_src_ek}"
                    _src_df  = _current_editor_data(_src_bk, _src_ek)
                    for dst in _fpaths[1:]:
                        _dst_kbe = f"_of_be_{dst['code']}_{_dir}"
                        _dst_ek  = f"editor_{_dst_kbe}_c{_cp_idx+1}_v{_reset_v}"
                        _dst_bk  = f"_base_{_dst_ek}"
                        st.session_state[_dst_bk] = _src_df.copy()
                        if _dst_ek in st.session_state:
                            del st.session_state[_dst_ek]
            st.rerun()
    with sf5:
        st.markdown("<div style='height:22px'></div>", unsafe_allow_html=True)
        if st.button("💾 Guardar", key="btn_save_draft", use_container_width=True,
                     help="Guarda en BD sin enviar a CENACE"):
            _mkt    = st.session_state.get("of_mercado", "ERCOT")
            _fpaths = [p for p in paths if p["market"] == _mkt]
            _errs   = []
            for _p in _fpaths:
                for _dir in ["IMPO", "EXPO"]:
                    _ok, _msg = save_morning_offers(
                        str(trade_date), _p["id"], _dir, tdc, fees,
                        _build_save_grid(_p["code"], _dir), cps, _cpt_off,
                    )
                    if not _ok:
                        _errs.append(f"{_p['name']} {_dir}: {_msg}")
            if _errs:
                st.error("\n".join(_errs))
            else:
                st.success("Guardado")
    with sf6:
        st.markdown("<div style='height:22px'></div>", unsafe_allow_html=True)
        if st.button("🗑 Clear All", key="btn_clear_all", use_container_width=True):
            st.session_state["_of_reset_v"] = st.session_state.get("_of_reset_v", 0) + 1
            for k in list(st.session_state.keys()):
                if (k.startswith("_base_editor_") or k.startswith("editor__of_be_")
                        or k.startswith("_of_prev_")):
                    del st.session_state[k]
            st.rerun()
    cp_idx = next(i for i, cp in enumerate(cps) if cp["name"] == cp_sel)

    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

    # ── Filtrar rutas por mercado ─────────────────────────────────────────────
    mkt_key = mercado_sel
    filtered_paths = [p for p in paths if p["market"] == mkt_key]

    icons  = {"CAISO": "☀️", "ERCOT": "⚡"}
    labels = [f"{icons.get(p['market'], '🔌')} {p['name']}" for p in filtered_paths]
    path_tabs = st.tabs(labels) if filtered_paths else []

    for path, ptab in zip(filtered_paths, path_tabs):
        with ptab:
            _render_section(path, "IMPO", cp_filter=cp_idx)
            st.markdown(
                "<div style='border-top:1px solid #2d3350;margin:20px 0 16px 0;'></div>",
                unsafe_allow_html=True,
            )
            _render_section(path, "EXPO", cp_filter=cp_idx)

# ══════════════ TAB 2: Enviar a CENACE ═══════════════════════════════════════
with tab_cenace:

    # ── Controles ─────────────────────────────────────────────────────────────
    ec1, ec2 = st.columns([1, 1])
    with ec1:
        cn_usuario = st.selectbox("Usuario CENACE", ["Marco", "Pedro"], key="cn_usuario")
    with ec2:
        cn_fecha = st.date_input("Fecha oferta", value=date.today() + timedelta(days=1), key="cn_fecha")
        cn_fecha_str = cn_fecha.strftime("%d/%m/%Y")

    cp_names_str = " · ".join(f"<span style='color:#34d399;'>{cp['name']}</span>" for cp in cps)
    st.markdown(
        f"<div style='color:#5a6280;font-size:0.72rem;margin-bottom:14px;'>"
        f"SIN: <span style='color:#00d4e8;'>{_CREDS[cn_usuario]['SIN'][0]}</span>"
        f" &nbsp;·&nbsp; BCA: <span style='color:#00d4e8;'>{_CREDS[cn_usuario]['BCA'][0]}</span>"
        f" &nbsp;·&nbsp; Fecha: <span style='color:#f59e0b;'>{cn_fecha_str}</span>"
        f" &nbsp;·&nbsp; CPs: {cp_names_str}</div>",
        unsafe_allow_html=True,
    )

    # ── Botones de envío ───────────────────────────────────────────────────────
    sin_paths = [p for p in paths if p["market"] == "ERCOT"]
    bca_paths = [p for p in paths if p["market"] == "CAISO"]
    _CN_RES_KEY = "cn_send_results"

    def _do_send(system_paths: list, sistema: str):
        results = []
        cn_user, cn_pwd, cn_hd = _CREDS[cn_usuario][sistema]
        for path in system_paths:
            mx = path.get("mx_node", "")
            if mx not in _NODE_CE:
                continue
            # IMPO → TE: todos los CPs combinados, orden ascendente (hasta 11 tiers)
            rows_i = _build_combined_priced_rows(path["code"], "IMPO")
            soap = _soap_te(cn_user, cn_pwd, cn_hd, sistema,
                            _NODE_TE[mx], cn_fecha_str, _rows_to_te_df(rows_i))
            code, resp = _send_soap(_URL_TE, _HDRS_TE, soap)
            results.append({"nodo": _NODE_TE[mx], "tipo": "TE · IMPO", "code": code, "resp": resp})
            ok_i, msg_i = save_morning_offers(
                cn_fecha.strftime("%Y-%m-%d"), path["id"], "IMPO", tdc, fees,
                _build_save_grid(path["code"], "IMPO"), cps, _cpt_off)
            results.append({"nodo": path["name"], "tipo": "💾 BD · IMPO",
                             "code": 200 if ok_i else None, "resp": msg_i})
            # EXPO → CE: todos los CPs combinados, orden descendente (máx 3 tiers)
            rows_e = _build_combined_priced_rows(path["code"], "EXPO")
            soap = _soap_ce(cn_user, cn_pwd, cn_hd, sistema,
                            _NODE_CE[mx], cn_fecha_str, _rows_to_ce_df(rows_e))
            code, resp = _send_soap(_URL_CE, _HDRS_CE, soap)
            results.append({"nodo": _NODE_CE[mx], "tipo": "CE · EXPO", "code": code, "resp": resp})
            ok_e, msg_e = save_morning_offers(
                cn_fecha.strftime("%Y-%m-%d"), path["id"], "EXPO", tdc, fees,
                _build_save_grid(path["code"], "EXPO"), cps, _cpt_off)
            results.append({"nodo": path["name"], "tipo": "💾 BD · EXPO",
                             "code": 200 if ok_e else None, "resp": msg_e})
        # EAP y GUA siempre en ceros (solo SIN)
        if sistema == "SIN":
            zeros = _empty_priced_rows()
            for tipo, url, hdrs, nodo_key, to_df in [
                ("TE · IMPO (ceros)", _URL_TE, _HDRS_TE, "EAP", _rows_to_te_df),
                ("CE · EXPO (ceros)", _URL_CE, _HDRS_CE, "EAP", _rows_to_ce_df),
                ("TE · IMPO (ceros)", _URL_TE, _HDRS_TE, "GUA", _rows_to_te_df),
                ("CE · EXPO (ceros)", _URL_CE, _HDRS_CE, "GUA", _rows_to_ce_df),
            ]:
                fn = _soap_te if "TE" in tipo else _soap_ce
                soap = fn(cn_user, cn_pwd, cn_hd, sistema,
                          (_NODE_TE if "TE" in tipo else _NODE_CE)[nodo_key],
                          cn_fecha_str, to_df(zeros))
                code, resp = _send_soap(url, hdrs, soap)
                results.append({"nodo": (_NODE_TE if "TE" in tipo else _NODE_CE)[nodo_key],
                                 "tipo": tipo, "code": code, "resp": resp})
        return results

    btn_sin, btn_bca = st.columns(2)
    with btn_sin:
        if st.button("⚡ Enviar Ofertas SIN", type="primary",
                     use_container_width=True, key="btn_enviar_sin"):
            with st.spinner("Enviando SIN (LAA · RRD · GUA · EAP)…"):
                st.session_state[_CN_RES_KEY] = _do_send(sin_paths, "SIN")
    with btn_bca:
        if st.button("☀️ Enviar Ofertas BCA", type="primary",
                     use_container_width=True, key="btn_enviar_bca"):
            with st.spinner("Enviando BCA (IVY · OMS)…"):
                st.session_state[_CN_RES_KEY] = _do_send(bca_paths, "BCA")

    # ── Resultados ─────────────────────────────────────────────────────────────
    if _CN_RES_KEY in st.session_state:
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        for r in st.session_state[_CN_RES_KEY]:
            ok    = r["code"] == 200
            color = "#34d399" if ok else "#ef4444"
            icon  = "✅" if ok else "❌"
            st.markdown(
                f"<div style='background:#1e2130;border-left:3px solid {color};"
                f"border-radius:4px;padding:7px 14px;margin:3px 0;'>"
                f"<span style='color:{color};font-weight:700;'>{icon}</span>"
                f" <b style='color:#c0c4cc;'>{r['nodo']}</b>"
                f" <span style='color:#5a6280;font-size:0.75rem;'>· {r['tipo']} · HTTP {r['code']}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )
            with st.expander(f"XML — {r['nodo']}"):
                st.code(r["resp"], language="xml")

    # ── Resumen de precios enviados ────────────────────────────────────────────
    st.markdown(
        "<div style='border-top:1px solid #2d3350;margin:20px 0 14px 0;'></div>"
        "<div style='color:#5a6280;font-size:0.72rem;letter-spacing:1.5px;"
        "text-transform:uppercase;margin-bottom:10px;'>Resumen de precios (MXN/MWh)</div>",
        unsafe_allow_html=True,
    )
    rv1, rv2, rv3, rv4 = st.columns(4)
    with rv1:
        rv_mkt = st.selectbox("Mercado", ["ERCOT", "CAISO"], key="rv_mkt")
    rv_paths = [p for p in paths if p["market"] == rv_mkt]
    with rv2:
        rv_path_name = st.selectbox("Ruta", [p["name"] for p in rv_paths] or ["—"], key="rv_path")
        rv_path = next((p for p in rv_paths if p["name"] == rv_path_name), None)
    with rv3:
        rv_dir = st.selectbox("Dirección", ["IMPO", "EXPO"], key="rv_dir")
    with rv4:
        rv_cp_name = st.selectbox("Contraparte", [cp["name"] for cp in cps], key="rv_cp")
        rv_cp_idx  = next(i for i, cp in enumerate(cps) if cp["name"] == rv_cp_name)
        rv_cp      = cps[rv_cp_idx]

    if rv_path:
        df_rv = _get_editor_df(rv_path["code"], rv_dir, rv_cp_idx)
        has_data = "T1 MW" in df_rv.columns and df_rv["T1 BE $"].abs().sum() > 0
        if has_data:
            priced = _build_priced_rows(df_rv, rv_dir, rv_cp, tdc, fees)
            table_rows = [
                {"HE": h+1,
                 "T1 MW": f"{r['MW1']:.0f}",  "T1 $/MWh": f"${r['P1']:,.2f}",
                 "T2 MW": f"{r['MW2']:.0f}",  "T2 $/MWh": f"${r['P2']:,.2f}",
                 "T3 MW": f"{r['MW3']:.0f}",  "T3 $/MWh": f"${r['P3']:,.2f}"}
                for h, r in enumerate(priced)
            ]
            st.markdown(_dark_table(table_rows), unsafe_allow_html=True)
        else:
            st.info("Sin datos para esta selección. Ingresa BEs y MWs en el tab Break-even.")

    # ── Preview de registro BD ────────────────────────────────────────────────
    st.markdown(
        "<div style='border-top:1px solid #2d3350;margin:28px 0 14px 0;'></div>"
        "<div style='color:#5a6280;font-size:0.72rem;letter-spacing:1.5px;"
        "text-transform:uppercase;margin-bottom:4px;'>Preview — Lo que se registrará en BD al enviar</div>"
        "<div style='color:#5a6280;font-size:0.68rem;margin-bottom:12px;'>"
        "BE IMPO = precio <b>mínimo</b> de tiers con MW&gt;0 &nbsp;·&nbsp; "
        "BE EXPO = precio <b>máximo</b> de tiers con MW&gt;0 &nbsp;·&nbsp; "
        "24 registros/día/nodo &nbsp;·&nbsp; tabla <code>trading.morning_offers</code> col <b>be_ofertado_usd</b>"
        "</div>",
        unsafe_allow_html=True,
    )
    pv_sys = st.radio("Sistema preview", ["SIN — ERCOT", "BCA — CAISO"],
                      horizontal=True, key="pv_sys_radio", label_visibility="collapsed")
    pv_paths = [p for p in (sin_paths if "SIN" in pv_sys else bca_paths)
                if p.get("mx_node", "") in _NODE_CE and p.get("mx_node", "") != "EAP"]

    # Pre-fetch todos los DFs para evitar llamadas repetidas en el loop
    _pv_dfs = {
        (path["code"], direction, ci): _get_editor_df(path["code"], direction, ci)
        for path in pv_paths
        for direction in ["IMPO", "EXPO"]
        for ci in range(len(cps))
    }

    def _eff_be_preview(path_code: str, direction: str, he: int) -> float:
        """Min BE (IMPO) o max BE (EXPO) entre tiers con MW total > 0."""
        candidates = []
        for t in [1, 2, 3]:
            # BE: primer CP con valor no-cero (los BEs son iguales para todos los CPs)
            be_val = 0.0
            for ci in range(len(cps)):
                df_ci = _pv_dfs.get((path_code, direction, ci))
                if df_ci is None or f"T{t} BE $" not in df_ci.columns:
                    continue
                v = float(df_ci.iloc[he - 1].get(f"T{t} BE $", 0.0))
                if v != 0:
                    be_val = v
                    break
            total_mw = sum(
                float(_pv_dfs[(path_code, direction, ci)].iloc[he - 1].get(f"T{t} MW", 0.0))
                for ci in range(len(cps))
                if f"T{t} MW" in _pv_dfs[(path_code, direction, ci)].columns
            )
            if total_mw > 0 and be_val != 0:
                candidates.append(be_val)
        if not candidates:
            return 0.0
        return min(candidates) if direction == "IMPO" else max(candidates)

    # Tabla de BEs por nodo (columnas) × hora (filas)
    be_rows = []
    for he in range(1, 25):
        row: dict = {"HE": he}
        for path in pv_paths:
            mx = path["mx_node"]
            row[f"{mx} IMPO $"] = f"${_eff_be_preview(path['code'], 'IMPO', he):.2f}"
            row[f"{mx} EXPO $"] = f"${_eff_be_preview(path['code'], 'EXPO', he):.2f}"
        be_rows.append(row)
    st.markdown(_dark_table(be_rows), unsafe_allow_html=True)

    # MWs detalle por nodo (expandible)
    for path in pv_paths:
        mx = path["mx_node"]
        with st.expander(f"MWs por hora — {path['name']} ({mx})"):
            impo_dfs = [_get_editor_df(path["code"], "IMPO", ci) for ci in range(len(cps))]
            expo_dfs = [_get_editor_df(path["code"], "EXPO", ci) for ci in range(len(cps))]
            mw_rows = []
            for he in range(1, 25):
                row = {"HE": he}
                for t in [1, 2, 3]:
                    for ci, cp in enumerate(cps):
                        df = impo_dfs[ci]
                        mw = float(df.iloc[he - 1][f"T{t} MW"]) if f"T{t} MW" in df.columns else 0.0
                        row[f"I·T{t} {cp['name'][:4]}"] = f"{mw:.0f}"
                for t in [1, 2, 3]:
                    for ci, cp in enumerate(cps):
                        df = expo_dfs[ci]
                        mw = float(df.iloc[he - 1][f"T{t} MW"]) if f"T{t} MW" in df.columns else 0.0
                        row[f"E·T{t} {cp['name'][:4]}"] = f"{mw:.0f}"
                mw_rows.append(row)
            st.markdown(_dark_table(mw_rows), unsafe_allow_html=True)

    # ── BE Ofertado en BD ────────────────────────────────────────────────────
    st.markdown(
        "<div style='border-top:1px solid #2d3350;margin:28px 0 14px 0;'></div>"
        "<div style='color:#5a6280;font-size:0.72rem;letter-spacing:1.5px;"
        "text-transform:uppercase;margin-bottom:4px;'>BE Ofertado registrado en BD</div>",
        unsafe_allow_html=True,
    )
    bd_col1, bd_col2 = st.columns([1, 3])
    with bd_col1:
        bd_fecha = st.date_input("Fecha BD", value=cn_fecha, key="bd_fecha_input")
    with bd_col2:
        st.markdown("<div style='height:32px'></div>", unsafe_allow_html=True)
        if st.button("🔍 Consultar BD", key="btn_consultar_bd", use_container_width=False):
            st.session_state["bd_be_df"] = load_be_ofertado(bd_fecha.strftime("%Y-%m-%d"))

    if "bd_be_df" in st.session_state:
        df_bd = st.session_state["bd_be_df"]
        if df_bd.empty:
            st.info("Sin registros en BD para esa fecha.")
        else:
            st.markdown(_dark_table(df_bd.to_dict("records")), unsafe_allow_html=True)
