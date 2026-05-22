"""
Afternoon — Energía Asignada
Embebido en el morning portal vía 10_Afternoon.py
"""
import re as _re
import pandas as _pd
import numpy as _np
import streamlit as st

# ── Colores morning ─────────────────────────────────────────────────────────────
_CYA  = "#00d4e8"
_AMB  = "#f59e0b"
_GRN  = "#34d399"
_RED  = "#f87171"
_BLU  = "#60a5fa"
_SUB  = "#5a6280"
_CARD = "#1e2130"

def _kpi(label, value, sub="", color=None):
    color = color or _CYA
    return (
        f'<div class="kpi-card" style="border-left-color:{color};">'
        f'<div class="kpi-label">{label}</div>'
        f'<div class="kpi-value" style="color:{color};">{value}</div>'
        f'<div class="kpi-sub">{sub}</div>'
        f'</div>'
    )

def _fmt(v, fmt=".2f", prefix="", suffix="", na="—"):
    if v is None or (isinstance(v, float) and _np.isnan(v)):
        return na
    return f"{prefix}{v:{fmt}}{suffix}"

# ── Título ─────────────────────────────────────────────────────────────────────
st.markdown(
    "<h1 style='color:#00d4e8;font-size:1.3rem;font-weight:700;letter-spacing:1.5px;"
    "text-transform:uppercase;border-bottom:1px solid #2d3350;padding-bottom:0.5rem;"
    "margin-bottom:1rem;'>Afternoon · Energía Asignada</h1>",
    unsafe_allow_html=True,
)

# ── Sub-nav (para futuras pestañas) ────────────────────────────────────────────
sub_page = st.selectbox(
    "Sección",
    ["Energía Asignada"],
    key="aft_sub_page",
    label_visibility="collapsed",
)

