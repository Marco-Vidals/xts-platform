"""
XTS Morning Portal — Entrada unificada ERCOT + CAISO
Correr con: streamlit run app/morning/portal.py
"""
import sys
import os
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "Extractors", ".env"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import streamlit as st
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ── Página ────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="XTS Morning Portal",
    page_icon="🔋",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Session state ─────────────────────────────────────────────────────────────
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "auth" not in st.session_state:
    st.session_state.auth = None

# ══════════════════════════════════════════════════════════════════════════════
# CREDENCIALES (mismas que los dashboards)
# ══════════════════════════════════════════════════════════════════════════════
ENVERUS_USER = os.environ.get("ENVERUS_USER", "mvidals@xiix.mx")
ENVERUS_PASS = os.environ.get("ENVERUS_PASS", "")
MU_ROOT      = "https://api.muenergyfutures.com"

import base64 as _b64mod
def _load_logo_b64(path):
    try:
        with open(path, "rb") as f:
            return _b64mod.b64encode(f.read()).decode()
    except Exception:
        return ""
_XTS_B64 = _load_logo_b64(os.path.join(os.path.dirname(__file__), "..", "..", "static", "logoxts_transparent.png"))

# XTS logo — base64 SVG en <img> (el parser markdown nunca ve el '>' del SVG)
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
    enc = _b64mod.b64encode(svg.encode('utf-8')).decode('ascii')
    return f"data:image/svg+xml;base64,{enc}"

_XTS_IMG    = f'<img src="{_xts_logo_uri(44)}" alt="XTS" style="height:44px;display:block;"/>'
_XTS_IMG_SM = f'<img src="{_xts_logo_uri(33)}" alt="XTS" style="height:33px;display:block;"/>'

LOGIN_CSS = """
<style>
    .stApp { background-color: #2d3242 !important; }
    [data-testid="stSidebar"], [data-testid="collapsedControl"] { display: none !important; }
    #MainMenu, footer, header { visibility: hidden !important; }
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
"""

XTS_LOGO_SVG = (
    "<div style='position:fixed;top:16px;left:28px;z-index:999;display:flex;align-items:center;gap:10px;'>"
    + _XTS_IMG
    + "<div style='border-left:1px solid #3d4258;padding-left:10px;'>"
    "<div style='color:#8a90aa;font-size:0.6rem;letter-spacing:2px;text-transform:uppercase;'>Morning Portal</div>"
    "<div style='color:#4a5070;font-size:0.58rem;'>Energy Analytics</div>"
    "</div></div>"
)

def _enverus_login(user: str, password: str):
    """Autenticacion Enverus Mosaic (HTTP Basic Auth)."""
    try:
        resp = requests.get(
            "https://api-mosaic-prod.enverus.com/mosaic-api/datasets",
            auth=(user, password),
            params={"response_type": "csv_wide", "response_info": "base"},
            timeout=15, verify=False,
        )
        if resp.status_code == 200:
            return (user, password)
    except Exception:
        pass
    return None


# ══════════════════════════════════════════════════════════════════════════════
# LOGIN
# ══════════════════════════════════════════════════════════════════════════════
if not st.session_state.logged_in:
    st.markdown(LOGIN_CSS, unsafe_allow_html=True)
    st.markdown(XTS_LOGO_SVG, unsafe_allow_html=True)

    _, col, _ = st.columns([1, 0.85, 1])
    with col:
        st.markdown("<div style='height:90px;'></div>", unsafe_allow_html=True)
        st.markdown(
            """<div style="background:#1e2130; border:1px solid #2d3350; border-radius:8px;
                padding:32px 36px 28px 36px;">
                <div style="color:#00d4e8; font-size:0.72rem; letter-spacing:3px;
                            text-transform:uppercase; margin-bottom:20px; text-align:center;">
                    Acceso al Portal
                </div>""",
            unsafe_allow_html=True,
        )
        user_in = st.text_input("Usuario", value=ENVERUS_USER, key="login_user_portal")
        pass_in = st.text_input("Contraseña", type="password", key="login_pass_portal")

        if st.button("ENTRAR", key="btn_login_portal"):
            if user_in and pass_in:
                with st.spinner("Autenticando..."):
                    auth = _enverus_login(user_in, pass_in)
                if auth:
                    st.session_state.logged_in = True
                    st.session_state.auth = auth
                    st.rerun()
                else:
                    st.error("Credenciales invalidas.")
            else:
                st.error("Ingresa usuario y contraseña.")

        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown(
        '<p style="text-align:center; color:#4a5070; font-size:0.72rem; margin-top:16px;">v1.1.0 · XTS Morning Portal</p>',
        unsafe_allow_html=True,
    )
    st.stop()


