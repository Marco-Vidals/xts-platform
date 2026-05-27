"""
Facturación CENACE — Estados de Cuenta (ECD)
Integrado en XTS Morning Portal como página 7_Facturacion.py
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import streamlit as st
import pandas as pd
from datetime import date, timedelta
import base64 as _b64

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
    .cuenta-badge {
        display: inline-block; padding: 3px 8px; border-radius: 3px;
        font-size: 0.7rem; font-weight: 600; margin: 2px;
        background: #0d2a1e; color: #34d399; border: 1px solid #34d399;
    }
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
        f"font-family:Segoe UI,sans-serif;margin-top:6px;'>FACTURACIÓN</div></div>",
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
    if st.button("Cerrar Sesión", use_container_width=True, key="fac_logout"):
        st.session_state.logged_in = False
        st.session_state.auth = None
        st.rerun()

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("# 📋 Facturación CENACE")
st.markdown(
    "<div style='color:#5a6280;font-size:0.8rem;margin-bottom:16px;'>"
    "Estados de Cuenta CENACE (ECD) · BCA-M024 · SIN-M024 · Liquidaciones y reliquidaciones"
    "</div>",
    unsafe_allow_html=True,
)

# Cuentas disponibles
_CUENTAS = {
    "BCA": ["BCA-M024ERO", "BCA-M024ETJ", "BCA-M024IRO", "BCA-M024ITJ"],
    "SIN": ["SIN-M024ELA", "SIN-M024ERD", "SIN-M024EGT", "SIN-M024IGT"],
}

# ── DB connection helper ──────────────────────────────────────────────────────
def _get_conn():
    import pyodbc
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "Extractors", ".env"))
    return pyodbc.connect(
        f"DRIVER={{ODBC Driver 18 for SQL Server}};"
        f"SERVER={os.environ.get('XTS_DB_SERVER','100.70.216.12')},{os.environ.get('XTS_DB_PORT','1433')};"
        f"DATABASE={os.environ.get('XTS_DB_NAME','XTS')};"
        f"UID={os.environ.get('XTS_DB_USER','sa')};"
        f"PWD={os.environ.get('XTS_DB_PASSWORD','')};"
        f"TrustServerCertificate=yes;"
    )

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_resumen, tab_flujo, tab_fuf = st.tabs(["Resumen", "Flujo Semanal", "Lista FUF"])

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 0 — Resumen Facturación
# ═══════════════════════════════════════════════════════════════════════════════
_PAGE_DIR = os.path.dirname(os.path.abspath(__file__))
FACTURACION_BASE = os.environ.get(
    "FACTURACION_BASE",
    os.path.normpath(os.path.join(_PAGE_DIR, "..", "..", "Facturacion"))
)
PATH_FACTURAS = os.path.join(FACTURACION_BASE, "XiiXFacturas.csv")
PATH_NOTAS    = os.path.join(FACTURACION_BASE, "XiiXNotas.xlsx")

with tab_resumen:
    if st.button("🔄 Actualizar resumen", key="btn_refresh_resumen"):
        st.rerun()

    col_f, col_n = st.columns(2)

    # ── Facturas ──────────────────────────────────────────────────────────────
    with col_f:
        st.markdown("### Facturas")
        try:
            df_fac = pd.read_csv(PATH_FACTURAS)
            df_fac.fillna(0, inplace=True)

            cols_fac = [c for c in ["FUF", "Participante", "Periodo ECD", "Fecha Limite de Pago",
                                     "Subtotal", "Descuento", "IVA", "TOTAL"] if c in df_fac.columns]
            st.dataframe(df_fac[cols_fac], use_container_width=True, hide_index=True)

            total_fac = df_fac["TOTAL"].sum() if "TOTAL" in df_fac.columns else 0
            st.markdown(
                f"<div style='text-align:right;color:#00d4e8;font-size:1.1rem;font-weight:700;"
                f"margin-top:6px;'>Total Facturas: ${total_fac:,.2f}</div>",
                unsafe_allow_html=True,
            )
        except FileNotFoundError:
            st.info("XiiXFacturas.csv no encontrado. Corre el Flujo Semanal primero.")
        except Exception as e:
            st.error(f"Error: {e}")

    # ── Notas ─────────────────────────────────────────────────────────────────
    with col_n:
        st.markdown("### Notas de Crédito / Débito")
        try:
            df_not = pd.read_excel(PATH_NOTAS)
            df_not.fillna(0, inplace=True)

            cols_not = [c for c in ["FUF", "Tipo", "Participante", "Periodo ECD",
                                     "Importe Original", "Monto Ajuste", "IVA", "TOTAL"] if c in df_not.columns]
            st.dataframe(df_not[cols_not], use_container_width=True, hide_index=True)

            total_not = df_not["TOTAL"].sum() if "TOTAL" in df_not.columns else 0
            st.markdown(
                f"<div style='text-align:right;color:#FF6B35;font-size:1.1rem;font-weight:700;"
                f"margin-top:6px;'>Total Notas: ${total_not:,.2f}</div>",
                unsafe_allow_html=True,
            )
        except FileNotFoundError:
            st.info("XiiXNotas.xlsx no encontrado. Corre el Flujo Semanal primero.")
        except Exception as e:
            st.error(f"Error: {e}")

    # ── Gran total ────────────────────────────────────────────────────────────
    try:
        total_fac
    except NameError:
        total_fac = 0
    try:
        total_not
    except NameError:
        total_not = 0

    gran_total = total_fac + total_not
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(
        f"<div style='background:#1e2130;border:1px solid #2d3350;border-left:4px solid #34d399;"
        f"border-radius:6px;padding:14px 20px;text-align:right;'>"
        f"<span style='color:#5a6280;font-size:0.75rem;letter-spacing:1px;text-transform:uppercase;'>Gran Total  (Facturas + Notas)</span><br>"
        f"<span style='color:#34d399;font-size:1.6rem;font-weight:700;font-family:Consolas,monospace;'>${gran_total:,.2f}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )




# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3 — Flujo Semanal
# ═══════════════════════════════════════════════════════════════════════════════
with tab_flujo:
    import subprocess, sys as _sys

    _FAC_DIR = os.path.normpath(os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "..", "Codigos_facturación"
    ))
    RUN_WEEKLY   = os.path.join(_FAC_DIR, "run_weekly.py")
    SCRIPT_FAC   = os.path.join(_FAC_DIR, "facturas.py")
    SCRIPT_NOTAS = os.path.join(_FAC_DIR, "notas.py")

    _PASOS_LABELS = [
        "1 · Descarga de EDCs",
        "2 · Organizar archivos por fecha",
        "3 · Extraer datos de EDCs",
        "4 · Generar facturas",
        "5 · Generar notas de crédito/débito",
    ]

    def _run_script(cmd, label, timeout=600):
        with st.spinner(f"{label}..."):
            try:
                r = subprocess.run(cmd, capture_output=True, text=True,
                                   cwd=_FAC_DIR, timeout=timeout)
                if r.returncode == 0:
                    st.success(f"✓ {label} completado.")
                else:
                    st.error(f"✗ {label} terminó con errores.")
                if r.stdout:
                    st.code(r.stdout[-4000:], language=None)
                if r.stderr:
                    st.code(r.stderr[-2000:], language=None)
                return r.returncode == 0
            except subprocess.TimeoutExpired:
                st.error(f"Tiempo límite excedido en {label}.")
            except Exception as e:
                st.error(f"Error en {label}: {e}")
        return False

    # ── ETAPA 1: Pasos 1-3 ────────────────────────────────────────────────────
    st.markdown("#### Etapa 1 · Descarga y Extracción")
    st.markdown("##### Pasos disponibles")
    for p in _PASOS_LABELS[:3]:
        st.markdown(f"<div style='color:#c0c4cc;font-size:0.82rem;margin:2px 0;'>• {p}</div>",
                    unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    col_d, col_h = st.columns(2)
    with col_d:
        desde_paso = st.selectbox("¿Desde qué paso?", [1, 2, 3],
                                  format_func=lambda x: _PASOS_LABELS[x-1], key="desde_paso")
    with col_h:
        hasta_paso_1 = st.selectbox("¿Hasta qué paso?", [1, 2, 3],
                                    index=2,
                                    format_func=lambda x: _PASOS_LABELS[x-1], key="hasta_paso_1")

    if st.button(f"▶  Correr pasos {desde_paso}–{hasta_paso_1}", key="btn_run_extraccion"):
        _run_script(
            [_sys.executable, RUN_WEEKLY,
             "--desde", str(desde_paso), "--hasta", str(hasta_paso_1)],
            f"Pasos {desde_paso}–{hasta_paso_1}"
        )

    st.divider()

    # ── ETAPA 2: Revisión ─────────────────────────────────────────────────────
    st.markdown("#### Etapa 2 · Revisión")
    st.caption("Revisa que los datos generados sean correctos antes de emitir.")

    _col_f2, _col_n2 = st.columns(2)
    with _col_f2:
        st.markdown("**XiiXFacturas.csv**")
        try:
            _df_prev_fac = pd.read_csv(PATH_FACTURAS)
            _cols_prev = [c for c in ["FUF","Participante","Periodo ECD","TOTAL"] if c in _df_prev_fac.columns]
            st.dataframe(_df_prev_fac[_cols_prev], use_container_width=True, hide_index=True, height=220)
            st.caption(f"{len(_df_prev_fac)} registros")
        except FileNotFoundError:
            st.info("Aún no existe — corre los pasos 1-3 primero.")
        except Exception as e:
            st.warning(f"No se pudo cargar: {e}")

    with _col_n2:
        st.markdown("**XiiXNotas.xlsx**")
        try:
            _df_prev_not = pd.read_excel(PATH_NOTAS)
            _cols_prev_n = [c for c in ["FUF","Participante","Periodo ECD","TOTAL"] if c in _df_prev_not.columns]
            st.dataframe(_df_prev_not[_cols_prev_n], use_container_width=True, hide_index=True, height=220)
            st.caption(f"{len(_df_prev_not)} registros")
        except FileNotFoundError:
            st.info("Aún no existe — corre los pasos 1-3 primero.")
        except Exception as e:
            st.warning(f"No se pudo cargar: {e}")

    confirmado = st.checkbox("✅  Las facturas y notas son correctas, proceder con la emisión",
                             key="fac_confirmado")

    st.divider()

    # ── ETAPA 3: Emisión (Pasos 4-5) ──────────────────────────────────────────
    st.markdown("#### Etapa 3 · Emisión en Click Factura")
    for p in _PASOS_LABELS[3:]:
        st.markdown(f"<div style='color:#c0c4cc;font-size:0.82rem;margin:2px 0;'>• {p}</div>",
                    unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    if not confirmado:
        st.info("Revisa y confirma los datos en Etapa 2 para habilitar la emisión.")
    else:
        col_f4, col_n5 = st.columns(2)
        with col_f4:
            folio_fac = st.number_input("Folio inicial — Facturas",
                                        min_value=1, step=1, value=1, key="folio_fac")
        with col_n5:
            folio_notas = st.number_input("Folio inicial — Notas",
                                          min_value=1, step=1, value=1, key="folio_notas")

        desde_emision = st.selectbox("¿Desde qué paso emitir?", [4, 5],
                                     format_func=lambda x: _PASOS_LABELS[x-1],
                                     key="desde_emision")

        if st.button(f"▶  Emitir desde paso {desde_emision}", key="btn_emitir"):
            ok = True
            if desde_emision <= 4:
                ok = _run_script(
                    [_sys.executable, SCRIPT_FAC, "--folio", str(int(folio_fac))],
                    "Paso 4 — Facturas"
                )
            if ok and desde_emision <= 5:
                _run_script(
                    [_sys.executable, SCRIPT_NOTAS, "--folio", str(int(folio_notas))],
                    "Paso 5 — Notas"
                )

# ═══════════════════════════════════════════════════════════════════════════════
# TAB — Lista FUF
# ═══════════════════════════════════════════════════════════════════════════════
with tab_fuf:
    st.markdown("### Lista FUF — Folios Fiscales")
    st.markdown(
        "<div style='color:#5a6280;font-size:0.8rem;margin-bottom:16px;'>"
        "Tabla de FUFs con UUID, Serie y Folio usada para generar facturas y notas. "
        "Sube un Excel con columnas FUF, UUDI, SERIE, FOLIO para agregar o actualizar registros.</div>",
        unsafe_allow_html=True,
    )

    # ── Tabla actual ──────────────────────────────────────────────────────────
    try:
        conn = _get_conn()
        df_fuf = pd.read_sql("SELECT FUF, UUDI, SERIE, FOLIO FROM facturacion.lista_fuf ORDER BY FUF DESC", conn)
        conn.close()
        st.markdown(f"**{len(df_fuf):,} registros en base de datos**")
        st.dataframe(df_fuf.head(100), use_container_width=True, hide_index=True)
        if len(df_fuf) > 100:
            st.caption(f"Mostrando primeros 100 de {len(df_fuf):,}")
    except Exception as e:
        st.error(f"No se pudo cargar la tabla: {e}")

    st.divider()

    # ── Uploader ──────────────────────────────────────────────────────────────
    st.markdown("#### Actualizar Lista FUF")
    uploaded = st.file_uploader(
        "Sube el Excel actualizado (columnas: FUF, UUDI, SERIE, FOLIO)",
        type=["xlsx", "xls"],
        key="fuf_uploader"
    )

    if uploaded is not None:
        try:
            df_new = pd.read_excel(uploaded)
            df_new.columns = [c.strip().upper() for c in df_new.columns]
            required = {"FUF", "UUDI", "SERIE", "FOLIO"}
            if not required.issubset(set(df_new.columns)):
                st.error(f"El Excel debe tener las columnas: {required}. Encontradas: {set(df_new.columns)}")
            else:
                st.markdown(f"**{len(df_new):,} registros en el archivo.** Vista previa:")
                st.dataframe(df_new.head(10), use_container_width=True, hide_index=True)

                if st.button("💾 Guardar en base de datos", key="btn_save_fuf"):
                    with st.spinner("Actualizando..."):
                        conn = _get_conn()
                        cursor = conn.cursor()
                        inserted = updated = 0
                        for _, row in df_new.iterrows():
                            folio_val = int(row.FOLIO) if pd.notna(row.FOLIO) and str(row.FOLIO).replace('.0','').isdigit() else None
                            cursor.execute("""
                                IF EXISTS (SELECT 1 FROM facturacion.lista_fuf WHERE FUF=?)
                                    UPDATE facturacion.lista_fuf SET UUDI=?, SERIE=?, FOLIO=? WHERE FUF=?
                                ELSE
                                    INSERT INTO facturacion.lista_fuf (FUF,UUDI,SERIE,FOLIO) VALUES (?,?,?,?)
                            """, row.FUF, row.UUDI, row.SERIE, folio_val, row.FUF,
                                row.FUF, row.UUDI, row.SERIE, folio_val)
                        conn.commit()
                        cursor.execute("SELECT COUNT(*) FROM facturacion.lista_fuf")
                        total = cursor.fetchone()[0]
                        conn.close()
                        st.success(f"Lista FUF actualizada. Total en DB: {total:,} registros.")
                        st.rerun()
        except Exception as e:
            st.error(f"Error al procesar el archivo: {e}")