# ══════════════════════════════════════════════════════════════════════════════
# ENERGÍA ASIGNADA
# ══════════════════════════════════════════════════════════════════════════════
if sub_page == "Energía Asignada":

    uploaded = st.file_uploader(
        "Cargar Excel de Energía Asignada (CENACE)",
        type=["xlsx"],
        key="asig_upload_am",
        help="Archivo 'Energía asignada DD-MM-YYYY M024-XiiX.xlsx'",
    )

    if uploaded is None:
        st.info("Sube el Excel de energía asignada para comenzar.")
        st.stop()

    # Guardar bytes antes de parsear (se usan luego para adjuntar)
    _file_bytes = uploaded.read()
    uploaded.seek(0)

    # ── Parseo del Excel ───────────────────────────────────────────────────────
    try:
        import io as _io
        df_hdr = _pd.read_excel(_io.BytesIO(_file_bytes), header=None, nrows=1, engine="openpyxl")
        df_raw  = _pd.read_excel(_io.BytesIO(_file_bytes), header=3, engine="openpyxl")
        df_raw.columns = [str(c).strip() for c in df_raw.columns]
        df_data = df_raw[df_raw["Clave"].notna()].copy().reset_index(drop=True)
        hour_cols = [c for c in df_data.columns if _re.match(r"^\d+\-\d+$", c)]

        def _he(col):
            hi = int(col.split("-")[1])
            return 24 if hi == 0 else hi

        he_nums = [_he(c) for c in hour_cols]
    except Exception as exc:
        st.error(f"Error leyendo el Excel: {exc}")
        st.stop()

    # ── KPIs de cabecera ──────────────────────────────────────────────────────
    sistema_val  = str(df_data["Sistema"].iloc[0]) if not df_data.empty else "?"
    total_mwh_all = sum(
        float(r.get("Total de flujo Asignado (MWh)", 0) or 0)
        for _, r in df_data.iterrows()
    )
    nodos_con_asig = sum(
        1 for _, r in df_data.iterrows()
        if float(r.get("Total de flujo Asignado (MWh)", 0) or 0) > 0
    )

    h1, h2, h3, h4 = st.columns(4)
    h1.markdown(_kpi("Archivo",         uploaded.name[:28],          "",                       _BLU),  unsafe_allow_html=True)
    h2.markdown(_kpi("Sistema",         sistema_val,                  "",                       _AMB),  unsafe_allow_html=True)
    h3.markdown(_kpi("Total Asignado",  f"{total_mwh_all:.0f} MWh",  f"{len(df_data)} nodos",  _GRN),  unsafe_allow_html=True)
    h4.markdown(_kpi("Con Asignación",  str(nodos_con_asig),          "nodos con MW > 0",       _RED),  unsafe_allow_html=True)

    st.markdown("<div style='height:14px;'></div>", unsafe_allow_html=True)

    fn = uploaded.name  # parte de las claves de sesión

    # ── Tablas por nodo ────────────────────────────────────────────────────────
    summary_rows = []

    for _, row in df_data.iterrows():
        clave    = str(row.get("Clave", "")).strip()
        tipo     = str(row.get("Tipo",  "")).strip()
        tot_asig = float(row.get("Total de flujo Asignado (MWh)", 0) or 0)
        icon     = "📥" if tipo == "IMP" else "📤"

        asig_vals = [float(row.get(hc, 0) or 0) for hc in hour_cols]

        # Persistir MW a Fluir en session_state
        skey = f"fluir_{fn}_{clave}"
        if skey not in st.session_state:
            st.session_state[skey] = asig_vals.copy()

        fluir_ss = st.session_state[skey]
        if len(fluir_ss) != len(asig_vals):
            fluir_ss = asig_vals.copy()
            st.session_state[skey] = fluir_ss

        diff_ss = [a - f for a, f in zip(asig_vals, fluir_ss)]

        df_edit = _pd.DataFrame({
            "HE":            he_nums,
            "Asignado (MW)": asig_vals,
            "Fluir (MW)":    fluir_ss,
            "No Flow (MW)":  diff_ss,
        })

        with st.expander(
            f"{icon}  {clave}   ·   {tipo}   ·   Asignado: {tot_asig:.0f} MWh",
            expanded=(tot_asig > 0),
        ):
            edited = st.data_editor(
                df_edit,
                column_config={
                    "HE":              st.column_config.NumberColumn("HE",              disabled=True, width="small",  format="%d"),
                    "Asignado (MW)":   st.column_config.NumberColumn("Asignado (MW)",   disabled=True, width="medium", format="%.1f"),
                    "Fluir (MW)":      st.column_config.NumberColumn("Fluir (MW)",      min_value=0.0, width="medium", step=1.0, format="%.1f"),
                    "No Flow (MW)":    st.column_config.NumberColumn("No Flow (MW)",    disabled=True, width="medium", format="%+.1f"),
                },
                hide_index=True,
                use_container_width=True,
                key=f"de_{fn}_{clave}",
                height=min(len(he_nums) * 35 + 54, 572),
                num_rows="fixed",
            )

            new_fluir = edited["Fluir (MW)"].tolist()
            st.session_state[skey] = new_fluir

            tot_fluir  = sum(new_fluir)
            tot_diff   = tot_asig - tot_fluir
            diff_color = _GRN if tot_diff == 0 else (_RED if tot_diff < 0 else _AMB)

            kc1, kc2, kc3 = st.columns(3)
            kc1.markdown(_kpi("Total Asignado", f"{tot_asig:.0f} MW",  "", _BLU),       unsafe_allow_html=True)
            kc2.markdown(_kpi("Total Fluir",    f"{tot_fluir:.0f} MW", "", _GRN),       unsafe_allow_html=True)
            kc3.markdown(_kpi("Diferencia",     f"{tot_diff:+.0f} MW", "", diff_color), unsafe_allow_html=True)

        summary_rows.append({
            "Nodo":             clave,
            "Tipo":             tipo,
            "Asignado (MWh)":   f"{tot_asig:.0f}",
            "Fluir (MWh)":      f"{tot_fluir:.0f}",
            "Diferencia (MWh)": f"{tot_diff:+.0f}",
        })

    # ── Resumen global ─────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### Resumen por Nodo")
    st.dataframe(
        _pd.DataFrame(summary_rows),
        use_container_width=True,
        hide_index=True,
        height=min(len(summary_rows) * 38 + 54, 360),
    )

    # ══════════════════════════════════════════════════════════════════════════
    # ENVIAR A CENACE
    # ══════════════════════════════════════════════════════════════════════════
    st.markdown("---")
    st.markdown(
        "<div style='color:#00d4e8;font-size:0.85rem;font-weight:700;letter-spacing:1px;"
        "text-transform:uppercase;margin-bottom:12px;'>Enviar Segregación a CENACE</div>",
        unsafe_allow_html=True,
    )

    # Extraer fecha del nombre de archivo (ej: "Energia Asignada 17042026 M024-XiiX SIN.xlsx" → 17-04-2026)
    _dm = _re.search(r'(\d{8})', fn)
    if _dm:
        _d = _dm.group(1)
        _fecha_subj = f"{_d[:2]}-{_d[2:4]}-{_d[4:]}"
    else:
        import datetime as _dt
        _fecha_subj = _dt.date.today().strftime("%d-%m-%Y")

    _DEFAULT_TO   = "cenal.transaccionesinter@cenace.gob.mx"

    if sistema_val.upper() == "BCA":
        _DEFAULT_CC = (
            "rafael.portillo@cenace.gob.mx; eduardo.duran@cenace.gob.mx; "
            "daniel.moya01@cenace.gob.mx; fausto.hernandez@cenace.gob.mx; "
            "roberto.castro@cenace.gob.mx; jose.salas@cenace.gob.mx; "
            "victor.cruz@cenace.gob.mx; medicion.mem@cenace.gob.mx; "
            "mvidals@xiix.mx; escuderop@xiix.mx"
        )
    else:  # SIN
        _DEFAULT_CC = (
            "rafael.portillo@cenace.gob.mx; mvidals@xiix.mx; "
            "fmendoza@xiix.mx; escuderop@xiix.mx"
        )

    _DEFAULT_SUBJ = f"Segregacion de Asignación del {_fecha_subj} M024 - XiiX {sistema_val}"
    _DEFAULT_BODY = (
        "Estimados,\n\n"
        "Adjuntamos la Segregación de la Asignación con el total de MWs que se le asignan "
        "a cada contraparte y el total de MWs a etiquetarse.\n\n"
        "Saludos\n\n"
        "XTS Operations"
    )

    col_subj, col_to = st.columns([3, 2])
    with col_subj:
        email_subj = st.text_input("Asunto", value=_DEFAULT_SUBJ, key="email_subj")
    with col_to:
        email_to = st.text_input("Para", value=_DEFAULT_TO, key="email_to")

    email_cc   = st.text_input("CC (separar con ;)", value=_DEFAULT_CC, key="email_cc")
    email_body = st.text_area("Cuerpo", value=_DEFAULT_BODY, height=150, key="email_body")

    st.caption(f"Adjunto: {fn}")

    if st.button("📧 Enviar a CENACE", type="primary", key="btn_send_cenace", use_container_width=False):
        import tempfile as _tmp, os as _os
        _tmp_path = _os.path.join(_tmp.gettempdir(), fn)
        with open(_tmp_path, "wb") as _tf:
            _tf.write(_file_bytes)
        try:
            import win32com.client as _win32
            _outlook = _win32.Dispatch("Outlook.Application")
            _mail = _outlook.CreateItem(0)
            _mail.To      = email_to
            _mail.CC      = email_cc
            _mail.Subject = email_subj
            _mail.Body    = email_body
            _mail.Attachments.Add(_tmp_path)
            _mail.Send()
            st.success(f"✅ Correo enviado correctamente a {email_to}")
        except Exception as _e:
            st.error(f"Error enviando correo: {_e}")