# ══════════════════════════════════════════════════════════════════════════════
# PORTAL HOME (post-login)
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<style>
    header, [data-testid="stHeader"], [data-testid="stToolbar"],
    [data-testid="stDecoration"], footer, #MainMenu { display: none !important; }
    html, body, .stApp { background-color: #1a1e2e !important; }
    .block-container { padding-top: 1.2rem !important; background-color: #1a1e2e !important; max-width: 100% !important; }
    html, body, [class*="css"] { color: #c0c4cc !important; font-family: 'Segoe UI', 'Consolas', monospace; }
    [data-testid="stSidebar"] { background-color: #131722 !important; border-right: 1px solid #1e2540 !important; }
    .market-card {
        background: #1e2130; border: 1px solid #2d3350; border-radius: 10px;
        padding: 24px 20px; text-align: center; cursor: pointer;
        transition: border-color 0.2s; height: 270px;
        display: flex; flex-direction: column; justify-content: center;
        align-items: center; overflow: hidden;
    }
    .market-card:hover { border-color: #00d4e8; }
    .market-icon { font-size: 3rem; margin-bottom: 8px; }
    .market-title { color: #00d4e8; font-size: 1.3rem; font-weight: 700; letter-spacing: 1px; }
    .market-desc { color: #5a6280; font-size: 0.82rem; margin-top: 6px; }
    .market-badge {
        display: inline-block; padding: 3px 10px; border-radius: 3px;
        font-size: 0.72rem; font-weight: 600; margin-top: 10px;
    }
    .badge-live { background: #0d2a1e; color: #34d399; border: 1px solid #34d399; }
    .badge-demo { background: #2a1a00; color: #f59e0b; border: 1px solid #f59e0b; }
    /* Botones de cards — estilo consistente */
    .stButton > button {
        background-color: #1e2130 !important; color: #c0c4cc !important;
        border: 1px solid #2d3350 !important; border-radius: 4px !important;
        font-size: 0.85rem !important; font-weight: 600 !important;
        letter-spacing: 0.5px !important; width: 100% !important;
        transition: border-color 0.2s, color 0.2s !important;
    }
    .stButton > button:hover {
        border-color: #00d4e8 !important; color: #00d4e8 !important;
        background-color: #1e2130 !important;
    }
</style>
""", unsafe_allow_html=True)

# Sidebar con navegación
with st.sidebar:
    st.markdown(
        "<div style='text-align:center;padding:14px 0 4px 0;'>"
        + _XTS_IMG
        + "<div style='color:#4a5478;font-size:0.6rem;letter-spacing:2.5px;text-transform:uppercase;"
        "font-family:Segoe UI,sans-serif;margin-top:6px;'>MORNING PORTAL</div></div>",
        unsafe_allow_html=True,
    )
    st.divider()

    st.markdown("<div style='color:#5a6280; font-size:0.7rem; letter-spacing:1.5px; text-transform:uppercase; margin-bottom:6px;'>Mercados</div>", unsafe_allow_html=True)
    st.page_link("pages/1_ERCOT.py",     label="⚡ ERCOT Morning",     help="Precios, load y renovables ERCOT")
    st.page_link("pages/2_CAISO.py",     label="☀️ CAISO Morning",     help="Precios DA/FMM, PML CENACE y solar")
    st.page_link("pages/3_CENACE.py",    label="🇲🇽 CENACE Morning",    help="PML MDA/MTR · SIN y BCA · Mapa de zonas")
    st.page_link("pages/4_Guatemala.py", label="🇬🇹 Guatemala Morning", help="POE AMM · LBR nodo 09LBR-230 · CENACE SIN")

    st.divider()
    st.markdown("<div style='color:#5a6280; font-size:0.7rem; letter-spacing:1.5px; text-transform:uppercase; margin-bottom:6px;'>Operaciones</div>", unsafe_allow_html=True)
    st.page_link("pages/5_Ofertas.py",     label="📋 Ofertas Morning",  help="Captura de ofertas por hora/tier/ruta")
    st.page_link("pages/6_Afternoon.py",   label="🌆 Afternoon",        help="Portal afternoon")
    st.page_link("pages/7_Trading.py",     label="📊 Trading / P&L",   help="Registro de operaciones y P&L")
    st.page_link("pages/8_Facturacion.py", label="📋 Facturación",      help="Estados de cuenta CENACE · ECD")
    st.page_link("pages/9_Config.py",      label="⚙️ Config Trading",   help="Contrapartes, fees y verificador de cálculo")

    st.divider()
    if st.button("Cerrar Sesion", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.auth = None
        st.rerun()

# ── Header ────────────────────────────────────────────────────────────────────
from datetime import datetime
from app.morning.data_loader import load_ercot, load_caiso, load_tipo_cambio

_hdr_auth = st.session_state.auth[0] if st.session_state.auth else ''
_hdr_now  = datetime.now().strftime('%A %d %B %Y  %H:%M')
st.markdown(
    "<div style='display:flex;align-items:center;justify-content:space-between;"
    "padding:0 4px 12px 4px;border-bottom:1px solid #1e2540;margin-bottom:20px;'>"
    "<div style='display:flex;align-items:center;gap:16px;'>"
    + _XTS_IMG_SM
    + "<div>"
    "<div style='color:#c0c4cc;font-size:1rem;font-weight:700;letter-spacing:1px;'>MORNING PORTAL</div>"
    + f"<div style='color:#4a5070;font-size:0.68rem;'>{_hdr_now} CT</div>"
    + "</div></div>"
    + f"<div style='color:#4a5070;font-size:0.75rem;text-align:right;'>"
    f"Bienvenido, <span style='color:#00d4e8;'>{_hdr_auth}</span></div></div>",
    unsafe_allow_html=True,
)

# ── Status de datos ───────────────────────────────────────────────────────────
with st.spinner("Verificando datos..."):
    _, live_ercot = load_ercot(1)
    _, live_caiso = load_caiso(1)
    tc, live_tc = load_tipo_cambio()

# ── Cards de mercados ─────────────────────────────────────────────────────────
st.markdown(
    "<div style='color:#5a6280; font-size:0.72rem; letter-spacing:2px; text-transform:uppercase; margin-bottom:14px;'>Selecciona un mercado</div>",
    unsafe_allow_html=True,
)

c1, c2, c3, c4, c5 = st.columns([1, 1, 1, 1, 1])

ercot_badge  = '<span class="market-badge badge-live">● LIVE</span>' if live_ercot else '<span class="market-badge badge-demo">⚠ DEMO</span>'
caiso_badge  = '<span class="market-badge badge-live">● LIVE</span>' if live_caiso else '<span class="market-badge badge-demo">⚠ DEMO</span>'
cenace_badge = '<span class="market-badge badge-live">● LIVE</span>'
gtm_badge    = '<span class="market-badge badge-live">● LIVE</span>'
tc_badge     = '<span class="market-badge badge-live">● LIVE</span>' if live_tc    else '<span class="market-badge badge-demo">⚠ DEMO</span>'

with c1:
    st.markdown(f"""
    <div class="market-card">
        <div class="market-icon" style="font-size:unset; margin-bottom:10px;">
          <svg width="168" height="58" viewBox="0 0 168 58" xmlns="http://www.w3.org/2000/svg" style="display:block;margin:0 auto;">
            <text x="2" y="44" font-family="'Arial Rounded MT Bold','Helvetica Neue','Arial',sans-serif"
                  font-weight="800" font-style="italic" font-size="42" fill="#5a6878">ercot</text>
            <path d="M 126,9 C 134,3 148,6 151,16" fill="none" stroke="#00b5cc" stroke-width="3.8" stroke-linecap="round"/>
            <path d="M 123,21 C 132,14 147,18 148,28" fill="none" stroke="#00b5cc" stroke-width="3.8" stroke-linecap="round"/>
            <path d="M 150,31 L 139,49 L 147,47 L 137,58 L 161,43 L 152,44 L 163,31 Z" fill="#00b5cc"/>
          </svg>
        </div>
        <div class="market-desc">Texas Grid · DA / RT Prices<br>Load · Wind · DART Spread</div>
        {ercot_badge}
    </div>
    """, unsafe_allow_html=True)
    if st.button("Abrir ERCOT →", use_container_width=True, key="btn_ercot"):
        st.switch_page("pages/1_ERCOT.py")

with c2:
    st.markdown(f"""
    <div class="market-card">
        <div class="market-icon" style="font-size:unset; margin-bottom:10px;">
          <svg width="168" height="58" viewBox="0 0 168 58" xmlns="http://www.w3.org/2000/svg" style="display:block;margin:0 auto;">
            <defs>
              <radialGradient id="sky-p" cx="45%" cy="35%" r="60%">
                <stop offset="0%" stop-color="#c8d8e8"/>
                <stop offset="100%" stop-color="#5888b0"/>
              </radialGradient>
              <radialGradient id="land-p" cx="50%" cy="80%" r="60%">
                <stop offset="0%" stop-color="#90c040"/>
                <stop offset="100%" stop-color="#4a8020"/>
              </radialGradient>
              <clipPath id="globe-p"><circle cx="28" cy="29" r="25"/></clipPath>
            </defs>
            <circle cx="28" cy="29" r="25" fill="url(#sky-p)"/>
            <circle cx="28" cy="12" r="3" fill="white" clip-path="url(#globe-p)"/>
            <g clip-path="url(#globe-p)" stroke="white" stroke-width="1.6" stroke-linecap="round">
              <line x1="28" y1="6" x2="28" y2="3"/><line x1="34" y1="8" x2="37" y2="5"/>
              <line x1="38" y1="13" x2="41" y2="12"/><line x1="22" y1="8" x2="19" y2="5"/>
              <line x1="18" y1="13" x2="15" y2="12"/><line x1="35" y1="17" x2="38" y2="17"/>
              <line x1="21" y1="17" x2="18" y2="17"/>
            </g>
            <path d="M 3,32 Q 14,24 28,30 Q 42,37 53,30" fill="none" stroke="#e07828" stroke-width="8" clip-path="url(#globe-p)" stroke-linecap="round"/>
            <rect x="3" y="39" width="50" height="18" fill="url(#land-p)" clip-path="url(#globe-p)"/>
            <circle cx="28" cy="29" r="25" fill="none" stroke="#88a0b8" stroke-width="1.5"/>
            <text x="61" y="40" font-family="'Segoe UI','Helvetica','Arial',sans-serif"
                  font-weight="700" font-size="30" fill="#5a6878" letter-spacing="2">CAISO</text>
          </svg>
        </div>
        <div class="market-desc">California Grid · DA / FMM<br>PML CENACE · Solar</div>
        {caiso_badge}
    </div>
    """, unsafe_allow_html=True)
    if st.button("Abrir CAISO →", use_container_width=True, key="btn_caiso"):
        st.switch_page("pages/2_CAISO.py")

with c3:
    st.markdown(f"""
    <div class="market-card">
        <div class="market-icon" style="font-size:unset; margin-bottom:10px;">
          <svg width="168" height="58" viewBox="0 0 168 58" xmlns="http://www.w3.org/2000/svg" style="display:block;margin:0 auto;">
            <text x="2" y="44" font-family="'Segoe UI','Arial',sans-serif"
                  font-weight="800" font-size="38" fill="#5a6878" letter-spacing="-1">CENACE</text>
            <circle cx="148" cy="20" r="10" fill="#006847" opacity="0.8"/>
            <circle cx="148" cy="20" r="7"  fill="#FFFFFF" opacity="0.9"/>
            <circle cx="148" cy="20" r="4"  fill="#CE1126" opacity="0.9"/>
          </svg>
        </div>
        <div class="market-desc">México · PML MDA / MTR<br>SIN · BCA · Mapa de Zonas</div>
        {cenace_badge}
    </div>
    """, unsafe_allow_html=True)
    if st.button("Abrir CENACE →", use_container_width=True, key="btn_cenace"):
        st.switch_page("pages/3_CENACE.py")

with c4:
    st.markdown(f"""
    <div class="market-card">
        <div class="market-icon" style="font-size:unset; margin-bottom:10px;">
          <svg width="168" height="58" viewBox="0 0 168 58" xmlns="http://www.w3.org/2000/svg" style="display:block;margin:0 auto;">
            <!-- Guatemala flag stripes -->
            <rect x="2"  y="10" width="18" height="36" rx="2" fill="#4997D0" opacity="0.9"/>
            <rect x="20" y="10" width="18" height="36" fill="#FFFFFF" opacity="0.9"/>
            <rect x="38" y="10" width="18" height="36" rx="2" fill="#4997D0" opacity="0.9"/>
            <!-- AMM text -->
            <text x="64" y="40" font-family="'Segoe UI','Arial',sans-serif"
                  font-weight="800" font-size="30" fill="#5a6878" letter-spacing="1">AMM</text>
          </svg>
        </div>
        <div class="market-desc">Guatemala · POE AMM<br>LBR Nodo 09LBR-230 · CENACE</div>
        {gtm_badge}
    </div>
    """, unsafe_allow_html=True)
    if st.button("Abrir Guatemala →", use_container_width=True, key="btn_gtm"):
        st.switch_page("pages/4_Guatemala.py")

with c5:
    st.markdown(f"""
    <div class="market-card">
        <div class="market-icon">💱</div>
        <div class="market-title">MXN / USD</div>
        <div class="market-desc">Tipo de cambio FIX<br>Banxico · Para solventar obligaciones</div>
        <div style="color:#B7D433; font-size:1.4rem; font-weight:700; margin-top:8px;">{tc:.4f}</div>
        {tc_badge}
    </div>
    """, unsafe_allow_html=True)
    if st.button("Abrir Tipo de Cambio →", use_container_width=True, key="btn_tc"):
        st.switch_page("pages/0_TipoCambio.py")

# ── Segunda fila: Análisis y Operaciones ──────────────────────────────────────
st.markdown("<div style='margin-top:8px; color:#5a6280; font-size:0.72rem; letter-spacing:2px; text-transform:uppercase; margin-bottom:14px;'>Análisis y Operaciones</div>", unsafe_allow_html=True)

ca, cb, cc, cd = st.columns(4)

with ca:
    st.markdown("""
    <div class="market-card">
        <div class="market-icon">📊</div>
        <div class="market-title">Trading / P&L</div>
        <div class="market-desc">P&L diario · Posición por nodo</div>
        <span class="market-badge badge-live">● LIVE</span>
    </div>
    """, unsafe_allow_html=True)
    if st.button("Abrir Trading →", use_container_width=True, key="btn_trading"):
        st.switch_page("pages/7_Trading.py")

with cb:
    st.markdown("""
    <div class="market-card">
        <div class="market-icon">📋</div>
        <div class="market-title">Facturación</div>
        <div class="market-desc">Estados de cuenta CENACE (ECD)<br>BCA · SIN · Liquidaciones</div>
        <span class="market-badge badge-live">● LIVE</span>
    </div>
    """, unsafe_allow_html=True)
    if st.button("Abrir Facturación →", use_container_width=True, key="btn_facturacion"):
        st.switch_page("pages/8_Facturacion.py")

with cc:
    st.markdown("""
    <div class="market-card">
        <div class="market-icon">📋</div>
        <div class="market-title">Ofertas Morning</div>
        <div class="market-desc">Break-even · IMPO/EXPO · 4 rutas</div>
        <span class="market-badge badge-live">● LIVE</span>
    </div>
    """, unsafe_allow_html=True)
    if st.button("Abrir Ofertas →", use_container_width=True, key="btn_ofertas"):
        st.switch_page("pages/5_Ofertas.py")

with cd:
    st.markdown("""
    <div class="market-card">
        <div class="market-icon">🛒</div>
        <div class="market-title">Checkouts</div>
        <div class="market-desc">Gestión de checkouts<br>y liquidaciones</div>
        <span class="market-badge badge-demo">⚙ En Desarrollo</span>
    </div>
    """, unsafe_allow_html=True)
    st.button("Próximamente →", use_container_width=True, key="btn_checkouts", disabled=True)

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown(
    "<div style='margin-top:32px; text-align:center; color:#2d3350; font-size:0.65rem; border-top:1px solid #1e2540; padding-top:12px;'>"
    "XTS Energy Portal v1.1.0 · XIIX Trading Solutions</div>",
    unsafe_allow_html=True,
)
