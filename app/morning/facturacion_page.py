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

    _PASOS = [
        "1 · Descarga de EDCs",
        "2 · Organizar archivos por fecha",
        "3 · Extraer datos de EDCs",
        "4 · Generar facturas",
        "5 · Generar notas de crédito/débito",
    ]

    # ── Session state init ────────────────────────────────────────────────────
    if "fac_w" not in st.session_state:
        st.session_state.fac_w = {"step": "inicio", "log": []}

    w   = st.session_state.fac_w
    log = w["log"]

    def _append_log(kind, text):
        log.append((kind, text))

    def _show_log():
        for kind, text in log:
            if kind == "ok":
                st.success(text)
            elif kind == "err":
                st.error(text)
            else:
                st.code(text, language=None)

    def _exec(cmd, label):
        with st.spinner(f"{label}..."):
            try:
                r = subprocess.run(cmd, capture_output=True, text=True,
                                   cwd=_FAC_DIR, timeout=600)
                out = (r.stdout or "") + ("\n" + r.stderr if r.stderr else "")
                _append_log("out", out[-4000:].strip())
                if r.returncode == 0:
                    _append_log("ok", f"✓ {label} completado.")
                    return True
                else:
                    _append_log("err", f"✗ {label} terminó con errores.")
                    return False
            except subprocess.TimeoutExpired:
                _append_log("err", f"Tiempo límite excedido en {label}.")
            except Exception as e:
                _append_log("err", f"Error: {e}")
        return False

    # ── Botón reiniciar (siempre visible si no es inicio) ─────────────────────
    if w["step"] != "inicio":
        if st.button("🔄 Reiniciar flujo", key="btn_reset"):
            st.session_state.fac_w = {"step": "inicio", "log": []}
            st.rerun()
        st.markdown("<br>", unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════════════════
    # PASO 0 — ¿Desde dónde empezar?
    # ══════════════════════════════════════════════════════════════════════════
    if w["step"] == "inicio":
        st.markdown("##### Pasos disponibles")
        for p in _PASOS:
            st.markdown(f"<div style='color:#c0c4cc;font-size:0.82rem;margin:2px 0;'>• {p}</div>",
                        unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

        desde = st.selectbox("¿Desde qué paso quieres empezar?", [1, 2, 3, 4, 5],
                             format_func=lambda x: _PASOS[x-1], key="w_desde")

        if st.button(f"▶  Iniciar desde paso {desde}", key="btn_iniciar"):
            w["desde"] = desde
            if desde <= 3:
                ok = _exec(
                    [_sys.executable, RUN_WEEKLY, "--desde", str(desde), "--hasta", "3"],
                    f"Pasos {desde}–3"
                )
                w["step"] = "review_fac" if ok else "inicio"
            elif desde == 4:
                w["step"] = "review_fac"
            else:
                w["step"] = "review_notas"
            st.rerun()

    # ══════════════════════════════════════════════════════════════════════════
    # PASO 1 — Revisión de Facturas + Folio
    # ══════════════════════════════════════════════════════════════════════════
    elif w["step"] == "review_fac":
        _show_log()
        st.divider()
        st.markdown("### Paso 4 · Facturas")
        st.caption("Revisa las facturas generadas y confirma antes de subir a Click Factura.")

        try:
            df_fac = pd.read_csv(PATH_FACTURAS)
            df_fac.fillna(0, inplace=True)
            cols_show = [c for c in ["FUF","Participante","Periodo ECD","Subtotal","IVA","TOTAL"]
                         if c in df_fac.columns]
            st.dataframe(df_fac[cols_show], use_container_width=True, hide_index=True)
            total = df_fac["TOTAL"].sum() if "TOTAL" in df_fac.columns else 0
            st.markdown(f"<div style='text-align:right;color:#00d4e8;font-weight:700;"
                        f"margin-top:4px;'>Total: ${total:,.2f} · {len(df_fac)} facturas</div>",
                        unsafe_allow_html=True)
        except FileNotFoundError:
            st.warning("XiiXFacturas.csv no encontrado. ¿Corriste el paso 3?")
        except Exception as e:
            st.warning(f"No se pudo cargar: {e}")

        st.markdown("<br>", unsafe_allow_html=True)
        folio_fac = st.number_input("Ingresa el número de folio inicial para Facturas:",
                                    min_value=1, step=1, value=1, key="w_folio_fac")
        ok_fac = st.checkbox("✅  Las facturas son correctas, subir a Click Factura",
                             key="w_confirm_fac")

        if st.button("▶  Subir Facturas", key="btn_subir_fac", disabled=not ok_fac):
            w["folio_fac"] = int(folio_fac)
            ok = _exec([_sys.executable, SCRIPT_FAC, "--folio", str(int(folio_fac))],
                       "Paso 4 — Facturas")
            w["step"] = "review_notas" if ok else "review_fac"
            st.rerun()

    # ══════════════════════════════════════════════════════════════════════════
    # PASO 2 — Revisión de Notas + Folio
    # ══════════════════════════════════════════════════════════════════════════
    elif w["step"] == "review_notas":
        _show_log()
        st.divider()
        st.markdown("### Paso 5 · Notas de Crédito/Débito")
        st.caption("Revisa las notas generadas y confirma antes de subir a Click Factura.")

        try:
            df_not = pd.read_excel(PATH_NOTAS)
            df_not.fillna(0, inplace=True)
            cols_show_n = [c for c in ["FUF","Participante","Periodo ECD","Importe Original","Monto Ajuste","IVA","TOTAL"]
                           if c in df_not.columns]
            st.dataframe(df_not[cols_show_n], use_container_width=True, hide_index=True)
            total_n = df_not["TOTAL"].sum() if "TOTAL" in df_not.columns else 0
            st.markdown(f"<div style='text-align:right;color:#FF6B35;font-weight:700;"
                        f"margin-top:4px;'>Total: ${total_n:,.2f} · {len(df_not)} notas</div>",
                        unsafe_allow_html=True)
        except FileNotFoundError:
            st.warning("XiiXNotas.xlsx no encontrado.")
        except Exception as e:
            st.warning(f"No se pudo cargar: {e}")

        st.markdown("<br>", unsafe_allow_html=True)
        folio_notas = st.number_input("Ingresa el número de folio inicial para Notas:",
                                      min_value=1, step=1, value=1, key="w_folio_notas")
        ok_notas = st.checkbox("✅  Las notas son correctas, subir a Click Factura",
                               key="w_confirm_notas")

        if st.button("▶  Subir Notas", key="btn_subir_notas", disabled=not ok_notas):
            w["folio_notas"] = int(folio_notas)
            _exec([_sys.executable, SCRIPT_NOTAS, "--folio", str(int(folio_notas))],
                  "Paso 5 — Notas")
            w["step"] = "done"
            st.rerun()

    # ══════════════════════════════════════════════════════════════════════════
    # DONE
    # ══════════════════════════════════════════════════════════════════════════
    elif w["step"] == "done":
        _show_log()
        st.divider()
        st.success("🎉 Flujo de facturación semanal completado.")
        if st.button("🔄 Nuevo flujo semanal", key="btn_nuevo"):
            st.session_state.fac_w = {"step": "inicio", "log": []}
            st.rerun()

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
